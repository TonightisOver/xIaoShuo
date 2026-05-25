"""单章生成共享逻辑"""

import asyncio
import json
from typing import Any

import structlog

from src.core.llm.prompts import (
    CHAPTER_GENERATION_PROMPT,
    CHAPTER_GENERATION_PROMPT_WITH_WORD_COUNT,
    CHAPTER_PLANNING_PROMPT,
)

logger = structlog.get_logger(__name__)

CHAPTER_TIMEOUT_SECONDS = 600

# Word count thresholds for long-form mode
WORD_COUNT_MIN_RATIO = 0.8  # 80% of target = minimum acceptable
WORD_COUNT_MAX_RATIO = 1.2  # 120% of target = maximum acceptable
WORD_COUNT续写阈值 = 0.6  # Below 60% triggers continuation


def _check_word_count(
    word_count: int,
    target_words: int | None = None,
) -> tuple[bool, str | None]:
    """Check if word count is within acceptable range.

    Args:
        word_count: Actual word count
        target_words: Target word count (if None, skip check)

    Returns:
        (is_valid, warning_message)
    """
    if target_words is None or target_words <= 0:
        return True, None

    min_words = int(target_words * WORD_COUNT_MIN_RATIO)
    max_words = int(target_words * WORD_COUNT_MAX_RATIO)

    if word_count < min_words:
        return False, f"字数不足：{word_count}字 < 最低{min_words}字（目标{target_words}字的80%）"
    elif word_count > max_words:
        return True, f"字数偏多：{word_count}字 > 建议{max_words}字（目标{target_words}字的120%），但保留完整性不截断"
    return True, None


async def _continuation_generation(
    client: Any,
    original_content: str,
    chapter_outline: dict[str, Any],
    characters_json: str,
    world_setting_json: str,
    target_words: int,
    current_words: int,
    style_instruction: str = "",
) -> str:
    """Generate continuation for short chapters.

    Args:
        client: LLM client
        original_content: Original generated content
        chapter_outline: Chapter outline dict
        characters_json: Characters JSON string
        world_setting_json: World setting JSON string
        target_words: Target word count
        current_words: Current word count
        style_instruction: Style instruction

    Returns:
        Continued content
    """
    remaining_words = target_words - current_words
    if remaining_words <= 0:
        return original_content

    continuation_prompt = f"""请继续续写以下章节内容，补充约 {remaining_words} 字，使总字数达到 {target_words} 字左右。

## 已有内容
{original_content[-2000:]}

## 章节大纲
{json.dumps(chapter_outline, ensure_ascii=False)}

## 要求
1. 与已有内容自然衔接
2. 补充的情节要符合章节大纲
3. 对话生动，描写细腻
4. 约续写 {remaining_words} 字

请直接输出续写内容（不需要重复章节标题），不要输出 JSON 或其他格式包装。
"""
    if style_instruction:
        continuation_prompt = f"{style_instruction}\n\n{continuation_prompt}"

    continued = await client.generate(continuation_prompt, max_tokens=4000)
    return original_content + "\n\n" + continued


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
    target_words: int | None = None,
) -> dict[str, Any]:
    """生成单章内容。

    Args:
        target_words: Target word count for long-form mode (None for standard mode)

    Returns:
        {"chapter": int, "title": str, "content": str, "word_count": int}
    """
    try:
        return await asyncio.wait_for(
            _generate_single_chapter_inner(
                client=client,
                chapter_outline=chapter_outline,
                previous_chapter=previous_chapter,
                characters_json=characters_json,
                world_setting_json=world_setting_json,
                storylines_json=storylines_json,
                style_instruction=style_instruction,
                kg_service=kg_service,
                novel_id=novel_id,
                target_words=target_words,
            ),
            timeout=CHAPTER_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        chapter_num = chapter_outline.get("chapter", 0)
        logger.error("chapter_generation_timeout", chapter=chapter_num, timeout=CHAPTER_TIMEOUT_SECONDS)
        return {
            "chapter": chapter_num,
            "title": chapter_outline.get("title", f"第{chapter_num}章"),
            "content": f"[章节生成失败：生成超时（{CHAPTER_TIMEOUT_SECONDS}s），可能是模型响应较慢，请稍后重试]",
            "word_count": 0,
            "generation_failed": True,
        }


async def _generate_single_chapter_inner(
    client: Any,
    chapter_outline: dict[str, Any],
    previous_chapter: str,
    characters_json: str,
    world_setting_json: str,
    storylines_json: str = "",
    style_instruction: str = "",
    kg_service: Any | None = None,
    novel_id: str | None = None,
    target_words: int | None = None,
) -> dict[str, Any]:
    """生成单章内容。

    Args:
        target_words: Target word count for long-form mode (None for standard mode)

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

    # 2. 检索故事圣经 (Story Bible) 精准约束抽取
    story_bible_context = "无历史圣经数据"
    if novel_id:
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
                    story_bible_context = extract_relevant_constraints(
                        bible, chapter_outline, chapter_num
                    )
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
    if target_words is not None and target_words > 0:
        target_min = int(target_words * WORD_COUNT_MIN_RATIO)
        target_max = int(target_words * WORD_COUNT_MAX_RATIO)
        prompt = CHAPTER_GENERATION_PROMPT_WITH_WORD_COUNT.format(
            chapter_outline=json.dumps(chapter_outline, ensure_ascii=False),
            previous_chapter=previous_chapter or "这是第一章",
            characters=characters_json,
            world_setting=world_setting_json,
            target_words=target_words,
            target_words_min=target_min,
            target_words_max=target_max,
        )
    else:
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

    # 7. Word count check and continuation for long-form mode
    word_count = len(content)
    if target_words is not None and target_words > 0:
        is_valid, warning = _check_word_count(word_count, target_words)
        if warning:
            logger.info(
                "word_count_check",
                chapter=chapter_outline.get("chapter", 0),
                word_count=word_count,
                target=target_words,
                warning=warning,
            )

        # Continuation for very short chapters
        min_threshold = int(target_words * WORD_COUNT续写阈值)
        if word_count < min_threshold:
            logger.info(
                "chapter_too_short_initiating_continuation",
                chapter=chapter_outline.get("chapter", 0),
                word_count=word_count,
                target=target_words,
            )
            try:
                content = await _continuation_generation(
                    client=client,
                    original_content=content,
                    chapter_outline=chapter_outline,
                    characters_json=characters_json,
                    world_setting_json=world_setting_json,
                    target_words=target_words,
                    current_words=word_count,
                    style_instruction=style_instruction,
                )
                word_count = len(content)
                logger.info(
                    "continuation_completed",
                    chapter=chapter_outline.get("chapter", 0),
                    new_word_count=word_count,
                )
            except Exception as e:
                logger.warning(
                    "continuation_failed",
                    chapter=chapter_outline.get("chapter", 0),
                    error=str(e),
                )

    return {
        "chapter": chapter_outline.get("chapter", 0),
        "title": chapter_outline.get("title", ""),
        "content": content,
        "word_count": word_count,
    }
