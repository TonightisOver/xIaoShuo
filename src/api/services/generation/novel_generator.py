"""小说生成服务

负责执行小说生成任务，通过事件总线推送实时进度。
"""

from typing import Any

import structlog

from src.api.models.requests import CreateNovelRequest
from src.api.services.content.novel_manager import get_novel_manager
from src.api.services.generation.chapter_generation_utils import (
    _emit_progress,
    _get_blueprint,
    _get_story_bible_context,
    _sync_chapter_type_to_db,
)
from src.api.services.generation.chapter_persistence_service import (
    persist_langgraph_result,
    persist_quality_to_version,
)
from src.api.services.generation.progress_event_bus import (
    EventType,
    ProgressEvent,
    get_event_bus,
)
from src.api.services.quality.rewrite_loop_service import RewriteLoopService
from src.api.services.tasks.task_manager import get_task_manager
from src.core.langgraph.graph import create_novel_graph

logger = structlog.get_logger(__name__)


async def pause_task(task_id: str) -> None:
    from src.api.services.generation.pause_state_store import get_pause_state_store

    await get_pause_state_store().set_paused(task_id)
    await _emit_progress(
        task_id,
        EventType.GENERATION_PAUSED,
        {"task_id": task_id, "status": "paused"},
    )


async def resume_task(task_id: str) -> None:
    from src.api.services.generation.pause_state_store import get_pause_state_store

    await get_pause_state_store().clear_paused(task_id)
    await _emit_progress(
        task_id,
        EventType.GENERATION_RESUMED,
        {"task_id": task_id, "status": "running"},
    )


async def is_task_paused(task_id: str) -> bool:
    from src.api.services.generation.pause_state_store import get_pause_state_store

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

# 规划常量与纯函数提取到独立模块（向后兼容 re-export，tests/unit/test_novel_generator_supplement 依赖此路径）
from src.api.services.generation.novel_generator_planning import (  # noqa: F401,E402
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
        from src.api.services.content.world_service import get_world_service
        existing_world = await get_world_service().get_world_setting(novel_id)
        from src.api.services.content.character_service import get_character_service
        existing_chars = await get_character_service().list_characters(novel_id)
        ws_keys = ["background", "rules", "culture", "geography"]
        if existing_world and any(existing_world.get(k) for k in ws_keys):
            initial_state["world_setting"] = existing_world
        if existing_chars:
            initial_state["characters"] = existing_chars
        from src.api.services.content.storyline_service import get_storyline_service
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
                from src.api.services.content.novel_manager import get_novel_manager
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
    from src.api.services.content.story_bible_service import detect_bible_conflicts
    from src.api.services.knowledge.knowledge_graph_service import (
        get_knowledge_graph_service,
    )
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
        "rewrite_service": RewriteLoopService(),
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

    configurable: dict[str, Any] = {
        "thread_id": task_id,
        "persist_quality": _persist_quality_to_version,
        "rewrite_service": RewriteLoopService(),
    }
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
                from src.api.services.content.novel_manager import get_novel_manager
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
    from src.api.services.content.conversation_service import get_conversation_service
    from src.api.services.content.outline_service import get_outline_service
    from src.api.services.generation.ai_generation_service import (
        get_ai_generation_service,
    )

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




# 长篇编排入口已迁入 long_form_generation_helpers（Ticket 02）。
# 此处 re-export 保持路由层与测试 patch 路径不变：
# tests/integration/test_change044_long_form_api.py patch 本模块符号。
from src.api.services.generation.long_form_generation_helpers import (  # noqa: E402,F401
    generate_chapters_background,
    generate_long_form_background,
    generate_volume_background,
)


async def _persist_to_novel(novel_id: str, result: dict[str, Any]) -> None:
    """Persist LangGraph result (delegates to persistence service)."""
    manager = get_novel_manager()
    await persist_langgraph_result(novel_id, result, manager=manager)
