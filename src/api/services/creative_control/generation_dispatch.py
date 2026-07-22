"""把创作控制生成计划投递为持久化任务。"""

from dataclasses import dataclass, field
from uuid import uuid4

import structlog

from src.api.services.tasks.task_dispatcher import TaskType
from src.api.services.tasks.task_manager import get_task_manager
from src.core.config import get_settings
from src.core.creative_control.scope_planner import ScopePlan

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class DispatchedGeneration:
    task_id: str
    task_ids: list[str]
    task_type: str
    target_chapters: list[int]
    skipped_locked: list[int]
    skipped_confirmed: list[int]
    accepted: list[dict] = field(default_factory=list)  # [{chapter_number, task_id}]
    already_generating: list[int] = field(default_factory=list)
    failed_to_enqueue: list[dict] = field(default_factory=list)  # [{chapter_number, error}]


class CreativeGenerationDispatcher:
    """复用现有任务白名单投递卷或章节生成。"""

    async def dispatch_scope(
        self,
        novel: dict,
        owner_id: int,
        plan: ScopePlan,
    ) -> DispatchedGeneration:
        novel_id = novel["novel_id"]
        dispatch_id = uuid4().hex
        control_target = plan.payload.get("_control_target")
        payloads: list[dict] = []
        operation_ids: list[str] = []
        task_type: str = ""

        if plan.endpoint == "blueprint/generate":
            chapter_numbers = plan.payload.get("chapter_numbers")
            if chapter_numbers:
                task_type = TaskType.NOVEL_BLUEPRINT.value
                ranges = _contiguous_ranges(list(chapter_numbers))
                payloads = [
                    {"novel_id": novel_id, "chapter_start": s, "chapter_end": e}
                    for s, e in ranges
                ]
                operation_ids = [
                    f"{novel_id}:blueprint:{p['chapter_start']}-{p['chapter_end']}:{dispatch_id}"
                    for p in payloads
                ]
            else:
                chapter_number = int(plan.payload["chapter_number"])
                task_type = TaskType.NOVEL_BLUEPRINT.value
                payloads = [{"novel_id": novel_id, "chapter_number": chapter_number}]
                operation_ids = [f"{novel_id}:blueprint:{chapter_number}:{dispatch_id}"]
        elif plan.endpoint == "auto-improve":
            chapter_number = int(plan.payload["chapter_number"])
            task_type = TaskType.NOVEL_QUALITY_FIX.value
            payloads = [{
                "novel_id": novel_id, "chapter_number": chapter_number,
                "issue_ids": list(plan.payload.get("issue_ids") or []),
            }]
            operation_ids = [f"{novel_id}:quality-fix:{chapter_number}:{dispatch_id}"]
        elif plan.endpoint == "generate-volume-outline":
            volume_number = int(plan.payload["volume_number"])
            task_type = TaskType.NOVEL_VOLUME_OUTLINE.value
            payloads = [{"novel_id": novel_id, "volume_number": volume_number}]
            operation_ids = [f"{novel_id}:volume-outline:{volume_number}:{dispatch_id}"]
        elif plan.endpoint in {"generate-chapters", "generate-volume"} and not (
            plan.skipped_locked or plan.skipped_confirmed
        ) and plan.endpoint == "generate-volume":
            volume_number = int(plan.payload["volume_number"])
            task_type = TaskType.NOVEL_VOLUME.value
            payloads = [{"novel_id": novel_id, "volume_number": volume_number}]
            operation_ids = [f"{novel_id}:volume:{volume_number}:{dispatch_id}"]
        elif plan.endpoint in {"generate-chapters", "generate-volume"}:
            if not plan.target_chapters:
                raise ValueError("生成范围没有可执行章节")
            task_type = TaskType.NOVEL_CHAPTERS.value
            ranges = _contiguous_ranges(plan.target_chapters)
            payloads = [
                {"novel_id": novel_id, "chapter_start": s, "chapter_end": e}
                for s, e in ranges
            ]
            operation_ids = [
                f"{novel_id}:chapters:{p['chapter_start']}-{p['chapter_end']}:{dispatch_id}"
                for p in payloads
            ]
        else:
            raise ValueError(f"暂不支持执行生成端点: {plan.endpoint}")

        # generation_targets 每个任务一组
        generation_targets_list: list[list[dict]] = []
        for payload in payloads:
            if control_target is not None:
                gts = [dict(control_target)]
                if (
                    task_type in {TaskType.NOVEL_CHAPTERS.value, TaskType.NOVEL_QUALITY_FIX.value}
                    and str(control_target["artifact_type"]) != "chapter"
                ):
                    gts.append({
                        "artifact_type": "chapter",
                        "artifact_id": str(payload.get("chapter_number") or payload.get("chapter_start")),
                    })
            elif task_type == TaskType.NOVEL_CHAPTERS.value:
                gts = [
                    {"artifact_type": "chapter", "artifact_id": str(c)}
                    for c in range(int(payload["chapter_start"]), int(payload["chapter_end"]) + 1)
                ]
            elif task_type == TaskType.NOVEL_VOLUME.value:
                gts = [
                    {"artifact_type": "chapter", "artifact_id": str(c)}
                    for c in plan.target_chapters
                ]
            elif task_type == TaskType.NOVEL_BLUEPRINT.value:
                if "chapter_number" in payload:
                    gts = [{"artifact_type": "blueprint", "artifact_id": str(payload["chapter_number"])}]
                else:
                    gts = [
                        {"artifact_type": "blueprint", "artifact_id": str(c)}
                        for c in range(int(payload["chapter_start"]), int(payload["chapter_end"]) + 1)
                    ]
            elif task_type == TaskType.NOVEL_QUALITY_FIX.value:
                gts = [{"artifact_type": "quality", "artifact_id": str(payload["chapter_number"])}]
            else:
                gts = [{"artifact_type": "volume_outline", "artifact_id": str(payload["volume_number"])}]
            generation_targets_list.append(gts)

        task_ids: list[str | None] = []
        for payload, operation_id, gts in zip(payloads, operation_ids, generation_targets_list, strict=True):
            try:
                tid = await get_task_manager().create_task(
                    idea=novel["idea"],
                    novel_type=novel["novel_type"],
                    target_words=novel["target_words"],
                    novel_id=novel_id,
                    owner_id=owner_id,
                    task_type=task_type,
                    task_payload=payload,
                    max_attempts=get_settings().LONG_FORM_MAX_ATTEMPTS,
                    operation_id=operation_id,
                    generation_targets=gts,
                )
                task_ids.append(tid)
            except Exception as exc:  # noqa: BLE001 - 入队失败逐章隔离
                logger.warning("dispatch_enqueue_failed", error=str(exc), payload=payload)
                task_ids.append(None)

        # 逐章明细（blueprint_only 多章）
        accepted: list[dict] = []
        failed_to_enqueue: list[dict] = []
        if plan.endpoint == "blueprint/generate" and plan.payload.get("chapter_numbers"):
            chap_to_task: dict[int, str] = {}
            for payload, tid in zip(payloads, task_ids, strict=True):
                if tid is None or "chapter_start" not in payload:
                    continue
                for c in range(payload["chapter_start"], payload["chapter_end"] + 1):
                    chap_to_task[c] = tid
            for c in plan.target_chapters:
                tid = chap_to_task.get(c)
                if tid:
                    accepted.append({"chapter_number": c, "task_id": tid})
                else:
                    failed_to_enqueue.append({"chapter_number": c, "error": "未入队"})

        real_task_ids = [t for t in task_ids if t]
        return DispatchedGeneration(
            task_id=real_task_ids[0] if real_task_ids else "",
            task_ids=real_task_ids,
            task_type=task_type,
            target_chapters=plan.target_chapters,
            skipped_locked=plan.skipped_locked,
            skipped_confirmed=plan.skipped_confirmed,
            accepted=accepted,
            already_generating=[],
            failed_to_enqueue=failed_to_enqueue,
        )


def _contiguous_ranges(chapters: list[int]) -> list[tuple[int, int]]:
    ordered = sorted(set(chapters))
    ranges: list[tuple[int, int]] = []
    start = end = ordered[0]
    for chapter in ordered[1:]:
        if chapter == end + 1:
            end = chapter
            continue
        ranges.append((start, end))
        start = end = chapter
    ranges.append((start, end))
    return ranges
