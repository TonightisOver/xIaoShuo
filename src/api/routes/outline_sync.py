"""大纲同步 API 路由"""

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.services.outline_sync_service import get_outline_sync_service
from src.core.auth_models import User
from src.core.security.auth import get_current_user
from src.api.owner_guard import verify_novel_owner

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["outline-sync"])


class AnalyzeRequest(BaseModel):
    level: str = Field(..., pattern="^(master|volume|chapter)$")
    volume_number: int | None = None
    chapter_number: int | None = None
    old_content: dict = Field(default_factory=dict)
    new_content: dict = Field(default_factory=dict)


class ReverseRequest(BaseModel):
    chapter_number: int


class BatchRequest(BaseModel):
    ids: list[int]
    action: str = Field(..., pattern="^(accept|reject)$")


@router.post("/{novel_id}/outlines/sync/analyze")
async def analyze_impact(novel_id: str, req: AnalyzeRequest, current_user: User = Depends(get_current_user)):
    await verify_novel_owner(novel_id, current_user)
    service = get_outline_sync_service()
    suggestions = await service.analyze_impact(
        novel_id=novel_id,
        level=req.level,
        volume_number=req.volume_number,
        chapter_number=req.chapter_number,
        old_content=req.old_content,
        new_content=req.new_content,
    )
    return {"suggestions": suggestions, "count": len(suggestions)}


@router.get("/{novel_id}/outlines/sync/suggestions")
async def list_suggestions(
    novel_id: str,
    current_user: User = Depends(get_current_user),
    status: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    await verify_novel_owner(novel_id, current_user)
    service = get_outline_sync_service()
    suggestions = await service.get_suggestions(
        novel_id, status=status, limit=limit, offset=offset
    )
    return {"suggestions": suggestions, "count": len(suggestions)}


@router.put("/{novel_id}/outlines/sync/suggestions/{suggestion_id}/accept")
async def accept_suggestion(novel_id: str, suggestion_id: int, current_user: User = Depends(get_current_user)):
    await verify_novel_owner(novel_id, current_user)
    service = get_outline_sync_service()
    ok = await service.accept_suggestion(suggestion_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Suggestion not found or not pending",
        )
    return {"status": "accepted"}


@router.put("/{novel_id}/outlines/sync/suggestions/{suggestion_id}/reject")
async def reject_suggestion(novel_id: str, suggestion_id: int, current_user: User = Depends(get_current_user)):
    await verify_novel_owner(novel_id, current_user)
    service = get_outline_sync_service()
    ok = await service.reject_suggestion(suggestion_id)
    if not ok:
        raise HTTPException(
            status_code=404,
            detail="Suggestion not found or not pending",
        )
    return {"status": "rejected"}


@router.post("/{novel_id}/outlines/sync/suggestions/batch")
async def batch_action(novel_id: str, req: BatchRequest, current_user: User = Depends(get_current_user)):
    await verify_novel_owner(novel_id, current_user)
    service = get_outline_sync_service()
    count = await service.batch_action(req.ids, req.action)
    return {"processed": count, "total": len(req.ids)}


@router.post("/{novel_id}/outlines/sync/reverse")
async def reverse_sync(novel_id: str, req: ReverseRequest, current_user: User = Depends(get_current_user)):
    await verify_novel_owner(novel_id, current_user)
    service = get_outline_sync_service()
    result = await service.detect_deviation(novel_id, req.chapter_number)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/{novel_id}/outlines/sync/status")
async def sync_status(novel_id: str, current_user: User = Depends(get_current_user)):
    await verify_novel_owner(novel_id, current_user)
    service = get_outline_sync_service()
    chapters = await service.get_sync_status(novel_id)
    return {"chapters": chapters}
