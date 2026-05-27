"""小说项目管理 API 路由"""

import asyncio
from typing import Literal

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.models.requests import CreateNovelRequest
from src.api.models.responses import (
    ChapterResponse,
    CreateResponse,
    NovelDetailResponse,
    NovelListResponse,
    StatusResponse,
    VolumeResponse,
)
from src.api.services.novel_generator import (
    generate_novel_background,
    generate_novel_full_background,
)
from src.api.services.novel_manager import get_novel_manager
from src.api.services.task_manager import get_task_manager
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


class WorldSettingRequest(BaseModel):
    background: str | None = None
    geography: str | None = None
    culture: str | None = None
    rules: str | None = None
    extra: dict | None = None


class PowerSystemRequest(BaseModel):
    name: str
    description: str | None = None
    levels: list[dict] = Field(default_factory=list)


class CharacterRequest(BaseModel):
    name: str
    role: str | None = None
    description: str | None = None
    personality: str | None = None
    abilities: str | None = None
    background_story: str | None = None
    extra: dict | None = None


class ChapterUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None


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
    """对已有项目启动 13 阶段全功能生成。

    如果项目已有章节内容，需要传 force=true 才能覆盖重新生成。
    如果已有正在运行的生成任务，拒绝重复触发。
    """
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

    # 防止覆盖已有章节：检查是否已有有效章节
    if not force:
        existing_chapters = await manager.list_chapters(novel_id)
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


# --- Volumes ---

@router.get("/{novel_id}/volumes")
async def list_volumes(novel_id: str):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    return await manager.list_volumes(novel_id)


@router.get("/{novel_id}/volumes/{volume_number}", response_model=VolumeResponse)
async def get_volume(novel_id: str, volume_number: int):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    vol = await manager.get_volume(novel_id, volume_number)
    if not vol:
        raise HTTPException(status_code=404, detail="Volume not found")
    return vol


class VolumeUpdateRequest(BaseModel):
    title: str | None = None
    summary: str | None = None


