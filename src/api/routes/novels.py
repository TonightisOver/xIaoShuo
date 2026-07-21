"""小说生成 API 路由"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.models.db_models import User
from src.api.models.requests import (
    CreateNovelRequest,
    LongFormNovelRequest,
    VolumeGenerateRequest,
)
from src.api.models.responses import (
    FillerDetectionResult,
    ForeshadowTrackerResult,
    LongFormProgressResponse,
    LongFormTaskResponse,
    QualityReport,
    TaskDetailResponse,
    TaskListResponse,
    TaskProgress,
    TaskResponse,
    TaskSummary,
)
from src.api.owner_guard import verify_novel_owner, verify_task_owner
from src.api.services.generation.novel_generator_planning import (
    calculate_long_form_chapter_plan,
)
from src.api.services.tasks.task_dispatcher import TaskType
from src.api.services.tasks.task_manager import get_task_manager
from src.core.config import get_settings
from src.core.security.auth import get_current_user, require_admin_user
from src.core.validation import ValidationError, validate_idea, validate_novel_type

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/novels", tags=["novels"])
tasks_router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.post("", response_model=TaskResponse, status_code=202)
async def create_novel(
    request: CreateNovelRequest,
    current_user: User = Depends(get_current_user),
) -> TaskResponse:
    """创建小说生成任务

    Args:
        request: 创建请求
        current_user: 当前登录用户
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
            owner_id=current_user.id,
            task_type=TaskType.NOVEL_GENERATE.value,
            task_payload={"request": request.model_dump(mode="json")},
            max_attempts=1,
        )

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
async def get_novel_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
) -> TaskDetailResponse:
    """获取任务详情

    Args:
        task_id: 任务 ID
        current_user: 当前登录用户（必须为任务 owner）

    Returns:
        任务详情

    Raises:
        HTTPException: 任务不存在 / 非 owner
    """
    task = await verify_task_owner(task_id, current_user)

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
    current_user: User = Depends(get_current_user),
) -> TaskListResponse:
    """列出当前用户的任务

    Args:
        status: 过滤状态
        limit: 返回数量
        offset: 偏移量
        current_user: 当前登录用户（只返回其 owner 的任务）

    Returns:
        任务列表
    """
    task_manager = get_task_manager()
    tasks, total = await task_manager.list_tasks_for_owner(
        owner_id=current_user.id, status=status, limit=limit, offset=offset
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
async def cleanup_stale_tasks(
    current_user: User = Depends(require_admin_user),
):
    """自动将超过2小时未完成的任务标记为失败（仅管理员，影响所有用户任务）。"""
    task_manager = get_task_manager()
    count = await task_manager.expire_stale_tasks(hours=2)
    return {"expired_count": count}


@router.post("/{task_id}/cancel")
async def cancel_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """将卡住的任务标记为失败（仅任务 owner）。"""
    task = await verify_task_owner(task_id, current_user)
    if task["status"] in ("completed", "failed"):
        raise HTTPException(status_code=400, detail="Task already finished")
    task_manager = get_task_manager()
    await task_manager.fail_task(task_id, "用户手动取消：任务超时未完成")
    return {"status": "cancelled"}


@tasks_router.post("/{task_id}/pause")
async def pause_generation_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    task = await verify_task_owner(task_id, current_user)
    if task["status"] != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Task can only be paused when running (current status: {task['status']})",
        )
    try:
        # Task 7（B14）：pause 只设"暂停意图"（长篇写 checkpoint.pause_requested，
        # 短篇降级写 Task.status='paused'）。长篇 worker 在下一章安全边界自行确认，
        # 故此处返回 pause_requested 更准确（真正确认见 is_paused_confirmed）。
        from src.api.services.generation.novel_generator import pause_task
        await pause_task(task_id)
        return {"task_id": task_id, "status": "pause_requested"}
    except Exception:
        logger.exception(f"Failed to pause task {task_id}")
        raise HTTPException(status_code=500, detail="Failed to pause task")


