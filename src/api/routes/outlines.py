"""大纲 API 路由"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.services.novel_manager import get_novel_manager
from src.api.services.outline_service import get_outline_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["outlines"])


class MasterOutlineRequest(BaseModel):
    premise: str | None = None
    main_conflict: str | None = None
    plot_arcs: list[dict] | None = None
    ending: str | None = None
    themes: list[str] | None = None


class VolumeOutlineRequest(BaseModel):
    title: str | None = None
    summary: str | None = None
    goal: str | None = None
    climax: str | None = None
    chapters: list[dict] | None = None


class ChapterOutlineRequest(BaseModel):
    title: str | None = None
    scenes: list[dict] | None = None
    turning_point: str | None = None
    emotional_beat: str | None = None
    word_target: int | None = None


@router.get("/{novel_id}/outlines")
async def get_outline_tree(novel_id: str):
    service = get_outline_service()
    return await service.get_outline_tree(novel_id)


@router.get("/{novel_id}/outlines/master")
async def get_master_outline(novel_id: str):
    service = get_outline_service()
    outline = await service.get_master_outline(novel_id)
    if not outline:
        return {"content": None, "status": "empty"}
    return outline


@router.put("/{novel_id}/outlines/master")
async def update_master_outline(novel_id: str, request: MasterOutlineRequest):
    service = get_outline_service()
    content = request.model_dump(exclude_none=True)
    await service.upsert_master_outline(novel_id, content)
    return {"status": "updated"}


@router.post("/{novel_id}/outlines/generate-volumes")
async def generate_volume_outlines(novel_id: str):
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")

    service = get_outline_service()
    try:
        volumes = await service.generate_volume_outlines(
            novel_id, novel["novel_type"], novel["target_words"]
        )
        return {"volumes": volumes, "count": len(volumes)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{novel_id}/outlines/generate-chapters/{volume_number}")
async def generate_chapter_outlines(novel_id: str, volume_number: int):
    service = get_outline_service()
    try:
        chapters = await service.generate_chapter_outlines(novel_id, volume_number)
        return {"chapters": chapters, "count": len(chapters)}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/{novel_id}/outlines/volume/{volume_number}")
async def update_volume_outline(novel_id: str, volume_number: int, request: VolumeOutlineRequest):
    service = get_outline_service()
    content = request.model_dump(exclude_none=True)
    await service.upsert_volume_outline(novel_id, volume_number, content)
    return {"status": "updated"}


@router.put("/{novel_id}/outlines/chapter/{chapter_number}")
async def update_chapter_outline(novel_id: str, chapter_number: int, request: ChapterOutlineRequest):
    service = get_outline_service()
    content = request.model_dump(exclude_none=True)
    await service.upsert_chapter_outline(novel_id, 0, chapter_number, content)
    return {"status": "updated"}


@router.post("/{novel_id}/outlines/generate-master")
async def generate_master_outline(novel_id: str):
    service = get_outline_service()
    try:
        content = await service.generate_master_from_novel(novel_id)
        return {"status": "generated", "content": content}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{novel_id}/outlines/from-conversation/{conv_id}")
async def generate_master_from_conversation(novel_id: str, conv_id: int):
    service = get_outline_service()
    try:
        content = await service.generate_master_from_conversation(novel_id, conv_id)
        return {"status": "generated", "content": content}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
