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
    _regeneration_count: int

    # 质量指标
    quality_scores: dict[str, float]
    # L0 规则预筛结果（quality_check 节点收集，运行时编排后续接入）
    l0_results: list[dict]
    # KG 连续性审查报告
    kg_continuity_report: dict | None

    # 知识图谱相关
    kg_context: str
    consistency_warnings: list[dict]

    # Long-form specific fields
    chapter_type: str | None
    volume_context: dict | None
    current_volume_number: int | None
    master_outline: dict | None
    target_words_per_chapter: int | None

    # 错误信息
    errors: list[str]
