"""章节生成节点"""

import json
import logging

from src.core.langgraph.state import NovelState
from src.core.llm.client import get_llm_client
from src.core.llm.prompts import CHAPTER_GENERATION_PROMPT
from src.core.validation import WRITING_STYLES

logger = logging.getLogger(__name__)


async def node(state: NovelState) -> NovelState:
    """章节生成节点"""
    try:
        chapters: list[dict] = []
        chapter_outlines = state.get("chapter_outlines", [])

        for i, chapter_outline in enumerate(chapter_outlines):
            # 获取上一章内容
            previous_chapter = ""
            if i > 0 and chapters:
                previous_chapter = chapters[-1].get("content", "")

            client = get_llm_client()
            prompt = CHAPTER_GENERATION_PROMPT.format(
                chapter_outline=json.dumps(
                    chapter_outline, ensure_ascii=False
                ),
                previous_chapter=(
                    previous_chapter[:500] if previous_chapter else "这是第一章"
                ),
                characters=json.dumps(state["characters"], ensure_ascii=False),
                world_setting=json.dumps(
                    state["world_setting"], ensure_ascii=False
                ),
            )

            logger.info(
                f"Generating chapter {chapter_outline['chapter']} "
                f"for project {state['project_id']}"
            )
            style_instruction = WRITING_STYLES.get(state.get("writing_style", ""), "")
            if style_instruction:
                prompt = f"{style_instruction}\n\n{prompt}"
            content = await client.generate(prompt, max_tokens=8000)

            chapters.append(
                {
                    "chapter": chapter_outline["chapter"],
                    "title": chapter_outline["title"],
                    "content": content,
                    "word_count": len(content),
                }
            )

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
