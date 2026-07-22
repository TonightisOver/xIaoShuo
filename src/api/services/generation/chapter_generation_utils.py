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
    sequence: int | None = None,
) -> None:
    """发布进度事件（Task 8 / R7 / B8）。

    - 永不抛异常：publish / update_status 失败仅 log，不阻断章节流程。
    - sequence 由持有 lease 的调用方通过 CheckpointStore 原子分配；本函数只发布，
      不再读取检查点推算序号，避免并发事件获得相同 sequence。
    """
    payload = dict(data)
    if sequence is not None:
        payload["sequence"] = sequence

    try:
        event_bus = get_event_bus()
        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=event_type,
            data=payload,
        ))
    except Exception as exc:
        logger.warning(
            "emit_progress_publish_failed",
            task_id=task_id,
            event_type=getattr(event_type, "value", event_type),
            error=str(exc),
        )
        return

    if update_status:
        try:
            task_manager = get_task_manager()
            await task_manager.update_status(task_id, status, progress=payload)
        except Exception as exc:
            logger.warning(
                "emit_progress_update_status_failed",
                task_id=task_id,
                error=str(exc),
            )


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
