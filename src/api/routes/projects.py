"""小说项目管理 API 路由"""

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.models.requests import CreateNovelRequest
from src.api.models.responses import (
    CreateResponse,
    NovelDetailResponse,
    NovelListResponse,
    StatusResponse,
)
from src.api.services.chapter_service import get_chapter_service
from src.api.services.novel_generator import (
    generate_novel_background,
    generate_novel_full_background,
)
from src.api.services.novel_manager import get_novel_manager
from src.api.services.task_manager import get_task_manager
from src.api.services.volume_service import get_volume_service
from src.core.validation import ValidationError, validate_idea, validate_novel_type

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


# --- Request/Response Models ---

class CreateProjectRequest(BaseModel):
    idea: str = Field(..., min_length=10, max_length=1000)
    novel_type: str
    target_words: int = Field(default=100000, ge=10000, le=10000000)
    title: str | None = None
    writing_style: str = Field(default="现代白话")
    custom_style_description: str | None = None
    writing_style_prompt: str | None = None


class UpdateProjectRequest(BaseModel):
    title: str | None = None
    idea: str | None = None
    novel_type: str | None = None
    target_words: int | None = None
    writing_style: str | None = None
    custom_style_description: str | None = None
    writing_style_prompt: str | None = None


# --- Novel Project CRUD ---

@router.post("", status_code=201, response_model=CreateResponse)
async def create_project(request: CreateProjectRequest):
    try:
        validate_idea(request.idea)
        validate_novel_type(request.novel_type)
    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    manager = get_novel_manager()
    novel_id = await manager.create_novel(
        idea=request.idea,
        novel_type=request.novel_type,
        target_words=request.target_words,
        title=request.title,
        writing_style=request.writing_style,
        custom_style_description=request.custom_style_description,
        writing_style_prompt=request.writing_style_prompt,
    )
    return {"novel_id": novel_id, "status": "draft"}


