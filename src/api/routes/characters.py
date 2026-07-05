"""角色管理路由"""

import structlog
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.api.services.character_service import get_character_service
from src.api.services.novel_manager import get_novel_manager

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["characters"])


class CharacterRequest(BaseModel):
    name: str
    role: str | None = None
    description: str | None = None
    personality: str | None = None
    abilities: str | None = None
    background_story: str | None = None
    extra: dict | None = None


async def _verify_novel_exists(novel_id: str) -> None:
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")


@router.get("/{novel_id}/characters")
async def list_characters(novel_id: str):
    await _verify_novel_exists(novel_id)
    service = get_character_service()
    return await service.list_characters(novel_id)


@router.post("/{novel_id}/characters", status_code=201)
async def create_character(novel_id: str, request: CharacterRequest):
    await _verify_novel_exists(novel_id)
    service = get_character_service()
    char_id = await service.create_character(novel_id, **request.model_dump(exclude_none=True))
    return {"id": char_id, "status": "created"}


@router.put("/{novel_id}/characters/{char_id}")
async def update_character(novel_id: str, char_id: int, request: CharacterRequest):
    await _verify_novel_exists(novel_id)
    service = get_character_service()
    updated = await service.update_character(novel_id, char_id, **request.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Character not found")
    return {"status": "updated"}


@router.delete("/{novel_id}/characters/{char_id}")
async def delete_character(novel_id: str, char_id: int):
    await _verify_novel_exists(novel_id)
    service = get_character_service()
    deleted = await service.delete_character(novel_id, char_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Character not found")
    return {"status": "deleted"}

