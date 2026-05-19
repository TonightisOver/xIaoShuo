"""小说生成服务

负责执行小说生成任务，通过事件总线推送实时进度。
"""

from typing import Any

import structlog

from src.api.models.requests import CreateNovelRequest
from src.api.services.novel_manager import get_novel_manager
from src.api.services.progress_event_bus import (
    EventType,
    ProgressEvent,
    get_event_bus,
    register_progress_callback,
    unregister_progress_callback,
)
from src.api.services.task_manager import get_task_manager
from src.core.langgraph.graph import create_novel_graph

logger = structlog.get_logger(__name__)

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
    event_bus = get_event_bus()

    try:
        await task_manager.update_status(task_id, "running")

        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.STAGE_START,
            data={"stage": "idea_expansion", "percentage": 0},
        ))

        logger.info("novel_generation_starting", task_id=task_id)

        initial_state, novel_id = await _build_initial_state(task_id, request)

        result = await _run_langgraph_pipeline(
            task_id, initial_state, stage_offset=0, total_stages=len(STAGE_ORDER),
        )

        await task_manager.complete_task(task_id, result)

        if novel_id:
            await _persist_to_novel(novel_id, result)

        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.COMPLETED,
            data={"percentage": 100, "current_stage": "completed"},
        ))

        logger.info(
            "novel_generation_completed",
            task_id=task_id,
            chapters=len(result.get("chapters", [])),
        )

    except Exception as e:
        logger.exception("novel_generation_failed", task_id=task_id)
        await task_manager.fail_task(task_id, str(e))
        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.ERROR,
            data={"error": str(e)},
        ))


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
        base = _full_generate_percentage(stage_offset + 3, total_stages)
        span = _full_generate_percentage(stage_offset + 4, total_stages) - base
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

    register_progress_callback(task_id, _chapter_progress_callback)

    result: dict[str, Any] = {}
    try:
        config = {"configurable": {"thread_id": task_id}}
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
        unregister_progress_callback(task_id)

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
    event_bus = get_event_bus()

    try:
        await task_manager.update_status(task_id, "running")

        logger.info("full_generation_starting", task_id=task_id)

        # --- Build initial state ---
        initial_state, novel_id = await _build_initial_state(task_id, request)

        # --- Stage 1-7: Run LangGraph pipeline ---
        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.STAGE_START,
            data={"stage": "idea_expansion", "percentage": 0},
        ))

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

        # Final completion — mark task complete and publish event
        await task_manager.complete_task(task_id, result)
        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.COMPLETED,
            data={"percentage": 100, "current_stage": "completed", "pipeline": "full"},
        ))

        logger.info("full_generation_completed", task_id=task_id)

    except Exception as e:
        logger.exception("full_generation_failed", task_id=task_id)
        await task_manager.fail_task(task_id, str(e))
        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.ERROR,
            data={"error": str(e)},
        ))


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
    from src.api.services.conversation_service import get_conversation_service
    from src.api.services.outline_service import get_outline_service
    from src.api.services.storyline_service import get_storyline_service

    event_bus = get_event_bus()
    task_manager = get_task_manager()

    percentage = _full_generate_percentage(feature_index)

    await event_bus.publish(ProgressEvent(
        task_id=task_id,
        event_type=EventType.SUB_FEATURE_START,
        data={"feature": feature_name, "label": label, "percentage": percentage},
    ))

    try:
        if feature_name == "power_systems" and novel_id:
            sl_service = get_storyline_service()
            ps_result = await sl_service.generate_power_systems_ai(novel_id)
            await event_bus.publish(ProgressEvent(
                task_id=task_id,
                event_type=EventType.SUB_FEATURE_COMPLETE,
                data={
                    "feature": feature_name, "label": label,
                    "percentage": percentage, "count": len(ps_result),
                },
            ))

        elif feature_name == "outline_persist" and novel_id:
            outline_service = get_outline_service()
            # Generate master outline from novel settings
            await outline_service.generate_master_from_novel(novel_id)
            # Generate volume outlines
            try:
                await outline_service.generate_volume_outlines(
                    novel_id, request.novel_type, request.target_words,
                )
            except Exception:
                logger.warning(
                "Volume outline generation failed, continuing", exc_info=True,
            )
            # Persist from LangGraph result
            persist_result = await outline_service.persist_outlines_from_result(novel_id, result)
            await event_bus.publish(ProgressEvent(
                task_id=task_id,
                event_type=EventType.SUB_FEATURE_COMPLETE,
                data={
                    "feature": feature_name, "label": label,
                    "percentage": percentage, **persist_result,
                },
            ))

        elif feature_name == "storylines" and novel_id:
            sl_service = get_storyline_service()
            sl_result = await sl_service.generate_storylines_ai(novel_id)
            await event_bus.publish(ProgressEvent(
                task_id=task_id,
                event_type=EventType.SUB_FEATURE_COMPLETE,
                data={
                    "feature": feature_name, "label": label,
                    "percentage": percentage, "count": len(sl_result),
                },
            ))

        elif feature_name == "character_arcs" and novel_id:
            sl_service = get_storyline_service()
            arc_result = await sl_service.generate_arcs_ai(novel_id)
            await event_bus.publish(ProgressEvent(
                task_id=task_id,
                event_type=EventType.SUB_FEATURE_COMPLETE,
                data={
                    "feature": feature_name, "label": label,
                    "percentage": percentage, "count": len(arc_result),
                },
            ))

        elif feature_name == "scenes" and novel_id:
            sl_service = get_storyline_service()
            scene_result = await sl_service.generate_scenes_ai(novel_id)
            await event_bus.publish(ProgressEvent(
                task_id=task_id,
                event_type=EventType.SUB_FEATURE_COMPLETE,
                data={
                    "feature": feature_name, "label": label,
                    "percentage": percentage, "count": len(scene_result),
                },
            ))

        elif feature_name == "auto_conversation" and novel_id:
            conv_service = get_conversation_service()
            conv_result = await conv_service.generate_auto_conversation(novel_id)
            await event_bus.publish(ProgressEvent(
                task_id=task_id,
                event_type=EventType.SUB_FEATURE_COMPLETE,
                data={
                    "feature": feature_name, "label": label,
                    "percentage": percentage,
                    "conversation_id": conv_result.get("conversation_id"),
                },
            ))

        # Update progress after sub-feature completion
        await task_manager.update_status(task_id, "running", progress={
            "current_stage": feature_name,
            "percentage": percentage,
            "completed_chapters": len(result.get("chapters", [])),
            "total_chapters": len(result.get("chapter_outlines", [])),
        })

    except Exception as e:
        logger.warning(f"Sub-feature '{feature_name}' failed (non-blocking): {e}", exc_info=True)
        await event_bus.publish(ProgressEvent(
            task_id=task_id,
            event_type=EventType.ERROR,
            data={"feature": feature_name, "label": label, "error": str(e), "non_blocking": True},
        ))


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

        novel = await novel_manager.get_novel(novel_id)

        # Fetch context: characters, world setting, and previous chapters
        world = await novel_manager.get_world_setting(novel_id)
        characters = await novel_manager.list_characters(novel_id)
        from src.api.services.storyline_service import get_storyline_service
        try:
            storylines = await get_storyline_service().list_storylines(novel_id)
        except Exception:
            storylines = []

        prev_context = ""
        prev_chapters = await novel_manager.list_chapters(novel_id)
        prev_in_earlier_vols = [c for c in prev_chapters if (c.get("volume_number") or 0) < volume_number]
        if prev_in_earlier_vols:
            last_ch = prev_in_earlier_vols[-1]
            prev_context = f"前文最后一章《{last_ch.get('title', '')}》结尾：{(last_ch.get('content', '') or '')[-500:]}"

        import json

        from src.api.models.db_models import Chapter
        from src.core.database import get_db_session
        from src.core.llm.chapter_generator import generate_single_chapter
        from src.core.llm.client import get_llm_client
        from src.core.validation import WRITING_STYLES

        client = get_llm_client()
        style_instruction = WRITING_STYLES.get(novel.get("writing_style", ""), "")

        # Build context strings
        chars_str = json.dumps([{
            "name": c.get("name"), "role": c.get("role"),
            "personality": c.get("personality"), "description": c.get("description"),
        } for c in characters], ensure_ascii=False) if characters else "暂无人物"

        world_str = json.dumps({
            "background": (world or {}).get("background", ""),
            "rules": (world or {}).get("rules", ""),
            "geography": (world or {}).get("geography", ""),
            "culture": (world or {}).get("culture", ""),
        }, ensure_ascii=False) if world else "暂无世界观"

        sl_str = json.dumps([{
            "name": s.get("name"), "type": s.get("type"),
            "description": s.get("description"),
        } for s in storylines], ensure_ascii=False) if storylines else ""

        generated_chapters = []
        for i, ch_outline in enumerate(chapters_data):
            previous_chapter = prev_context if i == 0 else (generated_chapters[-1].get("content", "")[:500] if generated_chapters else "")

            chapter_result = await generate_single_chapter(
                client=client,
                chapter_outline=ch_outline,
                previous_chapter=previous_chapter or "这是本卷第一章",
                characters_json=chars_str,
                world_setting_json=world_str,
                storylines_json=sl_str,
                style_instruction=style_instruction,
            )
            generated_chapters.append(chapter_result)

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

        logger.info(
            "volume_generation_completed",
            novel_id=novel_id,
            volume_number=volume_number,
        )

    except Exception as e:
        logger.exception("volume_generation_failed", error=str(e))
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

        import json

        from sqlalchemy import delete

        from src.api.models.db_models import Chapter
        from src.core.database import get_db_session
        from src.core.llm.chapter_generator import generate_single_chapter
        from src.core.llm.client import get_llm_client
        from src.core.validation import WRITING_STYLES

        client = get_llm_client()
        style_instruction = WRITING_STYLES.get(novel.get("writing_style", ""), "")

        # Fetch context: characters, world setting, and storylines
        world = await novel_manager.get_world_setting(novel_id)
        characters = await novel_manager.list_characters(novel_id)
        from src.api.services.storyline_service import get_storyline_service
        try:
            storylines = await get_storyline_service().list_storylines(novel_id)
        except Exception:
            storylines = []

        chars_str = json.dumps([{
            "name": c.get("name"), "role": c.get("role"),
            "personality": c.get("personality"), "description": c.get("description"),
        } for c in characters], ensure_ascii=False) if characters else "暂无人物"

        world_str = json.dumps({
            "background": (world or {}).get("background", ""),
            "rules": (world or {}).get("rules", ""),
            "geography": (world or {}).get("geography", ""),
            "culture": (world or {}).get("culture", ""),
        }, ensure_ascii=False) if world else "暂无世界观"

        sl_str = json.dumps([{
            "name": s.get("name"), "type": s.get("type"),
            "description": s.get("description"),
        } for s in storylines], ensure_ascii=False) if storylines else ""

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

            chapter_result = await generate_single_chapter(
                client=client,
                chapter_outline=ch_outline,
                previous_chapter=previous or "这是起始章节",
                characters_json=chars_str,
                world_setting_json=world_str,
                storylines_json=sl_str,
                style_instruction=style_instruction,
            )
            generated_chapters.append(chapter_result)

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

        logger.info(
            "chapters_generation_completed",
            novel_id=novel_id,
            chapter_start=chapter_start,
            chapter_end=chapter_end,
        )

    except Exception as e:
        logger.exception("chapters_generation_failed", error=str(e))
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
        from datetime import datetime, timezone

        from src.api.models.db_models import Chapter
        from src.core.database import get_db_session

        async with get_db_session() as session:
            for ch in chapters:
                if isinstance(ch, dict):
                    chapter = Chapter(
                        novel_id=novel_id,
                        volume_number=ch.get("volume_number"),
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

        logger.info("persist_results_completed", novel_id=novel_id)

    except Exception as e:
        logger.error("persist_results_failed", novel_id=novel_id, error=str(e))