@router.get("", response_model=NovelListResponse)
async def list_projects(
    novel_type: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    manager = get_novel_manager()
    novels, total = await manager.list_novels(novel_type=novel_type, limit=limit, offset=offset)
    return {"novels": novels, "total": total, "limit": limit, "offset": offset}


@router.get("/{novel_id}", response_model=NovelDetailResponse)
async def get_project(novel_id: str):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    return novel


@router.put("/{novel_id}", response_model=StatusResponse)
async def update_project(novel_id: str, request: UpdateProjectRequest):
    manager = get_novel_manager()
    updated = await manager.update_novel(novel_id, **request.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Novel not found")
    return {"status": "updated"}


@router.delete("/{novel_id}", response_model=StatusResponse)
async def delete_project(novel_id: str):
    manager = get_novel_manager()
    deleted = await manager.delete_novel(novel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Novel not found")
    return {"status": "deleted"}


# --- Generate ---

@router.post("/{novel_id}/generate", status_code=202)
async def generate_novel(novel_id: str, background_tasks: BackgroundTasks):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    task_manager = get_task_manager()
    task_id = await task_manager.create_task(
        idea=novel["idea"],
        novel_type=novel["novel_type"],
        target_words=novel["target_words"],
        novel_id=novel_id,
    )

    request = CreateNovelRequest(
        idea=novel["idea"],
        novel_type=novel["novel_type"],
        target_words=novel["target_words"],
        writing_style=novel.get("writing_style", "现代白话"),
        writing_style_prompt=novel.get("writing_style_prompt", ""),
    )
    background_tasks.add_task(generate_novel_background, task_id, request)

    await manager.update_novel(novel_id, status="generating")

    return {"task_id": task_id, "novel_id": novel_id, "status": "generating"}


# --- Full Generate (13-stage pipeline) ---


class FullGenerateRequest(BaseModel):
    idea: str = Field(..., min_length=10, max_length=1000)
    novel_type: str
    target_words: int = Field(default=100000, ge=10000, le=10000000)
    title: str | None = None
    writing_style: str = Field(default="现代白话")
    custom_style_description: str | None = None
    writing_style_prompt: str | None = None


@router.post("/full-generate", status_code=202)
async def full_generate_project(
    request: FullGenerateRequest, background_tasks: BackgroundTasks,
):
    """创建项目并启动 13 阶段全功能生成"""
    try:
        validate_idea(request.idea)
        validate_novel_type(request.novel_type)
    except (ValidationError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e))

    manager = get_novel_manager()
    novel_id = await manager.create_novel(
        idea=request.idea,
        novel_type=request.novel_type,
        target_words=request.target_words,
        title=request.title,
        writing_style=request.writing_style,
        custom_style_description=request.custom_style_description,
        writing_style_prompt=request.writing_style_prompt,
    )

    task_manager = get_task_manager()
    task_id = await task_manager.create_task(
        idea=request.idea,
        novel_type=request.novel_type,
        target_words=request.target_words,
        novel_id=novel_id,
    )

    gen_request = CreateNovelRequest(
        idea=request.idea,
        novel_type=request.novel_type,
        target_words=request.target_words,
        writing_style=request.writing_style,
        writing_style_prompt=request.writing_style_prompt or "",
    )
    background_tasks.add_task(generate_novel_full_background, task_id, gen_request)

    await manager.update_novel(novel_id, status="generating")

    return {
        "task_id": task_id, "novel_id": novel_id,
        "status": "full_generating", "pipeline": "full_13_stage",
    }


@router.post("/{novel_id}/generate-full", status_code=202)
async def full_generate_existing(novel_id: str, background_tasks: BackgroundTasks, force: bool = False):
    """对已有项目启动 13 阶段全功能生成。"""
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    # 防止重复触发：检查是否有正在运行的任务
    task_manager = get_task_manager()
    await task_manager.expire_stale_tasks(hours=1)
    all_tasks, _ = await task_manager.list_tasks()
    running_tasks = [
        t for t in all_tasks
        if t.get("novel_id") == novel_id
        and t.get("status") in ("pending", "running")
    ]
    if running_tasks:
        raise HTTPException(
            status_code=409,
            detail=f"该小说已有正在运行的生成任务 (task_id={running_tasks[0].get('task_id')}), 请等待完成或取消后再试"
        )

    # 防止盖已有章节：检查是否已有有效章节
    if not force:
        chapter_service = get_chapter_service()
        existing_chapters = await chapter_service.list_chapters(novel_id)
        valid_chapters = [ch for ch in existing_chapters if ch.get("word_count", 0) > 100]
        if valid_chapters:
            raise HTTPException(
                status_code=409,
                detail=f"该小说已有 {len(valid_chapters)} 个有效章节，全流程生成会覆盖所有内容。如确认要重新生成，请传入 force=true 参数"
            )

    task_id = await task_manager.create_task(
        idea=novel["idea"],
        novel_type=novel["novel_type"],
        target_words=novel["target_words"],
        novel_id=novel_id,
    )

    gen_request = CreateNovelRequest(
        idea=novel["idea"],
        novel_type=novel["novel_type"],
        target_words=novel["target_words"],
        writing_style=novel.get("writing_style", "现代白话"),
        writing_style_prompt=novel.get("writing_style_prompt", ""),
    )
    background_tasks.add_task(generate_novel_full_background, task_id, gen_request)

    await manager.update_novel(novel_id, status="generating")

    return {
        "task_id": task_id, "novel_id": novel_id,
        "status": "full_generating", "pipeline": "full_13_stage",
    }


class GenerateVolumeRequest(BaseModel):
    volume_number: int


@router.post("/{novel_id}/generate-volume", status_code=202)
async def generate_volume(novel_id: str, request: GenerateVolumeRequest, background_tasks: BackgroundTasks):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    # 防止重复触发；先清理超时任务
    task_manager = get_task_manager()
    await task_manager.expire_stale_tasks(hours=1)
    all_tasks, _ = await task_manager.list_tasks()
    running_tasks = [
        t for t in all_tasks
        if t.get("novel_id") == novel_id
        and t.get("status") in ("pending", "running")
    ]
    if running_tasks:
        raise HTTPException(
            status_code=409,
            detail=f"该小说已有正在运行的生成任务 (task_id={running_tasks[0].get('task_id')}), 请等待完成或取消后再试"
        )

    volume_service = get_volume_service()
    vol = await volume_service.get_volume(novel_id, request.volume_number)
    if not vol:
        # Fallback: check outlines table for volume data
        from src.api.services.outline_service import get_outline_service
        outline_svc = get_outline_service()
        vol_outlines = await outline_svc.get_volume_outlines(novel_id)
        outline_vol = next((v for v in vol_outlines if v["volume_number"] == request.volume_number), None)
        if not outline_vol:
            raise HTTPException(status_code=404, detail="Volume not found")

    from src.api.services.novel_generator import generate_volume_background

    task_id = await task_manager.create_task(
        idea=novel["idea"],
        novel_type=novel["novel_type"],
        target_words=novel["target_words"],
        novel_id=novel_id,
    )

    background_tasks.add_task(generate_volume_background, task_id, novel_id, request.volume_number)
    await volume_service.update_volume(novel_id, request.volume_number, status="generating")

    return {"task_id": task_id, "novel_id": novel_id, "volume_number": request.volume_number, "status": "generating"}


class GenerateChaptersRequest(BaseModel):
    chapter_start: int = Field(..., ge=1)
    chapter_end: int = Field(..., ge=1)


@router.post("/{novel_id}/generate-chapters", status_code=202)
async def generate_chapters(novel_id: str, request: GenerateChaptersRequest, background_tasks: BackgroundTasks):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    if request.chapter_end < request.chapter_start:
        raise HTTPException(status_code=400, detail="chapter_end must be >= chapter_start")

    # 防止重复触发；先清理超时任务
    task_manager = get_task_manager()
    await task_manager.expire_stale_tasks(hours=1)
    all_tasks, _ = await task_manager.list_tasks()
    running_tasks = [
        t for t in all_tasks
        if t.get("novel_id") == novel_id
        and t.get("status") in ("pending", "running")
    ]
    if running_tasks:
        raise HTTPException(
            status_code=409,
            detail=f"该小说已有正在运行的生成任务 (task_id={running_tasks[0].get('task_id')}), 请等待完成或取消后再试"
        )

    from src.api.services.novel_generator import generate_chapters_background

    task_id = await task_manager.create_task(
        idea=novel["idea"],
        novel_type=novel["novel_type"],
        target_words=novel["target_words"],
        novel_id=novel_id,
    )

    background_tasks.add_task(
        generate_chapters_background, task_id, novel_id,
        request.chapter_start, request.chapter_end
    )

    return {
        "task_id": task_id,
        "novel_id": novel_id,
        "chapter_start": request.chapter_start,
        "chapter_end": request.chapter_end,
        "status": "generating",
    }
