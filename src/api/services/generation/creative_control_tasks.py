"""创作控制台专用的持久化后台任务。"""

from types import SimpleNamespace

from sqlalchemy import select

from src.api.models.db_models import Outline
from src.api.services.content.blueprint_service import BlueprintService
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
            novel_id, chapter_number, chapter_outline
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
        result = await RewriteLoopService().auto_improve_chapter(
            novel_id=novel_id,
            chapter_number=chapter_number,
            operation_id=f"{novel_id}:quality-fix:{chapter_number}",
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
        outline_service = get_outline_service()
        await outline_service.upsert_volume_outline(
            novel_id, volume_number, outline
        )
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
