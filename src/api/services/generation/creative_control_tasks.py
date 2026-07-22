"""创作控制台专用的持久化后台任务。"""

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
