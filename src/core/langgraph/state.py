"""小说创作状态定义"""

from typing import TypedDict


class NovelState(TypedDict, total=False):
    """小说创作状态"""

    # 项目元信息
    project_id: str
    novel_id: str
    novel_type: str
    target_words: int
    writing_style: str
    writing_style_prompt: str

    # 创作内容
    idea: str
    world_setting: dict | None
    characters: list[dict]
    relationships: dict
    outline: dict | None
    chapter_outlines: list[dict]
    chapters: list[dict]
    volumes: list[dict]

    # 流程控制
    current_stage: str
    approval_status: str
    revision_requests: list[str]

    # 质量指标
    quality_scores: dict[str, float]

    # 知识图谱相关
    kg_context: str
    consistency_warnings: list[dict]

    # 错误信息
    errors: list[str]
