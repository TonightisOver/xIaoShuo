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
            "writing_style_prompt": request.writing_style_prompt,
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


async def generate_volume_background(
    task_id: str, novel_id: str, volume_number: int
) -> None:
    """按卷生成章节内容"""
    task_manager = get_task_manager()
    event_bus = get_event_bus()
    novel_manager = get_novel_manager()

    try:
        await task_manager.update_status(task_id, "running")

        vol = await novel_manager.get_volume(novel_id, volume_number)
        if not vol or not vol.get("outline"):
            raise ValueError(f"Volume {volume_number} has no outline")

        novel = await novel_manager.get_novel(novel_id)
        chapters_data = vol["outline"].get("chapters", [])

        # Get previous volumes' chapter summaries for context
        prev_context = ""
        prev_chapters = await novel_manager.list_chapters(novel_id)
        prev_in_earlier_vols = [c for c in prev_chapters if (c.get("volume_number") or 0) < volume_number]
        if prev_in_earlier_vols:
            last_ch = prev_in_earlier_vols[-1]
            prev_context = f"前文最后一章《{last_ch.get('title', '')}》结尾：{(last_ch.get('content', '') or '')[-500:]}"

        from src.core.llm.client import get_llm_client
        from src.core.llm.prompts import CHAPTER_GENERATION_PROMPT
        from src.core.validation import WRITING_STYLES
        from src.api.models.db_models import Chapter
        from src.core.database import get_db_session
        import json

        client = get_llm_client()
        style_instruction = WRITING_STYLES.get(novel.get("writing_style", ""), "")

        generated_chapters = []
        for i, ch_outline in enumerate(chapters_data):
            previous_chapter = prev_context if i == 0 else (generated_chapters[-1].get("content", "")[:500] if generated_chapters else "")

            prompt = CHAPTER_GENERATION_PROMPT.format(
                chapter_outline=json.dumps(ch_outline, ensure_ascii=False),
                previous_chapter=previous_chapter or "这是本卷第一章",
                characters=json.dumps([], ensure_ascii=False),
                world_setting=json.dumps({}, ensure_ascii=False),
            )
            if style_instruction:
                prompt = f"{style_instruction}\n\n{prompt}"

            content = await client.generate(prompt, max_tokens=8000)
            generated_chapters.append({
                "chapter": ch_outline.get("chapter", i + 1),
                "title": ch_outline.get("title", f"第{i+1}章"),
                "content": content,
                "word_count": len(content),
            })

            progress_data = {
                "current_stage": "chapter_generation",
                "completed_chapters": len(generated_chapters),
                "total_chapters": len(chapters_data),
                "percentage": int((len(generated_chapters) / len(chapters_data)) * 100),
            }
            await task_manager.update_status(task_id, "running", progress=progress_data)
            await event_bus.publish(ProgressEvent(
                task_id=task_id,
                event_type=EventType.CHAPTER_PROGRESS,
                data=progress_data,
            ))

        # Persist chapters to DB
        async with get_db_session() as session:
            for ch in generated_chapters:
                chapter = Chapter(
                    novel_id=novel_id,
                    volume_number=volume_number,
                    chapter_number=ch["chapter"],
                    title=ch["title"],
                    content=ch["content"],
                    word_count=ch["word_count"],
                    status="generated",
                )
                session.add(chapter)

        await novel_manager.update_volume(novel_id, volume_number, status="completed")
        await task_manager.complete_task(task_id, {"chapters": generated_chapters})
        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.COMPLETED,
            data={"percentage": 100, "volume_number": volume_number},
        ))

        logger.info(f"Volume {volume_number} generation completed for novel {novel_id}")

    except Exception as e:
        logger.exception(f"Volume generation failed: {e}")
        await task_manager.fail_task(task_id, str(e))
        await novel_manager.update_volume(novel_id, volume_number, status="failed")
        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.ERROR,
            data={"error": str(e)},
        ))


