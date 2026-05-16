"""LLM 客户端封装"""

import logging
from typing import Any

from langchain_core.messages import HumanMessage
from langchain_openai import ChatOpenAI
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.core.config import get_settings

logger = logging.getLogger(__name__)


class LLMClient:
    """LLM 客户端封装

    封装 DeepSeek API 调用，提供重试机制和错误处理
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

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((TimeoutError, ConnectionError)),
        reraise=True,
    )
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
            Exception: API 调用失败
        """
        try:
            messages = [HumanMessage(content=prompt)]

            kwargs: dict[str, Any] = {}
            if temperature is not None:
                kwargs["temperature"] = temperature
            if max_tokens is not None:
                kwargs["max_tokens"] = max_tokens

            logger.info(f"Calling LLM API with prompt length: {len(prompt)}")
            response = await self.llm.ainvoke(messages, **kwargs)
            logger.info(f"LLM API response length: {len(response.content)}")

            return str(response.content)

        except Exception as e:
            logger.error(f"LLM API call failed: {e}", exc_info=True)
            raise


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
