# tests/unit/test_change061_context_state_delta.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.novel_context_service import NovelContextBuilder


@pytest.mark.asyncio
async def test_build_rewrite_context_uses_state_delta():
    """有 state_delta 时，prev_chapter_summary 用 merge_delta_for_context 而非 content[:300]。"""
    builder = NovelContextBuilder()
    session = AsyncMock()
    novel = MagicMock(); novel.writing_style_prompt = None; novel.writing_style = "风格"
    ws = MagicMock(); ws.background = "背景"; ws.geography = None; ws.culture = None; ws.rules = None
    prev_ch = MagicMock()
    prev_ch.content = "x" * 500
    prev_ch.state_delta = {"key_events": ["上一章事件"], "next_chapter_must_carry": ["承接A"]}

    call_n = {"n": 0}
    async def _execute(stmt):
        call_n["n"] += 1
        m = MagicMock()
        if call_n["n"] == 1:
            m.scalar_one_or_none.return_value = novel
        elif call_n["n"] == 2:
            m.scalar_one_or_none.return_value = ws
        elif call_n["n"] == 3:
            m.scalar_one_or_none.return_value = None
        elif call_n["n"] == 4:
            m.scalar_one_or_none.return_value = prev_ch
        elif call_n["n"] == 5:
            m.scalar_one_or_none.return_value = None
        else:
            scalars_m = MagicMock()
            scalars_m.all.return_value = []
            m.scalars.return_value = scalars_m
        return m
    session.execute = AsyncMock(side_effect=_execute)

    with patch.object(builder, "_get_story_bible", new=AsyncMock(return_value=None)):
        ctx = await builder.build_rewrite_context(session, "n1", 2)

    assert "承接A" in ctx.prev_chapter_summary
    assert "上一章事件" in ctx.prev_chapter_summary
    assert "x" * 300 not in ctx.prev_chapter_summary


@pytest.mark.asyncio
async def test_build_rewrite_context_fallback_to_content_when_no_state_delta():
    """state_delta 为 None（历史章）时回退 content[:300]。"""
    builder = NovelContextBuilder()
    session = AsyncMock()
    novel = MagicMock(); novel.writing_style_prompt = None; novel.writing_style = ""
    ws = MagicMock(); ws.background = None; ws.geography = None; ws.culture = None; ws.rules = None
    prev_ch = MagicMock()
    prev_ch.content = "前300字内容" + "x" * 500
    prev_ch.state_delta = None

    call_n = {"n": 0}
    async def _execute(stmt):
        call_n["n"] += 1
        m = MagicMock()
        if call_n["n"] == 1:
            m.scalar_one_or_none.return_value = novel
        elif call_n["n"] == 2:
            m.scalar_one_or_none.return_value = ws
        elif call_n["n"] == 3:
            m.scalar_one_or_none.return_value = None
        elif call_n["n"] == 4:
            m.scalar_one_or_none.return_value = prev_ch
        elif call_n["n"] == 5:
            m.scalar_one_or_none.return_value = None
        else:
            scalars_m = MagicMock()
            scalars_m.all.return_value = []
            m.scalars.return_value = scalars_m
        return m
    session.execute = AsyncMock(side_effect=_execute)

    with patch.object(builder, "_get_story_bible", new=AsyncMock(return_value=None)):
        ctx = await builder.build_rewrite_context(session, "n1", 2)

    assert ctx.prev_chapter_summary == prev_ch.content[:300]
