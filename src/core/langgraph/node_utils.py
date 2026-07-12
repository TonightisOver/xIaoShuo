"""LangGraph 节点通用工具：LLM 调用 + 解析 + Pydantic 校验 + 失败重试。

封装节点中重复的「调用 LLM → 解析 JSON → Pydantic 校验」流程，并在校验失败时
自动重试一次 LLM 调用（短路重试），避免 LLM 偶发的结构漂移直接降级到 fallback。

设计原则：
- 校验失败不立即降级：先重试一次（LLM 输出有随机性，重试常能拿到合法结构）
- 仍失败才降级：保证节点始终返回可用数据，不阻断流水线
- 结构化日志：记录重试原因与最终结果，便于排查
"""
from __future__ import annotations

import logging
from typing import Any, TypeVar

from pydantic import BaseModel

from src.core.json_utils import safe_json_parse, validate_typed

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


async def generate_and_validate(
    client: Any,
    prompt: str,
    model: type[T],
    data_name: str,
    fallback: T | None = None,
    max_attempts: int = 2,
    **generate_kwargs: Any,
) -> T | None:
    """调用 LLM 生成文本，解析并校验为 Pydantic 模型；校验失败时重试。

    流程（最多 max_attempts 次）：
    1. ``client.generate(prompt, **generate_kwargs)`` 获取 LLM 文本响应
    2. ``safe_json_parse`` 解析 JSON（容错提取）
    3. ``validate_typed`` 用 Pydantic 模型校验结构
    4. 校验通过 → 返回模型实例；失败 → 记录日志并重试
    5. 所有尝试都失败 → 返回 ``fallback``

    Args:
        client: LLM 客户端（需有 async ``generate`` 方法）。
        prompt: 发给 LLM 的 prompt。
        model: 期望输出的 Pydantic 模型类。
        data_name: 数据名称（用于日志，如 "character_design"）。
        fallback: 全部失败时的降级值。
        max_attempts: 最大尝试次数（含首次），默认 2（首次 + 1 次重试）。
        **generate_kwargs: 透传给 ``client.generate`` 的参数（如 max_tokens）。

    Returns:
        校验通过的模型实例，或 ``fallback``。
    """
    for attempt in range(1, max_attempts + 1):
        try:
            response = await client.generate(prompt, **generate_kwargs)
        except Exception as e:
            logger.warning(
                "generate_and_validate_llm_call_failed",
                extra={"data_name": data_name, "attempt": attempt, "error": str(e)},
            )
            if attempt == max_attempts:
                logger.error(
                    "generate_and_validate_all_attempts_failed",
                    extra={"data_name": data_name, "reason": "llm_call_error"},
                )
                return fallback
            continue

        parsed = safe_json_parse(response, fallback=None, extract_partial=True)
        if parsed is None:
            logger.warning(
                "generate_and_validate_json_parse_failed",
                extra={"data_name": data_name, "attempt": attempt},
            )
            if attempt < max_attempts:
                continue
            return fallback

        result = validate_typed(parsed, model, data_name, fallback=None)
        if result is not None:
            if attempt > 1:
                logger.info(
                    "generate_and_validate_recovered_after_retry",
                    extra={"data_name": data_name, "attempts": attempt},
                )
            return result

        logger.warning(
            "generate_and_validate_validation_failed",
            extra={"data_name": data_name, "attempt": attempt, "model": model.__name__},
        )

    logger.error(
        "generate_and_validate_all_attempts_failed",
        extra={"data_name": data_name, "reason": "validation", "model": model.__name__},
    )
    return fallback
