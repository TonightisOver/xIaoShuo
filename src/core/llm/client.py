"""LLM 客户端封装"""

from __future__ import annotations

from typing import Any

import httpx
import openai
import structlog
from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from src.core.config import get_settings
from src.core.llm.token_tracker import get_token_tracker

logger = structlog.get_logger(__name__)


def _is_retryable_status_error(exc: httpx.HTTPStatusError | openai.APIStatusError) -> bool:
    """判断 HTTP 状态错误是否应该触发重试。"""
    # 非 HTTP 状态错误，直接返回 False
    if not isinstance(exc, httpx.HTTPStatusError | openai.APIStatusError):
        return False

    # 统一获取 status_code：httpx 和 openai 的 API 不同
    if isinstance(exc, openai.APIStatusError):
        status = exc.status_code
        body = str(getattr(exc, 'body', '') or '')
    else:
        status = exc.response.status_code
        body = (exc.response.text or "")

    # 429 rate limit / 500+ server errors — always retry
    if status in (429,) or status >= 500:
        return True
    # 400 "Upstream request failed" — 上游模型服务临时故障，应重试
    if status == 400 and "upstream" in body.lower():
        return True
    return False


# 兼容旧测试代码
_is_retryable_http_error = _is_retryable_status_error


def _should_retry(exc: BaseException) -> bool:
    """Determine if the exception should trigger a retry."""
    # openai SDK connection/timeout errors (not Python builtins)
    if isinstance(exc, openai.APIConnectionError | openai.APITimeoutError):
        return True
    if isinstance(exc, TimeoutError | ConnectionError):
        return True
    if isinstance(exc, httpx.HTTPStatusError | openai.APIStatusError):
        return _is_retryable_status_error(exc)
    return False


class LLMClient:
    """LLM 客户端封装

    封装 DeepSeek API 调用，提供重试机制 and 错误处理。
    支持双模型策略（flash / pro）和 token 用量追踪。
    """

    def __init__(self, llm_config: Any | None = None) -> None:
        """初始化 LLM 客户端。

        Args:
            llm_config: 可选的数据库 LLMConfig 对象（duck-typed）。
                        若传入，则从中读取 base_url、api_key、model_flash、model_pro；
                        否则从 Settings 读取。
        """
        settings = get_settings()

        if llm_config is not None:
            base_url = llm_config.base_url
            api_key = llm_config.api_key
            model_flash = llm_config.model_flash
            model_pro = llm_config.model_pro
        else:
            base_url = settings.DEEPSEEK_BASE_URL
            api_key = settings.DEEPSEEK_API_KEY
            model_flash = settings.DEEPSEEK_MODEL_FLASH
            model_pro = settings.DEEPSEEK_MODEL_PRO

        common_kwargs: dict[str, Any] = {
            "api_key": api_key,  # type: ignore[arg-type]
            "base_url": base_url,
            "temperature": settings.DEEPSEEK_TEMPERATURE,
            "timeout": settings.DEEPSEEK_TIMEOUT,
            "model_kwargs": {"max_tokens": settings.DEEPSEEK_MAX_TOKENS},
        }

        self.llm_flash = ChatOpenAI(model=model_flash, **common_kwargs)
        self.llm_pro = ChatOpenAI(model=model_pro, **common_kwargs)

        # 保留 self.llm 指向 pro，向后兼容任何直接访问该属性的代码
        self.llm = self.llm_pro

        self._model_flash = model_flash
        self._model_pro = model_pro
        self.max_retries = settings.DEEPSEEK_MAX_RETRIES

    def _get_llm(self, use_flash: bool = False) -> ChatOpenAI:
        return self.llm_flash if use_flash else self.llm_pro

    async def generate(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
        use_flash: bool = False,
    ) -> str:
        """生成文本。

        Args:
            prompt: 输入 prompt
            temperature: 温度参数（可选）
            max_tokens: 最大 token 数（可选）
            use_flash: True 时使用 flash 模型，默认使用 pro 模型

        Returns:
            生成的文本

        Raises:
            Exception: API 调用失败（不可重试错误或超过重试次数）
        """
        llm_instance = self._get_llm(use_flash)
        model_name = self._model_flash if use_flash else self._model_pro
        tracker = get_token_tracker()

        retry_policy = AsyncRetrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception(_should_retry),
            reraise=True,
        )

        try:
            async for attempt in retry_policy:
                with attempt:
                    try:
                        messages = [HumanMessage(content=prompt)]

                        kwargs: dict[str, Any] = {}
                        if temperature is not None:
                            kwargs["temperature"] = temperature
                        if max_tokens is not None:
                            kwargs["max_tokens"] = max_tokens

                        logger.info(
                            "calling_llm_api",
                            model=model_name,
                            prompt_length=len(prompt),
                            attempt=attempt.retry_state.attempt_number,
                        )
                        response = await llm_instance.ainvoke(messages, **kwargs)
                        logger.info(
                            "llm_api_response",
                            response_length=len(str(response.content)),
                        )

                        # Token 追踪
                        token_usage = (
                            response.response_metadata.get("token_usage", {})
                            if hasattr(response, "response_metadata")
                            else {}
                        )
                        if token_usage and "prompt_tokens" in token_usage:
                            tracker.record(
                                model=model_name,
                                prompt_tokens=token_usage.get("prompt_tokens", 0),
                                completion_tokens=token_usage.get("completion_tokens", 0),
                                total_tokens=token_usage.get("total_tokens", 0),
                            )
                        else:
                            tracker.skip()

                        return str(response.content)

                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 401:
                            # Auth error — do not retry
                            logger.error(
                                "llm_auth_error",
                                status_code=e.response.status_code,
                            )
                            raise
                        if not _is_retryable_status_error(e):
                            raise
                        logger.warning(
                            "llm_http_error_retrying",
                            status_code=e.response.status_code,
                            attempt=attempt.retry_state.attempt_number,
                        )
                        raise

                    except openai.APIStatusError as e:
                        if e.status_code == 401:
                            logger.error(
                                "llm_auth_error",
                                status_code=e.status_code,
                            )
                            raise
                        if not _is_retryable_status_error(e):
                            raise
                        logger.warning(
                            "llm_api_status_retrying",
                            status_code=e.status_code,
                            attempt=attempt.retry_state.attempt_number,
                        )
                        raise

                    except Exception as e:
                        logger.error("llm_api_call_failed", error=str(e), exc_info=True)
                        raise

        except RetryError as e:
            logger.error(
                "llm_api_exhausted_retries",
                max_retries=self.max_retries,
                error=str(e),
            )
            raise

        # Unreachable — AsyncRetrying always raises or returns via attempt
        raise RuntimeError("Unexpected exit from retry loop")  # pragma: no cover

    async def stream_generate(
        self,
        prompt: str,
        use_flash: bool = False,
    ):
        """Stream generated text chunks with usage accounting on completion."""
        from src.core.llm.token_tracker import get_token_tracker

        tracker = get_token_tracker()
        llm_instance = self._get_llm(use_flash)
        messages = [HumanMessage(content=prompt)]
        prompt_chars = len(prompt)

        try:
            async for chunk in llm_instance.astream(messages):
                content = getattr(chunk, "content", None)
                if content is not None:
                    yield str(content)
        finally:
            # Record approximate usage even when streaming provider omits token counts
            tracker.record(
                prompt_chars=prompt_chars,
                completion_chars=0,
                model=getattr(llm_instance, "model_name", "unknown"),
                mode="stream",
            )


# 全局客户端实例
_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """获取 LLM 客户端单例。

    Returns:
        LLMClient 实例
    """
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
