"""Volume management API routes"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.models.responses import StatusResponse, VolumeResponse
from src.api.services.novel_manager import get_novel_manager
from src.api.services.volume_service import get_volume_service
from src.core.auth_models import User
from src.core.security.auth import get_current_user
from src.api.owner_guard import verify_novel_owner

router = APIRouter(prefix="/api/v1/projects", tags=["volumes"])


class VolumeUpdateRequest(BaseModel):
    title: str | None = None
    summary: str | None = None


@router.get("/{novel_id}/volumes")
async def list_volumes(novel_id: str, current_user: User = Depends(get_current_user)):
    """获取小说所有卷"""
    await verify_novel_owner(novel_id, current_user)
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    service = get_volume_service()
    return await service.list_volumes(novel_id)


@router.get("/{novel_id}/volumes/{volume_number}", response_model=VolumeResponse)
async def get_volume(novel_id: str, volume_number: int, current_user: User = Depends(get_current_user)):
    """获取单卷详情"""
    await verify_novel_owner(novel_id, current_user)
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    service = get_volume_service()
    vol = await service.get_volume(novel_id, volume_number)
    if not vol:
        raise HTTPException(status_code=404, detail="Volume not found")
    vol["novel_id"] = novel_id
    return vol


@router.put("/{novel_id}/volumes/{volume_number}", response_model=StatusResponse)
async def update_volume(novel_id: str, volume_number: int, request: VolumeUpdateRequest, current_user: User = Depends(get_current_user)):
    """更新卷信息"""
    await verify_novel_owner(novel_id, current_user)
    manager = get_novel_manager()
    novel = await manager.get_novel(novel_id)
    if not novel:
        raise HTTPException(status_code=404, detail="Novel not found")
    service = get_volume_service()
    updated = await service.update_volume(novel_id, volume_number, **request.model_dump(exclude_none=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Volume not found")
    return {"status": "updated"}