async def generate_chapters_background(
    task_id: str, novel_id: str, chapter_start: int, chapter_end: int
) -> None:
    """按章节范围生成"""
    task_manager = get_task_manager()
    event_bus = get_event_bus()
    novel_manager = get_novel_manager()

    try:
        await task_manager.update_status(task_id, "running")

        novel = await novel_manager.get_novel(novel_id)
        all_chapters = await novel_manager.list_chapters(novel_id)

        prev_context = ""
        if chapter_start > 1:
            prev_chs = [c for c in all_chapters if c["chapter_number"] == chapter_start - 1]
            if prev_chs:
                prev_context = (prev_chs[0].get("content", "") or "")[-500:]

        from src.core.llm.client import get_llm_client
        from src.core.llm.prompts import CHAPTER_GENERATION_PROMPT
        from src.core.validation import WRITING_STYLES
        from src.api.models.db_models import Chapter
        from src.core.database import get_db_session
        from sqlalchemy import delete
        import json

        client = get_llm_client()
        style_instruction = WRITING_STYLES.get(novel.get("writing_style", ""), "")

        volumes = await novel_manager.list_volumes(novel_id)
        chapter_outlines = []
        for vol in volumes:
            outline = vol.get("outline") or {}
            for ch in outline.get("chapters", []):
                chapter_outlines.append(ch)

        total_to_generate = chapter_end - chapter_start + 1
        generated_chapters = []

        for ch_num in range(chapter_start, chapter_end + 1):
            ch_outline = next(
                (co for co in chapter_outlines if co.get("chapter") == ch_num),
                {"chapter": ch_num, "title": f"第{ch_num}章", "plot": "续写情节", "words": 5000}
            )

            previous = prev_context if not generated_chapters else (generated_chapters[-1].get("content", "")[:500])

            prompt = CHAPTER_GENERATION_PROMPT.format(
                chapter_outline=json.dumps(ch_outline, ensure_ascii=False),
                previous_chapter=previous or "这是起始章节",
                characters=json.dumps([], ensure_ascii=False),
                world_setting=json.dumps({}, ensure_ascii=False),
            )
            if style_instruction:
                prompt = f"{style_instruction}\n\n{prompt}"

            content = await client.generate(prompt, max_tokens=8000)
            generated_chapters.append({
                "chapter": ch_num,
                "title": ch_outline.get("title", f"第{ch_num}章"),
                "content": content,
                "word_count": len(content),
            })

            progress_data = {
                "current_stage": "chapter_generation",
                "completed_chapters": len(generated_chapters),
                "total_chapters": total_to_generate,
                "percentage": int((len(generated_chapters) / total_to_generate) * 100),
            }
            await task_manager.update_status(task_id, "running", progress=progress_data)
            await event_bus.publish(ProgressEvent(
                task_id=task_id,
                event_type=EventType.CHAPTER_PROGRESS,
                data=progress_data,
            ))

        async with get_db_session() as session:
            await session.execute(
                delete(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number >= chapter_start,
                    Chapter.chapter_number <= chapter_end,
                )
            )
            for ch in generated_chapters:
                chapter = Chapter(
                    novel_id=novel_id,
                    chapter_number=ch["chapter"],
                    title=ch["title"],
                    content=ch["content"],
                    word_count=ch["word_count"],
                    status="regenerated",
                )
                session.add(chapter)

        await task_manager.complete_task(task_id, {"chapters": generated_chapters})
        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.COMPLETED,
            data={"percentage": 100, "chapter_start": chapter_start, "chapter_end": chapter_end},
        ))

        logger.info(f"Chapters {chapter_start}-{chapter_end} generated for novel {novel_id}")

    except Exception as e:
        logger.exception(f"Chapter range generation failed: {e}")
        await task_manager.fail_task(task_id, str(e))
        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.ERROR,
            data={"error": str(e)},
        ))


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

        # Volumes
        volumes = result.get("volumes", [])
        for vol in volumes:
            if isinstance(vol, dict):
                vol_chapters = vol.get("chapters", [])
                ch_start = vol_chapters[0].get("chapter", 1) if vol_chapters else None
                ch_end = vol_chapters[-1].get("chapter", 1) if vol_chapters else None
                await manager.create_volume(
                    novel_id,
                    volume_number=vol.get("volume_number", 1),
                    title=vol.get("title"),
                    summary=vol.get("summary"),
                    outline=vol,
                    chapter_start=ch_start,
                    chapter_end=ch_end,
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
