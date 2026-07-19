"""Shared helpers for chapter generation services."""

from typing import Any

import structlog

from src.api.services.generation.progress_event_bus import (
    EventType,
    ProgressEvent,
    get_event_bus,
)
from src.api.services.quality.novel_context_service import NovelContextBuilder
from src.api.services.tasks.task_manager import get_task_manager

logger = structlog.get_logger(__name__)

_context_builder = NovelContextBuilder()


async def _emit_progress(
    task_id: str,
    event_type: EventType,
    data: dict[str, Any],
    *,
    update_status: bool = False,
    status: str = "running",
) -> None:
    event_bus = get_event_bus()
    await event_bus.publish(ProgressEvent(
        task_id=task_id,
        event_type=event_type,
        data=data,
    ))
    if update_status:
        task_manager = get_task_manager()
        await task_manager.update_status(task_id, status, progress=data)


async def _get_story_bible_context(novel_id: str, chapter_outline: dict) -> str | None:
    try:
        from sqlalchemy import select

        from src.api.models.db_models import StoryBible
        from src.api.services.content.story_bible_service import (
            extract_relevant_constraints,
        )
        from src.core.database import get_db_session

        async with get_db_session() as session:
            stmt = select(StoryBible).where(StoryBible.novel_id == novel_id)
            res = await session.execute(stmt)
            bible = res.scalar_one_or_none()
            if bible:
                chapter_num = chapter_outline.get("chapter", 0)
                return extract_relevant_constraints(bible, chapter_outline, chapter_num)
    except Exception as e:
        logger.warning("story_bible_context_fetch_failed", error=str(e))
    return None


async def _get_blueprint(novel_id: str, chapter_outline: dict) -> dict | None:
    chapter_num = chapter_outline.get("chapter", 0)
    try:
        from src.api.services.content.blueprint_service import BlueprintService

        bp_service = BlueprintService()
        existing_bp = await bp_service.get_blueprint(novel_id, chapter_num)
        if existing_bp:
            return existing_bp
        return await bp_service.generate_blueprint(
            novel_id, chapter_num, chapter_outline
        )
    except Exception as e:
        logger.warning("blueprint_fetch_failed", chapter=chapter_num, error=str(e))
    return None


async def _sync_chapter_type_to_db(
    novel_id: str, chapter_num: int, chapter_type: str | None
) -> None:
    if not chapter_type:
        return
    try:
        from sqlalchemy import update

        from src.api.models.db_models import Chapter
        from src.core.database import get_db_session

        async with get_db_session() as session:
            await session.execute(
                update(Chapter)
                .where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_num,
                )
                .values(chapter_type=chapter_type)
            )
    except Exception as e:
        logger.warning("chapter_type_sync_failed", chapter=chapter_num, error=str(e))
