"""输入验证工具"""

import re


class ValidationError(Exception):
    """验证错误"""

    pass


def validate_idea(idea: str, max_length: int = 1000) -> str:
    """验证并清洗创意输入

    Args:
        idea: 用户输入的创意
        max_length: 最大长度限制

    Returns:
        清洗后的创意

    Raises:
        ValidationError: 验证失败
    """
    if not idea or not idea.strip():
        raise ValidationError("创意不能为空")

    idea = idea.strip()

    if len(idea) > max_length:
        raise ValidationError(f"创意长度不能超过 {max_length} 字符")

    # 移除控制字符（保留换行符和制表符）
    idea = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", idea)

    # 检测并警告可能的 prompt injection
    suspicious_patterns = [
        r"ignore\s+previous\s+instructions",
        r"忽略.*指令",
        r"system\s*:",
        r"assistant\s*:",
        r"<\|.*\|>",
    ]

    for pattern in suspicious_patterns:
        if re.search(pattern, idea, re.IGNORECASE):
            raise ValidationError("输入包含可疑内容，请重新输入")

    return idea


def validate_novel_type(novel_type: str) -> str:
    """验证小说类型

    Args:
        novel_type: 小说类型

    Returns:
        验证后的小说类型

    Raises:
        ValidationError: 验证失败
    """
    if not novel_type or not novel_type.strip():
        raise ValidationError("小说类型不能为空")

    novel_type = novel_type.strip()

    # 允许的小说类型
    allowed_types = {
        "玄幻",
        "仙侠",
        "武侠",
        "都市",
        "科幻",
        "历史",
        "军事",
        "游戏",
        "竞技",
        "悬疑",
        "灵异",
        "言情",
        "同人",
    }

    if novel_type not in allowed_types:
        raise ValidationError(
            f"不支持的小说类型: {novel_type}，"
            f"支持的类型: {', '.join(allowed_types)}"
        )

    return novel_type


def validate_target_words(target_words: int) -> int:
    """验证目标字数

    Args:
        target_words: 目标字数

    Returns:
        验证后的目标字数

    Raises:
        ValidationError: 验证失败
    """
    if target_words < 10000:
        raise ValidationError("目标字数不能少于 10000 字")

    if target_words > 10000000:
        raise ValidationError("目标字数不能超过 1000 万字")

    return target_words


def validate_json_string(json_str: str, max_length: int = 50000) -> str:
    """验证 JSON 字符串

    Args:
        json_str: JSON 字符串
        max_length: 最大长度

    Returns:
        验证后的 JSON 字符串

    Raises:
        ValidationError: 验证失败
    """
    if not json_str or not json_str.strip():
        raise ValidationError("JSON 字符串不能为空")

    json_str = json_str.strip()

    if len(json_str) > max_length:
        raise ValidationError(f"JSON 字符串长度不能超过 {max_length} 字符")

    return json_str
