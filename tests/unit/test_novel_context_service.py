"""Unit tests for novel_context_service.NovelContextBuilder.

覆盖范围:
- build_generation_context: 有数据 / 无数据两条路径
- build_rewrite_context: 有数据 / 无数据 / 边界 (chapter_number==1 不查 prev) 路径
- build_blueprint_context: 非长篇 / 长篇有卷纲 / 首章无 prev 路径

依赖说明:
NovelContextBuilder 不自行创建 session（session 由调用方传入），
因此无需 mock get_db_session，直接传入 AsyncMock session 即可。
所有 DB 查询通过 mock session.execute 的 side_effect 按调用顺序分发结果，
被测方法本身的序列化/拼接逻辑真实执行。
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.services.quality.novel_context_service import (
    BlueprintContext,
    GenerationContext,
    NovelContextBuilder,
    RewriteContext,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scalar_result(value):
    """构造一个 execute 结果，其 scalar_one_or_none 返回 value。"""
    res = MagicMock()
    res.scalar_one_or_none.return_value = value
    return res


def _list_result(items):
    """构造一个 execute 结果，其 scalars().all() 返回 items。"""
    res = MagicMock()
    res.scalars.return_value.all.return_value = items
    return res


def _session_from_results(results):
    """构造 AsyncMock session，execute 按调用顺序依次返回 results 中的元素。

    超出列表长度的调用返回最后一个元素（兜底）。
    """
    session = AsyncMock()
    results = list(results)
    last = results[-1] if results else _scalar_result(None)

    async def _side_effect(*args, **kwargs):
        if results:
            return results.pop(0)
        return last

    session.execute = AsyncMock(side_effect=_side_effect)
    return session


def _novel(**kwargs):
    n = MagicMock()
    n.writing_style = kwargs.get("writing_style", "现代白话")
    n.writing_style_prompt = kwargs.get("writing_style_prompt", "")
    n.is_long_form = kwargs.get("is_long_form", False)
    return n


def _world_setting(**kwargs):
    ws = MagicMock()
    ws.background = kwargs.get("background")
    ws.geography = kwargs.get("geography")
    ws.culture = kwargs.get("culture")
    ws.rules = kwargs.get("rules")
    return ws


def _character(**kwargs):
    c = MagicMock()
    c.name = kwargs.get("name", "主角")
    c.role = kwargs.get("role", "主角")
    c.personality = kwargs.get("personality", None)
    c.description = kwargs.get("description", None)
    return c


def _storyline(**kwargs):
    s = MagicMock()
    s.name = kwargs.get("name", "主线")
    s.type = kwargs.get("type", "main")
    s.description = kwargs.get("description", "推进剧情")
    return s


def _chapter(**kwargs):
    ch = MagicMock()
    ch.content = kwargs.get("content", "章节正文内容")
    ch.volume_number = kwargs.get("volume_number", None)
    ch.state_delta = kwargs.get("state_delta", None)
    return ch


def _outline(**kwargs):
    o = MagicMock()
    o.content = kwargs.get("content", {"summary": "章纲"})
    return o


def _story_bible(**kwargs):
    b = MagicMock()
    b.worldview_rules = kwargs.get("worldview_rules", "规则A")
    b.character_cards = kwargs.get("character_cards", [{"name": "主角"}])
    b.faction_relations = kwargs.get("faction_relations", "势力1")
    b.location_settings = kwargs.get("location_settings", "地点1")
    b.prop_settings = kwargs.get("prop_settings", "道具1")
    b.foreshadowing_list = kwargs.get("foreshadowing_list", [{"id": 1}])
    b.hard_settings = kwargs.get("hard_settings", "硬设定A")
    return b


# ---------------------------------------------------------------------------
# build_generation_context
# ---------------------------------------------------------------------------


class TestBuildGenerationContext:
    """build_generation_context: 有数据 / 无数据两条路径。"""

    @pytest.fixture
    def builder(self):
        return NovelContextBuilder()

    @pytest.mark.asyncio
    async def test_no_data_uses_defaults(self, builder):
        """无 novel/世界观/人物/故事线时使用默认值。"""
        # 执行顺序: _get_novel -> _build_world_str -> _build_chars_str -> _build_storylines_str
        session = _session_from_results(
            [_scalar_result(None), _scalar_result(None), _list_result([]), _list_result([])]
        )

        ctx = await builder.build_generation_context(session, "novel-x")

        assert isinstance(ctx, GenerationContext)
        assert ctx.style_instruction == ""
        assert ctx.world_str == "暂无世界观"
        assert ctx.chars_str == "暂无人物"
        assert ctx.storylines_str == ""

    @pytest.mark.asyncio
    async def test_with_data_builds_strings(self, builder):
        """有数据时正确序列化 world/chars/storylines 与预设文风。"""
        novel = _novel(writing_style="现代白话", writing_style_prompt="")
        ws = _world_setting(background="末日荒原", rules="修炼", geography="沙漠", culture="部落")
        chars = [_character(name="阿甲", role="主角", personality="坚毅", description="少年")]
        storylines = [_storyline(name="复仇", type="main", description="寻找仇人")]

        session = _session_from_results(
            [
                _scalar_result(novel),
                _scalar_result(ws),
                _list_result(chars),
                _list_result(storylines),
            ]
        )

        ctx = await builder.build_generation_context(session, "novel-x")

        # 预设风格 -> get_style_instruction 返回非空常量
        assert ctx.style_instruction != ""
        assert json.loads(ctx.world_str) == {
            "background": "末日荒原",
            "rules": "修炼",
            "geography": "沙漠",
            "culture": "部落",
        }
        chars_data = json.loads(ctx.chars_str)
        assert len(chars_data) == 1
        assert chars_data[0]["name"] == "阿甲"
        sl_data = json.loads(ctx.storylines_str)
        assert sl_data[0]["name"] == "复仇"

    @pytest.mark.asyncio
    async def test_custom_style_uses_prompt(self, builder):
        """自定义文风应使用 writing_style_prompt 作为 style_instruction。"""
        novel = _novel(writing_style="自定义", writing_style_prompt="请写得像古龙")
        session = _session_from_results(
            [
                _scalar_result(novel),
                _scalar_result(None),  # world
                _list_result([]),  # chars
                _list_result([]),  # storylines
            ]
        )

        ctx = await builder.build_generation_context(session, "novel-x")

        assert ctx.style_instruction == "请写得像古龙"


# ---------------------------------------------------------------------------
# build_rewrite_context
# ---------------------------------------------------------------------------


class TestBuildRewriteContext:
    """build_rewrite_context: 有数据 / 无数据 / 边界路径。

    执行顺序 (chapter_number > 1):
      1. _get_novel
      2. _get_world_setting
      3. Outline 查询 (chapter level)
      4. prev Chapter 查询
      5. next Chapter 查询
      6. Character 查询 (list)
      7. _get_story_bible
    当 chapter_number == 1 时跳过步骤 4。
    """

    @pytest.fixture
    def builder(self):
        return NovelContextBuilder()

    @pytest.mark.asyncio
    async def test_all_none_returns_empty_context(self, builder):
        """所有查询均无数据时返回空 RewriteContext（用默认值）。"""
        session = _session_from_results(
            [
                _scalar_result(None),  # novel
                _scalar_result(None),  # world setting
                _scalar_result(None),  # outline
                _scalar_result(None),  # prev chapter
                _scalar_result(None),  # next chapter
                _list_result([]),  # characters
                _scalar_result(None),  # story bible
            ]
        )

        ctx = await builder.build_rewrite_context(session, "novel-x", chapter_number=2)

        assert isinstance(ctx, RewriteContext)
        assert ctx.writing_style == ""
        assert ctx.world_setting == ""
        assert ctx.chapter_outline == ""
        assert ctx.prev_chapter_summary == ""
        assert ctx.next_chapter_summary == ""
        assert ctx.characters == ""
        assert ctx.story_bible == ""

    @pytest.mark.asyncio
    async def test_with_data_builds_full_context(self, builder):
        """有数据时正确拼接 world_setting/outline/summaries/characters/bible。"""
        novel = _novel(writing_style="现代白话", writing_style_prompt="promptX")
        ws = _world_setting(background="背景A", geography="地理A", culture="文化A", rules="规则A")
        outline = _outline(content={"title": "章纲1", "beat": "起"})
        prev_ch = _chapter(content="上一章正文" + "x" * 400)  # >300 字符
        next_ch = _chapter(content="下一章正文" + "y" * 400)
        chars = [_character(name="李四", role="配角", description="剑客")]
        bible = _story_bible()

        session = _session_from_results(
            [
                _scalar_result(novel),
                _scalar_result(ws),
                _scalar_result(outline),
                _scalar_result(prev_ch),
                _scalar_result(next_ch),
                _list_result(chars),
                _scalar_result(bible),
            ]
        )

        ctx = await builder.build_rewrite_context(session, "novel-x", chapter_number=5)

        # writing_style 优先 prompt
        assert ctx.writing_style == "promptX"
        assert "背景：背景A" in ctx.world_setting
        assert "地理：地理A" in ctx.world_setting
        assert "文化：文化A" in ctx.world_setting
        assert "规则：规则A" in ctx.world_setting
        # outline 序列化为 JSON 字符串
        assert json.loads(ctx.chapter_outline) == {"title": "章纲1", "beat": "起"}
        # 上一/下一章截断到 300 字符
        assert ctx.prev_chapter_summary == prev_ch.content[:300]
        assert ctx.next_chapter_summary == next_ch.content[:300]
        # characters 列表化
        assert "- 李四（配角）：剑客" in ctx.characters
        # story_bible 含各字段
        assert "世界观规则：规则A" in ctx.story_bible
        assert "硬设定：硬设定A" in ctx.story_bible
        assert "势力关系：势力1" in ctx.story_bible

    @pytest.mark.asyncio
    async def test_chapter_number_one_skips_prev_chapter(self, builder):
        """chapter_number == 1 时不查询上一章（少一次 execute 调用）。"""
        session = _session_from_results(
            [
                _scalar_result(None),  # novel
                _scalar_result(None),  # world setting
                _scalar_result(None),  # outline
                # 注意: 没有 prev chapter 查询
                _scalar_result(None),  # next chapter
                _list_result([]),  # characters
                _scalar_result(None),  # story bible
            ]
        )

        ctx = await builder.build_rewrite_context(session, "novel-x", chapter_number=1)

        assert ctx.prev_chapter_summary == ""
        # 验证只执行了 6 次 execute (chapter_number==1 跳过 prev 查询)
        assert session.execute.await_count == 6


# ---------------------------------------------------------------------------
# build_blueprint_context
# ---------------------------------------------------------------------------


class TestBuildBlueprintContext:
    """build_blueprint_context: 非长篇 / 长篇有卷纲 / 首章无 prev 路径。

    非长篇执行顺序 (chapter_number > 1):
      1. prev Chapter 查询
      2. _get_story_bible
      3. _get_novel  (novel.is_long_form == False -> 结束)
    长篇且 is_long_form=True (chapter_number > 1):
      1. prev Chapter
      2. _get_story_bible
      3. _get_novel
      4. Chapter (current, for volume_number)
      5. Outline (volume level)  — 仅当 chapter 有 volume_number
    """

    @pytest.fixture
    def builder(self):
        return NovelContextBuilder()

    @pytest.mark.asyncio
    async def test_first_chapter_no_prev_and_not_long_form(self, builder):
        """首章且非长篇: previous_chapter 与 volume_context 均为空。"""
        novel = _novel(is_long_form=False)
        session = _session_from_results(
            [
                _scalar_result(None),  # story bible
                _scalar_result(novel),  # novel -> is_long_form False, 不再查询
            ]
        )

        ctx = await builder.build_blueprint_context(
            session, "novel-x", chapter_number=1, chapter_outline={}
        )

        assert isinstance(ctx, BlueprintContext)
        assert ctx.previous_chapter == ""
        assert ctx.volume_context == ""
        assert ctx.story_bible == ""
        # chapter_number==1 跳过 prev 查询；非长篇不查 volume -> 共 2 次 execute
        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_non_long_form_with_prev_and_bible(self, builder):
        """非长篇但有上一章和故事圣经: 拼接 previous_chapter 与 story_bible。"""
        prev_ch = _chapter(content="上一章内容" + "z" * 600)  # >500 字符
        bible = _story_bible(
            worldview_rules="规则W",
            hard_settings="硬设定H",
            character_cards=[{"name": "甲"}],
            foreshadowing_list=[{"id": 9}],
        )
        novel = _novel(is_long_form=False)
        session = _session_from_results(
            [
                _scalar_result(prev_ch),  # prev chapter
                _scalar_result(bible),  # story bible
                _scalar_result(novel),  # novel -> 非长篇结束
            ]
        )

        ctx = await builder.build_blueprint_context(
            session, "novel-x", chapter_number=3, chapter_outline={}
        )

        assert ctx.previous_chapter == prev_ch.content[:500]
        assert "世界观规则：规则W" in ctx.story_bible
        assert "硬设定：硬设定H" in ctx.story_bible
        assert "人物卡：" in ctx.story_bible
        assert "伏笔列表：" in ctx.story_bible
        assert ctx.volume_context == ""
        # 非长篇 -> 3 次 execute (prev, bible, novel)
        assert session.execute.await_count == 3

    @pytest.mark.asyncio
    async def test_long_form_builds_volume_context(self, builder):
        """长篇小说: 查询当前章 volume_number 并拼接卷纲。"""
        prev_ch = _chapter(content="上一章")
        bible = _story_bible()
        novel = _novel(is_long_form=True)
        chapter_obj = _chapter(volume_number=2)
        vol_outline = _outline(content={"volume_summary": "第二卷纲要"})
        session = _session_from_results(
            [
                _scalar_result(prev_ch),  # prev chapter
                _scalar_result(bible),  # story bible
                _scalar_result(novel),  # novel -> is_long_form True
                _scalar_result(chapter_obj),  # current chapter (volume_number=2)
                _scalar_result(vol_outline),  # volume outline
            ]
        )

        ctx = await builder.build_blueprint_context(
            session, "novel-x", chapter_number=5, chapter_outline={}
        )

        assert ctx.previous_chapter == "上一章"
        assert json.loads(ctx.volume_context) == {"volume_summary": "第二卷纲要"}
        assert session.execute.await_count == 5

    @pytest.mark.asyncio
    async def test_long_form_without_volume_number_skips_volume_context(self, builder):
        """长篇小说但当前章无 volume_number: 不查询卷纲，volume_context 为空。"""
        prev_ch = _chapter(content="上一章")
        bible = _story_bible()
        novel = _novel(is_long_form=True)
        chapter_obj = _chapter(volume_number=None)
        session = _session_from_results(
            [
                _scalar_result(prev_ch),  # prev chapter
                _scalar_result(bible),  # story bible
                _scalar_result(novel),  # novel -> is_long_form True
                _scalar_result(chapter_obj),  # current chapter, volume_number=None
                # 不再有 volume outline 查询
            ]
        )

        ctx = await builder.build_blueprint_context(
            session, "novel-x", chapter_number=5, chapter_outline={}
        )

        assert ctx.volume_context == ""
        assert ctx.previous_chapter == "上一章"
        assert session.execute.await_count == 4
