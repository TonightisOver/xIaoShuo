"""小说生成服务

负责执行小说生成任务，通过事件总线推送实时进度。
"""

import math
from typing import Any

import structlog

from src.api.models.requests import CreateNovelRequest
from src.api.services.chapter_persistence_service import (
    persist_chapters_with_replace,
    persist_generated_chapters,
    persist_langgraph_result,
    persist_quality_to_version,
)
from src.api.services.long_form_generation_helpers import (
    generate_master_outline,
    generate_volume_chapters,
    generate_volume_outline,
    generate_volume_quality_report,
)
from src.api.services.long_form_progress_service import get_long_form_progress_service
from src.api.services.novel_context_service import NovelContextBuilder
from src.api.services.novel_manager import get_novel_manager
from src.api.services.progress_event_bus import (
    EventType,
    ProgressEvent,
    get_event_bus,
)
from src.api.services.task_manager import get_task_manager
from src.core.langgraph.graph import create_novel_graph

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
    """Emit a progress event and optionally update task status.

    Reduces repetitive event_bus.publish + task_manager.update_status patterns.
    """
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


async def _prepare_chapter_context(
    novel_id: str, chapter_outline: dict
) -> tuple[str | None, dict | None]:
    """Prepare story_bible_context and blueprint for a chapter.

    This combines _get_story_bible_context and _get_blueprint into a single
    callable suitable for injection into the chapter_generation node.

    Returns:
        (story_bible_context, blueprint)
    """
    story_bible_ctx = await _get_story_bible_context(novel_id, chapter_outline)
    bp = await _get_blueprint(novel_id, chapter_outline)
    return story_bible_ctx, bp


async def _persist_quality_to_version(
    novel_id: str, chapter_number: int, quality_scores: dict, consistency_warnings: list
) -> None:
    """将质量评分回写到章节的活跃版本记录 (delegates to persistence service)"""
    await persist_quality_to_version(
        novel_id, chapter_number, quality_scores, consistency_warnings,
    )

STAGE_ORDER = [
    "idea_expansion",
    "world_building",
    "character_design",
    "outline_generation",
    "chapter_generation",
    "quality_check",
    "human_review",
]


