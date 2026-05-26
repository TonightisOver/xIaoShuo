"""质量评分到改写动作的映射服务"""

import structlog
from sqlalchemy import select

from src.api.models.db_models import ChapterBlueprint
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)

ACTION_MAPPING: dict[str, dict[str, str]] = {
    "advancement": {
        "action_type": "enhance_plot",
        "instruction": "主线停滞，需增加推进事件",
    },
    "pacing": {
        "action_type": "compress_pacing",
        "instruction": "节奏拖沓，需压缩/删减冗余描写",
    },
    "conflict": {
        "action_type": "enhance_hook",
        "instruction": "缺乏爽点，需增强冲突与悬念",
    },
    "character_consistency": {
        "action_type": "fix_character",
        "instruction": "人物漂移，需修复对话/行为使其符合人设",
    },
    "readability": {
        "action_type": "trim_filler",
        "instruction": "水文过多，需精简重复描写",
    },
    "foreshadowing": {
        "action_type": "add_foreshadow",
        "instruction": "伏笔缺失，需补充伏笔种植或回收",
    },
    "world_consistency": {
        "action_type": "fix_world",
        "instruction": "设定冲突，需修正违反世界观的内容",
    },
    "trope_alignment": {
        "action_type": "enhance_trope",
        "instruction": "爽感不足，需强化网文套路",
    },
}


class QualityActionService:
    """将八维质量评分转化为可执行的改写动作"""

    def generate_rewrite_actions(
        self, quality_scores: dict, threshold: float = 0.5
    ) -> list[dict]:
        """将低分维度转化为改写动作列表。

        Args:
            quality_scores: 八维评分 dict (含 overall)
            threshold: 低于此阈值的维度触发改写动作

        Returns:
            按 priority 降序排列的动作列表
        """
        actions: list[dict] = []

        for dimension, score in quality_scores.items():
            if dimension == "overall":
                continue
            if not isinstance(score, (int, float)):
                continue
            if score >= threshold:
                continue

            mapping = ACTION_MAPPING.get(dimension)
            if mapping is None:
                continue

            actions.append(
                {
                    "action_type": mapping["action_type"],
                    "dimension": dimension,
                    "score": score,
                    "instruction": mapping["instruction"],
                    "priority": round(1.0 - score, 4),
                }
            )

        actions.sort(key=lambda a: a["priority"], reverse=True)

        logger.info(
            "rewrite_actions_generated",
            total_dimensions=len(quality_scores) - 1,
            actions_count=len(actions),
            threshold=threshold,
        )
        return actions

    async def persist_actions(
        self, novel_id: str, chapter_number: int, actions: list[dict]
    ) -> None:
        """将 actions 写入 ChapterBlueprint.rewrite_actions"""
        async with get_db_session() as session:
            result = await session.execute(
                select(ChapterBlueprint).where(
                    ChapterBlueprint.novel_id == novel_id,
                    ChapterBlueprint.chapter_number == chapter_number,
                    ChapterBlueprint.is_active == True,  # noqa: E712
                )
            )
            bp = result.scalar_one_or_none()
            if bp is None:
                logger.warning(
                    "persist_actions_no_blueprint",
                    novel_id=novel_id,
                    chapter_number=chapter_number,
                )
                return

            bp.rewrite_actions = actions

        logger.info(
            "rewrite_actions_persisted",
            novel_id=novel_id,
            chapter_number=chapter_number,
            actions_count=len(actions),
        )
