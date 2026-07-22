"""Unit tests for RewriteLoopService.

Covers:
- auto_improve_chapter: first-round pass, max iterations reached
- _evaluate_chapter_quality: normal parse, parse failure fallback

All database, LLM, and manager interactions are mocked.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _novel_id() -> str:
    return f"novel-{uuid.uuid4().hex[:8]}"


def _fake_session(novel=None, ws=None, chars=None):
    """Return a mock async session context manager for _evaluate_chapter_quality."""
    session = AsyncMock()

    call_count = {"n": 0}

    async def _execute_side_effect(stmt):
        call_count["n"] += 1
        mock_result = MagicMock()
        n = call_count["n"]
        if n == 1:
            # Novel query
            mock_result.scalar_one_or_none.return_value = novel
        elif n == 2:
            # WorldSetting query
            mock_result.scalar_one_or_none.return_value = ws
        elif n == 3:
            # Character query
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


def _high_scores():
    """All dimensions above 0.6 threshold."""
    return {
        "advancement": 0.8,
        "conflict": 0.7,
        "character_consistency": 0.9,
        "world_consistency": 0.85,
        "foreshadowing": 0.75,
        "pacing": 0.7,
        "readability": 0.8,
        "trope_alignment": 0.65,
        "overall": 0.78,
    }


def _low_scores():
    """Some dimensions below 0.6 threshold."""
    return {
        "advancement": 0.4,
        "conflict": 0.3,
        "character_consistency": 0.9,
        "world_consistency": 0.85,
        "foreshadowing": 0.75,
        "pacing": 0.45,
        "readability": 0.8,
        "trope_alignment": 0.65,
        "overall": 0.55,
    }


# ===========================================================================
# Tests for RewriteLoopService.auto_improve_chapter
# ===========================================================================

class TestAutoImproveChapter:
    """Tests for RewriteLoopService.auto_improve_chapter."""

    @pytest.mark.asyncio
    async def test_first_round_already_passes(self):
        """If quality is already above target on first eval, iterations_done=0."""
        from src.api.services.quality.rewrite_loop_service import RewriteLoopService

        mock_manager = AsyncMock()
        mock_manager.get_chapter = AsyncMock(
            return_value={"content": "Great chapter content"}
        )

        svc = RewriteLoopService()

        with (
            patch(
                "src.api.services.quality.rewrite_loop_service.get_novel_manager",
                return_value=mock_manager,
            ),
            patch(
                "src.api.services.quality.rewrite_loop_service._evaluate_chapter_quality_for_novel",
                new_callable=AsyncMock,
                return_value=_high_scores(),
            ),
        ):
            result = await svc.auto_improve_chapter(
                _novel_id(), 1, max_iterations=3, target_score=0.6
            )

        assert result["iterations_done"] == 0
        assert result["reached_target"] is True
        assert result["improvement_history"] == []
        # 首轮即达标：无候选，best_version 为 None
        assert result["best_version"] is None

    @pytest.mark.asyncio
    async def test_max_iterations_reached(self):
        """If quality never reaches target, stops at max_iterations."""
        from src.api.services.quality.rewrite_loop_service import RewriteLoopService

        mock_manager = AsyncMock()
        mock_manager.get_chapter = AsyncMock(
            return_value={"content": "Mediocre chapter content"}
        )
        mock_manager.create_chapter_version = AsyncMock(return_value=2)

        mock_rewrite = AsyncMock(return_value="Rewritten content")

        # Mock the context builder used for rewrite context
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
                "src.api.services.quality.rewrite_loop_service.get_novel_manager",
                return_value=mock_manager,
            ),
            patch(
                "src.api.services.quality.rewrite_loop_service._evaluate_chapter_quality_for_novel",
                new_callable=AsyncMock,
                return_value=_low_scores(),
            ),
            patch(
                "src.core.llm.chapter_rewriter.batch_targeted_rewrite",
                mock_rewrite,
            ),
            patch(
                "src.api.services.quality.rewrite_loop_service.get_db_session",
                ctx_factory,
            ),
            patch(
                "src.api.services.quality.rewrite_loop_service.NovelContextBuilder",
                return_value=mock_builder,
            ),
        ):
            result = await svc.auto_improve_chapter(
                _novel_id(), 1, max_iterations=2, target_score=0.6
            )

        assert result["iterations_done"] == 2
        assert result["reached_target"] is False
        assert len(result["improvement_history"]) == 2
        # 新契约：L3 只创建候选，绝不自行激活（由 finalize 统一激活）
        mock_manager.activate_chapter_version.assert_not_called()
        # 分数从未提升 → 无最优候选
        assert result["best_version"] is None

    @pytest.mark.asyncio
    async def test_improved_candidate_returns_best_version_without_activating(self):
        """候选改善时返回 best_version 指向候选版本号，但不激活。"""
        from src.api.services.quality.rewrite_loop_service import RewriteLoopService

        mock_manager = AsyncMock()
        mock_manager.get_chapter = AsyncMock(
            return_value={"content": "Mediocre chapter content"}
        )
        mock_manager.create_chapter_version = AsyncMock(return_value=7)

        mock_rewrite = AsyncMock(return_value="Rewritten better content")

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

        # 第一次评估低分（触发改写），改写后评估达标
        eval_results = [_low_scores(), _high_scores()]

        async def _eval_side_effect(*args, **kwargs):
            return eval_results.pop(0)

        svc = RewriteLoopService()

        with (
            patch(
                "src.api.services.quality.rewrite_loop_service.get_novel_manager",
                return_value=mock_manager,
            ),
            patch(
                "src.api.services.quality.rewrite_loop_service._evaluate_chapter_quality_for_novel",
                new_callable=AsyncMock,
                side_effect=_eval_side_effect,
            ),
            patch(
                "src.core.llm.chapter_rewriter.batch_targeted_rewrite",
                mock_rewrite,
            ),
            patch(
                "src.api.services.quality.rewrite_loop_service.get_db_session",
                ctx_factory,
            ),
            patch(
                "src.api.services.quality.rewrite_loop_service.NovelContextBuilder",
                return_value=mock_builder,
            ),
        ):
            result = await svc.auto_improve_chapter(
                _novel_id(), 1, max_iterations=3, target_score=0.6,
                operation_id="op-long-form",
            )

        # 候选改善（overall 0.55 → 0.78）→ best_version 指向候选
        assert result["best_version"] == 7
        # 仍然不激活
        mock_manager.activate_chapter_version.assert_not_called()
        assert result["reached_target"] is True
        _, create_kwargs = mock_manager.create_chapter_version.await_args
        assert create_kwargs["idempotency_key"] == (
            "op-long-form:quality:1:candidate:1"
        )


# ===========================================================================
# Tests for _evaluate_chapter_quality
# ===========================================================================

class TestEvaluateChapterQuality:
    """Tests for the module-level _evaluate_chapter_quality_for_novel function."""

    @pytest.mark.asyncio
    async def test_normal_parse(self):
        """Valid LLM JSON response is parsed into scores dict."""
        from src.api.services.quality.rewrite_loop_service import (
            _evaluate_chapter_quality_for_novel,
        )

        valid_response = (
            '{"scores": {"advancement": 0.8, "conflict": 0.7, '
            '"character_consistency": 0.9, "world_consistency": 0.85, '
            '"foreshadowing": 0.75, "pacing": 0.7, "readability": 0.8, '
            '"trope_alignment": 0.65}, "overall_score": 0.78}'
        )

        mock_novel = MagicMock()
        mock_novel.novel_type = "fantasy"
        mock_novel.idea = "hero journey"

        ctx_factory, _ = _fake_session(novel=mock_novel)
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=valid_response)

        with (
            patch(
                "src.api.services.quality.rewrite_loop_service.get_db_session",
                ctx_factory,
            ),
            patch(
                "src.core.quality.evaluator.get_llm_client",
                return_value=mock_client,
            ),
        ):
            scores = await _evaluate_chapter_quality_for_novel(_novel_id(), 1, "chapter text")

        assert scores["advancement"] == 0.8
        assert scores["conflict"] == 0.7
        assert scores["overall"] == 0.78

    @pytest.mark.asyncio
    async def test_parse_failure_returns_default_scores(self):
        """Invalid LLM response returns default 0.5 scores for all dimensions."""
        from src.api.services.quality.rewrite_loop_service import (
            _evaluate_chapter_quality_for_novel,
        )
        from src.core.quality import QUALITY_DIMENSIONS

        ctx_factory, _ = _fake_session()
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="totally broken response")

        with (
            patch(
                "src.api.services.quality.rewrite_loop_service.get_db_session",
                ctx_factory,
            ),
            patch(
                "src.core.quality.evaluator.get_llm_client",
                return_value=mock_client,
            ),
        ):
            scores = await _evaluate_chapter_quality_for_novel(_novel_id(), 1, "chapter text")

        for dim in QUALITY_DIMENSIONS:
            assert scores[dim] == 0.5
        assert scores["overall"] == 0.5