async def _build_initial_state(
    task_id: str,
    request: CreateNovelRequest,
) -> tuple[dict[str, Any], str | None]:
    """构建 LangGraph 初始状态，注入已有设定。

    Returns:
        (initial_state, novel_id)
    """
    initial_state: dict[str, Any] = {
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

    task_manager = get_task_manager()
    task_data = await task_manager.get_task(task_id)
    novel_id = task_data.get("novel_id") if task_data else None
    initial_state["novel_id"] = novel_id
    if novel_id:
        novel_manager = get_novel_manager()
        existing_world = await novel_manager.get_world_setting(novel_id)
        existing_chars = await novel_manager.list_characters(novel_id)
        ws_keys = ["background", "rules", "culture", "geography"]
        if existing_world and any(existing_world.get(k) for k in ws_keys):
            initial_state["world_setting"] = existing_world
        if existing_chars:
            initial_state["characters"] = existing_chars
        from src.api.services.storyline_service import get_storyline_service
        sl_service = get_storyline_service()
        storylines = await sl_service.list_storylines(novel_id)
        if storylines:
            sl_parts = [
                f"- [{sl['type']}] {sl['name']}: {sl.get('description', '')}"
                for sl in storylines
            ]
            sl_context = "\n".join(sl_parts)
            initial_state["idea"] = f"{request.idea}\n\n已确定的故事线：\n{sl_context}"

    return initial_state, novel_id


async def generate_novel_background(
    task_id: str, request: CreateNovelRequest
) -> None:
    """后台执行小说生成"""
    task_manager = get_task_manager()
    novel_id: str | None = None

    try:
        await task_manager.update_status(task_id, "running")
        await _emit_progress(
            task_id, EventType.STAGE_START,
            {"stage": "idea_expansion", "percentage": 0},
        )

        logger.info("novel_generation_starting", task_id=task_id)

        initial_state, novel_id = await _build_initial_state(task_id, request)

        result = await _run_langgraph_pipeline(
            task_id, initial_state, stage_offset=0, total_stages=len(STAGE_ORDER),
        )

        await task_manager.complete_task(task_id, result)

        if novel_id:
            await _persist_to_novel(novel_id, result)

        await _emit_progress(
            task_id, EventType.COMPLETED,
            {"percentage": 100, "current_stage": "completed"},
        )

        logger.info(
            "novel_generation_completed",
            task_id=task_id,
            chapters=len(result.get("chapters", [])),
        )

    except Exception as e:
        logger.exception("novel_generation_failed", task_id=task_id)
        await task_manager.fail_task(task_id, str(e))
        await _emit_progress(task_id, EventType.ERROR, {"error": str(e)})
        if novel_id:
            try:
                from src.api.services.novel_manager import get_novel_manager
                await get_novel_manager().update_novel(novel_id, status="failed")
            except Exception as ne:
                logger.error("failed_to_update_novel_status", novel_id=novel_id, error=str(ne))


FULL_GENERATE_STAGES = [
    "idea_expansion",
    "world_building",
    "character_design",
    "outline_generation",
    "chapter_generation",
    "quality_check",
    "human_review",
    "power_systems",
    "outline_persist",
    "storylines",
    "character_arcs",
    "scenes",
    "auto_conversation",
]


def _full_generate_percentage(stage_index: int, total_stages: int | None = None) -> int:
    """Calculate percentage for a stage index (0-based).

    Args:
        stage_index: 0-based index of the current stage.
        total_stages: Override total stage count (defaults to len(FULL_GENERATE_STAGES)).
    """
    total = total_stages if total_stages is not None else len(FULL_GENERATE_STAGES)
    return int(((stage_index + 1) / total) * 100)


async def _run_langgraph_pipeline(
    task_id: str,
    initial_state: dict[str, Any],
    stage_offset: int = 0,
    total_stages: int | None = None,
) -> dict[str, Any]:
    """Run the LangGraph 7-node pipeline, emitting progress events.

    Args:
        task_id: Task identifier for progress tracking.
        initial_state: Initial state dict.
        stage_offset: How many stages to skip in percentage calculation
                      (for when LangGraph is part of a larger pipeline).
        total_stages: Override total stage count for percentage calculation.
                      Defaults to len(FULL_GENERATE_STAGES).

    Returns:
        The final state from the LangGraph execution.
    """
    task_manager = get_task_manager()
    event_bus = get_event_bus()
    graph = create_novel_graph()

    async def _chapter_progress_callback(data: dict[str, Any]) -> None:
        total = max(data.get("total_chapters", 1), 1)
        completed = data.get("completed_chapters", 0)
        successful = data.get("successful_chapters", completed)
        failed = data.get("failed_chapters", 0)
        base = _full_generate_percentage(stage_offset + 3, total_stages)
        span = _full_generate_percentage(stage_offset + 4, total_stages) - base
        pct = base + int((completed / total) * span)
        progress_data = {
            "current_stage": "chapter_generation",
            "completed_chapters": completed,
            "successful_chapters": successful,
            "failed_chapters": failed,
            "total_chapters": total,
            "percentage": pct,
        }
        await task_manager.update_status(task_id, "running", progress=progress_data)
        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.CHAPTER_PROGRESS,
            data=progress_data,
        ))

    # Build configurable dict with injected dependencies for LangGraph nodes
    from src.api.services.knowledge_graph_service import get_knowledge_graph_service
    from src.api.services.story_bible_service import detect_bible_conflicts
    from src.core.config import get_settings

    settings = get_settings()
    kg_service = (
        get_knowledge_graph_service()
        if settings.KNOWLEDGE_GRAPH_ENABLED
        else None
    )

    configurable: dict[str, Any] = {
        "thread_id": task_id,
        # chapter_generation node dependencies
        "kg_service": kg_service,
        "progress_callback": _chapter_progress_callback,
        "prepare_chapter_context": _prepare_chapter_context,
        "sync_chapter_type": _sync_chapter_type_to_db,
        # quality_check node dependencies
        "detect_bible_conflicts": detect_bible_conflicts,
        "persist_quality": _persist_quality_to_version,
    }

    result: dict[str, Any] = {}
    try:
        config = {"configurable": configurable}
        async for event in graph.astream(initial_state, config=config):
            for node_name, state_update in event.items():
                result = state_update
                if node_name in STAGE_ORDER:
                    node_idx = STAGE_ORDER.index(node_name)
                else:
                    node_idx = -1
                if node_idx < 0:
                    continue
                percentage = _full_generate_percentage(stage_offset + node_idx, total_stages)

                progress_data = {
                    "current_stage": node_name,
                    "completed_chapters": len(state_update.get("chapters", [])),
                    "total_chapters": len(state_update.get("chapter_outlines", [])),
                    "percentage": percentage,
                }
                await task_manager.update_status(
                    task_id, "running", progress=progress_data,
                )
                await event_bus.publish(ProgressEvent(
                    task_id=task_id,
                    event_type=EventType.STAGE_COMPLETE,
                    data=progress_data,
                ))
                if 0 <= node_idx < len(STAGE_ORDER) - 1:
                    next_stage = STAGE_ORDER[node_idx + 1]
                    await event_bus.publish(ProgressEvent(
                        task_id=task_id,
                        event_type=EventType.STAGE_START,
                        data={"stage": next_stage, "percentage": percentage},
                    ))
    finally:
        pass  # No callback registry cleanup needed; callback is local

    return result


