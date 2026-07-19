"""小说生成规划：纯函数与阶段常量。

从 novel_generator.py 提取的无副作用计算逻辑，便于独立单元测试与复用。
novel_generator.py 通过 re-export 保持向后兼容（外部仍可从原路径导入）。
"""
from __future__ import annotations

import math
from typing import Any

# 7-node LangGraph 流水线阶段顺序（用于百分比计算与进度推进）
STAGE_ORDER = [
    "idea_expansion",
    "world_building",
    "character_design",
    "outline_generation",
    "chapter_generation",
    "quality_check",
    "human_review",
]

# 13 阶段全功能生成流水线
FULL_GENERATE_STAGES = [
    "idea_expansion",
    "world_building",
    "character_design",
    "outline_generation",
    "chapter_generation",
    "quality_check",
    "human_review",
    "power_systems",
    "outline_persist",
    "storylines",
    "character_arcs",
    "scenes",
    "auto_conversation",
]


def calculate_long_form_chapter_plan(request: Any) -> dict[str, int]:
    """Calculate actual long-form chapter counts used by generation.

    auto_calc_chapters=True 时按目标字数估算每卷章节数并 clamp 到 [20, 60]；
    否则直接使用 request.chapters_per_volume。
    """
    if request.auto_calc_chapters:
        estimated_total_chapters = math.ceil(
            request.target_words / request.words_per_chapter
        )
        computed_chapters_per_volume = math.ceil(
            estimated_total_chapters / request.volumes
        )
        chapters_per_volume = max(20, min(60, computed_chapters_per_volume))
    else:
        estimated_total_chapters = request.volumes * request.chapters_per_volume
        computed_chapters_per_volume = request.chapters_per_volume
        chapters_per_volume = request.chapters_per_volume

    return {
        "estimated_total_chapters": estimated_total_chapters,
        "computed_chapters_per_volume": computed_chapters_per_volume,
        "chapters_per_volume": chapters_per_volume,
        "total_chapters": request.volumes * chapters_per_volume,
    }


def _full_generate_percentage(stage_index: int, total_stages: int | None = None) -> int:
    """Calculate percentage for a stage index (0-based).

    Args:
        stage_index: 0-based index of the current stage.
        total_stages: Override total stage count (defaults to len(FULL_GENERATE_STAGES)).
    """
    total = total_stages if total_stages is not None else len(FULL_GENERATE_STAGES)
    return int(((stage_index + 1) / total) * 100)
