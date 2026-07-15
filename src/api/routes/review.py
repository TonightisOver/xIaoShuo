"""人工审核路由

提供 HITL (Human-In-The-Loop) 接口：
- POST /api/v1/tasks/{task_id}/review — 提交审核决策
- GET /api/v1/tasks/{task_id}/review — 获取待审核数据
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.services.novel_generator import resume_pipeline
from src.api.services.task_manager import get_task_manager
from src.core.auth_models import User
from src.core.security.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/tasks", tags=["review"])


class ReviewRequest(BaseModel):
    """审核决策请求"""

    approval_status: str = Field(
        ...,
        description="审核结果: approved/rejected/revision",
        pattern=r"^(approved|rejected|revision)$",
    )
    revision_instructions: str = Field(
        default="",
        description="修改意见（rejected/revision 时需要）",
    )


class ReviewResponse(BaseModel):
    """审核决策响应"""

    task_id: str
    approval_status: str
    message: str


class ReviewDataResponse(BaseModel):
    """待审核数据响应"""

    task_id: str
    current_stage: str
    approval_status: str
    waiting_for_review: bool
    progress: dict | None = None
    result: dict | None = None


@router.post("/{task_id}/review", response_model=ReviewResponse)
async def submit_review(
    task_id: str,
    request: ReviewRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
) -> ReviewResponse:
    """提交人工审核决策

    接受审核结果并更新 LangGraph 状态，使流水线继续或被修正。
    approved/revision 触发 resume_pipeline 续跑；rejected 终止任务。

    Args:
        task_id: 任务 ID
        request: 审核决策
        background_tasks: FastAPI 后台任务（用于 resume pipeline）

    Returns:
        审核决策处理结果

    Raises:
        HTTPException: 任务不存在或不在审核阶段
    """
    task_manager = get_task_manager()
    task = await task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 检查当前是否在 human_review 阶段
    progress = task.get("progress") or {}
    current_stage = progress.get("current_stage", "")
    if current_stage != "human_review" and task["status"] not in ("running", "pending"):
        raise HTTPException(
            status_code=400,
            detail=f"Task is not waiting for review (current stage: {current_stage})",
        )

    # 校验 revision 时必须提供修改意见
    if request.approval_status in ("rejected", "revision") and not request.revision_instructions.strip():
        raise HTTPException(
            status_code=400,
            detail="revision_instructions is required when approval_status is 'rejected' or 'revision'",
        )

    try:
        await task_manager.set_review_decision(
            task_id=task_id,
            status=request.approval_status,
            instructions=request.revision_instructions,
        )

        # approved/revision：后台 resume pipeline（LangGraph Command(resume=decision)）
        # rejected：标记任务失败，不 resume
        if request.approval_status == "rejected":
            await task_manager.fail_task(task_id, "用户驳回审核")
        else:
            decision = {
                "approval_status": request.approval_status,
                "revision_instructions": request.revision_instructions,
            }
            background_tasks.add_task(resume_pipeline, task_id, decision)

        status_text_map = {
            "approved": "已通过，流水线将继续",
            "rejected": "已拒绝，流水线已终止",
            "revision": "已要求修改，将根据意见调整",
        }

        return ReviewResponse(
            task_id=task_id,
            approval_status=request.approval_status,
            message=f"审核决策已提交: {status_text_map.get(request.approval_status, '')}",
        )
    except Exception as e:
        logger.exception(f"Failed to submit review for task {task_id}")
        raise HTTPException(status_code=500, detail=f"Failed to submit review: {str(e)}")


@router.get("/{task_id}/review", response_model=ReviewDataResponse)
async def get_review_data(task_id: str, current_user: User = Depends(get_current_user)) -> ReviewDataResponse:
    """获取当前待审核数据

    返回任务当前是否在 human_review 阶段等待人工审核。

    Args:
        task_id: 任务 ID

    Returns:
        审核状态和待审数据

    Raises:
        HTTPException: 任务不存在
    """
    task_manager = get_task_manager()
    task = await task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    review_data = await task_manager.get_review_data(task_id)

    return ReviewDataResponse(
        task_id=task_id,
        current_stage=review_data.get("current_stage", ""),
        approval_status=review_data.get("approval_status", "none"),
        waiting_for_review=review_data.get("waiting_for_review", False),
        progress=review_data.get("progress"),
        result=review_data.get("result"),
    )
