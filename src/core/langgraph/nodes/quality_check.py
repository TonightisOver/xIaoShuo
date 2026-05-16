"""质量检查节点"""

from src.core.langgraph.state import NovelState


def node(state: NovelState) -> NovelState:
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

    return {
        **state,
        "quality_scores": quality_scores,
        "current_stage": "quality_check_completed",
    }
