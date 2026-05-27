"""NovelContextBuilder — 统一的小说上下文构建器。

将分散在 novel_generator / chapter_rewriter / blueprint_service 中的
DB 查询 + 序列化逻辑集中到此模块，消除重复代码。
"""

from __future__ import annotations

import json
from dataclasses import dataclass

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.models.db_models import (
    Chapter,
    Character,
    Novel,
    Outline,
    StoryBible,
    Storyline,
    WorldSetting,
)
from src.core.validation import get_style_instruction

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Data classes for structured context results
# ---------------------------------------------------------------------------


@dataclass
class GenerationContext:
    """章节生成所需的上下文。"""

    world_str: str = "暂无世界观"
    chars_str: str = "暂无人物"
    storylines_str: str = ""
    style_instruction: str = ""


@dataclass
class RewriteContext:
    """改写所需的完整上下文。"""

    world_setting: str = ""
    chapter_outline: str = ""
    prev_chapter_summary: str = ""
    next_chapter_summary: str = ""
    characters: str = ""
    story_bible: str = ""
    writing_style: str = ""


@dataclass
class BlueprintContext:
    """蓝图生成所需的上下文。"""

    previous_chapter: str = ""
    story_bible: str = ""
    kg_context: str = ""
    volume_context: str = ""


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------


