# tests/unit/test_change060_rewrite_rollback.py
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.rewrite_loop_service import RewriteLoopService


def _novel_id() -> str:
    return f"novel-{uuid.uuid4().hex[:8]}"


def _low_scores():
    """Some dimensions below target — rewrite will be attempted."""
    return {
        "advancement": 0.7,
        "conflict": 0.7,
        "character_consistency": 0.8,
        "world_consistency": 0.8,
        "foreshadowing": 0.7,
        "pacing": 0.7,
        "readability": 0.7,
        "trope_alignment": 0.7,
        "overall": 0.7,
    }


def _worse_scores():
    """After rewrite, overall dropped while protected dims stayed flat."""
    return {
        "advancement": 0.5,
        "conflict": 0.5,
        "character_consistency": 0.8,
        "world_consistency": 0.8,
        "foreshadowing": 0.5,
        "pacing": 0.5,
        "readability": 0.5,
        "trope_alignment": 0.5,
        "overall": 0.5,
    }


def _fake_session(novel=None, ws=None, chars=None):
    """Return a mock async session context manager."""
    session = AsyncMock()
    call_count = {"n": 0}

    async def _execute_side_effect(stmt):
        call_count["n"] += 1
        mock_result = MagicMock()
        n = call_count["n"]
        if n == 1:
            mock_result.scalar_one_or_none.return_value = novel
        elif n == 2:
            mock_result.scalar_one_or_none.return_value = ws
        elif n == 3:
            scalars_mock = MagicMock()
            scalars_mock.all.return_value = chars or []
            mock_result.scalars.return_value = scalars_mock
        else:
            mock_result.scalar_one_or_none.return_value = None
        return mock_result

    session.execute = AsyncMock(side_effect=_execute_side_effect)

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx, session


@pytest.mark.asyncio
async def test_rewrite_reverts_when_score_drops():
    """候选评分低于基线时不应激活(不改变活跃版本)。"""
    mock_manager = AsyncMock()
    mock_manager.get_chapter = AsyncMock(
        return_value={"content": "基线正文"}
    )
    mock_manager.create_chapter_version = AsyncMock(return_value=2)
    mock_manager.activate_chapter_version = AsyncMock(return_value=True)

    # Rewrite context builder mock (so context build does not touch real DB)
    mock_rewrite_ctx = MagicMock()
    mock_rewrite_ctx.world_setting = ""
    mock_rewrite_ctx.chapter_outline = ""
    mock_rewrite_ctx.prev_chapter_summary = ""
    mock_rewrite_ctx.next_chapter_summary = ""
    mock_rewrite_ctx.characters = ""
    mock_rewrite_ctx.story_bible = ""
    mock_rewrite_ctx.writing_style = ""
    mock_builder = MagicMock()
    mock_builder.build_rewrite_context = AsyncMock(return_value=mock_rewrite_ctx)

    ctx_factory, _ = _fake_session()

    svc = RewriteLoopService()

    with (
        patch(
            "src.api.services.rewrite_loop_service.get_novel_manager",
            return_value=mock_manager,
        ),
        patch(
            "src.api.services.rewrite_loop_service._evaluate_chapter_quality_for_novel",
            new_callable=AsyncMock,
            side_effect=[_low_scores(), _worse_scores()],
        ),
        patch(
            "src.core.llm.chapter_rewriter.batch_targeted_rewrite",
            new_callable=AsyncMock,
            return_value="候选正文",
        ),
        patch(
            "src.api.services.rewrite_loop_service.QualityActionService",
        ) as mock_qas,
        patch(
            "src.api.services.rewrite_loop_service.get_db_session",
            ctx_factory,
        ),
        patch(
            "src.api.services.rewrite_loop_service.NovelContextBuilder",
            return_value=mock_builder,
        ),
    ):
        mock_qas.return_value.generate_rewrite_actions = MagicMock(
            return_value=[{"action_type": "enhance", "dimension": "pacing"}]
        )
        result = await svc.auto_improve_chapter(_novel_id(), 1,
                                                  max_iterations=1, target_score=0.9)

    assert result["iterations_done"] == 1

    # 版本 2 创建时被记录为候选择优(is_active=False),不应再被激活
    activate_calls = mock_manager.activate_chapter_version.call_args_list
    activated_versions = [c.kwargs.get("version_number")
                          for c in activate_calls]
    assert 2 not in activated_versions

    # improvement_history 应标记该候选未被激活
    hist = result["improvement_history"]
    assert len(hist) == 1
    assert hist[0].get("activated") is False