async def generate_novel_full_background(
    task_id: str, request: CreateNovelRequest,
) -> None:
    """后台执行小说全功能生成（13 阶段流水线）。

    Stages 1-7:  LangGraph 7-node pipeline
    Stage 8:  力量体系 AI 生成
    Stage 9:  总纲生成 + 大纲持久化
    Stage 10: 故事线 AI 生成
    Stage 11: 人物弧光 AI 生成
    Stage 12: 场景 AI 生成
    Stage 13: 自动创作对话
    """
    task_manager = get_task_manager()
    novel_id: str | None = None

    try:
        await task_manager.update_status(task_id, "running")

        logger.info("full_generation_starting", task_id=task_id)

        # --- Build initial state ---
        initial_state, novel_id = await _build_initial_state(task_id, request)

        # --- Stage 1-7: Run LangGraph pipeline ---
        await _emit_progress(
            task_id, EventType.STAGE_START,
            {"stage": "idea_expansion", "percentage": 0},
        )

        result = await _run_langgraph_pipeline(task_id, initial_state, stage_offset=0)

        # Persist to novel
        if novel_id:
            await _persist_to_novel(novel_id, result)

        # --- Stages 8-13: Additional AI generation ---
        await _run_sub_feature(
            task_id=task_id, novel_id=novel_id, result=result, request=request,
            feature_index=7,  # power_systems is stage 8 (0-indexed 7)
            feature_name="power_systems",
            label="力量体系",
        )

        await _run_sub_feature(
            task_id=task_id, novel_id=novel_id, result=result, request=request,
            feature_index=8,  # outline_persist is stage 9
            feature_name="outline_persist",
            label="大纲生成与持久化",
        )

        await _run_sub_feature(
            task_id=task_id, novel_id=novel_id, result=result, request=request,
            feature_index=9,  # storylines is stage 10
            feature_name="storylines",
            label="故事线生成",
        )

        await _run_sub_feature(
            task_id=task_id, novel_id=novel_id, result=result, request=request,
            feature_index=10,  # character_arcs is stage 11
            feature_name="character_arcs",
            label="人物弧光",
        )

        await _run_sub_feature(
            task_id=task_id, novel_id=novel_id, result=result, request=request,
            feature_index=11,  # scenes is stage 12
            feature_name="scenes",
            label="场景生成",
        )

        await _run_sub_feature(
            task_id=task_id, novel_id=novel_id, result=result, request=request,
            feature_index=12,  # auto_conversation is stage 13
            feature_name="auto_conversation",
            label="自动对话",
        )

        # Final completion
        await task_manager.complete_task(task_id, result)
        await _emit_progress(
            task_id, EventType.COMPLETED,
            {"percentage": 100, "current_stage": "completed", "pipeline": "full"},
        )

        logger.info("full_generation_completed", task_id=task_id)

    except Exception as e:
        logger.exception("full_generation_failed", task_id=task_id)
        await task_manager.fail_task(task_id, str(e))
        await _emit_progress(task_id, EventType.ERROR, {"error": str(e)})
        if novel_id:
            try:
                from src.api.services.novel_manager import get_novel_manager
                await get_novel_manager().update_novel(novel_id, status="failed")
            except Exception as ne:
                logger.error("failed_to_update_novel_status", novel_id=novel_id, error=str(ne))


