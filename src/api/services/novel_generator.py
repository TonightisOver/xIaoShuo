"""小说生成服务

负责执行小说生成任务，通过事件总线推送实时进度。
"""

import asyncio
from typing import Any

import structlog

from src.api.models.requests import CreateNovelRequest
from src.api.services.chapter_generation_utils import (
    _context_builder,
    _emit_progress,
    _get_blueprint,
    _get_story_bible_context,
    _sync_chapter_type_to_db,
)
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
from src.api.services.novel_manager import get_novel_manager
from src.api.services.progress_event_bus import (
    EventType,
    ProgressEvent,
    get_event_bus,
)
from src.api.services.task_manager import get_task_manager
from src.api.services.volume_service import get_volume_service
from src.core.langgraph.graph import create_novel_graph

logger = structlog.get_logger(__name__)


async def pause_task(task_id: str) -> None:
    from src.api.services.pause_state_store import get_pause_state_store

    await get_pause_state_store().set_paused(task_id)
    await _emit_progress(
        task_id,
        EventType.GENERATION_PAUSED,
        {"task_id": task_id, "status": "paused"},
    )


async def resume_task(task_id: str) -> None:
    from src.api.services.pause_state_store import get_pause_state_store

    await get_pause_state_store().clear_paused(task_id)
    await _emit_progress(
        task_id,
        EventType.GENERATION_RESUMED,
        {"task_id": task_id, "status": "running"},
    )


async def is_task_paused(task_id: str) -> bool:
    from src.api.services.pause_state_store import get_pause_state_store

    return await get_pause_state_store().is_paused(task_id)


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

# 规划常量与纯函数提取到独立模块（向后兼容 re-export）
from src.api.services.novel_generator_planning import (
    FULL_GENERATE_STAGES,
    STAGE_ORDER,
    _full_generate_percentage,
    calculate_long_form_chapter_plan,
)


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
        from src.api.services.world_service import get_world_service
        existing_world = await get_world_service().get_world_setting(novel_id)
        from src.api.services.character_service import get_character_service
        existing_chars = await get_character_service().list_characters(novel_id)
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
    from src.core.trace_context import _bind_trace, _clear_trace

    _trace_token = _bind_trace(task_id)
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

        # HITL interrupt：pipeline 暂停等待人工审核，不 complete，等 review API resume
        if isinstance(result, dict) and result.get("_interrupted_for_review"):
            return  # 任务保持 running/waiting_for_review，由 resume_pipeline 续跑

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
    finally:
        _clear_trace(_trace_token)


# FULL_GENERATE_STAGES 与 _full_generate_percentage 已提取到 novel_generator_planning
# （上方 import 已 re-export，保持向后兼容）


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
    # 追踪已完成的最多章节数与重生成轮次，避免 regenerate 时 progress 倒退误导用户
    max_completed_chapters = 0
    last_regeneration_round = 0
    last_total_chapters = 0
    interrupted_for_review = False
    config = {"configurable": configurable}
    async for event in graph.astream(initial_state, config=config):
        # LangGraph interrupt：astream 产出 {'__interrupt__': ...} 后正常结束
        if "__interrupt__" in event:
            interrupted_for_review = True
            logger.info("pipeline_interrupted_for_review", task_id=task_id)
            break
        for node_name, state_update in event.items():
            result = state_update
            if node_name in STAGE_ORDER:
                node_idx = STAGE_ORDER.index(node_name)
            else:
                node_idx = -1
            if node_idx < 0:
                continue
            percentage = _full_generate_percentage(stage_offset + node_idx, total_stages)

            completed = len(state_update.get("chapters", []))
            total = len(state_update.get("chapter_outlines", []))
            regen_round = state_update.get("_regeneration_count", 0)

            # regenerate（quality_check 回 chapter_generation）时，章节会重新生成，
            # completed 可能暂时下降。保留历史 max，避免 progress 倒退；
            # 同时用 regeneration_round 标注当前是第几轮质量优化。
            if regen_round > last_regeneration_round:
                last_regeneration_round = regen_round
                max_completed_chapters = 0  # 新一轮重置基准（重生成会覆盖旧章节）
            if completed > max_completed_chapters:
                max_completed_chapters = completed
            if total > 0:
                last_total_chapters = total

            progress_data = {
                "current_stage": node_name,
                "completed_chapters": max_completed_chapters,
                "total_chapters": last_total_chapters,
                "percentage": percentage,
            }
            if last_regeneration_round > 0 and node_name == "chapter_generation":
                progress_data["regeneration_round"] = last_regeneration_round
                progress_data["current_stage"] = "chapter_generation_optimizing"
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

    # 若因 HITL interrupt 暂停，标记 task 为 waiting_for_review（不 complete）
    if interrupted_for_review:
        task_manager = get_task_manager()
        await task_manager.update_status(
            task_id, "running",
            progress={"current_stage": "human_review", "waiting_for_review": True},
        )
        await _emit_progress(
            task_id, EventType.STAGE_START,
            {"stage": "human_review", "percentage": _full_generate_percentage(stage_offset + 5, total_stages)},
        )
        logger.info("pipeline_paused_for_human_review", task_id=task_id)
        return {"_interrupted_for_review": True}

    return result