@tasks_router.post("/{task_id}/resume")
async def resume_generation_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    # Task 7（B5/§七.4）：长篇暂停后 Task.status 仍为 running（暂停意图在
    # checkpoint，队列层 queue_state='idle'），故不再用 Task.status=='paused'
    # 作前置。改为经 requeue_paused_task 按 checkpoint 状态判定：
    #   requeued=True                → 200 已重入队
    #   reason='not_paused'（幂等）    → 200 no-op（目标态已达成）
    #   reason='no_checkpoint'（短篇） → 降级走旧 resume（要求 status=='paused'）
    #   reason='illegal_state:*'      → 409 状态冲突
    task = await verify_task_owner(task_id, current_user)
    try:
        from src.api.services.generation.novel_generator import resume_task
        from src.api.services.tasks.task_manager import get_task_manager

        result = await get_task_manager().requeue_paused_task(task_id)
        if result.requeued:
            await resume_task(task_id)
            return {"task_id": task_id, "status": "running"}
        if result.reason == "not_paused":
            # 幂等：已在 running/queued，视作 no-op。
            return {"task_id": task_id, "status": "running", "noop": True}
        if result.reason == "no_checkpoint":
            # 短篇/HITL 降级：沿用旧前置条件。
            if task["status"] != "paused":
                raise HTTPException(
                    status_code=400,
                    detail=f"Task can only be resumed when paused (current status: {task['status']})",
                )
            await resume_task(task_id)
            return {"task_id": task_id, "status": "running"}
        # illegal_state / task_not_found → 409
        raise HTTPException(
            status_code=409,
            detail=f"Task cannot be resumed: {result.reason}",
        )
    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Failed to resume task {task_id}")
        raise HTTPException(status_code=500, detail="Failed to resume task")


