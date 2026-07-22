"""把创作控制生成计划投递为持久化任务。"""

from dataclasses import dataclass
from uuid import uuid4

from src.api.services.tasks.task_dispatcher import TaskType
from src.api.services.tasks.task_manager import get_task_manager
from src.core.config import get_settings
from src.core.creative_control.scope_planner import ScopePlan


@dataclass(frozen=True)
class DispatchedGeneration:
    task_id: str
    task_ids: list[str]
    task_type: str
    target_chapters: list[int]
    skipped_locked: list[int]
    skipped_confirmed: list[int]


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
        if plan.endpoint == "blueprint/generate":
            chapter_number = int(plan.payload["chapter_number"])
            task_type = TaskType.NOVEL_BLUEPRINT.value
            payloads = [{"novel_id": novel_id, "chapter_number": chapter_number}]
            operation_ids = [f"{novel_id}:blueprint:{chapter_number}"]
        elif plan.endpoint == "auto-improve":
            chapter_number = int(plan.payload["chapter_number"])
            task_type = TaskType.NOVEL_QUALITY_FIX.value
            payloads = [{
                "novel_id": novel_id,
                "chapter_number": chapter_number,
                "issue_ids": list(plan.payload.get("issue_ids") or []),
            }]
            operation_ids = [f"{novel_id}:quality-fix:{chapter_number}"]
        elif plan.endpoint == "generate-volume-outline":
            volume_number = int(plan.payload["volume_number"])
            task_type = TaskType.NOVEL_VOLUME_OUTLINE.value
            payloads = [{"novel_id": novel_id, "volume_number": volume_number}]
            operation_ids = [f"{novel_id}:volume-outline:{volume_number}"]
        elif plan.endpoint == "generate-volume" and not (
            plan.skipped_locked or plan.skipped_confirmed
        ):
            task_type = TaskType.NOVEL_VOLUME.value
            payloads = [{
                "novel_id": novel_id,
                "volume_number": int(plan.payload["volume_number"]),
            }]
            operation_ids = [
                f"{novel_id}:volume:{payloads[0]['volume_number']}"
            ]
        elif plan.endpoint in {"generate-chapters", "generate-volume"}:
            if not plan.target_chapters:
                raise ValueError("生成范围没有可执行章节")
            task_type = TaskType.NOVEL_CHAPTERS.value
            ranges = _contiguous_ranges(plan.target_chapters)
            payloads = [
                {
                    "novel_id": novel_id,
                    "chapter_start": start,
                    "chapter_end": end,
                }
                for start, end in ranges
            ]
            operation_ids = [
                f"{novel_id}:chapters:{payload['chapter_start']}-{payload['chapter_end']}"
                for payload in payloads
            ]
        else:
            raise ValueError(f"暂不支持执行生成端点: {plan.endpoint}")

        # operation_id 标识一次用户操作：同一 Task 重试保持不变，不同时间再次
        # 生成相同范围必须不同，避免命中上一次正文 baseline 的幂等键。
        operation_ids = [f"{value}:{dispatch_id}" for value in operation_ids]

        task_ids = []
        for payload, operation_id in zip(payloads, operation_ids, strict=True):
            if control_target is not None:
                generation_targets = [dict(control_target)]
                if (
                    task_type in {
                        TaskType.NOVEL_CHAPTERS.value,
                        TaskType.NOVEL_QUALITY_FIX.value,
                    }
                    and str(control_target["artifact_type"]) != "chapter"
                ):
                    generation_targets.append({
                        "artifact_type": "chapter",
                        "artifact_id": str(
                            payload.get("chapter_number")
                            or payload.get("chapter_start")
                        ),
                    })
            elif task_type == TaskType.NOVEL_CHAPTERS.value:
                generation_targets = [
                    {"artifact_type": "chapter", "artifact_id": str(chapter)}
                    for chapter in range(
                        int(payload["chapter_start"]),
                        int(payload["chapter_end"]) + 1,
                    )
                ]
            elif task_type == TaskType.NOVEL_VOLUME.value:
                generation_targets = [
                    {"artifact_type": "chapter", "artifact_id": str(chapter)}
                    for chapter in plan.target_chapters
                ]
            elif task_type == TaskType.NOVEL_BLUEPRINT.value:
                generation_targets = [{
                    "artifact_type": "blueprint",
                    "artifact_id": str(payload["chapter_number"]),
                }]
            elif task_type == TaskType.NOVEL_QUALITY_FIX.value:
                generation_targets = [{
                    "artifact_type": "quality",
                    "artifact_id": str(payload["chapter_number"]),
                }]
            else:
                generation_targets = [{
                    "artifact_type": "volume_outline",
                    "artifact_id": str(payload["volume_number"]),
                }]
            task_ids.append(await get_task_manager().create_task(
                idea=novel["idea"],
                novel_type=novel["novel_type"],
                target_words=novel["target_words"],
                novel_id=novel_id,
                owner_id=owner_id,
                task_type=task_type,
                task_payload=payload,
                max_attempts=get_settings().LONG_FORM_MAX_ATTEMPTS,
                operation_id=operation_id,
                generation_targets=generation_targets,
            ))
        return DispatchedGeneration(
            task_id=task_ids[0],
            task_ids=task_ids,
            task_type=task_type,
            target_chapters=plan.target_chapters,
            skipped_locked=plan.skipped_locked,
            skipped_confirmed=plan.skipped_confirmed,
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
