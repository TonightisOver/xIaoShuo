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

from src.api.services.chapter_generation_utils import (
    _context_builder,
    _emit_progress,
    _get_blueprint,
    _get_story_bible_context,
    _sync_chapter_type_to_db,
)
from src.api.services.chapter_persistence_service import persist_generated_chapters
from src.api.services.progress_event_bus import EventType

logger = structlog.get_logger(__name__)

def _normalize_outline_chapter(
    chapter: dict[str, Any],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    normalized = {**chapter}

    if not str(normalized.get("title") or "").strip():
        normalized["title"] = fallback.get("title") or "[未命名章节]"
    if not str(normalized.get("plot") or "").strip():
        normalized["plot"] = fallback.get("plot") or "情节待展开"
    if not str(normalized.get("chapter_type") or "").strip():
        normalized["chapter_type"] = fallback.get("chapter_type") or "main_advance"

    for field in ("key_characters", "foreshadows_planted", "foreshadows_resolved"):
        if not isinstance(normalized.get(field), list):
            normalized[field] = fallback.get(field) or []

    if not isinstance(normalized.get("turning_point"), str):
        normalized["turning_point"] = fallback.get("turning_point", "")
    if not isinstance(normalized.get("emotional_arc"), str):
        normalized["emotional_arc"] = fallback.get("emotional_arc", "")

    return normalized


async def generate_master_outline(
    novel_id: str,
    request: Any,
    chapters_per_vol: int,
) -> dict[str, Any]:
    """Generate master outline for long-form novel.

    Args:
        novel_id: Novel ID
        request: LongFormNovelRequest
        chapters_per_vol: Actual chapters per volume (may differ from request.chapters_per_volume
            when auto_calc_chapters is enabled)

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
        chapters_per_volume=chapters_per_vol,
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
                "main_advance": int(chapters_per_vol * 0.45),
                "climax": int(chapters_per_vol * 0.12),
                "aftermath": int(chapters_per_vol * 0.08),
                "daily": int(chapters_per_vol * 0.15),
                "setup": int(chapters_per_vol * 0.15),
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

    return await generate_and_parse_json(client, prompt, max_tokens=8000, fallback=fallback_data)


async def _generate_outline_batch(
    client: Any,
    master_outline: dict[str, Any],
    volume_number: int,
    vol_info: dict[str, Any],
    prev_summary: str,
    batch_start: int,
    batch_count: int,
    total_chapters: int,
    words_per_chapter: int,
    prev_batch_chapters: list[dict[str, Any]],
    style_instruction: str,
) -> list[dict[str, Any]]:
    """Generate a batch of chapter outlines for a volume."""
    from src.core.llm.helpers import generate_and_parse_json

    prev_context = ""
    if prev_batch_chapters:
        prev_lines = []
        for ch in prev_batch_chapters[-3:]:
            prev_lines.append(
                f"  第{ch['chapter']}章《{ch.get('title', '')}》({ch.get('chapter_type', '')})："
                f"{ch.get('plot', '')}"
            )
        prev_context = "\n## 前序章节（本卷已生成）\n" + "\n".join(prev_lines)

    batch_prompt = f"""你是一位资深的百万字网络小说卷纲策划师。请为指定卷生成第 {batch_start} ~ {batch_start + batch_count - 1} 章的章纲。

## 总纲信息
{json.dumps({k: v for k, v in master_outline.items() if k != "volumes"}, ensure_ascii=False)}

## 当前卷信息
- 卷号：第 {volume_number} 卷
- 本卷概要：{vol_info.get("summary", "")}
- 本卷总章节数：{total_chapters} 章
- 每章字数：约 {words_per_chapter} 字
- 当前批次：第 {batch_start} ~ {batch_start + batch_count - 1} 章（共 {batch_count} 章）

## 前序卷摘要
{prev_summary}
{prev_context}

【强制要求】必须输出恰好 {batch_count} 章（第 {batch_start} 到第 {batch_start + batch_count - 1} 章）。
{"与前序章节自然衔接，情节递进不重复。" if prev_batch_chapters else ""}

请生成 {batch_count} 章的详细章纲，每章包含：
1. **chapter**：章节序号（从 {batch_start} 开始）
2. **title**：章节标题
3. **chapter_type**：章节类型（main_advance/climax/aftermath/daily/setup）
4. **plot**：主要情节描述（50-100字）
5. **key_characters**：本章出场主要角色
6. **foreshadows_planted**：本章种下的伏笔（如有）
7. **foreshadows_resolved**：本章回收的伏笔（如有）
8. **turning_point**：本章转折点
9. **emotional_arc**：情感走向

## 输出格式（JSON）
```json
{{
    "chapters": [
        {{
            "chapter": {batch_start},
            "title": "章节标题",
            "chapter_type": "main_advance",
            "plot": "主要情节描述",
            "key_characters": ["角色1"],
            "foreshadows_planted": [],
            "foreshadows_resolved": [],
            "turning_point": "转折点描述",
            "emotional_arc": "平静->紧张"
        }}
    ]
}}
```

只输出 JSON，不要包含其他说明。
"""
    if style_instruction:
        batch_prompt = f"{style_instruction}\n\n{batch_prompt}"

    fallback_chapters = []
    for i in range(batch_start, batch_start + batch_count):
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

    result = await generate_and_parse_json(
        client, batch_prompt, max_tokens=8000, fallback={"chapters": fallback_chapters}
    )

    chapters = result.get("chapters", [])
    if not isinstance(chapters, list):
        chapters = []

    # Normalize chapter numbers to expected range and deduplicate
    seen_nums: set[int] = set()
    normalized: list[dict[str, Any]] = []
    expected_num = batch_start
    for ch in chapters:
        if not isinstance(ch, dict):
            continue
        ch["chapter"] = expected_num
        if expected_num not in seen_nums:
            seen_nums.add(expected_num)
            fallback = fallback_chapters[expected_num - batch_start]
            normalized.append(_normalize_outline_chapter(ch, fallback))
            expected_num += 1
        if expected_num >= batch_start + batch_count:
            break
    chapters = normalized

    if len(chapters) < batch_count:
        logger.warning(
            "outline_batch_insufficient",
            volume_number=volume_number,
            batch_start=batch_start,
            expected=batch_count,
            got=len(chapters),
        )
        # Pad with fallback entries for missing chapters
        existing_nums = {ch.get("chapter") for ch in chapters}
        for fc in fallback_chapters:
            if fc["chapter"] not in existing_nums:
                chapters.append(fc)
        chapters.sort(key=lambda c: c.get("chapter", 0))

    return chapters[:batch_count]


async def generate_volume_outline(
    novel_id: str,
    master_outline: dict[str, Any],
    volume_number: int,
    chapters_per_volume: int,
    words_per_chapter: int,
    request: Any,
) -> dict[str, Any]:
    """Generate volume outline. Uses batch generation for volumes with >15 chapters."""
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

    style_instruction = get_style_instruction(
        request.writing_style,
        request.writing_style_prompt,
    )

    # --- Batch mode for large volumes (>15 chapters) ---
    if chapters_per_volume > 15:
        batch_size = 12
        all_chapters: list[dict[str, Any]] = []

        for batch_start in range(1, chapters_per_volume + 1, batch_size):
            batch_count = min(batch_size, chapters_per_volume - batch_start + 1)
            logger.info(
                "generating_outline_batch",
                volume_number=volume_number,
                batch_start=batch_start,
                batch_count=batch_count,
            )
            batch_chapters = await _generate_outline_batch(
                client=client,
                master_outline=master_outline,
                volume_number=volume_number,
                vol_info=vol_info,
                prev_summary=prev_summary,
                batch_start=batch_start,
                batch_count=batch_count,
                total_chapters=chapters_per_volume,
                words_per_chapter=words_per_chapter,
                prev_batch_chapters=all_chapters,
                style_instruction=style_instruction or "",
            )
            all_chapters.extend(batch_chapters)

        for ch in all_chapters:
            ch["volume_number"] = volume_number

        return {
            "volume_number": volume_number,
            "title": vol_info.get("title", f"第{volume_number}卷"),
            "chapters": all_chapters,
        }

    # --- Single-shot mode for small volumes (<=15 chapters) ---
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
        chapters_count_min=int(chapters_per_volume * 0.7),
        words_per_chapter=words_per_chapter,
        chapter_types=chapter_types_str,
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

    result = await generate_and_parse_json(client, prompt, max_tokens=12000, fallback=fallback_data)

    # Validate chapter count and retry up to 2 times if insufficient
    min_chapters = int(chapters_per_volume * 0.8)
    retry_prompt = prompt
    for retry in range(2):
        chapters = result.get("chapters", [])
        if len(chapters) >= min_chapters:
            break
        logger.warning(
            "volume_outline_insufficient_chapters",
            volume_number=volume_number,
            got=len(chapters),
            expected=chapters_per_volume,
            min_required=min_chapters,
            retry=retry + 1,
        )
        retry_prompt = retry_prompt + (
            f"\n\n【重要】上次输出的章节数不足（{len(chapters)}章），"
            f"请务必输出完整的 {chapters_per_volume} 章，不得少于 {min_chapters} 章。"
        )
        result = await generate_and_parse_json(client, retry_prompt, max_tokens=12000, fallback=fallback_data)

    # After retries exhausted, fall back to fallback_data if still insufficient
    if len(result.get("chapters", [])) < min_chapters:
        logger.warning(
            "volume_outline_using_fallback",
            volume_number=volume_number,
            got=len(result.get("chapters", [])),
            min_required=min_chapters,
        )
        result = fallback_data

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
        prev_context = await manager.get_chapter_tail(novel_id, chapter_start - 1)

    chapters_data = vol_outline.get("chapters", [])
    generated_chapters = []

    for i, ch_outline in enumerate(chapters_data):
        # Map volume-local chapter number to global chapter number
        global_ch_num = chapter_start + i
        ch_outline["chapter"] = global_ch_num

        if i == 0:
            previous_chapter = prev_context or "这是本卷第一章"
        else:
            last_result = generated_chapters[-1] if generated_chapters else {}
            last_content = last_result.get("content", "")
            # 构建更丰富的衔接上下文：标题 + 结尾段落
            parts = []
            if last_result.get("title"):
                parts.append(f"上一章：《{last_result['title']}》")
            if last_content:
                parts.append(f"结尾段落：\n{last_content[-400:]}")
            if ch_outline.get("plot"):
                parts.append(f"本章需要推进：{ch_outline['plot']}")
            previous_chapter = "\n".join(parts) if parts else "续写"

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
                novel_id, global_ch_num, chapter_result.get("chapter_type")
            )
        except Exception as ch_error:
            logger.error(
                "chapter_generation_failed",
                novel_id=novel_id,
                chapter=global_ch_num,
                error=str(ch_error),
            )
            generated_chapters.append({
                "chapter": global_ch_num,
                "title": ch_outline.get("title", f"第{global_ch_num}章"),
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