async def resume_pipeline(task_id: str, decision: dict[str, Any]) -> None:
    """恢复因 HITL interrupt 暂停的生成流水线。

    用相同 thread_id 的 config + Command(resume=decision) 重新 astream，
    LangGraph 从 checkpointer 恢复状态，human_review 节点的 interrupt() 返回 decision。

    Args:
        task_id: 任务 ID（即 LangGraph thread_id）
        decision: 审核决策，如 {"approval_status": "approved"} 或
                  {"approval_status": "revision", "revision_instructions": "..."}
    """
    from langgraph.types import Command

    task_manager = get_task_manager()
    event_bus = get_event_bus()
    graph = create_novel_graph()

    configurable: dict[str, Any] = {"thread_id": task_id}
    config = {"configurable": configurable}

    result: dict[str, Any] = {}
    try:
        async for event in graph.astream(Command(resume=decision), config=config):
            if "__interrupt__" in event:
                # 再次 interrupt（如 revision 后又触发审核）——继续等待
                logger.info("pipeline_re_interrupted_after_resume", task_id=task_id)
                await task_manager.update_status(
                    task_id, "running",
                    progress={"current_stage": "human_review", "waiting_for_review": True},
                )
                return
            for node_name, state_update in event.items():
                result = state_update

        # resume 完成，持久化结果
        novel_id = None
        task_data = await task_manager.get_task(task_id)
        if task_data:
            novel_id = task_data.get("novel_id")

        await task_manager.complete_task(task_id, result)
        if novel_id:
            await _persist_to_novel(novel_id, result)
        await _emit_progress(
            task_id, EventType.COMPLETED,
            {"percentage": 100, "current_stage": "completed"},
        )
        logger.info("pipeline_resumed_completed", task_id=task_id)

    except Exception as e:
        logger.exception("pipeline_resume_failed", task_id=task_id)
        await task_manager.fail_task(task_id, str(e))
        await _emit_progress(task_id, EventType.ERROR, {"error": str(e)})


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
        while await is_task_paused(task_id):
            await asyncio.sleep(1)

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
    volume_service = get_volume_service()

    try:
        await task_manager.update_status(task_id, "running")

        vol = await volume_service.get_volume(novel_id, volume_number)
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
        from src.api.services.chapter_service import get_chapter_service
        ch_service = get_chapter_service()
        prev_chapters = await ch_service.list_chapters_preview(novel_id)
        prev_in_earlier_vols = [c for c in prev_chapters if (c.get("volume_number") or 0) < volume_number]
        if prev_in_earlier_vols:
            last_ch = prev_in_earlier_vols[-1]
            last_tail = await ch_service.get_chapter_tail(
                novel_id, last_ch["chapter_number"]
            )
            prev_context = f"前文最后一章《{last_ch.get('title', '')}》结尾：{last_tail}"

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

        await volume_service.update_volume(novel_id, volume_number, status="completed")
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
        await volume_service.update_volume(novel_id, volume_number, status="failed")
        await _emit_progress(task_id, EventType.ERROR, {"error": str(e)})


async def generate_chapters_background(
    task_id: str, novel_id: str, chapter_start: int, chapter_end: int
) -> None:
    """按章节范围生成"""
    task_manager = get_task_manager()
    novel_manager = get_novel_manager()
    volume_service = get_volume_service()

    try:
        await task_manager.update_status(task_id, "running")

        prev_context = ""
        if chapter_start > 1:
            from src.api.services.chapter_service import get_chapter_service
            prev_context = await get_chapter_service().get_chapter_tail(
                novel_id, chapter_start - 1
            )

        # Build ordered chapter outlines for the requested range
        volumes = await volume_service.list_volumes(novel_id)
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

        chapter_plan = calculate_long_form_chapter_plan(request)
        chapters_per_vol = chapter_plan["chapters_per_volume"]

        if request.auto_calc_chapters:
            if chapters_per_vol != chapter_plan["computed_chapters_per_volume"]:
                logger.warning(
                    "auto_calc_chapters_clamped",
                    computed=chapter_plan["computed_chapters_per_volume"],
                    clamped=chapters_per_vol,
                    target_words=request.target_words,
                    words_per_chapter=request.words_per_chapter,
                    volumes=request.volumes,
                )
            logger.info(
                "auto_calc_chapters",
                target_words=request.target_words,
                words_per_chapter=request.words_per_chapter,
                total_chapters=chapter_plan["estimated_total_chapters"],
                chapters_per_vol=chapters_per_vol,
            )

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
        failed_volumes: list[int] = []
        unverified_volumes: list[int] = []

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
                    volume_offset = (vol_num - 1) * chapters_per_vol
                    for idx, ch in enumerate(chapters_data):
                        local_ch_num = ch.get("chapter", idx + 1)
                        global_ch_num = volume_offset + local_ch_num
                        await outline_service.upsert_chapter_outline(novel_id, vol_num, global_ch_num, ch)
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

                if quality_report.get("has_unverified"):
                    unverified_volumes.append(vol_num)

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
                failed_volumes.append(vol_num)
                await progress_service.update_volume_status(
                    novel_id=novel_id,
                    volume_number=vol_num,
                    status="failed",
                    errors=[str(vol_error)],
                )
                # Continue to next volume
                continue

        # Final completion — distinguish volume-level statuses
        if failed_volumes and not all_chapters_generated:
            final_status = "failed"
        elif failed_volumes:
            final_status = "partially_completed"
        elif unverified_volumes:
            final_status = "completed_with_unverified_quality"
        else:
            final_status = "completed"
        await task_manager.complete_task(task_id, {
            "novel_id": novel_id,
            "total_volumes": total_volumes,
            "total_chapters": len(all_chapters_generated),
        }, status=final_status)

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

