"""创作控制台专用的持久化后台任务。"""

from types import SimpleNamespace

from sqlalchemy import select

from src.api.models.db_models import Outline
from src.api.services.content.blueprint_service import BlueprintService
from src.api.services.content.chapter_service import get_chapter_service
from src.api.services.creative_control.artifact_write_service import (
    CreativeArtifactWriteService,
)
from src.api.services.quality.rewrite_loop_service import RewriteLoopService
from src.api.services.tasks.task_manager import get_task_manager
from src.core.creative_control.control_service import CreativeControlService
from src.core.database import get_db_session


async def generate_blueprint_background(
    task_id: str,
    novel_id: str,
    chapter_number: int,
    *,
    worker_id: str | None = None,
) -> None:
    task_manager = get_task_manager()
    try:
        await task_manager.update_status(task_id, "running", worker_id=worker_id)
        await CreativeControlService().assert_generation_allowed(
            novel_id, "blueprint", str(chapter_number)
        )
        async with get_db_session() as session:
            outline = (
                await session.execute(
                    select(Outline).where(
                        Outline.novel_id == novel_id,
                        Outline.level == "chapter",
                        Outline.chapter_number == chapter_number,
                    )
                )
            ).scalar_one_or_none()
        chapter_outline = (
            outline.content
            if outline
            else {"chapter": chapter_number, "title": f"第{chapter_number}章"}
        )
        blueprint = await BlueprintService().generate_blueprint(
            novel_id, chapter_number, chapter_outline, persist=False
        )
        task = await task_manager.get_task(task_id)
        await CreativeArtifactWriteService().record_generated_artifact(
            novel_id=novel_id,
            artifact_type="blueprint",
            artifact_id=str(chapter_number),
            content=blueprint,
            task_id=task_id,
            operation_id=(task or {}).get("operation_id") or task_id,
            model="deepseek",
        )
        await task_manager.complete_task(
            task_id,
            {
                "current_stage": "blueprint_completed",
                "chapter_number": chapter_number,
                "blueprint": blueprint,
            },
            worker_id=worker_id,
        )
    except Exception as exc:
        if worker_id is None:
            await task_manager.fail_task(task_id, str(exc))
        raise


async def fix_quality_background(
    task_id: str,
    novel_id: str,
    chapter_number: int,
    *,
    issue_ids: list[str] | None = None,
    worker_id: str | None = None,
) -> None:
    task_manager = get_task_manager()
    try:
        await task_manager.update_status(task_id, "running", worker_id=worker_id)
        await CreativeControlService().assert_generation_allowed(
            novel_id, "chapter", str(chapter_number)
        )
        task = await task_manager.get_task(task_id)
        operation_id = (task or {}).get("operation_id") or task_id
        chapter_service = get_chapter_service()
        active_version = await chapter_service.get_active_chapter_version(
            novel_id, chapter_number
        )
        result = await RewriteLoopService().auto_improve_chapter(
            novel_id=novel_id,
            chapter_number=chapter_number,
            operation_id=operation_id,
        )
        best_version = result.get("best_version")
        if best_version is not None:
            final_scores = result.get("final_scores") or {}
            await chapter_service.finalize_chapter_version(
                novel_id,
                chapter_number,
                expected_active_version=(
                    active_version.get("version_number") if active_version else None
                ),
                selected_version=int(best_version),
                quality_score=final_scores.get("overall"),
                quality_scores=final_scores,
            )
        await task_manager.complete_task(
            task_id,
            {
                "current_stage": "quality_fix_completed",
                "chapter_number": chapter_number,
                "issue_ids": issue_ids or [],
                "quality_result": result,
            },
            worker_id=worker_id,
        )
    except Exception as exc:
        if worker_id is None:
            await task_manager.fail_task(task_id, str(exc))
        raise


async def generate_volume_outline_background(
    task_id: str,
    novel_id: str,
    volume_number: int,
    *,
    worker_id: str | None = None,
) -> None:
    """重新生成并持久化指定卷纲，不触发章节正文生成。"""
    from src.api.services.content.novel_manager import get_novel_manager
    from src.api.services.content.outline_service import get_outline_service
    from src.api.services.generation.long_form_generation_helpers import (
        generate_volume_outline,
    )

    task_manager = get_task_manager()
    try:
        await task_manager.update_status(task_id, "running", worker_id=worker_id)
        await CreativeControlService().assert_generation_allowed(
            novel_id, "volume_outline", str(volume_number)
        )
        novel = await get_novel_manager().get_novel(novel_id)
        if novel is None or not isinstance(novel.get("master_outline"), dict):
            raise ValueError("小说尚无可用总纲，无法重生成卷纲")
        chapters_per_volume = int(novel.get("chapters_per_volume") or 40)
        request = SimpleNamespace(
            writing_style=novel.get("writing_style") or "现代白话",
            writing_style_prompt=novel.get("writing_style_prompt") or "",
        )
        outline = await generate_volume_outline(
            novel_id=novel_id,
            master_outline=novel["master_outline"],
            volume_number=volume_number,
            chapters_per_volume=chapters_per_volume,
            words_per_chapter=int(novel.get("words_per_chapter") or 3000),
            request=request,
        )
        task = await task_manager.get_task(task_id)
        await CreativeArtifactWriteService().record_generated_artifact(
            novel_id=novel_id,
            artifact_type="volume_outline",
            artifact_id=str(volume_number),
            content=outline,
            task_id=task_id,
            operation_id=(task or {}).get("operation_id") or task_id,
            model="deepseek",
        )
        outline_service = get_outline_service()
        volume_offset = (volume_number - 1) * chapters_per_volume
        for index, chapter in enumerate(outline.get("chapters", [])):
            local_number = int(chapter.get("chapter", index + 1))
            await outline_service.upsert_chapter_outline(
                novel_id,
                volume_number,
                volume_offset + local_number,
                chapter,
            )
        await task_manager.complete_task(
            task_id,
            {
                "current_stage": "volume_outline_completed",
                "volume_number": volume_number,
                "outline": outline,
            },
            worker_id=worker_id,
        )
    except Exception as exc:
        if worker_id is None:
            await task_manager.fail_task(task_id, str(exc))
        raise