async def _run_sub_feature(
    task_id: str,
    novel_id: str | None,
    result: dict[str, Any],
    request: CreateNovelRequest,
    feature_index: int,
    feature_name: str,
    label: str,
) -> None:
    """Execute a single sub-feature generation step with progress events.

    Each sub-feature runs in its own try-catch so failure does not block
    subsequent features.
    """
    from src.api.services.ai_generation_service import get_ai_generation_service
    from src.api.services.conversation_service import get_conversation_service
    from src.api.services.outline_service import get_outline_service

    task_manager = get_task_manager()

    percentage = _full_generate_percentage(feature_index)

    await _emit_progress(
        task_id, EventType.SUB_FEATURE_START,
        {"feature": feature_name, "label": label, "percentage": percentage},
    )

    try:
        if feature_name == "power_systems" and novel_id:
            ai_service = get_ai_generation_service()
            ps_result = await ai_service.generate_power_systems_ai(novel_id)
            await _emit_progress(task_id, EventType.SUB_FEATURE_COMPLETE, {
                "feature": feature_name, "label": label,
                "percentage": percentage, "count": len(ps_result),
            })

        elif feature_name == "outline_persist" and novel_id:
            outline_service = get_outline_service()
            await outline_service.generate_master_from_novel(novel_id)
            try:
                await outline_service.generate_volume_outlines(
                    novel_id, request.novel_type, request.target_words,
                )
            except Exception:
                logger.warning(
                "Volume outline generation failed, continuing", exc_info=True,
            )
            persist_result = await outline_service.persist_outlines_from_result(novel_id, result)
            await _emit_progress(task_id, EventType.SUB_FEATURE_COMPLETE, {
                "feature": feature_name, "label": label,
                "percentage": percentage, **persist_result,
            })

        elif feature_name == "storylines" and novel_id:
            ai_service = get_ai_generation_service()
            sl_result = await ai_service.generate_storylines_ai(novel_id)
            await _emit_progress(task_id, EventType.SUB_FEATURE_COMPLETE, {
                "feature": feature_name, "label": label,
                "percentage": percentage, "count": len(sl_result),
            })

        elif feature_name == "character_arcs" and novel_id:
            ai_service = get_ai_generation_service()
            arc_result = await ai_service.generate_arcs_ai(novel_id)
            await _emit_progress(task_id, EventType.SUB_FEATURE_COMPLETE, {
                "feature": feature_name, "label": label,
                "percentage": percentage, "count": len(arc_result),
            })

        elif feature_name == "scenes" and novel_id:
            ai_service = get_ai_generation_service()
            scene_result = await ai_service.generate_scenes_ai(novel_id)
            await _emit_progress(task_id, EventType.SUB_FEATURE_COMPLETE, {
                "feature": feature_name, "label": label,
                "percentage": percentage, "count": len(scene_result),
            })

        elif feature_name == "auto_conversation" and novel_id:
            conv_service = get_conversation_service()
            conv_result = await conv_service.generate_auto_conversation(novel_id)
            await _emit_progress(task_id, EventType.SUB_FEATURE_COMPLETE, {
                "feature": feature_name, "label": label,
                "percentage": percentage,
                "conversation_id": conv_result.get("conversation_id"),
            })

        # Update progress after sub-feature completion
        await task_manager.update_status(task_id, "running", progress={
            "current_stage": feature_name,
            "percentage": percentage,
            "completed_chapters": len(result.get("chapters", [])),
            "total_chapters": len(result.get("chapter_outlines", [])),
        })

    except Exception as e:
        logger.warning(f"Sub-feature '{feature_name}' failed (non-blocking): {e}", exc_info=True)
        await _emit_progress(task_id, EventType.ERROR, {
            "feature": feature_name, "label": label, "error": str(e), "non_blocking": True,
        })


