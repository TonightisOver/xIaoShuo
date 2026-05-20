"""LLM 客户端封装"""

from typing import Any

import httpx
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

logger = structlog.get_logger(__name__)


def _is_retryable_http_error(exc: BaseException) -> bool:
    """Return True if the HTTP status error should trigger a retry."""
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in (429,) or exc.response.status_code >= 500
    return False


def _should_retry(exc: BaseException) -> bool:
    """Determine if the exception should trigger a retry."""
    if isinstance(exc, TimeoutError | ConnectionError):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return _is_retryable_http_error(exc)
    return False


class LLMClient:
    """LLM 客户端封装

    封装 DeepSeek API 调用，提供重试机制 and 错误处理
    """

    def __init__(self) -> None:
        """初始化 LLM 客户端"""
        settings = get_settings()
        self.llm = ChatOpenAI(
            model=settings.DEEPSEEK_MODEL,
            api_key=settings.DEEPSEEK_API_KEY,  # type: ignore[arg-type]
            base_url=settings.DEEPSEEK_BASE_URL,
            temperature=settings.DEEPSEEK_TEMPERATURE,
            timeout=settings.DEEPSEEK_TIMEOUT,
            model_kwargs={"max_tokens": settings.DEEPSEEK_MAX_TOKENS},
        )
        self.max_retries = settings.DEEPSEEK_MAX_RETRIES

    async def generate(
        self,
        prompt: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """生成文本

        Args:
            prompt: 输入 prompt
            temperature: 温度参数（可选）
            max_tokens: 最大 token 数（可选）

        Returns:
            生成的文本

        Raises:
            Exception: API 调用失败（不可重试错误或超过重试次数）
        """
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
                            prompt_length=len(prompt),
                            attempt=attempt.retry_state.attempt_number,
                        )
                        response = await self.llm.ainvoke(messages, **kwargs)
                        logger.info(
                            "llm_api_response",
                            response_length=len(str(response.content)),
                        )
                        return str(response.content)

                    except httpx.HTTPStatusError as e:
                        if e.response.status_code == 401:
                            # Auth error — do not retry
                            logger.error(
                                "llm_auth_error",
                                status_code=e.response.status_code,
                            )
                            raise
                        if not _is_retryable_http_error(e):
                            raise
                        logger.warning(
                            "llm_http_error_retrying",
                            status_code=e.response.status_code,
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


# 全局客户端实例
_client: LLMClient | None = None


def get_llm_client() -> LLMClient:
    """获取 LLM 客户端单例

    Returns:
        LLMClient 实例
    """
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
