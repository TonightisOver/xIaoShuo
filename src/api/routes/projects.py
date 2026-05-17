"""小说项目管理 API 路由"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.models.requests import CreateNovelRequest
from src.api.services.novel_generator import generate_novel_background
from src.api.services.novel_manager import get_novel_manager
from src.api.services.task_manager import get_task_manager
from src.core.validation import ValidationError, validate_idea, validate_novel_type

logger = logging.getLogger(__name__)

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

@router.post("", status_code=201)
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


@router.get("")
async def list_projects(
    novel_type: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    manager = get_novel_manager()
    novels, total = await manager.list_novels(novel_type=novel_type, limit=limit, offset=offset)
    return {"novels": novels, "total": total, "limit": limit, "offset": offset}


@router.get("/{novel_id}")
async def get_project(novel_id: str):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    return novel


@router.put("/{novel_id}")
async def update_project(novel_id: str, request: UpdateProjectRequest):
    manager = get_novel_manager()
    updated = await manager.update_novel(novel_id, **request.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Novel not found")
    return {"status": "updated"}


@router.delete("/{novel_id}")
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


# --- Volumes ---

@router.get("/{novel_id}/volumes")
async def list_volumes(novel_id: str):
    manager = get_novel_manager()
    return await manager.list_volumes(novel_id)


@router.get("/{novel_id}/volumes/{volume_number}")
async def get_volume(novel_id: str, volume_number: int):
    manager = get_novel_manager()
    vol = await manager.get_volume(novel_id, volume_number)
    if not vol:
        raise HTTPException(status_code=404, detail="Volume not found")
    return vol


class VolumeUpdateRequest(BaseModel):
    title: str | None = None
    summary: str | None = None


@router.put("/{novel_id}/volumes/{volume_number}")
async def update_volume(novel_id: str, volume_number: int, request: VolumeUpdateRequest):
    manager = get_novel_manager()
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

    vol = await manager.get_volume(novel_id, request.volume_number)
    if not vol:
        raise HTTPException(status_code=404, detail="Volume not found")

    from src.api.services.novel_generator import generate_volume_background

    task_manager = get_task_manager()
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

    from src.api.services.novel_generator import generate_chapters_background

    task_manager = get_task_manager()
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
    return await manager.list_power_systems(novel_id)


@router.post("/{novel_id}/power-systems", status_code=201)
async def create_power_system(novel_id: str, request: PowerSystemRequest):
    manager = get_novel_manager()
    ps_id = await manager.create_power_system(
        novel_id, name=request.name,
        description=request.description, levels=request.levels
    )
    return {"id": ps_id, "status": "created"}


@router.put("/{novel_id}/power-systems/{ps_id}")
async def update_power_system(novel_id: str, ps_id: int, request: PowerSystemRequest):
    manager = get_novel_manager()
    updated = await manager.update_power_system(
        ps_id, name=request.name,
        description=request.description, levels=request.levels
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Power system not found")
    return {"status": "updated"}


@router.delete("/{novel_id}/power-systems/{ps_id}")
async def delete_power_system(novel_id: str, ps_id: int):
    manager = get_novel_manager()
    deleted = await manager.delete_power_system(ps_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Power system not found")
    return {"status": "deleted"}


# --- Characters ---

@router.get("/{novel_id}/characters")
async def list_characters(novel_id: str):
    manager = get_novel_manager()
    return await manager.list_characters(novel_id)


@router.post("/{novel_id}/characters", status_code=201)
async def create_character(novel_id: str, request: CharacterRequest):
    manager = get_novel_manager()
    char_id = await manager.create_character(novel_id, **request.model_dump(exclude_none=True))
    return {"id": char_id, "status": "created"}


@router.put("/{novel_id}/characters/{char_id}")
async def update_character(novel_id: str, char_id: int, request: CharacterRequest):
    manager = get_novel_manager()
    updated = await manager.update_character(char_id, **request.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Character not found")
    return {"status": "updated"}


@router.delete("/{novel_id}/characters/{char_id}")
async def delete_character(novel_id: str, char_id: int):
    manager = get_novel_manager()
    deleted = await manager.delete_character(char_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Character not found")
    return {"status": "deleted"}


# --- Chapters ---

@router.get("/{novel_id}/chapters")
async def list_chapters(novel_id: str):
    manager = get_novel_manager()
    return await manager.list_chapters(novel_id)


@router.get("/{novel_id}/chapters/{chapter_number}")
async def get_chapter(novel_id: str, chapter_number: int):
    manager = get_novel_manager()
    chapter = await manager.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return chapter


@router.put("/{novel_id}/chapters/{chapter_number}")
async def update_chapter(novel_id: str, chapter_number: int, request: ChapterUpdateRequest):
    manager = get_novel_manager()
    updated = await manager.update_chapter(
        novel_id, chapter_number, **request.model_dump(exclude_none=True)
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"status": "updated"}


@router.delete("/{novel_id}/chapters/{chapter_number}")
async def delete_chapter(novel_id: str, chapter_number: int):
    manager = get_novel_manager()
    deleted = await manager.delete_chapter(novel_id, chapter_number)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chapter not found")
    return {"status": "deleted"}
