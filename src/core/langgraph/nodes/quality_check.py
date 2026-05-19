"""质量检查节点"""

import logging

from src.core.config import get_settings
from src.core.langgraph.state import NovelState

logger = logging.getLogger(__name__)


async def node(state: NovelState) -> NovelState:
    """质量检查节点

    检查生成内容的质量。

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    # 暂时使用 mock 数据，模拟质量评分
    quality_scores = {
        "overall": 0.85,  # 总体质量分数
        "coherence": 0.9,  # 连贯性
        "creativity": 0.8,  # 创意性
        "readability": 0.85,  # 可读性
    }

    # 一致性检查（知识图谱）
    consistency_score = 1.0
    settings = get_settings()
    if settings.KNOWLEDGE_GRAPH_ENABLED:
        try:
            from src.api.services.knowledge_graph_service import (
                get_knowledge_graph_service,
            )
            kg_service = get_knowledge_graph_service()
            chapters = state.get("chapters", [])
            last_chapter = chapters[-1] if chapters else None
            if last_chapter and last_chapter.get("content"):
                conflicts = await kg_service.check_consistency(
                    novel_id=state["project_id"],
                    chapter_number=last_chapter.get("chapter", len(chapters)),
                    chapter_text=last_chapter["content"],
                )
                error_count = sum(1 for c in conflicts if c.get("severity") == "error")
                if error_count > 0:
                    consistency_score = max(0.3, 1.0 - error_count * 0.2)
        except Exception as e:
            logger.warning(f"Consistency check failed: {e}")

    quality_scores["consistency"] = consistency_score

    return {
        **state,
        "quality_scores": quality_scores,
        "current_stage": "quality_check_completed",
    }
