"""长篇生成辅助模块

从 novel_generator.py 中提取的长篇生成相关函数：
- generate_master_outline
- generate_volume_outline
- generate_volume_chapters
- generate_volume_quality_report
"""

# ruff: noqa: E501

import asyncio
import json
import math
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


async def persist_single_chapter(
    novel_id: str,
    chapter_data: dict[str, Any],
) -> None:
    """Persist one generated chapter immediately."""
    await persist_generated_chapters(novel_id, [chapter_data], chapter_data.get("volume_number"))


async def _persist_quality_for_gate(
    novel_id: str, chapter_number: int, scores: dict, warnings: list
) -> None:
    """gate 的质量评分持久化回调。

    简化实现：仅记录日志。逐章评分持久化由后续扩展（更新 ChapterVersion.quality_scores）。
    当前不阻断——卷级报告已能处理 None 评分。
    """
    logger.info(
        "gate_quality_scores",
        novel_id=novel_id, chapter=chapter_number,
        overall=scores.get("overall"),
    )


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
        words_per_chapter=min(request.words_per_chapter, 4000),
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
    words_per_chapter = min(words_per_chapter, 4000)

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
    from src.api.services.pause_state_store import get_pause_state_store
    from src.core.database import get_db_session
    from src.core.llm.chapter_generator import (
        CHAPTER_WORD_HARD_CAP,
        generate_chapter_stream,
    )
    from src.core.llm.client import get_llm_client

    manager = get_novel_manager()
    client = get_llm_client()
    pause_store = get_pause_state_store()
    words_per_chapter = min(words_per_chapter, CHAPTER_WORD_HARD_CAP)

    # CHANGE-059: bounded concurrent prefetch of StoryBible context for
    # upcoming chapters (prefetch_window ahead of the serial generation loop).
    prefetch_window = 3
    prefetched_contexts: dict[int, Any] = {}
    sem = asyncio.Semaphore(prefetch_window)

    async def _prefetch_one(idx: int) -> None:
        async with sem:
            try:
                async with get_db_session() as session:
                    ctx = await _context_builder.build_generation_context(
                        session, novel_id
                    )
                    prefetched_contexts[idx] = ctx
            except Exception as exc:  # pragma: no cover - prefetch is best-effort
                logger.warning(
                    "long_form_prefetch_failed",
                    novel_id=novel_id,
                    idx=idx,
                    error=str(exc),
                )

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
    existing_chapters = await manager.list_chapters(novel_id)
    generated_word_count = sum(
        ch.get("word_count", 0)
        for ch in existing_chapters
        if ch.get("chapter", 0) < chapter_start
    )
    total_chapters = max(
        chapter_end,
        getattr(request, "volumes", 1) * max(chapter_end - chapter_start + 1, 1),
    )
    target_total_words = getattr(request, "target_words", 0) or 0

    for i, ch_outline in enumerate(chapters_data):
        # Map volume-local chapter number to global chapter number
        global_ch_num = chapter_start + i
        ch_outline["chapter"] = global_ch_num

        while await pause_store.is_paused(task_id):
            await asyncio.sleep(1)

        if i == 0:
            previous_chapter = prev_context or "这是本卷第一章"
        else:
            last_result = generated_chapters[-1] if generated_chapters else {}
            # 构建更丰富的衔接上下文：标题 + 结尾段落
            parts = []
            if last_result.get("title"):
                parts.append(f"上一章：《{last_result['title']}》")
            last_delta = last_result.get("state_delta")
            if last_delta and not last_delta.get("_unverified"):
                from src.core.quality.state_delta import merge_delta_for_context
                merged = merge_delta_for_context(last_delta, {})
                if merged:
                    parts.append(merged)
            else:
                last_content = last_result.get("content", "")
                if last_content:
                    parts.append(f"结尾段落：\n{last_content[-400:]}")
            if ch_outline.get("plot"):
                parts.append(f"本章需要推进：{ch_outline['plot']}")
            previous_chapter = "\n".join(parts) if parts else "续写"

        try:
            # Prepare story bible context and blueprint
            story_bible_ctx = await _get_story_bible_context(novel_id, ch_outline)
            bp = await _get_blueprint(novel_id, ch_outline)

            async def on_token(token: str, accumulated: str) -> None:
                await _emit_progress(task_id, EventType.CHAPTER_TOKEN, {
                    "chapter": global_ch_num,
                    "token": token,
                    "accumulated_length": len(accumulated),
                })

            async def on_complete(full_text: str) -> None:
                return None

            async def pause_checker() -> bool:
                return await pause_store.is_paused(task_id)

            remaining_words = max(target_total_words - generated_word_count, 0)
            is_final_chapter = global_ch_num >= total_chapters
            if target_total_words <= 0:
                chapter_target_words = words_per_chapter
            elif is_final_chapter:
                chapter_target_words = remaining_words
            else:
                remaining_chapters = max(total_chapters - global_ch_num + 1, 1)
                chapter_target_words = min(
                    CHAPTER_WORD_HARD_CAP,
                    max(1, math.ceil(remaining_words / remaining_chapters)),
                )

            chapter_result = await generate_chapter_stream(
                client=client,
                chapter_outline=ch_outline,
                previous_chapter=previous_chapter,
                characters_json=chars_str,
                world_setting_json=world_str,
                on_token=on_token,
                on_complete=on_complete,
                style_instruction=style_instruction,
                target_words=chapter_target_words,
                novel_id=novel_id,
                blueprint=bp,
                story_bible_context=story_bible_ctx,
                pause_checker=pause_checker,
            )
            chapter_result["volume_number"] = volume_number
            generated_chapters.append(chapter_result)
            generated_word_count += chapter_result.get("word_count", 0)
            # 先落库章节行，使质量门禁的 update_state_delta /
            # update_quality_status 回调能 UPDATE 到已存在的 Chapter 行。
            # ⚠️ L3 改善由 rewrite_service.auto_improve_chapter 自行激活候选并
            # 写回 Chapter.content（在 gate 内完成），晚于本 persist，不会互相覆盖。
            persisted_by_gate = False
            if not chapter_result.get("generation_failed"):
                await persist_single_chapter(novel_id, chapter_result)
                # === 质量门禁漏斗：抽取state_delta → L0 → L1 → L2 → L3 ===
                try:
                    from src.api.services.rewrite_loop_service import RewriteLoopService
                    from src.core.quality.gate import (
                        GatePersistCallbacks,
                        run_quality_gate,
                    )

                    gate_callbacks = GatePersistCallbacks(
                        update_state_delta=manager.update_state_delta,
                        update_quality_status=manager.update_quality_status,
                        persist_quality_scores=_persist_quality_for_gate,
                        detect_bible_conflicts=None,
                    )
                    gate_result = await run_quality_gate(
                        novel_id=novel_id,
                        chapter_number=global_ch_num,
                        chapter_result=chapter_result,
                        chapter_outline=ch_outline,
                        novel_type=getattr(request, "novel_type", "网络小说"),
                        idea=getattr(request, "idea", ""),
                        world_setting=world_str,
                        characters=chars_str,
                        persist_callbacks=gate_callbacks,
                        rewrite_service=RewriteLoopService(),
                        chapter_index_in_volume=i,
                    )
                    chapter_result["quality_status"] = gate_result.quality_status
                    chapter_result["quality_scores"] = gate_result.quality_scores
                    chapter_result["state_delta"] = gate_result.state_delta
                    if gate_result.rewrite_improved:
                        persisted_by_gate = True
                except Exception as gate_err:
                    logger.warning(
                        "quality_gate_failed_non_fatal",
                        novel_id=novel_id, chapter=global_ch_num, error=str(gate_err),
                    )
            # === 漏斗结束 ===
            # 失败章节在此落库（上面成功章节已在 gate 前落库）
            if chapter_result.get("generation_failed") and not persisted_by_gate:
                await persist_single_chapter(novel_id, chapter_result)

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

    return generated_chapters