@tasks_router.get("/{task_id}/checkpoint")
async def get_task_checkpoint(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Task 10：返回 checkpoint 公开摘要（不含 failure_detail 敏感字段）。

    无 checkpoint（短篇/HITL）返回 404。
    """
    await verify_task_owner(task_id, current_user)
    from src.api.services.tasks.checkpoint_store import get_checkpoint_store

    view = await get_checkpoint_store().public_view(task_id)
    if view is None:
        raise HTTPException(status_code=404, detail="No checkpoint for this task")
    return view


@tasks_router.post("/{task_id}/retry")
async def retry_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Task 10：从断点重试。recoverable/needs_human 重入队；unrecoverable 返回 409。"""
    await verify_task_owner(task_id, current_user)
    from src.api.services.tasks.task_manager import get_task_manager

    result = await get_task_manager().retry_task(task_id)
    if result.requeued:
        return {"task_id": task_id, "status": "queued"}
    if result.reason == "unrecoverable":
        raise HTTPException(
            status_code=409,
            detail="Task is unrecoverable; cannot retry from checkpoint",
        )
    if result.reason == "no_checkpoint":
        raise HTTPException(
            status_code=404, detail="No checkpoint; cannot retry from breakpoint"
        )
    raise HTTPException(
        status_code=409, detail=f"Cannot retry: {result.reason}"
    )


@tasks_router.post("/{task_id}/abort")
async def abort_task(
    task_id: str,
    current_user: User = Depends(get_current_user),
):
    """Task 10：用户主动中止——置 failed，保留 checkpoint 诊断。"""
    await verify_task_owner(task_id, current_user)
    from src.api.services.tasks.task_manager import get_task_manager

    result = await get_task_manager().abort_task(task_id)
    if not result.requeued and result.reason == "task_not_found":
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task_id": task_id, "status": "failed"}


# --- Long-form novel endpoints ---


@router.post("/long-form", response_model=LongFormTaskResponse, status_code=202)
async def create_long_form_novel(
    request: LongFormNovelRequest,
    current_user: User = Depends(get_current_user),
) -> LongFormTaskResponse:
    """创建百万字长篇生成任务

    Args:
        request: 长篇生成请求
    Returns:
        长篇任务响应

    Raises:
        HTTPException: 输入验证失败
    """
    try:
        # Validate input
        validate_idea(request.idea)
        validate_novel_type(request.novel_type)

        # Create novel record
        from src.api.services.content.novel_manager import get_novel_manager
        novel_manager = get_novel_manager()
        novel_id = await novel_manager.create_novel(
            idea=request.idea,
            novel_type=request.novel_type,
            target_words=request.target_words,
            writing_style=request.writing_style,
            writing_style_prompt=request.writing_style_prompt,
            owner_id=current_user.id,
        )

        task_manager = get_task_manager()
        task_id = await task_manager.create_task(
            idea=request.idea,
            novel_type=request.novel_type,
            target_words=request.target_words,
            novel_id=novel_id,
            owner_id=current_user.id,
            task_type=TaskType.NOVEL_LONG_FORM.value,
            task_payload={
                "novel_id": novel_id,
                "request": request.model_dump(mode="json"),
            },
            max_attempts=get_settings().LONG_FORM_MAX_ATTEMPTS,
            operation_id=f"{novel_id}:{TaskType.NOVEL_LONG_FORM.value}",
        )

        logger.info(f"Created long-form novel task {task_id} for novel {novel_id}")

        total_chapters = calculate_long_form_chapter_plan(request)["total_chapters"]
        estimated_hours = (total_chapters * 3) / 60  # ~3 minutes per chapter

        return LongFormTaskResponse(
            task_id=task_id,
            novel_id=novel_id,
            status="pending",
            total_volumes=request.volumes,
            total_chapters=total_chapters,
            target_words=request.target_words,
            volumes_completed=0,
            chapters_completed=0,
            created_at=datetime.now(),
            estimated_duration_hours=round(estimated_hours, 1),
        )

    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception("Failed to create long-form novel task")
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{novel_id}/quality-report", response_model=QualityReport)
async def get_quality_report(
    novel_id: str,
    current_user: User = Depends(get_current_user),
) -> QualityReport:
    """获取质量趋势报告

    Args:
        novel_id: 小说 ID
        current_user: 当前登录用户（必须为小说 owner）

    Returns:
        质量报告

    Raises:
        HTTPException: 小说不存在 / 非 owner
    """
    await verify_novel_owner(novel_id, current_user)
    try:
        from src.api.services.quality.quality_report_service import (
            get_quality_report_service,
        )
        service = get_quality_report_service()
        report = await service.generate_novel_quality_report(novel_id)
        return QualityReport(**report)
    except Exception:
        logger.exception(f"Failed to get quality report for {novel_id}")
        raise HTTPException(status_code=500, detail="Failed to generate quality report")


@router.get("/{novel_id}/filler-detection", response_model=FillerDetectionResult)
async def get_filler_detection(
    novel_id: str,
    current_user: User = Depends(get_current_user),
) -> FillerDetectionResult:
    """获取注水检测结果

    Args:
        novel_id: 小说 ID
        current_user: 当前登录用户（必须为小说 owner）
    """
    await verify_novel_owner(novel_id, current_user)
    try:
        from src.api.services.quality.filler_detection_service import (
            get_filler_detection_service,
        )
        service = get_filler_detection_service()
        result = await service.detect_filler_chapters(novel_id)
        return FillerDetectionResult(**result)
    except Exception:
        logger.exception(f"Failed to detect filler for {novel_id}")
        raise HTTPException(status_code=500, detail="Failed to detect filler chapters")


@router.get("/{novel_id}/foreshadow-tracker", response_model=ForeshadowTrackerResult)
async def get_foreshadow_tracker(
    novel_id: str,
    current_user: User = Depends(get_current_user),
) -> ForeshadowTrackerResult:
    """获取伏笔追踪报告

    Args:
        novel_id: 小说 ID
        current_user: 当前登录用户（必须为小说 owner）
    """
    await verify_novel_owner(novel_id, current_user)
    try:
        from src.api.services.quality.foreshadow_tracker_service import (
            get_foreshadow_tracker_service,
        )
        service = get_foreshadow_tracker_service()
        result = await service.track_foreshadows(novel_id)
        return ForeshadowTrackerResult(**result)
    except Exception:
        logger.exception(f"Failed to track foreshadows for {novel_id}")
        raise HTTPException(status_code=500, detail="Failed to track foreshadows")


@router.get("/{novel_id}/long-form/progress", response_model=LongFormProgressResponse)
async def get_long_form_progress(
    novel_id: str,
    current_user: User = Depends(get_current_user),
) -> LongFormProgressResponse:
    """获取百万字长篇生成进度

    Args:
        novel_id: 小说 ID
        current_user: 当前登录用户（必须为小说 owner）
    """
    await verify_novel_owner(novel_id, current_user)
    try:
        from src.api.services.generation.long_form_progress_service import (
            get_long_form_progress_service,
        )
        service = get_long_form_progress_service()
        progress = await service.get_progress(novel_id)
        if "error" in progress:
            raise HTTPException(status_code=404, detail=progress["error"])
        return LongFormProgressResponse(**progress)
    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Failed to get progress for {novel_id}")
        raise HTTPException(status_code=500, detail="Failed to get progress")


@router.post("/{novel_id}/volumes/{volume_number}/generate", status_code=202)
async def trigger_volume_generate(
    novel_id: str,
    volume_number: int,
    request: VolumeGenerateRequest,
    current_user: User = Depends(get_current_user),
):
    """按卷触发生成

    Args:
        novel_id: 小说 ID
        volume_number: 卷号
        request: 生成请求
        current_user: 当前登录用户（必须为小说 owner）
    Returns:
        任务状态

    Raises:
        HTTPException: 小说或卷不存在 / 非 owner
    """
    await verify_novel_owner(novel_id, current_user)
    try:
        from src.api.services.generation.long_form_progress_service import (
            get_long_form_progress_service,
        )
        progress_service = get_long_form_progress_service()

        # Check if volume exists
        vol_progress = await progress_service.get_volume_progress(novel_id, volume_number)
        if not vol_progress:
            raise HTTPException(
                status_code=404,
                detail=f"Volume {volume_number} not found for novel {novel_id}",
            )

        if vol_progress["status"] == "generating":
            raise HTTPException(
                status_code=400,
                detail=f"Volume {volume_number} is already being generated",
            )

        # Create task
        task_manager = get_task_manager()
        task_id = await task_manager.create_task(
            idea=f"Volume {volume_number} generation",
            novel_type="long_form",
            target_words=0,
            novel_id=novel_id,
            owner_id=current_user.id,
            task_type=TaskType.NOVEL_VOLUME.value,
            task_payload={
                "novel_id": novel_id,
                "volume_number": volume_number,
            },
            max_attempts=get_settings().LONG_FORM_MAX_ATTEMPTS,
            operation_id=f"{novel_id}:volume:{volume_number}",
        )

        return {
            "task_id": task_id,
            "novel_id": novel_id,
            "volume_number": volume_number,
            "status": "pending",
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Failed to trigger volume generation for {novel_id} vol {volume_number}")
        raise HTTPException(status_code=500, detail="Failed to trigger generation")


@router.post("/{novel_id}/volumes/{volume_number}/pause")
async def pause_volume_generate(
    novel_id: str,
    volume_number: int,
    current_user: User = Depends(get_current_user),
):
    """暂停指定卷生成（仅小说 owner）。

    Task 7（§七.6）：卷级 pause 统一为 task 级 pause 意图。一个 task 可能跨多卷，
    卷级 pause 语义即"task 在下一章安全边界停下"。除写 LFP.status='paused'（前端
    展示）外，同时对该 novel 的活跃长篇 task 设 checkpoint.pause_requested=True，
    消除 LFP.status 与 task 状态的双轨制。
    """
    await verify_novel_owner(novel_id, current_user)
    try:
        from sqlalchemy import select

        from src.api.models.db_models import TaskCheckpoint
        from src.api.services.generation.long_form_progress_service import (
            get_long_form_progress_service,
        )
        from src.api.services.generation.pause_state_store import (
            get_pause_state_store,
        )
        from src.core.database import get_db_session

        service = get_long_form_progress_service()
        await service.update_volume_status(
            novel_id=novel_id,
            volume_number=volume_number,
            status="paused",
        )

        # 对该 novel 尚未终态的 checkpoint 任务设暂停意图（跨进程 worker 感知）。
        async with get_db_session() as session:
            task_id = (
                await session.execute(
                    select(TaskCheckpoint.task_id).where(
                        TaskCheckpoint.novel_id == novel_id,
                        TaskCheckpoint.status.notin_(
                            ["succeeded", "failed", "completed"]
                        ),
                    )
                )
            ).scalar_one_or_none()
        if task_id is not None:
            await get_pause_state_store().set_paused(task_id)

        return {"status": "paused", "novel_id": novel_id, "volume_number": volume_number}
    except Exception:
        logger.exception(f"Failed to pause volume {volume_number}")
        raise HTTPException(status_code=500, detail="Failed to pause generation")


@router.post("/{novel_id}/volumes/{volume_number}/resume")
async def resume_volume_generate(
    novel_id: str,
    volume_number: int,
    current_user: User = Depends(get_current_user),
):
    """恢复指定卷生成（仅小说 owner）。"""
    await verify_novel_owner(novel_id, current_user)
    try:
        from src.api.services.generation.long_form_progress_service import (
            get_long_form_progress_service,
        )
        progress_service = get_long_form_progress_service()

        vol_progress = await progress_service.get_volume_progress(novel_id, volume_number)
        if not vol_progress:
            raise HTTPException(
                status_code=404,
                detail=f"Volume {volume_number} not found",
            )

        if vol_progress["status"] != "paused":
            raise HTTPException(
                status_code=400,
                detail=f"Volume {volume_number} is not paused (current status: {vol_progress['status']})",
            )

        # Create task
        task_manager = get_task_manager()
        task_id = await task_manager.create_task(
            idea=f"Volume {volume_number} resume",
            novel_type="long_form",
            target_words=0,
            novel_id=novel_id,
            owner_id=current_user.id,
            task_type=TaskType.NOVEL_VOLUME.value,
            task_payload={
                "novel_id": novel_id,
                "volume_number": volume_number,
            },
            max_attempts=get_settings().LONG_FORM_MAX_ATTEMPTS,
            operation_id=f"{novel_id}:volume:{volume_number}",
        )

        return {
            "task_id": task_id,
            "novel_id": novel_id,
            "volume_number": volume_number,
            "status": "resuming",
        }

    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Failed to resume volume {volume_number}")
        raise HTTPException(status_code=500, detail="Failed to resume generation")
