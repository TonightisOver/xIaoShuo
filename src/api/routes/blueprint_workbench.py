"""章节蓝图工作台路由 —— 面向作者的独立蓝图工作台后端。

只读聚合（list/options/workspace）+ 批量控制（batch lock/unlock/approve）。
单章编辑保存/确认/锁定/重生成/版本/回退/影响均复用现有 creative-control 通用路由。
设计依据：docs/superpowers/specs/2026-07-22-chapter-blueprint-workbench-design.md
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.owner_guard import verify_novel_owner
from src.api.services.content.blueprint_workbench_service import (
    BlueprintWorkbenchService,
)
from src.core.auth_models import User
from src.core.creative_control.control_service import CreativeControlService
from src.core.exceptions import ArtifactConflictError
from src.core.security.auth import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["blueprint-workbench"])

_BATCH_LIMIT = 50


class BatchControlRequest(BaseModel):
    action: str = Field(..., pattern="^(lock|unlock|approve)$")
    artifact_type: str = "blueprint"
    chapter_numbers: list[int] = Field(..., min_length=1)
    expected_versions: dict[str, int] = Field(default_factory=dict)


@router.get("/{novel_id}/blueprints")
async def list_blueprints(
    novel_id: str,
    current_user: User = Depends(get_current_user),
    volume_number: int | None = Query(None, ge=1),
    status: str | None = Query(None),
    search: str | None = Query(None, max_length=100),
    chapter_start: int | None = Query(None, ge=1),
    chapter_end: int | None = Query(None, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """章节摘要列表（服务端分页 + 筛选 + status_counts）。"""
    await verify_novel_owner(novel_id, current_user)
    service = BlueprintWorkbenchService()
    return await service.list_chapter_summaries(
        novel_id,
        volume_number=volume_number,
        status=status,
        search=search,
        chapter_start=chapter_start,
        chapter_end=chapter_end,
        page=page,
        page_size=page_size,
    )


@router.get("/{novel_id}/blueprints/options")
async def get_options(
    novel_id: str, current_user: User = Depends(get_current_user),
):
    """蓝图字段枚举选项（静态，无 DB）。"""
    await verify_novel_owner(novel_id, current_user)
    return BlueprintWorkbenchService().get_options()


@router.get("/{novel_id}/blueprints/{chapter_number}/workspace")
async def get_workspace_route(
    novel_id: str, chapter_number: int, current_user: User = Depends(get_current_user),
):
    """单章工作台详情聚合。"""
    await verify_novel_owner(novel_id, current_user)
    service = BlueprintWorkbenchService()
    return await service.get_workspace(novel_id, chapter_number)


@router.post("/{novel_id}/creative-control/batch")
async def batch_control(
    novel_id: str, request: BatchControlRequest,
    current_user: User = Depends(get_current_user),
):
    """批量 lock/unlock/approve（首期仅 blueprint）。逐章独立事务，部分失败不整体回滚。"""
    await verify_novel_owner(novel_id, current_user)
    if len(request.chapter_numbers) > _BATCH_LIMIT:
        raise HTTPException(status_code=422, detail=f"单次最多 {_BATCH_LIMIT} 章")
    if request.artifact_type != "blueprint":
        raise HTTPException(status_code=422, detail="首期仅支持 blueprint 类型批量操作")

    control_service = CreativeControlService()
    action_map = {
        "lock": control_service.lock,
        "unlock": control_service.unlock,
        "approve": control_service.approve,
    }
    fn = action_map[request.action]
    results: list[dict[str, Any]] = []
    for ch in request.chapter_numbers:
        expected = request.expected_versions.get(str(ch), 0)
        try:
            new_v = await fn(
                novel_id, "blueprint", str(ch),
                expected_version=expected, operator_id=current_user.id,
            )
            results.append({"chapter_number": ch, "status": "ok", "version": new_v})
        except ArtifactConflictError as exc:
            results.append({
                "chapter_number": ch, "status": "conflict",
                "current_version": exc.current_version,
                "expected_version": exc.expected_version,
            })
        except ValueError as exc:
            results.append({"chapter_number": ch, "status": "skipped", "error": str(exc)})
    return {"action": request.action, "results": results}
