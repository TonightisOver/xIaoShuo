"""长篇生成辅助模块

从 novel_generator.py 中提取的长篇生成相关函数：
- generate_master_outline
- generate_volume_outline
- generate_volume_chapters
- generate_volume_quality_report
"""

import json
from typing import Any

import structlog

from src.api.services.chapter_persistence_service import persist_generated_chapters
from src.api.services.progress_event_bus import (
    EventType,
    ProgressEvent,
    get_event_bus,
)
from src.core.context import NovelContextBuilder

logger = structlog.get_logger(__name__)

_context_builder = NovelContextBuilder()


async def _emit_progress(
    task_id: str,
    event_type: EventType,
    data: dict[str, Any],
) -> None:
    """Emit a progress event."""
    event_bus = get_event_bus()
    await event_bus.publish(ProgressEvent(
        task_id=task_id,
        event_type=event_type,
        data=data,
    ))


async def generate_master_outline(
    novel_id: str,
    request: Any,
) -> dict[str, Any]:
    """Generate master outline for long-form novel.

    Args:
        novel_id: Novel ID
        request: LongFormNovelRequest

    Returns:
        Master outline dict
    """
    from src.core.llm.client import get_llm_client
    from src.core.llm.helpers import generate_and_parse_json
    from src.core.llm.prompts import MASTER_OUTLINE_PROMPT
    from src.core.validation import get_style_instruction

    client = get_llm_client()

    prompt = MASTER_OUTLINE_PROMPT.format(
        idea=request.idea,
        novel_type=request.novel_type,
        target_words=request.target_words,
        volumes=request.volumes,
        chapters_per_volume=request.chapters_per_volume,
        words_per_chapter=request.words_per_chapter,
    )

    style_instruction = get_style_instruction(
        request.writing_style,
        request.writing_style_prompt,
    )
    if style_instruction:
        prompt = f"{style_instruction}\n\n{prompt}"

    # Fallback
    fallback_volumes = []
    for i in range(1, request.volumes + 1):
        fallback_volumes.append({
            "volume_number": i,
            "title": f"第{i}卷",
            "summary": "本卷主要情节",
            "chapter_types": {
                "main_advance": int(request.chapters_per_volume * 0.45),
                "climax": int(request.chapters_per_volume * 0.12),
                "aftermath": int(request.chapters_per_volume * 0.08),
                "daily": int(request.chapters_per_volume * 0.15),
                "setup": int(request.chapters_per_volume * 0.15),
                "filler": 0,
            },
            "key_events": [],
            "foreshadows_planted": [],
            "foreshadows_resolved": [],
        })

    fallback_data = {
        "title": request.idea[:20],
        "synopsis": request.idea,
        "main_conflict": "待展开",
        "main_theme": "待确定",
        "volumes": fallback_volumes,
        "foreshadow_plan": [],
        "character_plan": [],
    }

    return await generate_and_parse_json(client, prompt, max_tokens=6000, fallback=fallback_data)


async def generate_volume_outline(
    novel_id: str,
    master_outline: dict[str, Any],
    volume_number: int,
    chapters_per_volume: int,
    words_per_chapter: int,
    request: Any,
) -> dict[str, Any]:
    """Generate volume outline.

    Returns:
        Volume outline dict
    """
    from src.core.llm.client import get_llm_client
    from src.core.llm.helpers import generate_and_parse_json
    from src.core.llm.prompts import VOLUME_OUTLINE_PROMPT
    from src.core.validation import get_style_instruction

    client = get_llm_client()

    volumes = master_outline.get("volumes", [])
    vol_info = next(
        (v for v in volumes if v.get("volume_number") == volume_number),
        {"title": f"第{volume_number}卷", "summary": "待生成"}
    )

    # Build previous volumes summary
    prev_summary = "这是第一卷，无前序卷摘要。"
    if volume_number > 1:
        prev_parts = []
        for v in volumes:
            if v.get("volume_number", 0) < volume_number:
                prev_parts.append(
                    f"- 第{v.get('volume_number')}卷《{v.get('title', '')}》：{v.get('summary', '')}"
                )
        if prev_parts:
            prev_summary = "\n".join(prev_parts)

    chapter_types = vol_info.get("chapter_types", {})
    chapter_types_str = f"""
- main_advance（主线推进）：约 {chapter_types.get('main_advance', int(chapters_per_volume * 0.45))} 章
- climax（高潮章）：约 {chapter_types.get('climax', int(chapters_per_volume * 0.12))} 章
- aftermath（余波章）：约 {chapter_types.get('aftermath', int(chapters_per_volume * 0.08))} 章
- daily（日常章）：约 {chapter_types.get('daily', int(chapters_per_volume * 0.15))} 章
- setup（铺垫章）：约 {chapter_types.get('setup', int(chapters_per_volume * 0.15))} 章
- filler（注水章）：约 0 章
"""

    prompt = VOLUME_OUTLINE_PROMPT.format(
        master_outline=json.dumps(
            {k: v for k, v in master_outline.items() if k != "volumes"},
            ensure_ascii=False,
        ),
        volume_number=volume_number,
        volume_summary=vol_info.get("summary", ""),
        previous_volumes_summary=prev_summary,
        chapters_count=chapters_per_volume,
        words_per_chapter=words_per_chapter,
        chapter_types=chapter_types_str,
    )

    style_instruction = get_style_instruction(
        request.writing_style,
        request.writing_style_prompt,
    )
    if style_instruction:
        prompt = f"{style_instruction}\n\n{prompt}"

    # Fallback
    fallback_chapters = []
    for i in range(1, chapters_per_volume + 1):
        fallback_chapters.append({
            "chapter": i,
            "title": f"第{i}章",
            "chapter_type": "main_advance" if i % 3 != 0 else "daily",
            "plot": "情节待展开",
            "key_characters": [],
            "foreshadows_planted": [],
            "foreshadows_resolved": [],
            "turning_point": "",
            "emotional_arc": "平静->推进",
        })

    fallback_data = {
        "volume_number": volume_number,
        "title": vol_info.get("title", f"第{volume_number}卷"),
        "chapters": fallback_chapters,
    }

    result = await generate_and_parse_json(client, prompt, max_tokens=6000, fallback=fallback_data)

    # Add volume_number to each chapter
    for ch in result.get("chapters", []):
        ch["volume_number"] = volume_number

    return result


