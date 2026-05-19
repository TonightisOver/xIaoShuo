"""单章生成共享逻辑"""

import json
from typing import Any

import structlog

from src.core.llm.prompts import CHAPTER_GENERATION_PROMPT

logger = structlog.get_logger(__name__)


async def generate_single_chapter(
    client: Any,
    chapter_outline: dict[str, Any],
    previous_chapter: str,
    characters_json: str,
    world_setting_json: str,
    storylines_json: str = "",
    style_instruction: str = "",
    kg_service: Any | None = None,
    novel_id: str | None = None,
) -> dict[str, Any]:
    """生成单章内容。

    Returns:
        {"chapter": int, "title": str, "content": str, "word_count": int}
    """
    # 知识图谱上下文（可选）
    kg_context = ""
    if kg_service and novel_id:
        try:
            kg_context = await kg_service.retrieve_context(
                novel_id=novel_id,
                chapter_outline=chapter_outline,
            )
        except Exception as e:
            logger.warning("kg_context_retrieval_failed", error=str(e))

    prompt = CHAPTER_GENERATION_PROMPT.format(
        chapter_outline=json.dumps(chapter_outline, ensure_ascii=False),
        previous_chapter=previous_chapter or "这是第一章",
        characters=characters_json,
        world_setting=world_setting_json,
    )

    if kg_context:
        prompt = f"{kg_context}\n\n{prompt}"
    if storylines_json:
        prompt += f"\n\n已确定的故事线：\n{storylines_json}"
    if style_instruction:
        prompt = f"{style_instruction}\n\n{prompt}"

    content = await client.generate(prompt, max_tokens=8000)

    # 知识抽取（可选）
    if kg_service and novel_id:
        try:
            await kg_service.extract_from_chapter(
                novel_id=novel_id,
                chapter_number=chapter_outline.get("chapter", 0),
                chapter_text=content,
            )
        except Exception as e:
            logger.warning("kg_extraction_failed", error=str(e))

    return {
        "chapter": chapter_outline.get("chapter", 0),
        "title": chapter_outline.get("title", ""),
        "content": content,
        "word_count": len(content),
    }