async def _generate_chapters_batch(
    task_id: str,
    novel_id: str,
    chapter_outlines: list[dict],
    prev_context: str,
    default_previous_text: str = "这是起始章节",
) -> list[dict]:
    """Unified chapter generation loop used by volume and range generators.

    Iterates over chapter_outlines, generates each chapter sequentially,
    emits progress, syncs chapter_type, and returns the list of generated chapters.

    Args:
        task_id: Task identifier for progress events.
        novel_id: Novel identifier.
        chapter_outlines: Ordered list of chapter outline dicts
            (must have "chapter" key).
        prev_context: Text context from previous chapters
            (before the first outline).
        default_previous_text: Fallback text when prev_context is empty
            for the first chapter.

    Returns:
        List of generated chapter result dicts.
    """
    from src.core.database import get_db_session
    from src.core.llm.chapter_generator import generate_single_chapter
    from src.core.llm.client import get_llm_client

    client = get_llm_client()

    # Build context via NovelContextBuilder
    async with get_db_session() as session:
        gen_ctx = await _context_builder.build_generation_context(session, novel_id)

    chars_str = gen_ctx.chars_str
    world_str = gen_ctx.world_str
    sl_str = gen_ctx.storylines_str
    style_instruction = gen_ctx.style_instruction

    total_chapters = len(chapter_outlines)
    generated_chapters: list[dict] = []

    for i, ch_outline in enumerate(chapter_outlines):
        # Determine previous chapter text with richer context for continuity
        if i == 0:
            previous_chapter = prev_context
        else:
            last_result = generated_chapters[-1]
            last_content = last_result.get("content") or ""
            parts = []
            if last_result.get("title"):
                parts.append(f"上一章：《{last_result['title']}》")
            if last_content:
                parts.append(f"结尾段落：\n{last_content[-400:]}")
            if ch_outline.get("plot"):
                parts.append(f"本章需要推进：{ch_outline['plot']}")
            previous_chapter = "\n".join(parts) if parts else last_content[:500]

        # Prepare story bible context and blueprint
        story_bible_ctx = await _get_story_bible_context(novel_id, ch_outline)
        bp = await _get_blueprint(novel_id, ch_outline)

        chapter_result = await generate_single_chapter(
            client=client,
            chapter_outline=ch_outline,
            previous_chapter=previous_chapter or default_previous_text,
            characters_json=chars_str,
            world_setting_json=world_str,
            storylines_json=sl_str,
            style_instruction=style_instruction,
            novel_id=novel_id,
            blueprint=bp,
            story_bible_context=story_bible_ctx,
        )
        generated_chapters.append(chapter_result)

        # Sync chapter_type to DB
        ch_num = ch_outline.get("chapter", i + 1)
        await _sync_chapter_type_to_db(
            novel_id, ch_num, chapter_result.get("chapter_type")
        )

        # Emit progress
        progress_data = {
            "current_stage": "chapter_generation",
            "completed_chapters": len(generated_chapters),
            "total_chapters": total_chapters,
            "percentage": int((len(generated_chapters) / total_chapters) * 100),
        }
        await _emit_progress(
            task_id, EventType.CHAPTER_PROGRESS, progress_data, update_status=True,
        )

    return generated_chapters