@router.put("/{novel_id}/volumes/{volume_number}", response_model=StatusResponse)
async def update_volume(novel_id: str, volume_number: int, request: VolumeUpdateRequest):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    updated = await manager.update_volume(novel_id, volume_number, **request.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Volume not found")
    return {"status": "updated"}


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

    vol = await manager.get_volume(novel_id, request.volume_number)
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
    await manager.update_volume(novel_id, request.volume_number, status="generating")

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


# --- World Setting ---

@router.get("/{novel_id}/world")
async def get_world_setting(novel_id: str):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    ws = await manager.get_world_setting(novel_id)
    if not ws:
        return {"novel_id": novel_id, "background": None, "geography": None,
                "culture": None, "rules": None, "extra": None}
    return ws


@router.put("/{novel_id}/world")
async def update_world_setting(novel_id: str, request: WorldSettingRequest):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    await manager.upsert_world_setting(novel_id, **request.model_dump(exclude_none=True))
    return {"status": "updated"}


# --- Power Systems ---

@router.get("/{novel_id}/power-systems")
async def list_power_systems(novel_id: str):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    return await manager.list_power_systems(novel_id)


@router.post("/{novel_id}/power-systems", status_code=201)
async def create_power_system(novel_id: str, request: PowerSystemRequest):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    ps_id = await manager.create_power_system(
        novel_id, name=request.name,
        description=request.description, levels=request.levels
    )
    return {"id": ps_id, "status": "created"}


@router.put("/{novel_id}/power-systems/{ps_id}")
async def update_power_system(novel_id: str, ps_id: int, request: PowerSystemRequest):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    updated = await manager.update_power_system(
        novel_id, ps_id, name=request.name,
        description=request.description, levels=request.levels
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Power system not found")
    return {"status": "updated"}


@router.delete("/{novel_id}/power-systems/{ps_id}")
async def delete_power_system(novel_id: str, ps_id: int):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    deleted = await manager.delete_power_system(novel_id, ps_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Power system not found")
    return {"status": "deleted"}


# --- Characters ---

@router.get("/{novel_id}/characters")
async def list_characters(novel_id: str):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    return await manager.list_characters(novel_id)


@router.post("/{novel_id}/characters", status_code=201)
async def create_character(novel_id: str, request: CharacterRequest):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    char_id = await manager.create_character(novel_id, **request.model_dump(exclude_none=True))
    return {"id": char_id, "status": "created"}


@router.put("/{novel_id}/characters/{char_id}")
async def update_character(novel_id: str, char_id: int, request: CharacterRequest):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    updated = await manager.update_character(novel_id, char_id, **request.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Character not found")
    return {"status": "updated"}


@router.delete("/{novel_id}/characters/{char_id}")
async def delete_character(novel_id: str, char_id: int):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    deleted = await manager.delete_character(novel_id, char_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Character not found")
    return {"status": "deleted"}


# --- Chapters ---

@router.get("/{novel_id}/chapters")
async def list_chapters(novel_id: str):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    return await manager.list_chapters(novel_id)


@router.get("/{novel_id}/chapters/{chapter_number}", response_model=ChapterResponse)
async def get_chapter(novel_id: str, chapter_number: int):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    chapter = await manager.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter


@router.put("/{novel_id}/chapters/{chapter_number}", response_model=StatusResponse)
async def update_chapter(novel_id: str, chapter_number: int, request: ChapterUpdateRequest):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    updated = await manager.update_chapter(
        novel_id, chapter_number, **request.model_dump(exclude_none=True)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"status": "updated"}


@router.delete("/{novel_id}/chapters/cleanup")
async def cleanup_failed_chapters(novel_id: str, min_words: int = Query(default=100, ge=1)):
    """批量删除生成失败的章节（word_count < min_words）"""
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    deleted_count = await manager.delete_failed_chapters(novel_id, min_words=min_words)
    return {"deleted_count": deleted_count}


@router.delete("/{novel_id}/chapters/{chapter_number}")
async def delete_chapter(novel_id: str, chapter_number: int):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    deleted = await manager.delete_chapter(novel_id, chapter_number)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"status": "deleted"}


# --- Chapter AI Rewrite ---

class RewriteRequest(BaseModel):
    full_content: str
    selected_text: str = Field(..., min_length=1)
    selection_start: int
    selection_end: int
    instruction: str = Field(..., min_length=1)


@router.post("/{novel_id}/chapters/{chapter_number}/rewrite")
async def rewrite_chapter_segment(novel_id: str, chapter_number: int, request: RewriteRequest):
    """对章节中选中的文本片段进行 AI 改写。"""
    manager = get_novel_manager()
    chapter = await manager.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    from src.api.services.novel_context_service import NovelContextBuilder
    from src.core.database import get_db_session
    from src.core.llm.chapter_rewriter import rewrite_chapter_segment as do_rewrite

    async with get_db_session() as session:
        ctx = await NovelContextBuilder().build_rewrite_context(
            session, novel_id, chapter_number
        )
    context = {
        "world_setting": ctx.world_setting,
        "chapter_outline": ctx.chapter_outline,
        "prev_chapter_summary": ctx.prev_chapter_summary,
        "next_chapter_summary": ctx.next_chapter_summary,
        "characters": ctx.characters,
        "story_bible": ctx.story_bible,
        "writing_style": ctx.writing_style,
    }

    try:
        rewritten = await do_rewrite(
            novel_id=novel_id,
            chapter_number=chapter_number,
            full_content=request.full_content,
            selected_text=request.selected_text,
            instruction=request.instruction,
            context=context,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="AI rewrite timed out")
    except Exception as e:
        logger.error("rewrite_chapter_segment_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Rewrite failed")

    return {"rewritten_text": rewritten, "original_text": request.selected_text}


# --- Chapter Version Management ---

class CreateVersionRequest(BaseModel):
    content: str
    source: Literal["manual", "ai_rewrite", "rollback"] = "manual"
    rewrite_instruction: str | None = None


@router.get("/{novel_id}/chapters/{chapter_number}/versions")
async def list_chapter_versions(novel_id: str, chapter_number: int):
    """返回章节版本列表（不含 content）。"""
    manager = get_novel_manager()
    chapter = await manager.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return await manager.list_chapter_versions(novel_id, chapter_number)


@router.get("/{novel_id}/chapters/{chapter_number}/versions/compare")
async def compare_chapter_versions(
    novel_id: str, chapter_number: int, v1: int, v2: int
):
    """对比两个版本的内容差异。"""
    manager = get_novel_manager()
    result = await manager.compare_chapter_versions(novel_id, chapter_number, v1, v2)
    if result is None:
        raise HTTPException(status_code=404, detail="One or both versions not found")
    return result


@router.get("/{novel_id}/chapters/{chapter_number}/versions/{version_number}")
async def get_chapter_version(novel_id: str, chapter_number: int, version_number: int):
    """返回单个版本完整内容。"""
    manager = get_novel_manager()
    chapter = await manager.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    version = await manager.get_chapter_version(novel_id, chapter_number, version_number)
    if not version:
        raise HTTPException(status_code=404, detail="Version not found")
    return version


@router.post("/{novel_id}/chapters/{chapter_number}/versions", status_code=201)
async def create_chapter_version(novel_id: str, chapter_number: int, request: CreateVersionRequest):
    """手动创建章节版本快照。"""
    manager = get_novel_manager()
    chapter = await manager.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    version_number = await manager.create_chapter_version(
        novel_id=novel_id,
        chapter_number=chapter_number,
        content=request.content,
        source=request.source,
        rewrite_instruction=request.rewrite_instruction,
    )
    return {"version_number": version_number, "status": "created"}


@router.post("/{novel_id}/chapters/{chapter_number}/versions/{version_number}/rollback")
async def rollback_chapter_version(novel_id: str, chapter_number: int, version_number: int):
    """回滚到指定版本。"""
    manager = get_novel_manager()
    chapter = await manager.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    new_version = await manager.rollback_chapter_version(novel_id, chapter_number, version_number)
    if new_version is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"status": "rolled_back", "new_version_number": new_version}


@router.post("/{novel_id}/chapters/{chapter_number}/versions/{version_number}/activate")
async def activate_chapter_version(novel_id: str, chapter_number: int, version_number: int):
    """将指定版本设为活跃版本（更新章节正文为该版本内容）。"""
    manager = get_novel_manager()
    result = await manager.activate_chapter_version(novel_id, chapter_number, version_number)
    if result is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"status": "activated", "version_number": version_number}


@router.post("/{novel_id}/fix-volume-numbers")
async def fix_volume_numbers(novel_id: str):
    """根据卷的章节范围为已有章节补充 volume_number。"""
    manager = get_novel_manager()
    fixed_count = await manager.fix_volume_numbers(novel_id)
    return {"status": "fixed", "chapters_updated": fixed_count}


# --- Blueprint API ---


class BlueprintUpdateRequest(BaseModel):
    chapter_type: str | None = None
    plot_goal: str | None = None
    hook_design: str | None = None
    foreshadow_actions: list[dict] | None = None
    cliffhanger: str | None = None
    pacing_target: str | None = None
    key_characters: list[str] | None = None
    word_target: int | None = None


@router.get("/{novel_id}/chapters/{chapter_number}/blueprint")
async def get_blueprint(novel_id: str, chapter_number: int):
    """获取章节蓝图"""
    from src.api.services.blueprint_service import BlueprintService

    service = BlueprintService()
    blueprint = await service.get_blueprint(novel_id, chapter_number)
    if not blueprint:
        raise HTTPException(status_code=404, detail="该章节暂无蓝图")
    return blueprint


@router.put("/{novel_id}/chapters/{chapter_number}/blueprint")
async def update_blueprint(
    novel_id: str, chapter_number: int, request: BlueprintUpdateRequest
):
    """用户手动编辑蓝图"""
    from src.api.services.blueprint_service import BlueprintService

    service = BlueprintService()
    updates = request.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="无更新字段")
    result = await service.update_blueprint(novel_id, chapter_number, updates)
    return result


@router.post(
    "/{novel_id}/chapters/{chapter_number}/blueprint/generate",
    status_code=201,
)
async def generate_blueprint(novel_id: str, chapter_number: int):
    """触发 LLM 生成蓝图（不触发章节生成）"""
    from sqlalchemy import select

    from src.api.models.db_models import Outline
    from src.api.services.blueprint_service import BlueprintService
    from src.core.database import get_db_session

    async with get_db_session() as session:
        stmt = select(Outline).where(
            Outline.novel_id == novel_id,
            Outline.level == "chapter",
            Outline.chapter_number == chapter_number,
        )
        result = await session.execute(stmt)
        outline = result.scalar_one_or_none()

    chapter_outline = (
        outline.content
        if outline
        else {"chapter": chapter_number, "title": f"第{chapter_number}章"}
    )

    service = BlueprintService()
    blueprint = await service.generate_blueprint(
        novel_id, chapter_number, chapter_outline
    )
    return blueprint


# --- Targeted Rewrite API ---


class TargetedRewriteRequest(BaseModel):
    rewrite_type: str = Field(..., description="改写类型")
    instruction: str = Field(default="", description="额外改写指令")
    auto_actions: bool = Field(default=False, description="是否自动执行所有改写动作")


@router.post("/{novel_id}/chapters/{chapter_number}/targeted-rewrite")
async def targeted_rewrite_chapter(
    novel_id: str, chapter_number: int, request: TargetedRewriteRequest
):
    """定向改写章节"""
    from src.api.services.novel_context_service import NovelContextBuilder
    from src.core.database import get_db_session
    from src.core.llm.chapter_rewriter import (
        batch_targeted_rewrite,
        targeted_rewrite,
    )

    manager = get_novel_manager()
    chapter = await manager.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    if not chapter.get("content"):
        raise HTTPException(status_code=400, detail="章节无内容，无法改写")

    full_content = chapter["content"]

    async with get_db_session() as session:
        ctx = await NovelContextBuilder().build_rewrite_context(
            session, novel_id, chapter_number
        )
    context = {
        "world_setting": ctx.world_setting,
        "chapter_outline": ctx.chapter_outline,
        "prev_chapter_summary": ctx.prev_chapter_summary,
        "next_chapter_summary": ctx.next_chapter_summary,
        "characters": ctx.characters,
        "story_bible": ctx.story_bible,
        "writing_style": ctx.writing_style,
    }

    try:
        if request.auto_actions:
            # 从 blueprint 读取 rewrite_actions，调用 batch_targeted_rewrite
            from src.api.services.blueprint_service import BlueprintService

            bp_service = BlueprintService()
            bp = await bp_service.get_blueprint(novel_id, chapter_number)
            actions = (bp or {}).get("rewrite_actions", [])
            if not actions:
                raise HTTPException(
                    status_code=400, detail="蓝图中无改写动作，请先生成质量评估"
                )
            new_content = await batch_targeted_rewrite(
                novel_id=novel_id,
                chapter_number=chapter_number,
                full_content=full_content,
                actions=actions,
                context=context,
            )
        else:
            new_content = await targeted_rewrite(
                novel_id=novel_id,
                chapter_number=chapter_number,
                full_content=full_content,
                rewrite_type=request.rewrite_type,
                instruction=request.instruction,
                context=context,
            )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="AI rewrite timed out")
    except Exception as e:
        logger.error("targeted_rewrite_failed", error=str(e))
        raise HTTPException(status_code=500, detail="Targeted rewrite failed")

    # 创建新 ChapterVersion
    new_version = await manager.create_chapter_version(
        novel_id=novel_id,
        chapter_number=chapter_number,
        content=new_content,
        source="ai_rewrite",
        rewrite_instruction=request.rewrite_type,
        is_active=True,
    )

    return {
        "new_version_number": new_version,
        "word_count": len(new_content),
        "rewrite_type": request.rewrite_type,
    }


# --- Auto Improve API ---


class AutoImproveRequest(BaseModel):
    max_iterations: int = Field(default=3, ge=1, le=5)
    target_score: float = Field(default=0.6, ge=0.3, le=0.9)
    dimensions: list[str] | None = None


@router.post("/{novel_id}/chapters/{chapter_number}/auto-improve")
async def auto_improve_chapter(
    novel_id: str, chapter_number: int, request: AutoImproveRequest
):
    """自动改善闭环"""
    from src.api.services.rewrite_loop_service import RewriteLoopService

    manager = get_novel_manager()
    chapter = await manager.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    if not chapter.get("content"):
        raise HTTPException(status_code=400, detail="章节无内容，无法改善")

    service = RewriteLoopService()
    try:
        result = await service.auto_improve_chapter(
            novel_id=novel_id,
            chapter_number=chapter_number,
            max_iterations=request.max_iterations,
            target_score=request.target_score,
            dimensions=request.dimensions,
        )
    except Exception as e:
        logger.error(
            "auto_improve_failed",
            novel_id=novel_id,
            chapter_number=chapter_number,
            error=str(e),
        )
        raise HTTPException(
            status_code=500, detail=f"Auto improve failed: {str(e)}"
        )

    return result
