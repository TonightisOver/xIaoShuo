"""人工审核节点"""

from src.core.langgraph.state import NovelState


def node(state: NovelState) -> NovelState:
    """人工审核节点

    等待人工审核和反馈。

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    # 标记为等待人工审核
    return {
        **state,
        "approval_status": "pending",
        "current_stage": "human_review",
    }
