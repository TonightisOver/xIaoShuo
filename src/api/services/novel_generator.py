"""小说生成服务

负责执行小说生成任务，通过事件总线推送实时进度。
"""

import logging
from typing import Any

from src.api.models.requests import CreateNovelRequest
from src.api.services.progress_event_bus import (
    EventType,
    ProgressEvent,
    get_event_bus,
    register_progress_callback,
    unregister_progress_callback,
)
from src.api.services.task_manager import get_task_manager
from src.api.services.novel_manager import get_novel_manager
from src.core.langgraph.graph import create_novel_graph
from src.core.langgraph.state import NovelState

logger = logging.getLogger(__name__)

STAGE_ORDER = [
    "idea_expansion",
    "world_building",
    "character_design",
    "outline_generation",
    "chapter_generation",
    "quality_check",
    "human_review",
]


def _stage_percentage(stage: str) -> int:
    try:
        idx = STAGE_ORDER.index(stage)
        return int(((idx + 1) / len(STAGE_ORDER)) * 100)
    except ValueError:
        return 0


async def generate_novel_background(
    task_id: str, request: CreateNovelRequest
) -> None:
    """后台执行小说生成"""
    task_manager = get_task_manager()
    event_bus = get_event_bus()

    try:
        await task_manager.update_status(task_id, "running")

        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.STAGE_START,
            data={"stage": "idea_expansion", "percentage": 0},
        ))

        logger.info(f"Starting novel generation for task {task_id}")

        graph = create_novel_graph()

        async def _chapter_progress_callback(data: dict[str, Any]) -> None:
            total = max(data.get("total_chapters", 1), 1)
            completed = data.get("completed_chapters", 0)
            base = _stage_percentage("outline_generation")
            span = _stage_percentage("chapter_generation") - base
            pct = base + int((completed / total) * span)

            progress_data = {
                "current_stage": "chapter_generation",
                "completed_chapters": completed,
                "total_chapters": total,
                "percentage": pct,
            }
            await task_manager.update_status(task_id, "running", progress=progress_data)
            await event_bus.publish(ProgressEvent(
                task_id=task_id,
                event_type=EventType.CHAPTER_PROGRESS,
                data=progress_data,
            ))

        initial_state: NovelState = {
            "project_id": task_id,
            "idea": request.idea,
            "novel_type": request.novel_type,
            "target_words": request.target_words,
            "writing_style": request.writing_style,
            "current_stage": "start",
            "chapters": [],
            "errors": [],
        }

        register_progress_callback(task_id, _chapter_progress_callback)

        config = {"configurable": {"thread_id": task_id}}
        result: dict[str, Any] = {}

        async for event in graph.astream(initial_state, config=config):
            for node_name, state_update in event.items():
                result = state_update
                percentage = _stage_percentage(node_name)

                progress_data = {
                    "current_stage": node_name,
                    "completed_chapters": len(state_update.get("chapters", [])),
                    "total_chapters": len(state_update.get("chapter_outlines", [])),
                    "percentage": percentage,
                }
                await task_manager.update_status(
                    task_id, "running", progress=progress_data
                )

                await event_bus.publish(ProgressEvent(
                    task_id=task_id,
                    event_type=EventType.STAGE_COMPLETE,
                    data=progress_data,
                ))

                idx = STAGE_ORDER.index(node_name) if node_name in STAGE_ORDER else -1
                if 0 <= idx < len(STAGE_ORDER) - 1:
                    await event_bus.publish(ProgressEvent(
                        task_id=task_id,
                        event_type=EventType.STAGE_START,
                        data={
                            "stage": STAGE_ORDER[idx + 1],
                            "percentage": percentage,
                        },
                    ))

        await task_manager.complete_task(task_id, result)

        # Persist results into novel sub-tables if linked to a project
        task_data = await task_manager.get_task(task_id)
        if task_data and task_data.get("novel_id"):
            await _persist_to_novel(task_data["novel_id"], result)

        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.COMPLETED,
            data={"percentage": 100, "current_stage": "completed"},
        ))

        logger.info(
            f"Novel generation completed for task {task_id}, "
            f"generated {len(result.get('chapters', []))} chapters"
        )

    except Exception as e:
        logger.exception(f"Novel generation failed for task {task_id}")
        await task_manager.fail_task(task_id, str(e))
        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.ERROR,
            data={"error": str(e)},
        ))
    finally:
        unregister_progress_callback(task_id)


async def _persist_to_novel(novel_id: str, result: dict[str, Any]) -> None:
    """Persist LangGraph result into novel sub-tables."""
    manager = get_novel_manager()

    try:
        # World setting
        ws = result.get("world_setting")
        if ws and isinstance(ws, dict):
            await manager.upsert_world_setting(
                novel_id,
                background=ws.get("background") or ws.get("世界背景"),
                geography=ws.get("geography") or ws.get("地理环境"),
                culture=ws.get("culture") or ws.get("文化体系"),
                rules=ws.get("rules") or ws.get("世界规则"),
                extra={k: v for k, v in ws.items()
                       if k not in ("background", "geography", "culture", "rules",
                                    "世界背景", "地理环境", "文化体系", "世界规则")},
            )

        # Characters
        characters = result.get("characters", [])
        for char in characters:
            if isinstance(char, dict) and char.get("name"):
                await manager.create_character(
                    novel_id,
                    name=char.get("name", ""),
                    role=char.get("role") or char.get("角色"),
                    description=char.get("description") or char.get("描述"),
                    personality=char.get("personality") or char.get("性格"),
                    abilities=char.get("abilities") or char.get("能力"),
                    background_story=char.get("background_story") or char.get("背景"),
                )

        # Chapters
        chapters = result.get("chapters", [])
        from src.api.models.db_models import Chapter
        from src.core.database import get_db_session
        from datetime import datetime, timezone

        async with get_db_session() as session:
            for ch in chapters:
                if isinstance(ch, dict):
                    chapter = Chapter(
                        novel_id=novel_id,
                        chapter_number=ch.get("chapter", 0),
                        title=ch.get("title", ""),
                        content=ch.get("content", ""),
                        word_count=ch.get("word_count", 0),
                        status="generated",
                        updated_at=datetime.now(timezone.utc),
                    )
                    session.add(chapter)

        # Update novel status
        await manager.update_novel(novel_id, status="completed")

        logger.info(f"Persisted generation results to novel {novel_id}")

    except Exception as e:
        logger.error(f"Failed to persist results to novel {novel_id}: {e}")
