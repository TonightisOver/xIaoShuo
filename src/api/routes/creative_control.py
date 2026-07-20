"""Creative Control API 路由 —— 阶段化创作过程控制台后端。

所有写操作携带 expected_version 做乐观锁，冲突映射 HTTP 409。
锁定内容不被覆盖，重生成锁定产物需 force=True。
设计依据：docs/superpowers/specs/2026-07-21-creative-control-design.md
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query

from src.api.models.creative_control import (
    EditArtifactRequest,
    GenerateScopeRequest,
    LockRequest,
    RegenerateRequest,
    SetModeRequest,
    SetStatusRequest,
)
from src.api.owner_guard import verify_novel_owner
from src.api.services.content.novel_manager import get_novel_manager
from src.core.auth_models import User
from src.core.creative_control.artifact_version_store import ArtifactVersionStore
from src.core.creative_control.control_service import CreativeControlService
from src.core.creative_control.impact_analyzer import ImpactAnalyzer
from src.core.creative_control.operation_log import OperationLogService
from src.core.creative_control.scope_planner import (
    GenerationScopeIntent,
    GenerationScopePlanner,
)
from src.core.exceptions import (
    ArtifactBusyError,
    ArtifactConflictError,
    ArtifactLockedError,
)
from src.core.security.auth import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["creative-control"])


# ----------------------------------------------------------- 异常映射辅助


def _conflict_response(exc: Exception, code: str, message: str) -> HTTPException:
    """把 ArtifactConflict/Locked/Busy 映射为 409。"""
    detail: dict[str, Any] = {"code": code, "message": message}
    if isinstance(exc, ArtifactConflictError):
        detail["current_version"] = exc.current_version
        detail["expected_version"] = exc.expected_version
    elif isinstance(exc, ArtifactLockedError | ArtifactBusyError):
        detail["artifact_type"] = exc.artifact_type
        detail["artifact_id"] = exc.artifact_id
    return HTTPException(status_code=409, detail=detail)


def _services():
    return (
        CreativeControlService(),
        ArtifactVersionStore(),
        ImpactAnalyzer(),
        OperationLogService(),
        GenerationScopePlanner(),
    )


# ----------------------------------------------------------- 阶段导航


@router.get("/{novel_id}/creative-control/stage")
async def get_stage(novel_id: str, current_user: User = Depends(get_current_user)):
    """返回 10 阶段导航 + 各产物 control 摘要 + 当前创作模式。"""
    await verify_novel_owner(novel_id, current_user)
    from src.core.creative_control.contracts import CREATIVE_STAGES

    novel = await get_novel_manager().get_novel(novel_id)
    control_service = CreativeControlService()
    summaries: list[dict[str, Any]] = []
    for stage in CREATIVE_STAGES:
        # 每阶段产物 control（best-effort，无行则跳过）
        try:
            ctrl = await control_service.get_or_create(
                novel_id, stage.artifact_type, novel_id, stage=stage.number
            )
        except Exception:  # noqa: BLE001 - 阶段聚合不因单产物失败中断
            ctrl = None
        summaries.append({
            "number": stage.number,
            "name": stage.name,
            "artifact_type": stage.artifact_type,
            "control": ctrl,
        })
    return {
        "creation_mode": (novel or {}).get("creation_mode", "auto"),
        "creative_stage": (novel or {}).get("creative_stage", 1),
        "stages": summaries,
    }


# ----------------------------------------------------------- 产物查看/编辑


@router.get("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}")
async def get_artifact(
    novel_id: str, artifact_type: str, artifact_id: str,
    current_user: User = Depends(get_current_user),
):
    """查看产物 + control 元数据。"""
    await verify_novel_owner(novel_id, current_user)
    control_service, version_store, *_ = _services()
    control = await control_service.get_or_create(
        novel_id, artifact_type, artifact_id
    )
    versions: list[dict] = []
    if artifact_type in ("world", "character", "master_outline", "volume_outline", "blueprint"):
        versions = await version_store.list_versions(novel_id, artifact_type, artifact_id)
    return {"control": control, "versions": versions}


@router.put("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}")
async def edit_artifact(
    novel_id: str, artifact_type: str, artifact_id: str,
    request: EditArtifactRequest, current_user: User = Depends(get_current_user),
):
    """人工编辑产物（带乐观锁）。改正文级产物需同时 expected_active_version。"""
    control_service, version_store, _, op_log, _ = _services()
    await verify_novel_owner(novel_id, current_user)
    try:
        await control_service.assert_writable(
            novel_id, artifact_type, artifact_id, request.expected_version
        )
    except (ArtifactConflictError, ArtifactLockedError, ArtifactBusyError) as exc:
        code = {
            ArtifactConflictError: "stale_version",
            ArtifactLockedError: "locked",
            ArtifactBusyError: "busy",
        }[type(exc)]
        raise _conflict_response(exc, code, "产物版本已变化或被锁定，请刷新后重试") from exc

    # 保存版本快照（非正文产物）
    if artifact_type in ("world", "character", "master_outline", "volume_outline", "blueprint"):
        new_vn = await version_store.save_version(
            novel_id, artifact_type, artifact_id,
            content_snapshot=request.content, source="manual",
            operator_id=current_user.id,
        )
    else:
        new_vn = request.expected_version + 1
    # 状态 -> edited
    await control_service.set_status(
        novel_id, artifact_type, artifact_id,
        expected_version=request.expected_version, to_status="edited",
        action="edit", operator_id=current_user.id,
    )
    await op_log.record(
        novel_id=novel_id, artifact_type=artifact_type, artifact_id=artifact_id,
        action="edit", from_version=request.expected_version, to_version=new_vn,
        operator_id=current_user.id,
    )
    return {"status": "edited", "version": new_vn}


# ----------------------------------------------------------- lock/unlock/approve


@router.post("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}/lock")
async def lock_artifact(
    novel_id: str, artifact_type: str, artifact_id: str,
    request: LockRequest, current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    control_service, _, _, op_log, _ = _services()
    try:
        new_v = await control_service.lock(
            novel_id, artifact_type, artifact_id,
            expected_version=request.expected_version, operator_id=current_user.id,
        )
    except ArtifactConflictError as exc:
        raise _conflict_response(exc, "stale_version", "产物版本已变化，请刷新后重试") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "illegal_state", "message": str(exc)}) from exc
    await op_log.record(
        novel_id=novel_id, artifact_type=artifact_type, artifact_id=artifact_id,
        action="lock", from_version=request.expected_version, to_version=new_v,
        operator_id=current_user.id,
    )
    return {"status": "locked", "version": new_v}


@router.post("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}/unlock")
async def unlock_artifact(
    novel_id: str, artifact_type: str, artifact_id: str,
    request: LockRequest, current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    control_service, _, _, op_log, _ = _services()
    try:
        new_v = await control_service.unlock(
            novel_id, artifact_type, artifact_id,
            expected_version=request.expected_version, operator_id=current_user.id,
        )
    except ArtifactConflictError as exc:
        raise _conflict_response(exc, "stale_version", "产物版本已变化，请刷新后重试") from exc
    await op_log.record(
        novel_id=novel_id, artifact_type=artifact_type, artifact_id=artifact_id,
        action="unlock", from_version=request.expected_version, to_version=new_v,
        operator_id=current_user.id,
    )
    return {"status": "unlocked", "version": new_v}


@router.post("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}/approve")
async def approve_artifact(
    novel_id: str, artifact_type: str, artifact_id: str,
    request: LockRequest, current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    control_service, _, _, op_log, _ = _services()
    try:
        new_v = await control_service.approve(
            novel_id, artifact_type, artifact_id,
            expected_version=request.expected_version, operator_id=current_user.id,
        )
    except ArtifactConflictError as exc:
        raise _conflict_response(exc, "stale_version", "产物版本已变化，请刷新后重试") from exc
    await op_log.record(
        novel_id=novel_id, artifact_type=artifact_type, artifact_id=artifact_id,
        action="approve", from_version=request.expected_version, to_version=new_v,
        operator_id=current_user.id,
    )
    return {"status": "approved", "version": new_v}


# ----------------------------------------------------------- 重生成 + 影响范围


@router.post("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}/regenerate")
async def regenerate_artifact(
    novel_id: str, artifact_type: str, artifact_id: str,
    request: RegenerateRequest, current_user: User = Depends(get_current_user),
):
    """重新生成当前阶段产物。锁定产物需 force=True。"""
    await verify_novel_owner(novel_id, current_user)
    control_service, _, _, op_log, _ = _services()
    try:
        await control_service.assert_writable(
            novel_id, artifact_type, artifact_id, request.expected_version,
            force=request.force,
        )
        new_v = await control_service.begin_generating(
            novel_id, artifact_type, artifact_id,
            expected_version=request.expected_version,
            operator_id=current_user.id,
        )
    except (ArtifactConflictError, ArtifactLockedError, ArtifactBusyError) as exc:
        code = {
            ArtifactConflictError: "stale_version",
            ArtifactLockedError: "locked",
            ArtifactBusyError: "busy",
        }[type(exc)]
        raise _conflict_response(exc, code, "产物版本已变化或被锁定，请刷新后重试") from exc
    await op_log.record(
        novel_id=novel_id, artifact_type=artifact_type, artifact_id=artifact_id,
        action="regenerate", from_version=request.expected_version, to_version=new_v,
        operator_id=current_user.id, reason=request.reason,
    )
    # 实际生成由任务系统异步执行（现有 generate-* 端点），此处仅完成控制状态转移
    return {"status": "generating", "version": new_v}


@router.get("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}/impact")
async def get_impact(
    novel_id: str, artifact_type: str, artifact_id: str,
    current_user: User = Depends(get_current_user),
):
    """影响范围预览。"""
    await verify_novel_owner(novel_id, current_user)
    _, _, impact, *_ = _services()
    return await impact.analyze(novel_id, artifact_type, artifact_id)


@router.post("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}/mark-stale")
async def mark_stale(
    novel_id: str, artifact_type: str, artifact_id: str,
    request: SetStatusRequest, current_user: User = Depends(get_current_user),
):
    """仅标记下游过期（保留现有下游内容）。"""
    await verify_novel_owner(novel_id, current_user)
    control_service, _, _, op_log, _ = _services()
    result = await control_service.mark_stale(
        novel_id, artifact_type, artifact_id, reason=request.reason or "manual mark stale"
    )
    await op_log.record(
        novel_id=novel_id, artifact_type=artifact_type, artifact_id=artifact_id,
        action="update_params", operator_id=current_user.id, reason=request.reason,
    )
    return result


# ----------------------------------------------------------- 版本历史/比较/回退


@router.get("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}/versions")
async def list_versions(
    novel_id: str, artifact_type: str, artifact_id: str,
    current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    _, version_store, *_ = _services()
    return await version_store.list_versions(novel_id, artifact_type, artifact_id)


@router.get("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}/versions/compare")
async def compare_versions(
    novel_id: str, artifact_type: str, artifact_id: str,
    a: int = Query(..., ge=1), b: int = Query(..., ge=1),
    current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    _, version_store, *_ = _services()
    try:
        return await version_store.compare_versions(novel_id, artifact_type, artifact_id, a, b)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}/versions/{version_number}/rollback")
async def rollback_version(
    novel_id: str, artifact_type: str, artifact_id: str, version_number: int,
    request: LockRequest, current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    _, version_store, _, op_log, _ = _services()
    try:
        result = await version_store.rollback_to(
            novel_id, artifact_type, artifact_id, version_number,
            operator_id=current_user.id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    await op_log.record(
        novel_id=novel_id, artifact_type=artifact_type, artifact_id=artifact_id,
        action="rollback", to_version=version_number, operator_id=current_user.id,
    )
    return result


# ----------------------------------------------------------- 操作记录


@router.get("/{novel_id}/creative-control/operations")
async def list_operations(
    novel_id: str,
    artifact_type: str | None = Query(None),
    action: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    *_, op_log, _ = _services()
    return await op_log.list(
        novel_id, artifact_type=artifact_type, action=action, limit=limit
    )


# ----------------------------------------------------------- 生成范围


@router.post("/{novel_id}/creative-control/generate-scope/preview")
async def preview_generate_scope(
    novel_id: str, request: GenerateScopeRequest,
    current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    *_, planner = _services()
    intent = _to_intent(novel_id, request)
    preview = await planner.preview(intent)
    return {
        "estimated_chapters": preview.estimated_chapters,
        "estimated_tokens": preview.estimated_tokens,
        "target_chapters": preview.target_chapters,
        "skipped_locked": preview.skipped_locked,
        "skipped_confirmed": preview.skipped_confirmed,
        "impact": preview.impact,
    }


@router.post("/{novel_id}/creative-control/generate-scope")
async def plan_generate_scope(
    novel_id: str, request: GenerateScopeRequest,
    current_user: User = Depends(get_current_user),
):
    """生成范围规划。返回 endpoint + payload + 过滤结果；前端据此调用现有生成端点。"""
    await verify_novel_owner(novel_id, current_user)
    *_, planner = _services()
    intent = _to_intent(novel_id, request)
    plan = await planner.plan(intent)
    return {
        "endpoint": plan.endpoint,
        "payload": plan.payload,
        "target_chapters": plan.target_chapters,
        "skipped_locked": plan.skipped_locked,
        "skipped_confirmed": plan.skipped_confirmed,
    }


def _to_intent(novel_id: str, request: GenerateScopeRequest) -> GenerationScopeIntent:
    return GenerationScopeIntent(
        novel_id=novel_id,
        mode=request.mode,
        chapter_start=request.chapter_start,
        chapter_end=request.chapter_end,
        volume_number=request.volume_number,
        chapter_number=request.chapter_number,
        issue_ids=request.issue_ids,
        skip_confirmed=request.skip_confirmed,
        respect_locked=request.respect_locked,
        words_per_chapter=request.words_per_chapter,
    )


# ----------------------------------------------------------- 创作模式


@router.put("/{novel_id}/creative-control/mode")
async def set_creation_mode(
    novel_id: str, request: SetModeRequest,
    current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    manager = get_novel_manager()
    try:
        await manager.update_novel(novel_id, creation_mode=request.creation_mode)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    _, _, _, op_log, _ = _services()
    await op_log.record(
        novel_id=novel_id, artifact_type="novel", artifact_id=novel_id,
        action="update_params", operator_id=current_user.id,
        reason=f"creation_mode={request.creation_mode}",
    )
    return {"status": "updated", "creation_mode": request.creation_mode}