async def generate_volume_quality_report(
    novel_id: str,
    volume_number: int,
    chapters: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate quality report for a volume based on real L0 rule checks.

    不再返回固定 0.7 假分。失败/异常章节标记为 unverified，告警非空。
    真实的多维 LLM 评分由 quality_check 节点逐章持久化，此处汇总已存评分 +
    对每章跑 L0 规则门禁。
    """
    from src.api.services.novel_manager import get_novel_manager
    from src.core.quality.rules import run_l0_rules

    total_word_count = sum(ch.get("word_count", 0) for ch in chapters)
    chapter_count = len(chapters)

    warnings: list[dict[str, Any]] = []
    unverified_chapters: list[dict[str, Any]] = []
    filler_chapters: list[dict[str, Any]] = []
    stalled_chapters: list[dict[str, Any]] = []

    # 计算本卷平均字数用于灌水判断
    avg_word = (total_word_count / chapter_count) if chapter_count else 0

    # 收集已持久化的逐章评分（若存在）
    persisted_scores: dict[int, dict[str, float]] = {}
    try:
        manager = get_novel_manager()
        for ch in chapters:
            ch_num = ch.get("chapter")
            if not ch_num:
                continue
            scores = await _get_persisted_chapter_scores(manager, novel_id, ch_num)
            if scores:
                persisted_scores[ch_num] = scores
    except Exception:
        # 评分获取失败不应阻断报告生成
        pass

    dimension_keys = [
        "advancement", "character_consistency", "world_consistency",
        "pacing", "conflict", "foreshadowing", "dialogue_quality",
        "emotional_impact",
    ]

    for ch in chapters:
        ch_num = ch.get("chapter")
        content = ch.get("content", "") or ""
        word_count = ch.get("word_count", 0) or len(content)
        title = ch.get("title", f"第{ch_num}章")

        # 1. 失败章 → unverified + 告警
        if ch.get("generation_failed") or ch.get("paused"):
            reason = "paused" if ch.get("paused") and not ch.get("generation_failed") else "generation_failed"
            unverified_chapters.append({"chapter": ch_num, "title": title, "reason": reason})
            warn_type = "paused" if ch.get("paused") and not ch.get("generation_failed") else "generation_failed"
            warn_msg = f"第{ch_num}章" + ("已暂停，质量未评估" if reason == "paused" else "生成失败，质量未评估")
            warnings.append({
                "chapter": ch_num, "title": title,
                "severity": "error", "type": warn_type,
                "message": warn_msg,
            })
            continue

        # 2. L0 规则门禁
        l0 = run_l0_rules(
            content=content,
            word_count=word_count,
            avg_word_count=avg_word,
            chapter_outline=ch.get("outline") or ch.get("plot"),
            chapter_number=ch_num,
        )
        for v in l0.get("violations", []):
            warnings.append({
                "chapter": ch_num, "title": title,
                "severity": v.get("severity", "warning"),
                "type": v.get("type"),
                "message": v.get("message"),
            })
        if l0.get("filler_flag"):
            filler_chapters.append({"chapter": ch_num, "title": title, "score": l0.get("filler_score", 0)})
        if l0.get("stalled_flag"):
            stalled_chapters.append({"chapter": ch_num, "title": title})

    # 汇总分数：仅基于已持久化的真实评分，未评估的维度不伪造
    has_unverified = bool(unverified_chapters)
    if persisted_scores:
        dim_sums: dict[str, list[float]] = {k: [] for k in dimension_keys}
        for sc in persisted_scores.values():
            for k in dimension_keys:
                v = sc.get(k)
                if isinstance(v, (int, float)):
                    dim_sums[k].append(float(v))
        # 只包含已评估维度（有真实值），未评估维度不出现在 dict 中
        # 下游 .get(dim, 0) 对缺失 key 返回 0，区分"未评估"与"评了 0 分"由 dim 是否在 dict 决定
        avg_scores = {
            k: round(sum(v) / len(v), 4)
            for k, v in dim_sums.items() if v
        }
        if avg_scores:
            avg_quality_score = round(sum(avg_scores.values()) / len(avg_scores), 4)
        else:
            avg_quality_score = None
    else:
        # 无任何持久化评分：avg_scores 为空 dict，avg_quality_score 为 None
        avg_scores = {}
        avg_quality_score = None

    return {
        "volume_number": volume_number,
        "chapter_count": chapter_count,
        "total_word_count": total_word_count,
        "avg_scores": avg_scores,
        "avg_quality_score": avg_quality_score,
        "has_unverified": has_unverified,
        "unverified_chapters": unverified_chapters,
        "warnings": warnings,
        "filler_chapters": filler_chapters,
        "stalled_chapters": stalled_chapters,
    }


async def _get_persisted_chapter_scores(
    manager, novel_id: str, chapter_number: int
) -> dict[str, float] | None:
    """从持久层获取单章已存评分。优先读多维 quality_scores，回退单数 quality_score。

    无评分/异常返回 None，触发"未评估"语义，绝不伪造 0.7。
    """
    try:
        versions = await manager.list_chapter_versions(novel_id, chapter_number)
        for v in versions:
            multi = v.get("quality_scores")
            if isinstance(multi, dict) and multi:
                # 复数多维：直接返回（key 应含 advancement 等维度）
                return {k: float(val) for k, val in multi.items() if isinstance(val, (int, float))}
            qs = v.get("quality_score")
            if isinstance(qs, (int, float)):
                return {"overall": float(qs)}
        return None
    except Exception:
        return None

