"""Unit tests for CHANGE-038: chapter timeout increase, error message fix,
character upsert deduplication, chapter dedup (delete-before-insert),
and volume_number assignment in generate_chapters_background."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# 1. CHAPTER_TIMEOUT_SECONDS value
# ===========================================================================

class TestChapterTimeout:

    def test_timeout_is_600(self):
        from src.core.llm.chapter_generator import CHAPTER_TIMEOUT_SECONDS
        assert CHAPTER_TIMEOUT_SECONDS == 600

    @pytest.mark.asyncio
    async def test_timeout_error_message_no_api_key(self):
        """Timeout error message should NOT mention API Key."""
        from src.core.llm.chapter_generator import generate_single_chapter

        async def _hang(*args, **kwargs):
            await asyncio.sleep(9999)

        with patch(
            "src.core.llm.chapter_generator._generate_single_chapter_inner",
            side_effect=_hang,
        ):
            with patch(
                "src.core.llm.chapter_generator.CHAPTER_TIMEOUT_SECONDS", 0.1
            ):
                result = await asyncio.wait_for(
                    generate_single_chapter(
                        client=MagicMock(),
                        chapter_outline={"chapter": 1, "title": "Test"},
                        previous_chapter="",
                        characters_json="[]",
                        world_setting_json="{}",
                    ),
                    timeout=5,
                )
        assert "API Key" not in result["content"]
        assert result["generation_failed"] is True


# ===========================================================================
# 2. get_character_by_name existence
# ===========================================================================

class TestGetCharacterByName:

    def test_method_exists(self):
        from src.api.services.character_service import CharacterService
        assert hasattr(CharacterService, "get_character_by_name")
        assert callable(getattr(CharacterService, "get_character_by_name"))
