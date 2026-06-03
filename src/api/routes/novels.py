"""小说生成 API 路由"""

import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query

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
from src.api.services import generate_novel_background, get_task_manager
from src.core.validation import ValidationError, validate_idea, validate_novel_type

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/novels", tags=["novels"])
tasks_router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


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


@tasks_router.post("/{task_id}/pause")
async def pause_generation_task(task_id: str):
    task_manager = get_task_manager()
    task = await task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Task can only be paused when running (current status: {task['status']})",
        )
    try:
        from src.api.services.novel_generator import pause_task
        await pause_task(task_id)
        return {"task_id": task_id, "status": "paused"}
    except Exception:
        logger.exception(f"Failed to pause task {task_id}")
        raise HTTPException(status_code=500, detail="Failed to pause task")


@tasks_router.post("/{task_id}/resume")
async def resume_generation_task(task_id: str):
    task_manager = get_task_manager()
    task = await task_manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task["status"] != "paused":
        raise HTTPException(
            status_code=400,
            detail=f"Task can only be resumed when paused (current status: {task['status']})",
        )
    try:
        from src.api.services.novel_generator import resume_task
        await resume_task(task_id)
        return {"task_id": task_id, "status": "running"}
    except Exception:
        logger.exception(f"Failed to resume task {task_id}")
        raise HTTPException(status_code=500, detail="Failed to resume task")


# --- Long-form novel endpoints ---


@router.post("/long-form", response_model=LongFormTaskResponse, status_code=202)
async def create_long_form_novel(
    request: LongFormNovelRequest,
    background_tasks: BackgroundTasks,
) -> LongFormTaskResponse:
    """创建百万字长篇生成任务

    Args:
        request: 长篇生成请求
        background_tasks: 后台任务

    Returns:
        长篇任务响应

    Raises:
        HTTPException: 输入验证失败
    """
    try:
        # Validate input
        validate_idea(request.idea)
        validate_novel_type(request.novel_type)

        # Create task
        task_manager = get_task_manager()
        task_id = await task_manager.create_task(
            idea=request.idea,
            novel_type=request.novel_type,
            target_words=request.target_words,
        )

        # Create novel record
        from src.api.services.novel_manager import get_novel_manager
        novel_manager = get_novel_manager()
        novel_id = await novel_manager.create_novel(
            idea=request.idea,
            novel_type=request.novel_type,
            target_words=request.target_words,
            writing_style=request.writing_style,
            writing_style_prompt=request.writing_style_prompt,
        )

        # Update task with novel_id
        await task_manager.update_status(
            task_id, "pending", progress={"novel_id": novel_id}
        )

        # Add background task
        from src.api.services.novel_generator import (
            calculate_long_form_chapter_plan,
            generate_long_form_background,
        )
        background_tasks.add_task(
            generate_long_form_background,
            task_id,
            novel_id,
            request,
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
async def get_quality_report(novel_id: str) -> QualityReport:
    """获取质量趋势报告

    Args:
        novel_id: 小说 ID

    Returns:
        质量报告

    Raises:
        HTTPException: 小说不存在
    """
    try:
        from src.api.services.quality_report_service import get_quality_report_service
        service = get_quality_report_service()
        report = await service.generate_novel_quality_report(novel_id)
        return QualityReport(**report)
    except Exception:
        logger.exception(f"Failed to get quality report for {novel_id}")
        raise HTTPException(status_code=500, detail="Failed to generate quality report")


@router.get("/{novel_id}/filler-detection", response_model=FillerDetectionResult)
async def get_filler_detection(novel_id: str) -> FillerDetectionResult:
    """获取注水检测结果

    Args:
        novel_id: 小说 ID

    Returns:
        注水检测结果

    Raises:
        HTTPException: 小说不存在
    """
    try:
        from src.api.services.filler_detection_service import (
            get_filler_detection_service,
        )
        service = get_filler_detection_service()
        result = await service.detect_filler_chapters(novel_id)
        return FillerDetectionResult(**result)
    except Exception:
        logger.exception(f"Failed to detect filler for {novel_id}")
        raise HTTPException(status_code=500, detail="Failed to detect filler chapters")


@router.get("/{novel_id}/foreshadow-tracker", response_model=ForeshadowTrackerResult)
async def get_foreshadow_tracker(novel_id: str) -> ForeshadowTrackerResult:
    """获取伏笔追踪报告

    Args:
        novel_id: 小说 ID

    Returns:
        伏笔追踪结果

    Raises:
        HTTPException: 小说不存在
    """
    try:
        from src.api.services.foreshadow_tracker_service import (
            get_foreshadow_tracker_service,
        )
        service = get_foreshadow_tracker_service()
        result = await service.track_foreshadows(novel_id)
        return ForeshadowTrackerResult(**result)
    except Exception:
        logger.exception(f"Failed to track foreshadows for {novel_id}")
        raise HTTPException(status_code=500, detail="Failed to track foreshadows")


@router.get("/{novel_id}/progress", response_model=LongFormProgressResponse)
async def get_long_form_progress(novel_id: str) -> LongFormProgressResponse:
    """获取百万字长篇生成进度

    Args:
        novel_id: 小说 ID

    Returns:
        进度响应

    Raises:
        HTTPException: 小说不存在
    """
    try:
        from src.api.services.long_form_progress_service import (
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
    background_tasks: BackgroundTasks,
):
    """按卷触发生成

    Args:
        novel_id: 小说 ID
        volume_number: 卷号
        request: 生成请求
        background_tasks: 后台任务

    Returns:
        任务状态

    Raises:
        HTTPException: 小说或卷不存在
    """
    try:
        from src.api.services.long_form_progress_service import (
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
        )

        # Add background task
        from src.api.services.novel_generator import generate_volume_background
        background_tasks.add_task(
            generate_volume_background,
            task_id,
            novel_id,
            volume_number,
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
async def pause_volume_generate(novel_id: str, volume_number: int):
    """暂停指定卷生成

    Args:
        novel_id: 小说 ID
        volume_number: 卷号

    Returns:
        状态响应

    Raises:
        HTTPException: 操作失败
    """
    try:
        from src.api.services.long_form_progress_service import (
            get_long_form_progress_service,
        )
        service = get_long_form_progress_service()
        await service.update_volume_status(
            novel_id=novel_id,
            volume_number=volume_number,
            status="paused",
        )
        return {"status": "paused", "novel_id": novel_id, "volume_number": volume_number}
    except Exception:
        logger.exception(f"Failed to pause volume {volume_number}")
        raise HTTPException(status_code=500, detail="Failed to pause generation")


@router.post("/{novel_id}/volumes/{volume_number}/resume")
async def resume_volume_generate(
    novel_id: str,
    volume_number: int,
    background_tasks: BackgroundTasks,
):
    """恢复指定卷生成

    Args:
        novel_id: 小说 ID
        volume_number: 卷号
        background_tasks: 后台任务

    Returns:
        任务状态

    Raises:
        HTTPException: 操作失败
    """
    try:
        from src.api.services.long_form_progress_service import (
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
        )

        # Add background task
        from src.api.services.novel_generator import generate_volume_background
        background_tasks.add_task(
            generate_volume_background,
            task_id,
            novel_id,
            volume_number,
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
