"""LLM 调用辅助函数 — 封装 generate → parse → fallback 标准流程"""

from typing import Any

import structlog

from src.core.json_utils import safe_json_parse
from src.core.llm.client import LLMClient

logger = structlog.get_logger(__name__)


async def generate_and_parse_json(
    client: LLMClient,
    prompt: str,
    *,
    max_tokens: int = 2000,
    temperature: float | None = None,
    fallback: Any = None,
    extract_partial: bool = True,
) -> Any:
    """调用 LLM 生成文本并解析为 JSON，失败时返回 fallback。

    封装标准流程：client.generate() → safe_json_parse() → fallback

    Args:
        client: LLMClient 实例
        prompt: 输入 prompt
        max_tokens: 最大 token 数
        temperature: 温度参数（可选）
        fallback: JSON 解析失败时的降级值
        extract_partial: 是否尝试提取部分有效 JSON

    Returns:
        解析后的 JSON 对象，或 fallback 值
    """
    try:
        response = await client.generate(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
        )
    except Exception:
        logger.exception("llm_generate_failed_in_helper")
        return fallback

    result = safe_json_parse(
        response, fallback=fallback, extract_partial=extract_partial
    )
    return result
