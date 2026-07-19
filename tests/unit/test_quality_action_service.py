"""Unit tests for QualityActionService.

Covers:
- generate_rewrite_actions: normal mapping, threshold boundary, sorting, empty input,
  "overall" key skipping, custom threshold
- persist_actions: DB write with mock session

All database interactions are mocked; tests exercise pure business logic.
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


def _fake_session(bp=None):
    """Return a mock session context manager."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = bp
    session.execute = AsyncMock(return_value=mock_result)

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx, session


# ===========================================================================
# Tests for QualityActionService.generate_rewrite_actions
# ===========================================================================

class TestGenerateRewriteActions:
    """Tests for QualityActionService.generate_rewrite_actions."""

    def _get_service(self):
        from src.api.services.quality.quality_action_service import QualityActionService
        return QualityActionService()

    def test_low_scores_generate_actions(self):
        """Input with advancement=0.3, pacing=0.4, conflict=0.8 generates 2 actions."""
        svc = self._get_service()
        scores = {"advancement": 0.3, "pacing": 0.4, "conflict": 0.8}
        actions = svc.generate_rewrite_actions(scores, threshold=0.5)

        assert len(actions) == 2
        dims = [a["dimension"] for a in actions]
        assert "advancement" in dims
        assert "pacing" in dims
        assert "conflict" not in dims

    def test_score_equal_to_threshold_no_action(self):
        """Score exactly equal to threshold does NOT generate an action."""
        svc = self._get_service()
        scores = {"advancement": 0.5}
        actions = svc.generate_rewrite_actions(scores, threshold=0.5)
        assert len(actions) == 0

    def test_priority_descending_order(self):
        """Actions are sorted by priority descending (lowest score = highest priority)."""
        svc = self._get_service()
        scores = {"advancement": 0.3, "pacing": 0.1, "conflict": 0.4}
        actions = svc.generate_rewrite_actions(scores, threshold=0.5)

        priorities = [a["priority"] for a in actions]
        assert priorities == sorted(priorities, reverse=True)
        # pacing (0.1) should have highest priority (0.9)
        assert actions[0]["dimension"] == "pacing"
        assert actions[0]["priority"] == pytest.approx(0.9)

    def test_empty_dict_returns_empty_list(self):
        """Empty quality_scores dict returns empty actions list."""
        svc = self._get_service()
        actions = svc.generate_rewrite_actions({})
        assert actions == []

    def test_overall_key_is_skipped(self):
        """The 'overall' key is always skipped."""
        svc = self._get_service()
        scores = {"overall": 0.2, "advancement": 0.8}
        actions = svc.generate_rewrite_actions(scores, threshold=0.5)
        dims = [a["dimension"] for a in actions]
        assert "overall" not in dims
        assert len(actions) == 0

    def test_custom_threshold_generates_more_actions(self):
        """Custom threshold=0.7 triggers actions for scores below 0.7."""
        svc = self._get_service()
        scores = {"advancement": 0.6, "pacing": 0.5, "conflict": 0.8}
        actions = svc.generate_rewrite_actions(scores, threshold=0.7)
        assert len(actions) == 2
        dims = [a["dimension"] for a in actions]
        assert "advancement" in dims
        assert "pacing" in dims


# ===========================================================================
# Tests for QualityActionService.persist_actions
# ===========================================================================

class TestPersistActions:
    """Tests for QualityActionService.persist_actions (async, mocked DB)."""

    @pytest.mark.asyncio
    async def test_persist_actions_updates_blueprint(self):
        """persist_actions writes actions to existing blueprint."""
        from src.api.services.quality.quality_action_service import QualityActionService

        mock_bp = MagicMock()
        mock_bp.rewrite_actions = None
        ctx_factory, _ = _fake_session(bp=mock_bp)

        svc = QualityActionService()
        actions = [{"action_type": "enhance_plot", "dimension": "advancement"}]

        with patch("src.api.services.quality.quality_action_service.get_db_session", ctx_factory):
            await svc.persist_actions(_novel_id(), 1, actions)

        assert mock_bp.rewrite_actions == actions

    @pytest.mark.asyncio
    async def test_persist_actions_no_blueprint_does_not_raise(self):
        """persist_actions with no existing blueprint logs warning but does not raise."""
        from src.api.services.quality.quality_action_service import QualityActionService

        ctx_factory, _ = _fake_session(bp=None)

        svc = QualityActionService()
        actions = [{"action_type": "enhance_plot"}]

        with patch("src.api.services.quality.quality_action_service.get_db_session", ctx_factory):
            # Should not raise
            await svc.persist_actions(_novel_id(), 1, actions)
