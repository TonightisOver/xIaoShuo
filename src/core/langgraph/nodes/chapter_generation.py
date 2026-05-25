"""章节生成节点"""

import json

import structlog

from src.core.config import get_settings
from src.core.langgraph.state import NovelState
from src.core.llm.chapter_generator import generate_single_chapter
from src.core.llm.client import get_llm_client
from src.core.validation import get_style_instruction

logger = structlog.get_logger(__name__)

# Default word count for standard mode
DEFAULT_TARGET_WORDS = 3000


async def node(state: NovelState) -> NovelState:
    """章节生成节点"""
    try:
        chapters: list[dict] = []
        chapter_outlines = state.get("chapter_outlines", [])
        regeneration_count = state.get("_regeneration_count", 0)

        # If we already have chapters, this is a regeneration attempt
        if state.get("chapters"):
            regeneration_count += 1

        settings = get_settings()
        kg_enabled = settings.KNOWLEDGE_GRAPH_ENABLED

        if kg_enabled:
            from src.api.services.knowledge_graph_service import (
                get_knowledge_graph_service,
            )
            kg_service = get_knowledge_graph_service()
        else:
            kg_service = None

        client = get_llm_client()
        characters_json = json.dumps(state["characters"], ensure_ascii=False)
        world_setting_json = json.dumps(state["world_setting"], ensure_ascii=False)
        style_instruction = get_style_instruction(
            state.get("writing_style", ""),
            state.get("writing_style_prompt", ""),
        )

        # Determine target words per chapter (long-form mode vs standard)
        target_words_per_chapter = state.get("target_words_per_chapter") or DEFAULT_TARGET_WORDS

        chapter_errors: list[str] = []

        for i, chapter_outline in enumerate(chapter_outlines):
            previous_chapter = ""
            if i > 0 and chapters:
                # Use last successful chapter's content as context
                previous_chapter = chapters[-1].get("content", "")[:500]

            chapter_num = chapter_outline.get("chapter", i + 1)
            logger.info(
                f"Generating chapter {chapter_num} "
                f"for project {state['project_id']}"
            )

            try:
                chapter_result = await generate_single_chapter(
                    client=client,
                    chapter_outline=chapter_outline,
                    previous_chapter=previous_chapter,
                    characters_json=characters_json,
                    world_setting_json=world_setting_json,
                    style_instruction=style_instruction,
                    kg_service=kg_service,
                    novel_id=state.get("novel_id") or state["project_id"],
                    target_words=target_words_per_chapter,
                )
            except Exception as chapter_exc:
                error_msg = str(chapter_exc)
                logger.error(
                    f"Chapter {chapter_num} generation failed: {error_msg}",
                    chapter=chapter_num,
                    project_id=state["project_id"],
                )
                chapter_errors.append(f"第{chapter_num}章生成失败: {error_msg}")
                chapter_result = {
                    "chapter": chapter_num,
                    "title": chapter_outline.get("title", f"第{chapter_num}章"),
                    "content": f"[章节生成失败：{error_msg}，请检查 API Key 配置后重试]",
                    "word_count": 0,
                    "generation_failed": True,
                }

            chapters.append(chapter_result)

            # Emit per-chapter progress via callback registry
            from src.api.services.progress_event_bus import get_progress_callback

            successful = sum(1 for c in chapters if not c.get("generation_failed"))
            failed = sum(1 for c in chapters if c.get("generation_failed"))
            callback = get_progress_callback(state["project_id"])
            if callback:
                await callback({
                    "completed_chapters": len(chapters),
                    "successful_chapters": successful,
                    "failed_chapters": failed,
                    "total_chapters": len(chapter_outlines),
                    "current_chapter": chapter_num,
                })

        accumulated_errors = list(state.get("errors") or []) + chapter_errors
        return {
            **state,
            "chapters": chapters,
            "current_stage": "chapter_generation_completed",
            "_regeneration_count": regeneration_count,
            "errors": accumulated_errors,
        }

    except Exception as e:
        logger.error(f"Chapter generation node failed unexpectedly: {e}")
        regeneration_count = state.get("_regeneration_count", 0) + 1
        return {
            **state,
            "chapters": chapters,
            "current_stage": "chapter_generation_completed",
            "_regeneration_count": regeneration_count,
            "errors": list(state.get("errors") or []) + [f"chapter_generation node error: {str(e)}"],
        }