async def generate_volume_background(
    task_id: str, novel_id: str, volume_number: int
) -> None:
    """按卷生成章节内容"""
    task_manager = get_task_manager()
    novel_manager = get_novel_manager()

    try:
        await task_manager.update_status(task_id, "running")

        vol = await novel_manager.get_volume(novel_id, volume_number)
        if not vol or not vol.get("outline"):
            # Fallback: try outlines table for volume/chapter data
            from src.api.services.outline_service import get_outline_service
            outline_svc = get_outline_service()
            vol_outlines = await outline_svc.get_volume_outlines(novel_id)
            outline_vol = next((v for v in vol_outlines if v["volume_number"] == volume_number), None)
            if not outline_vol or not outline_vol.get("content"):
                raise ValueError(f"Volume {volume_number} has no outline")
            chapters_from_outline = await outline_svc.get_chapter_outlines(novel_id, volume_number)
            if chapters_from_outline:
                chapters_data = [{
                    "chapter": ch["chapter_number"],
                    "title": (ch.get("content") or {}).get("title", f"第{ch['chapter_number']}章"),
                    "plot": (ch.get("content") or {}).get("turning_point", ""),
                    "scenes": (ch.get("content") or {}).get("scenes", []),
                } for ch in chapters_from_outline]
            else:
                # Use volume outline's own chapter list
                chapters_data = outline_vol["content"].get("chapters", [])
            vol = {"outline": {"chapters": chapters_data}}
        else:
            chapters_data = vol["outline"].get("chapters", [])

        # Fetch context: previous chapters from earlier volumes
        prev_context = ""
        prev_chapters = await novel_manager.list_chapters(novel_id)
        prev_in_earlier_vols = [c for c in prev_chapters if (c.get("volume_number") or 0) < volume_number]
        if prev_in_earlier_vols:
            last_ch = prev_in_earlier_vols[-1]
            prev_context = f"前文最后一章《{last_ch.get('title', '')}》结尾：{(last_ch.get('content', '') or '')[-500:]}"

        # Generate chapters using unified batch function
        generated_chapters = await _generate_chapters_batch(
            task_id=task_id,
            novel_id=novel_id,
            chapter_outlines=chapters_data,
            prev_context=prev_context,
            default_previous_text="这是本卷第一章",
        )

        # Persist chapters to DB
        await persist_generated_chapters(novel_id, generated_chapters, volume_number)

        await novel_manager.update_volume(novel_id, volume_number, status="completed")
        await task_manager.complete_task(task_id, {"chapters": generated_chapters})
        await _emit_progress(
            task_id, EventType.COMPLETED,
            {"percentage": 100, "volume_number": volume_number},
        )

        logger.info(
            "volume_generation_completed",
            novel_id=novel_id,
            volume_number=volume_number,
        )

    except Exception as e:
        logger.exception("volume_generation_failed", error=str(e))
        await task_manager.fail_task(task_id, str(e))
        await novel_manager.update_volume(novel_id, volume_number, status="failed")
        await _emit_progress(task_id, EventType.ERROR, {"error": str(e)})


async def generate_chapters_background(
    task_id: str, novel_id: str, chapter_start: int, chapter_end: int
) -> None:
    """按章节范围生成"""
    task_manager = get_task_manager()
    novel_manager = get_novel_manager()

    try:
        await task_manager.update_status(task_id, "running")

        all_chapters = await novel_manager.list_chapters(novel_id)

        prev_context = ""
        if chapter_start > 1:
            prev_chs = [c for c in all_chapters if c["chapter_number"] == chapter_start - 1]
            if prev_chs:
                prev_context = (prev_chs[0].get("content", "") or "")[-500:]

        # Build ordered chapter outlines for the requested range
        volumes = await novel_manager.list_volumes(novel_id)
        all_outlines = []
        for vol in volumes:
            outline = vol.get("outline") or {}
            for ch in outline.get("chapters", []):
                all_outlines.append(ch)

        chapter_outlines_for_range = []
        for ch_num in range(chapter_start, chapter_end + 1):
            ch_outline = next(
                (co for co in all_outlines if co.get("chapter") == ch_num),
                {"chapter": ch_num, "title": f"第{ch_num}章", "plot": "续写情节", "words": 5000},
            )
            chapter_outlines_for_range.append(ch_outline)

        # Generate chapters using unified batch function
        generated_chapters = await _generate_chapters_batch(
            task_id=task_id,
            novel_id=novel_id,
            chapter_outlines=chapter_outlines_for_range,
            prev_context=prev_context,
            default_previous_text="这是起始章节",
        )

        # Persist chapters (replace existing, create versions, update StoryBible)
        await persist_chapters_with_replace(novel_id, generated_chapters, volumes)

        await task_manager.complete_task(task_id, {"chapters": generated_chapters})
        await _emit_progress(
            task_id, EventType.COMPLETED,
            {"percentage": 100, "chapter_start": chapter_start, "chapter_end": chapter_end},
        )

        logger.info(
            "chapters_generation_completed",
            novel_id=novel_id,
            chapter_start=chapter_start,
            chapter_end=chapter_end,
        )

    except Exception as e:
        logger.exception("chapters_generation_failed", error=str(e))
        await task_manager.fail_task(task_id, str(e))
        await _emit_progress(task_id, EventType.ERROR, {"error": str(e)})


