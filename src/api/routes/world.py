"""世界观/力量体系管理 API 路由"""

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.services.novel_manager import get_novel_manager
from src.api.services.world_service import get_world_service
from src.core.auth_models import User
from src.core.security.auth import get_current_user
from src.api.owner_guard import verify_novel_owner

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["world"])


class WorldSettingRequest(BaseModel):
    background: str | None = None
    geography: str | None = None
    culture: str | None = None
    rules: str | None = None
    extra: dict | None = None


class PowerSystemRequest(BaseModel):
    name: str
    description: str | None = None
    levels: list[dict] = []


async def _verify_novel_exists(novel_id: str) -> None:
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")


@router.get("/{novel_id}/world")
async def get_world_setting(
    novel_id: str, current_user: User = Depends(get_current_user)
):
    await verify_novel_owner(novel_id, current_user)
    service = get_world_service()
    ws = await service.get_world_setting(novel_id)
    if not ws:
        return {"novel_id": novel_id, "background": None, "geography": None,
                "culture": None, "rules": None, "extra": None}
    return ws


@router.put("/{novel_id}/world")
async def update_world_setting(
    novel_id: str, request: WorldSettingRequest,
    current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    service = get_world_service()
    await service.upsert_world_setting(novel_id, **request.model_dump(exclude_none=True))
    return {"status": "updated"}


@router.get("/{novel_id}/power-systems")
async def list_power_systems(
    novel_id: str, current_user: User = Depends(get_current_user)
):
    await verify_novel_owner(novel_id, current_user)
    service = get_world_service()
    return await service.list_power_systems(novel_id)


@router.post("/{novel_id}/power-systems", status_code=201)
async def create_power_system(
    novel_id: str, request: PowerSystemRequest,
    current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    service = get_world_service()
    ps_id = await service.create_power_system(
        novel_id, name=request.name,
        description=request.description, levels=request.levels
    )
    return {"id": ps_id, "status": "created"}


@router.put("/{novel_id}/power-systems/{ps_id}")
async def update_power_system(
    novel_id: str, ps_id: int, request: PowerSystemRequest,
    current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    service = get_world_service()
    updated = await service.update_power_system(
        novel_id, ps_id, name=request.name,
        description=request.description, levels=request.levels
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Power system not found")
    return {"status": "updated"}


@router.delete("/{novel_id}/power-systems/{ps_id}")
async def delete_power_system(
    novel_id: str, ps_id: int,
    current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    service = get_world_service()
    deleted = await service.delete_power_system(novel_id, ps_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Power system not found")
    return {"status": "deleted"}

