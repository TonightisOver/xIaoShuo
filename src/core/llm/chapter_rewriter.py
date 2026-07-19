"""章节 AI 改写引擎"""

import asyncio

import structlog

from src.core.llm.chapter_generator import post_process_chapter
from src.core.llm.client import get_llm_client
from src.core.llm.prompts import TARGETED_REWRITE_PROMPTS

logger = structlog.get_logger(__name__)

REWRITE_TIMEOUT_SECONDS = 120


async def rewrite_chapter_segment(
    novel_id: str,
    chapter_number: int,
    full_content: str,
    selected_text: str,
    instruction: str,
    *,
    context: dict,
) -> str:
    """对章节中选中的文本片段进行 AI 改写。

    组装包含世界观、大纲、前后章摘要、人物卡、Story Bible、文风和完整正文的上下文 Prompt，
    然后调用 LLM 对选中文本按指令改写，返回改写后的文本。

    Args:
        novel_id: 小说 ID
        chapter_number: 章节号
        full_content: 章节完整正文
        selected_text: 用户选中的文本片段
        instruction: 改写指令
        context: 预构建的改写上下文 dict，包含 world_setting / chapter_outline /
            prev_chapter_summary / next_chapter_summary / characters /
            story_bible / writing_style 等字段

    Returns:
        改写后的文本（仅替换片段，不含其他内容）

    Raises:
        asyncio.TimeoutError: 超过 120s 超时
    """
    logger.info(
        "rewriting_chapter_segment",
        novel_id=novel_id,
        chapter_number=chapter_number,
        selected_length=len(selected_text),
        instruction=instruction,
    )

    prompt = _build_rewrite_prompt(
        context=context,
        full_content=full_content,
        selected_text=selected_text,
        instruction=instruction,
    )

    client = get_llm_client()
    result = await asyncio.wait_for(
        client.generate(prompt, max_tokens=4000),
        timeout=REWRITE_TIMEOUT_SECONDS,
    )

    logger.info(
        "rewriting_chapter_segment_done",
        novel_id=novel_id,
        chapter_number=chapter_number,
        result_length=len(result),
    )
    # 复用章节后处理：清洗半角连字符、AI 病句等（与单章生成一致）
    return post_process_chapter(result)


def _build_rewrite_prompt(
    context: dict,
    full_content: str,
    selected_text: str,
    instruction: str,
) -> str:
    """组装改写 Prompt。"""
    sections = []

    if context.get("writing_style"):
        sections.append(f"## 文风要求\n{context['writing_style']}")

    if context.get("story_bible"):
        sections.append(f"## Story Bible（核心设定约束）\n{context['story_bible']}")

    if context.get("world_setting"):
        sections.append(f"## 世界观\n{context['world_setting']}")

    if context.get("chapter_outline"):
        sections.append(f"## 本章大纲\n{context['chapter_outline']}")

    if context.get("characters"):
        sections.append(f"## 人物卡\n{context['characters']}")

    if context.get("prev_chapter_summary"):
        sections.append(f"## 上一章摘要（前300字）\n{context['prev_chapter_summary']}")

    if context.get("next_chapter_summary"):
        sections.append(f"## 下一章摘要（前300字）\n{context['next_chapter_summary']}")

    sections.append(f"## 本章完整正文\n{full_content}")

    sections.append(
        f"""## 改写任务

需要改写的选中文本：
「{selected_text}」

改写指令：{instruction}

请严格按照以上设定和文风，对选中文本进行改写。
要求：
1. 只输出改写后的文本，不要包含任何解释、说明或前缀
2. 保持与上下文的连贯性
3. 遵守 Story Bible 中的硬设定，不得违背
4. 改写后的文本应能直接替换原文中的选中部分"""
    )

    return "\n\n".join(sections)