async def _persist_to_novel(novel_id: str, result: dict[str, Any]) -> None:
    """Persist LangGraph result (delegates to persistence service)."""
    manager = get_novel_manager()
    await persist_langgraph_result(novel_id, result, manager=manager)


async def generate_long_form_background(
    task_id: str,
    novel_id: str,
    request: Any,
) -> None:
    """后台执行百万字长篇生成

    流程：
    1. 生成总纲（master_outline）
    2. 逐卷执行卷纲细化 + 卷内7节点流水线
    3. 每卷完成后生成质量报告
    4. 全部完成后生成最终报告

    Args:
        task_id: Task ID
        novel_id: Novel ID
        request: LongFormNovelRequest
    """
    task_manager = get_task_manager()
    progress_service = get_long_form_progress_service()

    try:
        await task_manager.update_status(task_id, "running")

        logger.info("long_form_generation_starting", task_id=task_id, novel_id=novel_id)

        # T1: 自动计算每卷章节数（必须在 initialize_progress / update_novel 之前）
        total_volumes = request.volumes
        words_per_chapter = request.words_per_chapter

        if request.auto_calc_chapters:
            total_chapters = math.ceil(request.target_words / request.words_per_chapter)
            computed_chapters_per_vol = math.ceil(total_chapters / request.volumes)
            chapters_per_vol = max(20, min(60, computed_chapters_per_vol))
            if chapters_per_vol != computed_chapters_per_vol:
                logger.warning(
                    "auto_calc_chapters_clamped",
                    computed=computed_chapters_per_vol,
                    clamped=chapters_per_vol,
                    target_words=request.target_words,
                    words_per_chapter=request.words_per_chapter,
                    volumes=request.volumes,
                )
            logger.info(
                "auto_calc_chapters",
                target_words=request.target_words,
                words_per_chapter=request.words_per_chapter,
                total_chapters=total_chapters,
                chapters_per_vol=chapters_per_vol,
            )
        else:
            chapters_per_vol = request.chapters_per_volume

        # Initialize progress tracking (uses correct chapters_per_vol)
        await progress_service.initialize_progress(
            novel_id=novel_id,
            total_volumes=request.volumes,
            chapters_per_volume=chapters_per_vol,
        )

        # Stage 1: Generate master outline
        await _emit_progress(
            task_id, EventType.STAGE_START,
            {"stage": "master_outline", "percentage": 0},
        )

        # T2: pass chapters_per_vol so the prompt uses the correct value
        master_outline = await generate_master_outline(
            novel_id=novel_id,
            request=request,
            chapters_per_vol=chapters_per_vol,
        )

        # Update novel with master outline (uses correct chapters_per_vol)
        from src.api.services.novel_manager import get_novel_manager
        novel_manager = get_novel_manager()
        await novel_manager.update_novel(
            novel_id,
            master_outline=master_outline,
            total_volumes=request.volumes,
            chapters_per_volume=chapters_per_vol,
            words_per_chapter=request.words_per_chapter,
            is_long_form=True,
        )

        await _emit_progress(
            task_id, EventType.STAGE_COMPLETE,
            {"stage": "master_outline", "percentage": 5},
        )

        # Stage 2: Generate volume by volume
        global_chapter_start = 1
        all_chapters_generated = []

        for vol_num in range(1, total_volumes + 1):
            # Update progress
            await progress_service.update_volume_status(
                novel_id=novel_id,
                volume_number=vol_num,
                status="generating",
            )

            vol_percentage = 5 + int((vol_num - 1) / total_volumes * 90)
            await _emit_progress(task_id, EventType.STAGE_START, {
                "stage": f"volume_{vol_num}",
                "volume_number": vol_num,
                "percentage": vol_percentage,
            })

            try:
                # Generate volume outline
                vol_outline = await generate_volume_outline(
                    novel_id=novel_id,
                    master_outline=master_outline,
                    volume_number=vol_num,
                    chapters_per_volume=chapters_per_vol,
                    words_per_chapter=words_per_chapter,
                    request=request,
                )

                # T3: Persist volume outline and chapter outlines to Outline table
                try:
                    from src.api.services.outline_service import get_outline_service
                    outline_service = get_outline_service()
                    await outline_service.upsert_volume_outline(novel_id, vol_num, vol_outline)
                    chapters_data = vol_outline.get("chapters", [])
                    for idx, ch in enumerate(chapters_data):
                        ch_num = ch.get("chapter", idx + 1)
                        await outline_service.upsert_chapter_outline(novel_id, vol_num, ch_num, ch)
                    logger.info(
                        "volume_outline_persisted",
                        novel_id=novel_id,
                        volume_number=vol_num,
                        chapter_count=len(chapters_data),
                    )
                except Exception as persist_error:
                    logger.warning(
                        "volume_outline_persist_failed",
                        novel_id=novel_id,
                        volume_number=vol_num,
                        error=str(persist_error),
                    )

                # Generate chapters for this volume
                chapter_end = global_chapter_start + chapters_per_vol - 1
                vol_chapters = await generate_volume_chapters(
                    task_id=task_id,
                    novel_id=novel_id,
                    volume_number=vol_num,
                    chapter_start=global_chapter_start,
                    chapter_end=chapter_end,
                    vol_outline=vol_outline,
                    words_per_chapter=words_per_chapter,
                    request=request,
                )

                all_chapters_generated.extend(vol_chapters)

                # Generate quality report for this volume
                quality_report = await generate_volume_quality_report(
                    novel_id=novel_id,
                    volume_number=vol_num,
                    chapters=vol_chapters,
                )

                # Update progress
                await progress_service.update_volume_status(
                    novel_id=novel_id,
                    volume_number=vol_num,
                    status="completed",
                    chapters_completed=len(vol_chapters),
                    quality_report=quality_report,
                )

                await _emit_progress(task_id, EventType.STAGE_COMPLETE, {
                    "stage": f"volume_{vol_num}",
                    "volume_number": vol_num,
                    "percentage": vol_percentage + int(90 / total_volumes),
                })

                global_chapter_start = chapter_end + 1

            except Exception as vol_error:
                logger.error(
                    "volume_generation_failed",
                    novel_id=novel_id,
                    volume_number=vol_num,
                    error=str(vol_error),
                )
                await progress_service.update_volume_status(
                    novel_id=novel_id,
                    volume_number=vol_num,
                    status="failed",
                    errors=[str(vol_error)],
                )
                # Continue to next volume
                continue

        # Final completion
        await task_manager.complete_task(task_id, {
            "novel_id": novel_id,
            "total_volumes": total_volumes,
            "total_chapters": len(all_chapters_generated),
        })

        await _emit_progress(
            task_id, EventType.COMPLETED,
            {"percentage": 100, "current_stage": "completed"},
        )

        logger.info(
            "long_form_generation_completed",
            task_id=task_id,
            novel_id=novel_id,
            total_chapters=len(all_chapters_generated),
        )

    except Exception as e:
        logger.exception("long_form_generation_failed", task_id=task_id)
        await task_manager.fail_task(task_id, str(e))
        await _emit_progress(task_id, EventType.ERROR, {"error": str(e)})

