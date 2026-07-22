"""章节蓝图字段枚举契约。

值严格取自 src/core/llm/prompts.py 的现有字面量（chapter_type/pacing_target/
foreshadow_action），禁止发明不兼容枚举。DB 列保持 String 不变，不引入 CHECK。
"""

from __future__ import annotations

from enum import StrEnum


class ChapterType(StrEnum):
    MAIN_ADVANCE = "main_advance"
    CLIMAX = "climax"
    AFTERMATH = "aftermath"
    DAILY = "daily"
    SETUP = "setup"


class BlueprintPacing(StrEnum):
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"


class ForeshadowAction(StrEnum):
    PLANT = "plant"
    CALLBACK = "callback"
    ADVANCE = "advance"


BLUEPRINT_FIELD_OPTIONS: dict[str, list[str]] = {
    "chapter_type": [e.value for e in ChapterType],
    "pacing_target": [e.value for e in BlueprintPacing],
    "foreshadow_action": [e.value for e in ForeshadowAction],
}


def validate_blueprint_fields(data: dict) -> None:
    """写入前校验 chapter_type/pacing_target/word_target。不符抛 ValueError（路由层映射 422）。"""
    chapter_type = data.get("chapter_type")
    if chapter_type is not None and chapter_type not in BLUEPRINT_FIELD_OPTIONS["chapter_type"]:
        raise ValueError(f"非法 chapter_type: {chapter_type}")
    pacing = data.get("pacing_target")
    if pacing is not None and pacing not in BLUEPRINT_FIELD_OPTIONS["pacing_target"]:
        raise ValueError(f"非法 pacing_target: {pacing}")
    word_target = data.get("word_target")
    if word_target is not None:
        if not isinstance(word_target, int) or isinstance(word_target, bool) or word_target < 2000 or word_target > 6000:
            raise ValueError(f"word_target 必须为 2000-6000 的正整数: {word_target}")
