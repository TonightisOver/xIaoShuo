"""LLM 客户端封装"""

from __future__ import annotations

from collections.abc import AsyncIterator
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

    async def _invoke_with_retry(
        self,
        llm_instance: ChatOpenAI,
        model_name: str,
        prompt: str,
        temperature: float | None,
        max_tokens: int | None,
    ) -> str:
        """对单个 LLM 实例执行带重试的调用（不含模型降级）。

        Raises:
            RetryError: 重试耗尽（可重试错误持续）。
            httpx.HTTPStatusError / openai.APIStatusError: 不可重试错误（401 等）。
            Exception: 其他调用异常。
        """
        tracker = get_token_tracker()
        retry_policy = AsyncRetrying(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(multiplier=1, min=2, max=30),
            retry=retry_if_exception(_should_retry),
        )
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

        raise RuntimeError("Unexpected exit from retry loop")  # pragma: no cover

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
            Exception: API 调用失败（不可重试错误或超过重试次数，含 flash 降级也失败）。

        模型降级策略：当 use_flash=False（使用 pro 模型）且 pro 重试耗尽时，
        自动降级到 flash 模型再试一轮，以在 pro 限流/宕机时保底生成。
        use_flash=True 时不降级（已是最轻量模型）。
        """
        try:
            return await self._invoke_with_retry(
                self._get_llm(use_flash),
                self._model_flash if use_flash else self._model_pro,
                prompt, temperature, max_tokens,
            )
        except RetryError as e:
            if use_flash:
                # flash 模型已耗尽重试，不再降级
                logger.error("llm_api_exhausted_retries_flash", max_retries=self.max_retries, error=str(e))
                raise
            # pro 重试耗尽 → 降级到 flash 保底
            logger.warning(
                "llm_pro_exhausted_fallback_to_flash",
                max_retries=self.max_retries,
                error=str(e),
            )
            try:
                return await self._invoke_with_retry(
                    self.llm_flash, self._model_flash,
                    prompt, temperature, max_tokens,
                )
            except RetryError as fe:
                logger.error(
                    "llm_flash_fallback_also_exhausted",
                    max_retries=self.max_retries,
                    error=str(fe),
                )
                raise


    async def stream_generate(
        self,
        prompt: str,
        use_flash: bool = False,
    ) -> AsyncIterator[str]:
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
            prompt_tokens = prompt_chars // 3
            tracker.record(
                model=getattr(llm_instance, "model_name", "unknown"),
                prompt_tokens=prompt_tokens,
                completion_tokens=0,
                total_tokens=prompt_tokens,
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


# ---------------------------------------------------------------------------
# Embedding helpers
# ---------------------------------------------------------------------------

_embedding_client: httpx.AsyncClient | None = None


def get_embedding_client() -> httpx.AsyncClient:
    """获取 embedding 专用的 httpx 客户端单例。

    使用 DEEPSEEK_BASE_URL（或 EMBEDDING_BASE_URL 若配置），
    方便复用连接。

    Returns:
        httpx.AsyncClient 实例
    """
    global _embedding_client
    if _embedding_client is None:
        settings = get_settings()
        base_url = settings.EMBEDDING_BASE_URL or settings.DEEPSEEK_BASE_URL
        _embedding_client = httpx.AsyncClient(
            base_url=base_url,
            headers={
                "Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}",
                "Content-Type": "application/json",
            },
            timeout=settings.DEEPSEEK_TIMEOUT,
        )
    return _embedding_client


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """调用 DeepSeek 兼容的 embedding 接口批量生成向量。

    Args:
        texts: 需要生成向量的文本列表

    Returns:
        与 texts 一一对应的向量列表。

    Raises:
        RuntimeError: embedding API 调用失败（网络错误、非 2xx 响应、响应体缺失
            embedding 字段等）。调用方应捕获并降级处理，**不得**用零向量静默
            替代——零向量会污染知识图谱的语义检索与实体 embedding 落库。
    """
    settings = get_settings()

    try:
        client = get_embedding_client()
        payload = {
            "model": settings.EMBEDDING_MODEL,
            "input": texts,
        }
        resp = await client.post("/embeddings", json=payload)
        resp.raise_for_status()
        data = resp.json()
        embeddings = [item["embedding"] for item in data.get("data", [])]
    except Exception as exc:
        logger.warning("embedding_api_failed", error=str(exc))
        raise RuntimeError(f"embedding API 调用失败: {exc}") from exc

    if len(embeddings) != len(texts):
        raise RuntimeError(
            f"embedding 数量与输入不匹配: 期望 {len(texts)}, 实际 {len(embeddings)}"
        )
    return embeddings
