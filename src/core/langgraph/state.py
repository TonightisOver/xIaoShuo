"""小说创作状态定义"""

from typing import TypedDict


class NovelState(TypedDict, total=False):
    """小说创作状态"""

    # 项目元信息
    project_id: str
    novel_type: str
    target_words: int

    # 创作内容
    idea: str
    world_setting: dict | None
    characters: list[dict]
    relationships: dict
    outline: dict | None
    chapter_outlines: list[dict]
    chapters: list[dict]

    # 流程控制
    current_stage: str
    approval_status: str
    revision_requests: list[str]

    # 质量指标
    quality_scores: dict[str, float]

    # 错误信息
    errors: list[str]
