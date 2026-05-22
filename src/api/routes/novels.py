"""小说生成 API 路由"""

import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

from src.api.models.requests import CreateNovelRequest
from src.api.models.responses import (
    TaskDetailResponse,
    TaskListResponse,
    TaskProgress,
    TaskResponse,
    TaskSummary,
)
from src.api.services import generate_novel_background, get_task_manager
from src.core.validation import ValidationError, validate_idea, validate_novel_type

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/novels", tags=["novels"])


@router.post("", response_model=TaskResponse, status_code=202)
async def create_novel(
    request: CreateNovelRequest, background_tasks: BackgroundTasks
) -> TaskResponse:
    """创建小说生成任务

    Args:
        request: 创建请求
        background_tasks: 后台任务

    Returns:
        任务响应

    Raises:
        HTTPException: 输入验证失败
    """
    try:
        # 验证输入
        validate_idea(request.idea)
        validate_novel_type(request.novel_type)

        # 创建任务
        task_manager = get_task_manager()
        task_id = await task_manager.create_task(
            idea=request.idea,
            novel_type=request.novel_type,
            target_words=request.target_words,
        )

        # 添加后台任务
        background_tasks.add_task(generate_novel_background, task_id, request)

        logger.info(f"Created novel generation task {task_id}")

        return TaskResponse(
            task_id=task_id,
            status="pending",
            created_at=datetime.now(),
            estimated_duration_minutes=70,
        )

    except (ValidationError, ValueError) as e:
        # 捕获验证错误
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Failed to create novel task")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{task_id}", response_model=TaskDetailResponse)
async def get_novel_task(task_id: str) -> TaskDetailResponse:
    """获取任务详情

    Args:
        task_id: 任务 ID

    Returns:
        任务详情

    Raises:
        HTTPException: 任务不存在
    """
    task_manager = get_task_manager()
    task = await task_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # 构建进度信息
    progress = None
    if task.get("progress"):
        progress = TaskProgress(**task["progress"])

    return TaskDetailResponse(
        task_id=task["task_id"],
        novel_id=task.get("novel_id"),
        status=task["status"],
        progress=progress,
        created_at=task["created_at"],
        started_at=task.get("started_at"),
        completed_at=task.get("completed_at"),
        estimated_completion=task.get("estimated_completion"),
        result=task.get("result"),
        errors=task.get("errors", []),
    )


@router.get("", response_model=TaskListResponse)
async def list_novel_tasks(
    status: str | None = Query(None, description="过滤状态"),
    limit: int = Query(20, ge=1, le=100, description="返回数量"),
    offset: int = Query(0, ge=0, description="偏移量"),
) -> TaskListResponse:
    """列出任务

    Args:
        status: 过滤状态
        limit: 返回数量
        offset: 偏移量

    Returns:
        任务列表
    """
    task_manager = get_task_manager()
    tasks, total = await task_manager.list_tasks(
        status=status, limit=limit, offset=offset
    )

    # 转换为摘要格式
    task_summaries = [
        TaskSummary(
            task_id=task["task_id"],
            novel_id=task.get("novel_id"),
            status=task["status"],
            created_at=task["created_at"],
            completed_at=task.get("completed_at"),
            novel_type=task.get("novel_type"),
            target_words=task.get("target_words"),
            idea=task.get("idea"),
        )
        for task in tasks
    ]

    return TaskListResponse(
        tasks=task_summaries,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/cleanup/stale")
async def cleanup_stale_tasks():
    """自动将超过2小时未完成的任务标记为失败"""
    task_manager = get_task_manager()
    count = await task_manager.expire_stale_tasks(hours=2)
    return {"expired_count": count}


@router.post("/{task_id}/cancel")
async def cancel_task(task_id: str):
    """将卡住的任务标记为失败"""
    task_manager = get_task_manager()
    task = await task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] in ("completed", "failed"):
        raise HTTPException(status_code=400, detail="Task already finished")
    await task_manager.fail_task(task_id, "用户手动取消：任务超时未完成")
    return {"status": "cancelled"}
