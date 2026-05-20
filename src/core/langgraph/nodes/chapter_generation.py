"""章节生成节点"""

import json

import structlog

from src.core.config import get_settings
from src.core.langgraph.state import NovelState
from src.core.llm.chapter_generator import generate_single_chapter
from src.core.llm.client import get_llm_client
from src.core.validation import get_style_instruction

logger = structlog.get_logger(__name__)


async def node(state: NovelState) -> NovelState:
    """章节生成节点"""
    try:
        chapters: list[dict] = []
        chapter_outlines = state.get("chapter_outlines", [])

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

        for i, chapter_outline in enumerate(chapter_outlines):
            previous_chapter = ""
            if i > 0 and chapters:
                previous_chapter = chapters[-1].get("content", "")[:500]

            logger.info(
                f"Generating chapter {chapter_outline['chapter']} "
                f"for project {state['project_id']}"
            )

            chapter_result = await generate_single_chapter(
                client=client,
                chapter_outline=chapter_outline,
                previous_chapter=previous_chapter,
                characters_json=characters_json,
                world_setting_json=world_setting_json,
                style_instruction=style_instruction,
                kg_service=kg_service,
                novel_id=state.get("novel_id") or state["project_id"],
            )
            chapters.append(chapter_result)

            # Emit per-chapter progress via callback registry
            from src.api.services.progress_event_bus import get_progress_callback

            callback = get_progress_callback(state["project_id"])
            if callback:
                await callback({
                    "completed_chapters": len(chapters),
                    "total_chapters": len(chapter_outlines),
                    "current_chapter": chapter_outline["chapter"],
                })

        return {
            **state,
            "chapters": chapters,
            "current_stage": "chapter_generation_completed",
        }

    except Exception as e:
        logger.error(f"Chapter generation failed, using fallback: {e}")
        chapters = [
            {
                "chapter": 1,
                "title": "家乡变故",
                "content": (
                    "夜幕降临，张家村笼罩在一片祥和之中。\n\n"
                    "张三正在院子里练习基础拳法，突然，天边传来一阵轰鸣声。"
                    "只见数道黑影从天而降，为首之人正是邪派高手王五。\n\n"
                    "\"交出宝物，饶你们不死！\"王五冷笑道。\n\n"
                    "就在这千钧一发之际，一道白光闪过，李四长老出现在众人面前。"
                    "\"邪派妖人，休得猖狂！\"\n\n"
                    "一场激战就此展开..."
                ),
                "word_count": 150,
            }
        ]

        return {
            **state,
            "chapters": chapters,
            "current_stage": "chapter_generation_completed",
            "errors": state["errors"] + [f"chapter_generation API failed: {str(e)}"],
        }