class NovelContextBuilder:
    """统一的上下文构建器，所有 DB 查询集中在此。

    session 由调用方传入，本类不自行创建 session。
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def build_generation_context(
        self, session: AsyncSession, novel_id: str
    ) -> GenerationContext:
        """构建章节生成上下文。

        返回 world_str, chars_str, storylines_str, style_instruction。
        用于 generate_volume_background / generate_chapters_background /
        _generate_volume_chapters 等场景。
        """
        ctx = GenerationContext()

        # Novel — writing style
        novel = await self._get_novel(session, novel_id)
        if novel:
            ctx.style_instruction = get_style_instruction(
                novel.writing_style or "",
                novel.writing_style_prompt or "",
            )

        # World setting
        ctx.world_str = await self._build_world_str(session, novel_id)

        # Characters
        ctx.chars_str = await self._build_chars_str(session, novel_id)

        # Storylines
        ctx.storylines_str = await self._build_storylines_str(session, novel_id)

        return ctx

    async def build_rewrite_context(
        self, session: AsyncSession, novel_id: str, chapter_number: int
    ) -> RewriteContext:
        """构建改写所需的完整上下文。

        用于 chapter_rewriter.rewrite_chapter_segment / targeted_rewrite。
        """
        ctx = RewriteContext()

        # Novel — writing style
        novel = await self._get_novel(session, novel_id)
        if novel:
            ctx.writing_style = novel.writing_style_prompt or novel.writing_style or ""

        # World setting (detailed)
        ws = await self._get_world_setting(session, novel_id)
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
            ctx.world_setting = "\n".join(parts)

        # Chapter outline
        outline_res = await session.execute(
            select(Outline).where(
                Outline.novel_id == novel_id,
                Outline.level == "chapter",
                Outline.chapter_number == chapter_number,
            )
        )
        outline = outline_res.scalar_one_or_none()
        if outline and outline.content:
            ctx.chapter_outline = json.dumps(outline.content, ensure_ascii=False)

        # Previous chapter summary (first 300 chars)
        if chapter_number > 1:
            prev_res = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number - 1,
                )
            )
            prev_ch = prev_res.scalar_one_or_none()
            if prev_ch and prev_ch.content:
                ctx.prev_chapter_summary = prev_ch.content[:300]

        # Next chapter summary (first 300 chars)
        next_res = await session.execute(
            select(Chapter).where(
                Chapter.novel_id == novel_id,
                Chapter.chapter_number == chapter_number + 1,
            )
        )
        next_ch = next_res.scalar_one_or_none()
        if next_ch and next_ch.content:
            ctx.next_chapter_summary = next_ch.content[:300]

        # Characters
        chars_res = await session.execute(
            select(Character).where(Character.novel_id == novel_id)
        )
        chars = chars_res.scalars().all()
        if chars:
            char_list = [
                f"- {c.name}（{c.role or '未知'}）：{c.description or ''}"
                for c in chars
            ]
            ctx.characters = "\n".join(char_list)

        # Story Bible
        bible = await self._get_story_bible(session, novel_id)
        if bible:
            char_cards_str = json.dumps(
                bible.character_cards or [], ensure_ascii=False, indent=2
            )
            foreshadowings_str = json.dumps(
                bible.foreshadowing_list or [], ensure_ascii=False, indent=2
            )
            ctx.story_bible = (
                f"世界观规则：{bible.worldview_rules or '未设定'}\n"
                f"人物卡：{char_cards_str}\n"
                f"势力关系：{bible.faction_relations or '未设定'}\n"
                f"地点设定：{bible.location_settings or '未设定'}\n"
                f"道具设定：{bible.prop_settings or '未设定'}\n"
                f"伏笔列表：{foreshadowings_str}\n"
                f"禁止违背的硬设定：{bible.hard_settings or '未设定'}"
            )

        return ctx

    async def build_blueprint_context(
        self,
        session: AsyncSession,
        novel_id: str,
        chapter_number: int,
        chapter_outline: dict,
    ) -> BlueprintContext:
        """构建蓝图生成上下文。

        用于 blueprint_service.generate_blueprint。
        注意：kg_context 需要调用方自行补充（因为 KG 服务不依赖 session）。
        """
        ctx = BlueprintContext()

        # Previous chapter (first 500 chars)
        if chapter_number > 1:
            prev_res = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number - 1,
                )
            )
            prev_ch = prev_res.scalar_one_or_none()
            if prev_ch and prev_ch.content:
                ctx.previous_chapter = prev_ch.content[:500]

        # Story Bible
        bible = await self._get_story_bible(session, novel_id)
        if bible:
            parts = []
            if bible.worldview_rules:
                parts.append(f"世界观规则：{bible.worldview_rules}")
            if bible.hard_settings:
                parts.append(f"硬设定：{bible.hard_settings}")
            if bible.character_cards:
                parts.append(
                    f"人物卡：{json.dumps(bible.character_cards, ensure_ascii=False)}"
                )
            if bible.foreshadowing_list:
                foreshadow_json = json.dumps(
                    bible.foreshadowing_list, ensure_ascii=False
                )
                parts.append(f"伏笔列表：{foreshadow_json}")
            ctx.story_bible = "\n".join(parts)

        # Volume context (for long-form novels)
        novel = await self._get_novel(session, novel_id)
        if novel and novel.is_long_form:
            chapter_obj_res = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                )
            )
            chapter_obj = chapter_obj_res.scalar_one_or_none()
            if chapter_obj and chapter_obj.volume_number:
                vol_outline_res = await session.execute(
                    select(Outline).where(
                        Outline.novel_id == novel_id,
                        Outline.level == "volume",
                        Outline.volume_number == chapter_obj.volume_number,
                    )
                )
                vol_outline = vol_outline_res.scalar_one_or_none()
                if vol_outline and vol_outline.content:
                    ctx.volume_context = json.dumps(
                        vol_outline.content, ensure_ascii=False
                    )

        return ctx

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_novel(session: AsyncSession, novel_id: str) -> Novel | None:
        result = await session.execute(
            select(Novel).where(Novel.novel_id == novel_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_world_setting(
        session: AsyncSession, novel_id: str
    ) -> WorldSetting | None:
        result = await session.execute(
            select(WorldSetting).where(WorldSetting.novel_id == novel_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _get_story_bible(
        session: AsyncSession, novel_id: str
    ) -> StoryBible | None:
        result = await session.execute(
            select(StoryBible).where(StoryBible.novel_id == novel_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _build_world_str(session: AsyncSession, novel_id: str) -> str:
        """构建世界观 JSON 字符串（用于生成场景）。"""
        result = await session.execute(
            select(WorldSetting).where(WorldSetting.novel_id == novel_id)
        )
        ws = result.scalar_one_or_none()
        if not ws:
            return "暂无世界观"
        return json.dumps(
            {
                "background": ws.background or "",
                "rules": ws.rules or "",
                "geography": ws.geography or "",
                "culture": ws.culture or "",
            },
            ensure_ascii=False,
        )

    @staticmethod
    async def _build_chars_str(session: AsyncSession, novel_id: str) -> str:
        """构建人物 JSON 字符串（用于生成场景）。"""
        result = await session.execute(
            select(Character).where(Character.novel_id == novel_id)
        )
        chars = result.scalars().all()
        if not chars:
            return "暂无人物"
        return json.dumps(
            [
                {
                    "name": c.name,
                    "role": c.role,
                    "personality": c.personality,
                    "description": c.description,
                }
                for c in chars
            ],
            ensure_ascii=False,
        )

    @staticmethod
    async def _build_storylines_str(session: AsyncSession, novel_id: str) -> str:
        """构建故事线 JSON 字符串。"""
        result = await session.execute(
            select(Storyline).where(Storyline.novel_id == novel_id)
        )
        storylines = result.scalars().all()
        if not storylines:
            return ""
        return json.dumps(
            [
                {
                    "name": s.name,
                    "type": s.type,
                    "description": s.description,
                }
                for s in storylines
            ],
            ensure_ascii=False,
        )
