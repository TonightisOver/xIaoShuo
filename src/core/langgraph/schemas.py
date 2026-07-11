"""LangGraph 节点 LLM 输出的 Pydantic schema。

用于在节点边界校验 LLM 返回的 JSON 结构，拦截「结构漂移」（字段缺失、类型
错误、嵌套结构错误等），避免畸形数据顺着 NovelState 流到下游节点引发晦涩的
KeyError。校验通过 ``json_utils.validate_typed`` 执行，失败时降级到 fallback。

注意：NovelState 本身保持 TypedDict（LangGraph 要求），Pydantic 模型仅用于
节点入口/出口的边界校验，不替换 state 类型。
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class CharacterDesign(BaseModel):
    """单个角色设定。"""

    name: str
    role: str = ""
    personality: str = ""
    background: str = ""
    goal: str = ""
    ability: str = ""


class CharacterDesignResult(BaseModel):
    """character_design 节点的 LLM 输出结构。"""

    characters: list[CharacterDesign] = Field(default_factory=list)
    relationships: dict[str, str] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}


class WorldSetting(BaseModel):
    """世界观设定。"""

    background: str = ""
    rules: str = ""
    geography: str = ""
    culture: str = ""

    model_config = {"extra": "ignore"}


class ChapterOutline(BaseModel):
    """单章大纲。"""

    chapter: int = 0
    title: str = ""
    plot: str = ""
    words: int = 0

    model_config = {"extra": "ignore"}


class VolumeOutline(BaseModel):
    """卷大纲（outline_generation 节点用）。"""

    volume_number: int = 1
    title: str = ""
    summary: str = ""
    chapters: list[ChapterOutline] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class OutlineResult(BaseModel):
    """outline_generation 节点（分步生成）的 LLM 输出结构。"""

    outline: dict[str, str] = Field(default_factory=dict)
    volumes: list[VolumeOutline] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


class MasterOutlineVolume(BaseModel):
    """总纲中的卷概述。"""

    volume_number: int = 0
    title: str = ""
    summary: str = ""

    model_config = {"extra": "ignore"}


class MasterOutlineResult(BaseModel):
    """master_outline_generation 节点的 LLM 输出结构。"""

    title: str = ""
    synopsis: str = ""
    main_conflict: str = ""
    main_theme: str = ""
    volumes: list[MasterOutlineVolume] = Field(default_factory=list)
    foreshadow_plan: list[dict] = Field(default_factory=list)
    character_plan: list[dict] = Field(default_factory=list)

    model_config = {"extra": "ignore"}


