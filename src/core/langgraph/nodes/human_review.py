"""人工审核节点 — 使用 interrupt() 真阻塞等待用户决策"""

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from src.core.langgraph.state import NovelState

logger = structlog.get_logger(__name__)


def node(state: NovelState, config: RunnableConfig | None = None) -> NovelState:
    """人工审核节点

    使用 LangGraph interrupt() 真阻塞等待用户审核。
    审决策通过外部 API /api/v1/tasks/{task_id}/review 提交，
    LangGraph 通过 Command(resume=decision) 恢复执行。

    Args:
        state: 当前状态
        config: LangGraph config（应包含 thread_id）

    Returns:
        更新后的状态
    """
    # 1. 准备要呈现给用户的审核数据
    quality_scores = state.get("quality_scores", {})
    consistency_warnings = state.get("consistency_warnings", [])
    revision_requests = state.get("revision_requests", [])
    kg_continuity_report = state.get("kg_continuity_report")
    chapters = state.get("chapters", [])
    last_chapter = chapters[-1] if chapters else None

    # 2. 挂起等待用户决策
    # interrupt() 抛出 NodeInterrupt，LangGraph 暂停在此处等待 resume
    # resume 时传入的 Command(resume=user_input) 成为 interrupt() 的返回值
    review_data = {
        "quality_scores": quality_scores,
        "consistency_warnings": consistency_warnings[:5] if consistency_warnings else [],
        "revision_requests": revision_requests[:5] if revision_requests else [],
        "chapter_number": last_chapter.get("chapter", 0) if last_chapter else 0,
    }

    try:
        # 当 resume 被调用时，interrupt() 返回传入的数据
        resume_result = interrupt(review_data)
    except Exception:
        # 如果没有 resume，保持 pending 状态
        return {
            **state,
            "approval_status": "pending",
            "current_stage": "human_review",
        }

    # 3. 处理用户决策
    if isinstance(resume_result, dict):
        decision = resume_result.get("approval_status", "approved")
        instructions = resume_result.get("revision_instructions", "")
    else:
        decision = str(resume_result) if resume_result else "approved"
        instructions = ""

    logger.info(
        "human_review_decision_received",
        decision=decision,
        instructions_len=len(instructions),
    )

    if decision == "approved":
        return {
            **state,
            "approval_status": "approved",
            "current_stage": "approved",
        }
    elif decision == "revision":
        return {
            **state,
            "approval_status": "revision",
            "revision_instructions": instructions,
            "current_stage": "human_review",
            "_regeneration_count": state.get("_regeneration_count", 0) + 1,
        }
    else:  # rejected
        return {
            **state,
            "approval_status": "rejected",
            "current_stage": "rejected",
        }
