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
from src.api.services.content.chapter_service import get_chapter_service
from src.api.services.content.novel_manager import get_novel_manager
from src.api.services.creative_control.artifact_adapters import (
    ArtifactAdapterRegistry,
)
from src.api.services.creative_control.artifact_write_service import (
    CreativeArtifactWriteService,
)
from src.api.services.creative_control.generation_dispatch import (
    CreativeGenerationDispatcher,
)
from src.core.auth_models import User
from src.core.creative_control.artifact_version_store import ArtifactVersionStore
from src.core.creative_control.control_service import CreativeControlService
from src.core.creative_control.impact_analyzer import ImpactAnalyzer
from src.core.creative_control.operation_log import OperationLogService
from src.core.creative_control.scope_planner import (
    GenerationScopeIntent,
    GenerationScopePlanner,
    ScopePlan,
)
from src.core.exceptions import (
    ArtifactBusyError,
    ArtifactConflictError,
    ArtifactLockedError,
    StaleChapterVersionError,
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
    adapters = ArtifactAdapterRegistry()
    return (
        CreativeControlService(),
        ArtifactVersionStore(restore_callback=adapters.save),
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
    adapters = ArtifactAdapterRegistry()
    summaries: list[dict[str, Any]] = []
    for stage in CREATIVE_STAGES:
        stage_artifacts: list[dict[str, Any]] = []
        try:
            artifacts = await adapters.list_artifacts(
                novel_id, stage.artifact_type
            )
            for artifact in artifacts:
                ctrl = await control_service.get_or_create(
                    novel_id,
                    stage.artifact_type,
                    artifact["artifact_id"],
                    stage=stage.number,
                )
                stage_artifacts.append({**artifact, "control": ctrl})
        except Exception:  # noqa: BLE001 - 阶段聚合不因单产物失败中断
            stage_artifacts = []
        summaries.append({
            "number": stage.number,
            "name": stage.name,
            "artifact_type": stage.artifact_type,
            "artifacts": stage_artifacts,
            "control": (
                stage_artifacts[0]["control"] if stage_artifacts else None
            ),
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
    adapters = ArtifactAdapterRegistry()
    control = await control_service.get_or_create(
        novel_id, artifact_type, artifact_id
    )
    try:
        content = await adapters.load(novel_id, artifact_type, artifact_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    versions: list[dict] = []
    active_version_number: int | None = None
    if artifact_type in ("world", "character", "master_outline", "volume_outline", "blueprint"):
        versions = await version_store.list_versions(novel_id, artifact_type, artifact_id)
    elif artifact_type in ("chapter", "chapter_version", "quality", "final"):
        versions = await get_chapter_service().list_chapter_versions(
            novel_id, int(artifact_id)
        )
        active = next((item for item in versions if item.get("is_active")), None)
        active_version_number = active["version_number"] if active else None
    return {
        "control": control,
        "content": content,
        "versions": versions,
        "active_version_number": active_version_number,
    }


@router.put("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}")
async def edit_artifact(
    novel_id: str, artifact_type: str, artifact_id: str,
    request: EditArtifactRequest, current_user: User = Depends(get_current_user),
):
    """人工编辑产物（带乐观锁）。改正文级产物需同时 expected_active_version。"""
    await verify_novel_owner(novel_id, current_user)
    try:
        result = await CreativeArtifactWriteService().edit_artifact(
            novel_id=novel_id,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            content=request.content,
            expected_control_version=request.expected_version,
            expected_active_version=request.expected_active_version,
            operator_id=current_user.id,
        )
    except (ArtifactConflictError, ArtifactLockedError, ArtifactBusyError) as exc:
        code = {
            ArtifactConflictError: "stale_version",
            ArtifactLockedError: "locked",
            ArtifactBusyError: "busy",
        }[type(exc)]
        raise _conflict_response(exc, code, "产物版本已变化或被锁定，请刷新后重试") from exc
    except StaleChapterVersionError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stale_chapter_version",
                "message": "章节活跃版本已变化，请刷新后重试",
                "expected_version": exc.expected,
                "current_version": exc.actual,
            },
        ) from exc
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "status": "edited",
        "version": result.control_version,
        "artifact_version": result.artifact_version,
    }


# ----------------------------------------------------------- lock/unlock/approve


@router.post("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}/lock")
async def lock_artifact(
    novel_id: str, artifact_type: str, artifact_id: str,
    request: LockRequest, current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    control_service, _, _, _, _ = _services()
    try:
        new_v = await control_service.lock(
            novel_id, artifact_type, artifact_id,
            expected_version=request.expected_version, operator_id=current_user.id,
        )
    except ArtifactConflictError as exc:
        raise _conflict_response(exc, "stale_version", "产物版本已变化，请刷新后重试") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail={"code": "illegal_state", "message": str(exc)}) from exc
    return {"status": "locked", "version": new_v}


@router.post("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}/unlock")
async def unlock_artifact(
    novel_id: str, artifact_type: str, artifact_id: str,
    request: LockRequest, current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    control_service, _, _, _, _ = _services()
    try:
        new_v = await control_service.unlock(
            novel_id, artifact_type, artifact_id,
            expected_version=request.expected_version, operator_id=current_user.id,
        )
    except ArtifactConflictError as exc:
        raise _conflict_response(exc, "stale_version", "产物版本已变化，请刷新后重试") from exc
    return {"status": "unlocked", "version": new_v}


@router.post("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}/approve")
async def approve_artifact(
    novel_id: str, artifact_type: str, artifact_id: str,
    request: LockRequest, current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    control_service, _, _, _, _ = _services()
    try:
        new_v = await control_service.approve(
            novel_id, artifact_type, artifact_id,
            expected_version=request.expected_version, operator_id=current_user.id,
        )
    except ArtifactConflictError as exc:
        raise _conflict_response(exc, "stale_version", "产物版本已变化，请刷新后重试") from exc
    return {"status": "approved", "version": new_v}


# ----------------------------------------------------------- 重生成 + 影响范围


@router.post("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}/regenerate")
async def regenerate_artifact(
    novel_id: str, artifact_type: str, artifact_id: str,
    request: RegenerateRequest, current_user: User = Depends(get_current_user),
):
    """重新生成当前阶段产物。锁定产物需 force=True。"""
    await verify_novel_owner(novel_id, current_user)
    if artifact_type in {"chapter", "chapter_version", "final"}:
        try:
            chapter_number = int(artifact_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="章节产物 ID 必须为章号") from exc
        plan = ScopePlan(
            endpoint="generate-chapters",
            payload={
                "chapter_start": chapter_number,
                "chapter_end": chapter_number,
                "_control_target": {
                    "artifact_type": artifact_type,
                    "artifact_id": artifact_id,
                    "expected_version": request.expected_version,
                    "force": request.force,
                },
            },
            target_chapters=[chapter_number],
        )
    elif artifact_type in {"blueprint", "quality"}:
        try:
            chapter_number = int(artifact_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="章节产物 ID 必须为章号") from exc
        endpoint = "blueprint/generate" if artifact_type == "blueprint" else "auto-improve"
        plan = ScopePlan(
            endpoint=endpoint,
            payload={
                "chapter_number": chapter_number,
                "issue_ids": (request.scope or {}).get("issue_ids", []),
                "_control_target": {
                    "artifact_type": artifact_type,
                    "artifact_id": artifact_id,
                    "expected_version": request.expected_version,
                    "force": request.force,
                },
            },
            target_chapters=[chapter_number],
        )
    elif artifact_type == "volume_outline":
        try:
            volume_number = int(artifact_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="卷纲产物 ID 必须为卷号") from exc
        plan = ScopePlan(
            endpoint="generate-volume-outline",
            payload={
                "volume_number": volume_number,
                "_control_target": {
                    "artifact_type": artifact_type,
                    "artifact_id": artifact_id,
                    "expected_version": request.expected_version,
                    "force": request.force,
                },
            },
        )
    else:
        raise HTTPException(
            status_code=422,
            detail=f"当前产物类型尚无可执行的重生成任务: {artifact_type}",
        )

    novel = await get_novel_manager().get_novel(novel_id)
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    try:
        dispatched = await CreativeGenerationDispatcher().dispatch_scope(
            novel, current_user.id, plan
        )
    except (ArtifactConflictError, ArtifactLockedError, ArtifactBusyError) as exc:
        code = {
            ArtifactConflictError: "stale_version",
            ArtifactLockedError: "locked",
            ArtifactBusyError: "busy",
        }[type(exc)]
        raise _conflict_response(
            exc, code, "产物版本已变化或被锁定，请刷新后重试"
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "status": "generating",
        "version": request.expected_version + 1,
        "task_id": dispatched.task_id,
        "task_ids": getattr(dispatched, "task_ids", [dispatched.task_id]),
        "task_type": dispatched.task_type,
    }


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
    control_service, _, _, _, _ = _services()
    try:
        result = await control_service.mark_stale(
            novel_id,
            artifact_type,
            artifact_id,
            expected_version=request.expected_version,
            reason=request.reason or "manual mark stale",
        )
    except ArtifactConflictError as exc:
        raise _conflict_response(
            exc, "stale_version", "产物版本已变化，请刷新后重试"
        ) from exc
    return result


# ----------------------------------------------------------- 版本历史/比较/回退


@router.get("/{novel_id}/creative-control/artifacts/{artifact_type}/{artifact_id}/versions")
async def list_versions(
    novel_id: str, artifact_type: str, artifact_id: str,
    current_user: User = Depends(get_current_user),
):
    await verify_novel_owner(novel_id, current_user)
    if artifact_type in {"chapter", "chapter_version", "quality", "final"}:
        try:
            return await get_chapter_service().list_chapter_versions(
                novel_id, int(artifact_id)
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
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
    try:
        result = await CreativeArtifactWriteService().rollback_artifact(
            novel_id=novel_id,
            artifact_type=artifact_type,
            artifact_id=artifact_id,
            target_version=version_number,
            expected_control_version=request.expected_version,
            expected_active_version=request.expected_active_version,
            operator_id=current_user.id,
        )
    except (ArtifactConflictError, ArtifactLockedError, ArtifactBusyError) as exc:
        code = {
            ArtifactConflictError: "stale_version",
            ArtifactLockedError: "locked",
            ArtifactBusyError: "busy",
        }[type(exc)]
        raise _conflict_response(exc, code, "产物版本已变化或被锁定，请刷新后重试") from exc
    except StaleChapterVersionError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "stale_chapter_version",
                "message": "章节活跃版本已变化，请刷新后重试",
                "expected_version": exc.expected,
                "current_version": exc.actual,
            },
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "status": "rolled_back",
        "version": result.control_version,
        "artifact_version": result.artifact_version,
    }


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


@router.post("/{novel_id}/creative-control/generate-scope", status_code=202)
async def plan_generate_scope(
    novel_id: str, request: GenerateScopeRequest,
    current_user: User = Depends(get_current_user),
):
    """规划生成范围并立即投递持久化任务。"""
    await verify_novel_owner(novel_id, current_user)
    *_, planner = _services()
    intent = _to_intent(novel_id, request)
    plan = await planner.plan(intent)
    novel = await get_novel_manager().get_novel(novel_id)
    if novel is None:
        raise HTTPException(status_code=404, detail="Novel not found")
    try:
        dispatched = await CreativeGenerationDispatcher().dispatch_scope(
            novel, current_user.id, plan
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "task_id": dispatched.task_id,
        "task_ids": getattr(dispatched, "task_ids", [dispatched.task_id]),
        "task_type": dispatched.task_type,
        "target_chapters": dispatched.target_chapters,
        "skipped_locked": dispatched.skipped_locked,
        "skipped_confirmed": dispatched.skipped_confirmed,
        "accepted": getattr(dispatched, "accepted", []),
        "already_generating": getattr(dispatched, "already_generating", []),
        "failed_to_enqueue": getattr(dispatched, "failed_to_enqueue", []),
    }


def _to_intent(novel_id: str, request: GenerateScopeRequest) -> GenerationScopeIntent:
    return GenerationScopeIntent(
        novel_id=novel_id,
        mode=request.mode,
        chapter_start=request.chapter_start,
        chapter_end=request.chapter_end,
        volume_number=request.volume_number,
        chapter_number=request.chapter_number,
        chapter_numbers=request.chapter_numbers,
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
