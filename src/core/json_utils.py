"""JSON 解析工具"""

import json
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)


def safe_json_parse(
    json_str: str, fallback: Any = None, extract_partial: bool = True
) -> Any:
    """安全解析 JSON，支持部分提取和降级

    Args:
        json_str: JSON 字符串
        fallback: 解析失败时的降级值
        extract_partial: 是否尝试提取部分有效 JSON

    Returns:
        解析后的对象，或降级值
    """
    # 尝试直接解析
    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        logger.warning(f"JSON parse failed: {e}")

        if not extract_partial:
            return fallback

        # 尝试提取 JSON 块
        extracted = _extract_json_block(json_str)
        if extracted:
            try:
                return json.loads(extracted)
            except json.JSONDecodeError:
                logger.warning("Extracted JSON block is still invalid")

        # 尝试修复常见问题
        fixed = _fix_common_json_issues(json_str)
        if fixed:
            try:
                return json.loads(fixed)
            except json.JSONDecodeError:
                logger.warning("Fixed JSON is still invalid")

        logger.error("All JSON parsing attempts failed, using fallback")
        return fallback


def _extract_json_block(text: str) -> str | None:
    """从文本中提取 JSON 块

    Args:
        text: 包含 JSON 的文本

    Returns:
        提取的 JSON 字符串，或 None
    """
    # 尝试提取 ```json ... ``` 代码块
    json_block_pattern = r"```(?:json)?\s*(\{.*?\})\s*```"
    match = re.search(json_block_pattern, text, re.DOTALL)
    if match:
        return match.group(1)

    # 尝试提取第一个完整的 JSON 对象
    brace_pattern = r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}"
    match = re.search(brace_pattern, text, re.DOTALL)
    if match:
        return match.group(0)

    return None


def _fix_common_json_issues(json_str: str) -> str | None:
    """修复常见的 JSON 格式问题

    Args:
        json_str: 可能有问题的 JSON 字符串

    Returns:
        修复后的 JSON 字符串，或 None
    """
    try:
        # 移除 BOM
        json_str = json_str.lstrip("﻿")

        # 移除前后空白
        json_str = json_str.strip()

        # 修复单引号（替换为双引号）
        # 注意：这个简单实现可能在某些情况下不正确
        # json_str = json_str.replace("'", '"')

        # 移除尾部逗号
        json_str = re.sub(r",\s*}", "}", json_str)
        json_str = re.sub(r",\s*]", "]", json_str)

        return json_str
    except Exception as e:
        logger.error(f"Failed to fix JSON: {e}")
        return None


def validate_json_structure(
    data: dict, required_keys: list[str], data_name: str = "JSON"
) -> bool:
    """验证 JSON 结构是否包含必需的键

    Args:
        data: 解析后的 JSON 对象
        required_keys: 必需的键列表
        data_name: 数据名称（用于日志）

    Returns:
        是否验证通过
    """
    if not isinstance(data, dict):
        logger.error(f"{data_name} is not a dict: {type(data)}")
        return False

    missing_keys = [key for key in required_keys if key not in data]
    if missing_keys:
        logger.error(f"{data_name} missing required keys: {missing_keys}")
        return False

    return True
