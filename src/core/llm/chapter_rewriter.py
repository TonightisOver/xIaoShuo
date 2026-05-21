"""章节 AI 改写引擎"""

import asyncio
import json

import structlog

from src.core.llm.client import get_llm_client

logger = structlog.get_logger(__name__)

REWRITE_TIMEOUT_SECONDS = 120


async def rewrite_chapter_segment(
    novel_id: str,
    chapter_number: int,
    full_content: str,
    selected_text: str,
    instruction: str,
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

    context = await _build_rewrite_context(novel_id, chapter_number)

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
    return result.strip()


async def _build_rewrite_context(novel_id: str, chapter_number: int) -> dict:
    """从数据库读取改写所需的上下文信息。"""
    from sqlalchemy import select

    from src.api.models.db_models import Chapter, Novel, Outline, StoryBible
    from src.core.database import get_db_session

    ctx: dict = {
        "world_setting": "",
        "chapter_outline": "",
        "prev_chapter_summary": "",
        "next_chapter_summary": "",
        "characters": "",
        "story_bible": "",
        "writing_style": "",
    }

    async with get_db_session() as session:
        # 小说基本信息（文风）
        novel_res = await session.execute(
            select(Novel).where(Novel.novel_id == novel_id)
        )
        novel = novel_res.scalar_one_or_none()
        if novel:
            ctx["writing_style"] = novel.writing_style_prompt or novel.writing_style or ""

        # 世界观
        from src.api.models.db_models import WorldSetting
        ws_res = await session.execute(
            select(WorldSetting).where(WorldSetting.novel_id == novel_id)
        )
        ws = ws_res.scalar_one_or_none()
        if ws:
            parts = []
            if ws.background:
                parts.append(f"背景：{ws.background}")
            if ws.geography:
                parts.append(f"地理：{ws.geography}")
            if ws.culture:
                parts.append(f"文化：{ws.culture}")
            if ws.rules:
                parts.append(f"规则：{ws.rules}")
            ctx["world_setting"] = "\n".join(parts)

        # 章节大纲
        outline_res = await session.execute(
            select(Outline).where(
                Outline.novel_id == novel_id,
                Outline.level == "chapter",
                Outline.chapter_number == chapter_number,
            )
        )
        outline = outline_res.scalar_one_or_none()
        if outline and outline.content:
            ctx["chapter_outline"] = json.dumps(outline.content, ensure_ascii=False)

        # 前一章摘要（取正文前 300 字）
        if chapter_number > 1:
            prev_res = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number - 1,
                )
            )
            prev_ch = prev_res.scalar_one_or_none()
            if prev_ch and prev_ch.content:
                ctx["prev_chapter_summary"] = prev_ch.content[:300]

        # 后一章摘要（取正文前 300 字）
        next_res = await session.execute(
            select(Chapter).where(
                Chapter.novel_id == novel_id,
                Chapter.chapter_number == chapter_number + 1,
            )
        )
        next_ch = next_res.scalar_one_or_none()
        if next_ch and next_ch.content:
            ctx["next_chapter_summary"] = next_ch.content[:300]

        # 人物卡
        from src.api.models.db_models import Character
        chars_res = await session.execute(
            select(Character).where(Character.novel_id == novel_id)
        )
        chars = chars_res.scalars().all()
        if chars:
            char_list = [
                f"- {c.name}（{c.role or '未知'}）：{c.description or ''}"
                for c in chars
            ]
            ctx["characters"] = "\n".join(char_list)

        # Story Bible
        bible_res = await session.execute(
            select(StoryBible).where(StoryBible.novel_id == novel_id)
        )
        bible = bible_res.scalar_one_or_none()
        if bible:
            char_cards_str = json.dumps(bible.character_cards or [], ensure_ascii=False, indent=2)
            foreshadowings_str = json.dumps(bible.foreshadowing_list or [], ensure_ascii=False, indent=2)
            ctx["story_bible"] = f"""世界观规则：{bible.worldview_rules or "未设定"}
人物卡：{char_cards_str}
势力关系：{bible.faction_relations or "未设定"}
地点设定：{bible.location_settings or "未设定"}
道具设定：{bible.prop_settings or "未设定"}
伏笔列表：{foreshadowings_str}
禁止违背的硬设定：{bible.hard_settings or "未设定"}"""

    return ctx


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
