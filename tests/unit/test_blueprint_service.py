"""Unit tests for BlueprintService.

Covers:
- generate_blueprint: normal LLM response, JSON parse failure fallback
- get_blueprint: found vs not found
- update_blueprint: field update

All database and LLM interactions are mocked.
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _novel_id() -> str:
    return f"novel-{uuid.uuid4().hex[:8]}"


def _fake_session(bp=None, scalars=None):
    """Return a mock async session context manager."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = bp
    if scalars is not None:
        mock_result.scalars.return_value.all.return_value = scalars
    session.execute = AsyncMock(return_value=mock_result)
    session.add = MagicMock()

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx, session


VALID_BLUEPRINT_JSON = json.dumps({
    "chapter_type": "climax",
    "plot_goal": "Hero defeats villain",
    "hook_design": "Unexpected ally appears",
    "foreshadow_actions": ["sword glows"],
    "cliffhanger": "A new enemy emerges",
    "pacing_target": "fast",
    "key_characters": ["hero", "villain"],
    "word_target": 4000,
})


def _make_blueprint_model(**overrides):
    """Create a mock ChapterBlueprint ORM object."""
    m = MagicMock()
    m.novel_id = overrides.get("novel_id", _novel_id())
    m.chapter_number = overrides.get("chapter_number", 1)
    m.chapter_type = overrides.get("chapter_type", "main_advance")
    m.plot_goal = overrides.get("plot_goal", "advance plot")
    m.hook_design = overrides.get("hook_design", "hook")
    m.foreshadow_actions = overrides.get("foreshadow_actions", [])
    m.cliffhanger = overrides.get("cliffhanger", "cliff")
    m.pacing_target = overrides.get("pacing_target", "medium")
    m.key_characters = overrides.get("key_characters", ["hero"])
    m.word_target = overrides.get("word_target", 3000)
    m.rewrite_actions = overrides.get("rewrite_actions", None)
    m.is_active = overrides.get("is_active", True)
    return m


# ===========================================================================
# Tests for BlueprintService.generate_blueprint
# ===========================================================================

class TestGenerateBlueprint:
    """Tests for BlueprintService.generate_blueprint."""

    @pytest.mark.asyncio
    async def test_generate_blueprint_normal(self):
        """LLM returns valid JSON -> blueprint dict with all fields."""
        from src.api.services.content.blueprint_service import BlueprintService

        ctx_factory, session = _fake_session()
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=VALID_BLUEPRINT_JSON)

        svc = BlueprintService()
        chapter_outline = {"plot": "Hero fights", "key_characters": ["hero"]}

        with (
            patch("src.api.services.content.blueprint_service.get_db_session", ctx_factory),
            patch("src.api.services.content.blueprint_service.get_llm_client", return_value=mock_client),
            patch.object(svc, "_build_context", new_callable=AsyncMock, return_value={
                "previous_chapter": "",
                "story_bible": "",
                "kg_context": "",
                "volume_context": "",
            }),
        ):
            result = await svc.generate_blueprint(_novel_id(), 1, chapter_outline)

        assert result["chapter_type"] == "climax"
        assert result["plot_goal"] == "Hero defeats villain"
        assert result["word_target"] == 4000
        assert "hook_design" in result

    @pytest.mark.asyncio
    async def test_generate_blueprint_json_parse_failure_uses_default(self):
        """LLM returns invalid JSON -> falls back to default blueprint."""
        from src.api.services.content.blueprint_service import BlueprintService

        ctx_factory, session = _fake_session()
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="not valid json {{{")

        svc = BlueprintService()
        chapter_outline = {"plot": "Hero fights", "key_characters": ["hero"]}

        with (
            patch("src.api.services.content.blueprint_service.get_db_session", ctx_factory),
            patch("src.api.services.content.blueprint_service.get_llm_client", return_value=mock_client),
            patch.object(svc, "_build_context", new_callable=AsyncMock, return_value={
                "previous_chapter": "",
                "story_bible": "",
                "kg_context": "",
                "volume_context": "",
            }),
        ):
            result = await svc.generate_blueprint(_novel_id(), 1, chapter_outline)

        # Should use defaults from _default_blueprint
        assert result["chapter_type"] == "main_advance"
        assert result["plot_goal"] == "Hero fights"
        assert result["word_target"] == 3000


# ===========================================================================
# Tests for BlueprintService.get_blueprint
# ===========================================================================

class TestGetBlueprint:
    """Tests for BlueprintService.get_blueprint."""

    @pytest.mark.asyncio
    async def test_get_blueprint_found(self):
        """Returns dict when active blueprint exists."""
        from src.api.services.content.blueprint_service import BlueprintService

        mock_bp = _make_blueprint_model(chapter_type="climax", plot_goal="test goal")
        ctx_factory, _ = _fake_session(bp=mock_bp)

        svc = BlueprintService()
        with patch("src.api.services.content.blueprint_service.get_db_session", ctx_factory):
            result = await svc.get_blueprint(_novel_id(), 1)

        assert result is not None
        assert result["chapter_type"] == "climax"
        assert result["plot_goal"] == "test goal"

    @pytest.mark.asyncio
    async def test_get_blueprint_not_found(self):
        """Returns None when no active blueprint exists."""
        from src.api.services.content.blueprint_service import BlueprintService

        ctx_factory, _ = _fake_session(bp=None)

        svc = BlueprintService()
        with patch("src.api.services.content.blueprint_service.get_db_session", ctx_factory):
            result = await svc.get_blueprint(_novel_id(), 1)

        assert result is None


# ===========================================================================
# Tests for BlueprintService.update_blueprint
# ===========================================================================

class TestUpdateBlueprint:
    """Tests for BlueprintService.update_blueprint."""

    @pytest.mark.asyncio
    async def test_update_blueprint_applies_fields(self):
        """update_blueprint sets valid fields on the model."""
        from src.api.services.content.blueprint_service import BlueprintService

        mock_bp = _make_blueprint_model()
        ctx_factory, _ = _fake_session(bp=mock_bp)

        svc = BlueprintService()
        updates = {"plot_goal": "new goal", "pacing_target": "fast"}

        with patch("src.api.services.content.blueprint_service.get_db_session", ctx_factory):
            result = await svc.update_blueprint(_novel_id(), 1, updates)

        assert mock_bp.plot_goal == "new goal"
        assert mock_bp.pacing_target == "fast"

    @pytest.mark.asyncio
    async def test_update_blueprint_no_blueprint_raises(self):
        """update_blueprint raises ValueError when no active blueprint."""
        from src.api.services.content.blueprint_service import BlueprintService

        ctx_factory, _ = _fake_session(bp=None)

        svc = BlueprintService()
        with patch("src.api.services.content.blueprint_service.get_db_session", ctx_factory):
            with pytest.raises(ValueError, match="No active blueprint"):
                await svc.update_blueprint(_novel_id(), 1, {"plot_goal": "x"})
