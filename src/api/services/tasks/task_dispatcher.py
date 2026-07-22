"""持久化任务类型白名单与 JSON payload 调度。"""

from enum import StrEnum
from typing import Any

from src.api.models.requests import CreateNovelRequest, LongFormNovelRequest
from src.api.services.tasks.task_manager import get_task_manager


async def _finish_control_target(
    payload: dict[str, Any], *, error: Exception | None = None
) -> None:
    raw_targets = payload.get("control_targets")
    if isinstance(raw_targets, list):
        targets = [target for target in raw_targets if isinstance(target, dict)]
    else:
        legacy_target = payload.get("control_target")
        targets = [legacy_target] if isinstance(legacy_target, dict) else []
    if not targets:
        return
    from src.core.creative_control.control_service import CreativeControlService

    service = CreativeControlService()
    for target in targets:
        kwargs = {
            "novel_id": payload["novel_id"],
            "artifact_type": str(target["artifact_type"]),
            "artifact_id": str(target["artifact_id"]),
            "expected_version": int(target["generating_version"]),
        }
        if error is None:
            await service.complete_generating(
                **kwargs,
                generation_meta={"source": "task", "status": "completed"},
            )
        else:
            await service.fail_generating(**kwargs, reason=str(error))


async def _run_controlled(
    task_id: str, payload: dict[str, Any], operation
) -> None:
    try:
        await operation
    except Exception as exc:
        try:
            await _finish_control_target(payload, error=exc)
        except Exception:
            pass
        raise
    if not (
        isinstance(payload.get("control_target"), dict)
        or isinstance(payload.get("control_targets"), list)
    ):
        return
    task = await get_task_manager().get_task(task_id)
    if task is not None and task.get("status") in {"failed", "cancelled"}:
        await _finish_control_target(
            payload,
            error=RuntimeError(task.get("error") or "generation task failed"),
        )
        return
    await _finish_control_target(payload)


class TaskType(StrEnum):
    NOVEL_GENERATE = "novel.generate"
    NOVEL_FULL_GENERATE = "novel.full_generate"
    NOVEL_LONG_FORM = "novel.long_form"
    NOVEL_VOLUME = "novel.volume"
    NOVEL_CHAPTERS = "novel.chapters"
    NOVEL_BLUEPRINT = "novel.blueprint"
    NOVEL_QUALITY_FIX = "novel.quality_fix"
    NOVEL_VOLUME_OUTLINE = "novel.volume_outline"
    PIPELINE_RESUME = "pipeline.resume"


async def dispatch_task(task: dict[str, Any]) -> None:
    """只执行固定白名单中的任务类型。"""
    task_id = task["task_id"]
    from src.core.creative_control.control_service import bind_generation_task

    bind_generation_task(task_id)
    payload = task.get("task_payload") or {}
    # B1: worker_id 由 PersistentTaskWorker._run_claim 注入 claim dict；离线/直调
    # 场景（无 worker）为 None，长篇路径据此在安全边界复查 lease（None 跳过守卫）。
    worker_id = task.get("worker_id")
    try:
        task_type = TaskType(task["task_type"])
    except (KeyError, ValueError) as exc:
        raise ValueError(
            f"Unsupported task type: {task.get('task_type')!r}"
        ) from exc

    if task_type is TaskType.NOVEL_GENERATE:
        from src.api.services.generation.novel_generator import (
            generate_novel_background,
        )

        request = CreateNovelRequest.model_validate(payload["request"])
        await generate_novel_background(task_id, request)
        return

    if task_type is TaskType.NOVEL_FULL_GENERATE:
        from src.api.services.generation.novel_generator import (
            generate_novel_full_background,
        )

        request = CreateNovelRequest.model_validate(payload["request"])
        await generate_novel_full_background(task_id, request)
        return

    if task_type is TaskType.NOVEL_LONG_FORM:
        from src.api.services.generation.long_form_generation_helpers import (
            generate_long_form_background,
        )

        request = LongFormNovelRequest.model_validate(payload["request"])
        await generate_long_form_background(
            task_id, payload["novel_id"], request, worker_id=worker_id
        )
        return

    if task_type is TaskType.NOVEL_VOLUME:
        from src.api.services.generation.long_form_generation_helpers import (
            generate_volume_background,
        )

        await _run_controlled(
            task_id,
            payload,
            generate_volume_background(
                task_id,
                payload["novel_id"],
                int(payload["volume_number"]),
                worker_id=worker_id,
            ),
        )
        return

    if task_type is TaskType.NOVEL_CHAPTERS:
        from src.api.services.generation.long_form_generation_helpers import (
            generate_chapters_background,
        )

        await _run_controlled(
            task_id,
            payload,
            generate_chapters_background(
                task_id,
                payload["novel_id"],
                int(payload["chapter_start"]),
                int(payload["chapter_end"]),
                worker_id=worker_id,
            ),
        )
        return

    if task_type is TaskType.NOVEL_BLUEPRINT:
        from src.api.services.generation.creative_control_tasks import (
            generate_blueprint_background,
        )

        await _run_controlled(
            task_id,
            payload,
            generate_blueprint_background(
                task_id,
                payload["novel_id"],
                int(payload["chapter_number"]),
                worker_id=worker_id,
            ),
        )
        return

    if task_type is TaskType.NOVEL_QUALITY_FIX:
        from src.api.services.generation.creative_control_tasks import (
            fix_quality_background,
        )

        await _run_controlled(
            task_id,
            payload,
            fix_quality_background(
                task_id,
                payload["novel_id"],
                int(payload["chapter_number"]),
                issue_ids=list(payload.get("issue_ids") or []),
                worker_id=worker_id,
            ),
        )
        return

    if task_type is TaskType.NOVEL_VOLUME_OUTLINE:
        from src.api.services.generation.creative_control_tasks import (
            generate_volume_outline_background,
        )

        await _run_controlled(
            task_id,
            payload,
            generate_volume_outline_background(
                task_id,
                payload["novel_id"],
                int(payload["volume_number"]),
                worker_id=worker_id,
            ),
        )
        return

    if task_type is TaskType.PIPELINE_RESUME:
        from src.api.services.generation.novel_generator import resume_pipeline

        await resume_pipeline(task_id, dict(payload["decision"]))
        return

    raise ValueError(f"Unsupported task type: {task_type!r}")
