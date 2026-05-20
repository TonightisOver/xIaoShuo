"""单章生成共享逻辑"""

import json
from typing import Any

import structlog

from src.core.llm.prompts import CHAPTER_GENERATION_PROMPT, CHAPTER_PLANNING_PROMPT

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
    # 1. 检索知识图谱上下文
    kg_context = ""
    if kg_service and novel_id:
        try:
            kg_context = await kg_service.retrieve_context(
                novel_id=novel_id,
                chapter_outline=chapter_outline,
            )
        except Exception as e:
            logger.warning("kg_context_retrieval_failed", error=str(e))

    # 2. 检索故事圣经 (Story Bible) 核心设定约束
    story_bible_context = "无历史圣经数据"
    if novel_id:
        try:
            from sqlalchemy import select

            from src.api.models.db_models import StoryBible
            from src.core.database import get_db_session

            async with get_db_session() as session:
                stmt = select(StoryBible).where(StoryBible.novel_id == novel_id)
                res = await session.execute(stmt)
                bible = res.scalar_one_or_none()
                if bible:
                    char_cards_str = json.dumps(bible.character_cards or [], ensure_ascii=False, indent=2)
                    foreshadowings_str = json.dumps(bible.foreshadowing_list or [], ensure_ascii=False, indent=2)
                    story_bible_context = f"""
## 世界观规则:
{bible.worldview_rules or "未设定"}

## 人物卡:
{char_cards_str}

## 势力关系:
{bible.faction_relations or "未设定"}

## 地点设定:
{bible.location_settings or "未设定"}

## 道具设定:
{bible.prop_settings or "未设定"}

## 伏笔列表:
{foreshadowings_str}

## 禁止违背的硬设定:
{bible.hard_settings or "未设定"}
"""
        except Exception as e:
            logger.warning("story_bible_retrieval_failed", error=str(e))

    # 3. 双级联第 1 阶段：调用 LLM 进行前置大纲检查与伏笔情节规划
    planning_prompt = CHAPTER_PLANNING_PROMPT.format(
        chapter_outline=json.dumps(chapter_outline, ensure_ascii=False),
        previous_chapter=previous_chapter or "这是第一章",
        story_bible=story_bible_context,
        kg_context=kg_context or "无知识图谱上下文",
    )

    logger.info("generating_chapter_planning_check", chapter=chapter_outline.get("chapter", 0))
    chapter_plan = await client.generate(planning_prompt, max_tokens=3000)
    logger.info("chapter_planning_check_completed", chapter=chapter_outline.get("chapter", 0))

    # 4. 双级联第 2 阶段：将规划约束单注入正文生成 Prompt
    prompt = CHAPTER_GENERATION_PROMPT.format(
        chapter_outline=json.dumps(chapter_outline, ensure_ascii=False),
        previous_chapter=previous_chapter or "这是第一章",
        characters=characters_json,
        world_setting=world_setting_json,
    )

    # 结构化合并前置规划约束
    prompt = f"""\
# 章节生成依据规划单与约束

【特别提示】以下是你刚刚制定并必须严格遵守的“章节规划单”。生成正文时，你必须逐一贯彻这 7 点设定，特别是“必须遵循的旧设定”以及“本章回收的历史伏笔”、“本章种下的新伏笔”，绝对不要偏离！

{chapter_plan}

---

{prompt}
"""

    if kg_context:
        prompt = f"{kg_context}\n\n{prompt}"
    if storylines_json:
        prompt += f"\n\n已确定的故事线：\n{storylines_json}"
    if style_instruction:
        prompt = f"{style_instruction}\n\n{prompt}"

    # 5. 生成章节正文
    content = await client.generate(prompt, max_tokens=8000)

    # 6. 章节知识抽取（可选）
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