async def targeted_rewrite(
    novel_id: str,
    chapter_number: int,
    full_content: str,
    rewrite_type: str,
    instruction: str = "",
    *,
    context: dict,
) -> str:
    """按改写类型对整章内容执行定向改写。

    Args:
        novel_id: 小说 ID
        chapter_number: 章节号
        full_content: 章节完整正文
        rewrite_type: 改写类型
        instruction: 额外改写指令（可选）
        context: 预构建的改写上下文 dict

    Returns:
        改写后的完整章节内容

    Raises:
        ValueError: rewrite_type 不在支持列表中
        asyncio.TimeoutError: 超过 120s 超时
    """
    if rewrite_type not in TARGETED_REWRITE_PROMPTS:
        raise ValueError(
            f"Unsupported rewrite_type: {rewrite_type}. "
            f"Supported: {list(TARGETED_REWRITE_PROMPTS.keys())}"
        )

    logger.info(
        "targeted_rewrite_start",
        novel_id=novel_id,
        chapter_number=chapter_number,
        rewrite_type=rewrite_type,
        content_length=len(full_content),
    )

    prompt_template = TARGETED_REWRITE_PROMPTS[rewrite_type]
    prompt = prompt_template.format(
        full_content=full_content,
        instruction=instruction or "无额外指令",
        context=context.get("chapter_outline", ""),
        characters=context.get("characters", "无人物信息"),
        world_setting=context.get("world_setting", "无世界设定"),
    )

    client = get_llm_client()
    result = await asyncio.wait_for(
        client.generate(prompt, max_tokens=8000),
        timeout=REWRITE_TIMEOUT_SECONDS,
    )

    logger.info(
        "targeted_rewrite_done",
        novel_id=novel_id,
        chapter_number=chapter_number,
        rewrite_type=rewrite_type,
        result_length=len(result),
    )
    # 复用章节后处理：清洗半角连字符、AI 病句等（与单章生成一致）
    return post_process_chapter(result)


async def batch_targeted_rewrite(
    novel_id: str,
    chapter_number: int,
    full_content: str,
    actions: list[dict],
    *,
    context: dict,
) -> str:
    """按优先级顺序依次执行多个改写动作。

    每次改写基于上一次的输出。

    Args:
        novel_id: 小说 ID
        chapter_number: 章节号
        full_content: 章节完整正文
        actions: list of {action_type, dimension, score, instruction, priority}
        context: 预构建的改写上下文 dict

    Returns:
        最终改写后的完整章节内容
    """
    if not actions:
        return full_content

    sorted_actions = sorted(actions, key=lambda a: a.get("priority", 99))

    logger.info(
        "batch_targeted_rewrite_start",
        novel_id=novel_id,
        chapter_number=chapter_number,
        action_count=len(sorted_actions),
        action_types=[a.get("action_type") for a in sorted_actions],
    )

    current_content = full_content
    for i, action in enumerate(sorted_actions):
        action_type = action.get("action_type", "")
        instruction = action.get("instruction", "")

        if action_type not in TARGETED_REWRITE_PROMPTS:
            logger.warning(
                "batch_rewrite_skip_unknown_type",
                novel_id=novel_id,
                chapter_number=chapter_number,
                action_type=action_type,
                step=i + 1,
            )
            continue

        try:
            current_content = await targeted_rewrite(
                novel_id=novel_id,
                chapter_number=chapter_number,
                full_content=current_content,
                rewrite_type=action_type,
                instruction=instruction,
                context=context,
            )
            logger.info(
                "batch_rewrite_step_done",
                novel_id=novel_id,
                chapter_number=chapter_number,
                step=i + 1,
                action_type=action_type,
                content_length=len(current_content),
            )
        except Exception as e:
            logger.error(
                "batch_rewrite_step_failed",
                novel_id=novel_id,
                chapter_number=chapter_number,
                step=i + 1,
                action_type=action_type,
                error=str(e),
            )
            break

    logger.info(
        "batch_targeted_rewrite_done",
        novel_id=novel_id,
        chapter_number=chapter_number,
        final_length=len(current_content),
    )
    return current_content
