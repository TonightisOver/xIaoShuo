"""人工审核节点

支持两种模式（由 settings.HITL_AUTO_APPROVE 控制）：

1. auto-approve（默认 True）：跳过 interrupt()，直接返回 approved，让管线
   端到端跑通。审核数据仍写入 state 供前端展示。适用于 HITL interrupt/resume
   机制尚未实现的阶段（持久化 checkpointer + resume 路径待补）。

2. 真 HITL（HITL_AUTO_APPROVE=False）：调用 interrupt() 阻塞等待用户决策，
   由外部 review API 通过 Command(resume=decision) 恢复。需配合持久化
   checkpointer（SqliteSaver）+ _run_langgraph_pipeline 的 resume 路径。
"""

import structlog
from langchain_core.runnables import RunnableConfig
from langgraph.types import interrupt

from src.core.config import get_settings
from src.core.langgraph.state import NovelState

logger = structlog.get_logger(__name__)


def node(state: NovelState, config: RunnableConfig | None = None) -> NovelState:
    """人工审核节点

    Args:
        state: 当前状态
        config: LangGraph config（应包含 thread_id）

    Returns:
        更新后的状态
    """
    # 1. 准备要呈现给用户的审核数据（无论哪种模式都写入 state，供前端展示）
    quality_scores = state.get("quality_scores", {})
    consistency_warnings = state.get("consistency_warnings", [])
    revision_requests = state.get("revision_requests", [])
    kg_continuity_report = state.get("kg_continuity_report")
    chapters = state.get("chapters", [])
    last_chapter = chapters[-1] if chapters else None

    review_data = {
        "quality_scores": quality_scores,
        "consistency_warnings": consistency_warnings[:5] if consistency_warnings else [],
        "revision_requests": revision_requests[:5] if revision_requests else [],
        "chapter_number": last_chapter.get("chapter", 0) if last_chapter else 0,
    }

    settings = get_settings()

    # 2a. auto-approve 模式：跳过阻塞，直接通过
    if settings.HITL_AUTO_APPROVE:
        logger.info(
            "human_review_auto_approved",
            chapter_count=len(chapters),
            quality_overall=quality_scores.get("overall"),
            warnings_count=len(consistency_warnings),
        )
        return {
            **state,
            "approval_status": "approved",
            "current_stage": "approved",
            "review_data": review_data,
        }

    # 2b. 真 HITL 模式：阻塞等待用户决策
    # interrupt() 抛出 NodeInterrupt，LangGraph 暂停等待 resume
    # resume 时传入的 Command(resume=user_input) 成为 interrupt() 的返回值
    try:
        resume_result = interrupt(review_data)
    except Exception:
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
