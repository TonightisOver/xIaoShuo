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


def _format_blueprint_constraint(blueprint: dict) -> str:
    """将蓝图 dict 格式化为结构化约束文本。"""
    foreshadow_actions = blueprint.get("foreshadow_actions") or []
    if isinstance(foreshadow_actions, list):
        foreshadow_text = "; ".join(
            f"{a.get('type', '未知')}：{a.get('description', '')}"
            if isinstance(a, dict)
            else str(a)
            for a in foreshadow_actions
        )
    else:
        foreshadow_text = str(foreshadow_actions)

    key_characters = blueprint.get("key_characters") or []
    if isinstance(key_characters, list):
        characters_text = "、".join(str(c) for c in key_characters)
    else:
        characters_text = str(key_characters)

    return f"""\
# 章节蓝图约束（必须严格遵守）

- 章节类型: {blueprint.get("chapter_type", "main_advance")}
- 剧情推进目标: {blueprint.get("plot_goal", "")}
- 爽点/冲突设计: {blueprint.get("hook_design", "")}
- 伏笔操作: {foreshadow_text}
- 章末钩子: {blueprint.get("cliffhanger", "")}
- 节奏定位: {blueprint.get("pacing_target", "medium")}
- 核心出场人物: {characters_text}
- 目标字数: {blueprint.get("word_target", 3000)}"""

CHAPTER_TIMEOUT_SECONDS = 600

# Word count thresholds for long-form mode
WORD_COUNT_MIN_RATIO = 0.8  # 80% of target = minimum acceptable
WORD_COUNT_MAX_RATIO = 1.2  # 120% of target = maximum acceptable
WORD_COUNT续写阈值 = 0.75  # Below 75% triggers continuation
MAX_CONTINUATION_ATTEMPTS = 3  # 最多续写次数


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

    continued = await client.generate(continuation_prompt, max_tokens=6000, use_flash=True)
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
    blueprint: dict | None = None,
    story_bible_context: str | None = None,
) -> dict[str, Any]:
    """生成单章内容。

    Args:
        target_words: Target word count for long-form mode (None for standard mode)
        blueprint: 预生成的章节蓝图（可选，传入则跳过蓝图生成/查询）
        story_bible_context: 故事圣经约束文本（由调用方查询后传入）

    Returns:
        {"chapter": int, "title": str, "content": str, "word_count": int,
         "chapter_type": str | None}
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
                blueprint=blueprint,
                story_bible_context=story_bible_context,
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
    blueprint: dict | None = None,
    story_bible_context: str | None = None,
) -> dict[str, Any]:
    """生成单章内容。

    Args:
        target_words: Target word count for long-form mode (None for standard mode)
        blueprint: 预生成的章节蓝图（可选，传入则跳过蓝图生成/查询）
        story_bible_context: 故事圣经约束文本（由调用方查询后传入）

    Returns:
        {"chapter": int, "title": str, "content": str, "word_count": int,
         "chapter_type": str | None}
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

    # 2. 使用调用方传入的故事圣经上下文
    if not story_bible_context:
        story_bible_context = "无历史圣经数据"

    # 3. 结构化蓝图（由调用方传入）或降级到 LLM 规划
    chapter_num = chapter_outline.get("chapter", 0)
    blueprint_constraint: str | None = None

    if blueprint:
        blueprint_constraint = _format_blueprint_constraint(blueprint)
        logger.info("using_provided_blueprint", chapter=chapter_num)

    if blueprint_constraint is None:
        planning_prompt = CHAPTER_PLANNING_PROMPT.format(
            chapter_outline=json.dumps(chapter_outline, ensure_ascii=False),
            previous_chapter=previous_chapter or "这是第一章",
            story_bible=story_bible_context,
            kg_context=kg_context or "无知识图谱上下文",
        )
        logger.info("generating_chapter_planning_check", chapter=chapter_num)
        chapter_plan = await client.generate(planning_prompt, max_tokens=3000)
        logger.info("chapter_planning_check_completed", chapter=chapter_num)
        blueprint_constraint = f"""\
# 章节生成依据规划单与约束

【特别提示】以下是你刚刚制定并必须严格遵守的"章节规划单"。生成正文时，你必须逐一贯彻这 7 点设定，特别是"必须遵循的旧设定"以及"本章回收的历史伏笔"、"本章种下的新伏笔"，绝对不要偏离！

{chapter_plan}"""

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

    # 结构化合并蓝图/规划约束
    prompt = f"""\
{blueprint_constraint}

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
    content = await client.generate(prompt, max_tokens=8000, use_flash=True)

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

        # Continuation loop for short chapters — up to MAX_CONTINUATION_ATTEMPTS times
        min_threshold = int(target_words * WORD_COUNT续写阈值)
        for attempt in range(MAX_CONTINUATION_ATTEMPTS):
            if word_count >= min_threshold:
                break
            logger.info(
                "chapter_continuation_attempt",
                chapter=chapter_outline.get("chapter", 0),
                attempt=attempt + 1,
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
                word_count = len(content)  # 每次续写后重新计算实际字数
                logger.info(
                    "continuation_completed",
                    chapter=chapter_outline.get("chapter", 0),
                    attempt=attempt + 1,
                    new_word_count=word_count,
                )
            except Exception as e:
                logger.warning(
                    "continuation_failed",
                    chapter=chapter_outline.get("chapter", 0),
                    attempt=attempt + 1,
                    error=str(e),
                )
                break

    # 8. 提取 chapter_type 到返回值（由调用方负责 DB 更新）
    chapter_type = blueprint.get("chapter_type") if blueprint else None

    return {
        "chapter": chapter_outline.get("chapter", 0),
        "title": chapter_outline.get("title", ""),
        "content": content,
        "word_count": word_count,
        "chapter_type": chapter_type,
    }