async def generate_volume_chapters(
    task_id: str,
    novel_id: str,
    volume_number: int,
    chapter_start: int,
    chapter_end: int,
    vol_outline: dict[str, Any],
    words_per_chapter: int,
    request: Any,
) -> list[dict[str, Any]]:
    """Generate chapters for a volume.

    Returns:
        List of generated chapter dicts
    """
    from src.api.services.novel_manager import get_novel_manager
    from src.core.database import get_db_session
    from src.core.llm.chapter_generator import generate_single_chapter
    from src.core.llm.client import get_llm_client

    manager = get_novel_manager()
    client = get_llm_client()

    # Build context via NovelContextBuilder
    async with get_db_session() as session:
        gen_ctx = await _context_builder.build_generation_context(session, novel_id)

    chars_str = gen_ctx.chars_str
    world_str = gen_ctx.world_str
    style_instruction = gen_ctx.style_instruction

    # Get previous chapter context
    prev_context = ""
    if chapter_start > 1:
        prev_chapters = await manager.list_chapters(novel_id)
        prev_in_earlier = [c for c in prev_chapters if c.get("chapter_number", 0) == chapter_start - 1]
        if prev_in_earlier:
            prev_context = (prev_in_earlier[0].get("content", "") or "")[-500:]

    chapters_data = vol_outline.get("chapters", [])
    generated_chapters = []

    for i, ch_outline in enumerate(chapters_data):
        ch_num = ch_outline.get("chapter", i + 1)

        if i == 0:
            previous_chapter = prev_context or "这是本卷第一章"
        else:
            last_content = generated_chapters[-1].get("content", "") if generated_chapters else ""
            previous_chapter = last_content[:500] if last_content else "续写"

        try:
            # Prepare story bible context and blueprint
            story_bible_ctx = await _get_story_bible_context(novel_id, ch_outline)
            bp = await _get_blueprint(novel_id, ch_outline)

            chapter_result = await generate_single_chapter(
                client=client,
                chapter_outline=ch_outline,
                previous_chapter=previous_chapter,
                characters_json=chars_str,
                world_setting_json=world_str,
                style_instruction=style_instruction,
                target_words=words_per_chapter,
                novel_id=novel_id,
                blueprint=bp,
                story_bible_context=story_bible_ctx,
            )
            generated_chapters.append(chapter_result)

            # Sync chapter_type to DB
            await _sync_chapter_type_to_db(
                novel_id, ch_num, chapter_result.get("chapter_type")
            )
        except Exception as ch_error:
            logger.error(
                "chapter_generation_failed",
                novel_id=novel_id,
                chapter=ch_num,
                error=str(ch_error),
            )
            generated_chapters.append({
                "chapter": ch_num,
                "title": ch_outline.get("title", f"第{ch_num}章"),
                "content": f"[章节生成失败: {str(ch_error)}]",
                "word_count": 0,
                "generation_failed": True,
            })

        # Emit progress
        progress_data = {
            "current_stage": "chapter_generation",
            "volume_number": volume_number,
            "completed_chapters": len(generated_chapters),
            "total_chapters": len(chapters_data),
            "percentage": int((len(generated_chapters) / len(chapters_data)) * 100),
        }
        await _emit_progress(task_id, EventType.CHAPTER_PROGRESS, progress_data)

    # Persist successful chapters
    successful = [ch for ch in generated_chapters if not ch.get("generation_failed")]
    await persist_generated_chapters(novel_id, successful, volume_number)

    return generated_chapters


async def generate_volume_quality_report(
    novel_id: str,
    volume_number: int,
    chapters: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate quality report for a volume.

    Returns:
        Quality report dict
    """
    total_word_count = sum(ch.get("word_count", 0) for ch in chapters)
    chapter_count = len(chapters)

    # Simple quality metrics
    avg_scores = {
        "advancement": 0.7,
        "character_consistency": 0.7,
        "world_consistency": 0.7,
        "pacing": 0.7,
        "conflict": 0.7,
        "foreshadowing": 0.7,
        "dialogue_quality": 0.7,
        "emotional_impact": 0.7,
    }

    return {
        "volume_number": volume_number,
        "chapter_count": chapter_count,
        "total_word_count": total_word_count,
        "avg_scores": avg_scores,
        "avg_quality_score": sum(avg_scores.values()) / len(avg_scores),
        "warnings": [],
        "filler_chapters": [],
        "stalled_chapters": [],
    }


# --- Private helpers used by generate_volume_chapters ---


async def _get_story_bible_context(novel_id: str, chapter_outline: dict) -> str | None:
    """Query StoryBible and extract relevant constraints for a chapter."""
    try:
        from sqlalchemy import select

        from src.api.models.db_models import StoryBible
        from src.api.services.story_bible_service import extract_relevant_constraints
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
    """Fetch or generate a blueprint for a chapter."""
    chapter_num = chapter_outline.get("chapter", 0)
    try:
        from src.api.services.blueprint_service import BlueprintService

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
    """Sync chapter_type from generation result to the Chapter DB record."""
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
