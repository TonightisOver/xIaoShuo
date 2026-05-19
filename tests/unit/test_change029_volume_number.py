"""Unit tests for CHANGE-029: chapter volume_number display.

Tests cover:
- NovelManager.list_chapters() returns volume_number in each dict
- NovelManager.get_chapter() returns volume_number in the dict
- _persist_to_novel() passes volume_number when constructing Chapter objects
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_chapter_row(
    id_: int,
    novel_id: str,
    chapter_number: int,
    volume_number: int | None,
    title: str = "测试章节",
    content: str = "内容",
    word_count: int = 100,
    status: str = "generated",
) -> MagicMock:
    """Build a mock Chapter ORM row."""
    row = MagicMock()
    row.id = id_
    row.novel_id = novel_id
    row.chapter_number = chapter_number
    row.volume_number = volume_number
    row.title = title
    row.content = content
    row.word_count = word_count
    row.status = status
    row.updated_at = datetime(2026, 5, 19, tzinfo=timezone.utc)
    return row


# ---------------------------------------------------------------------------
# NovelManager.list_chapters
# ---------------------------------------------------------------------------

class TestListChaptersVolumeNumber:
    """list_chapters() must include volume_number in every returned dict."""

    @pytest.mark.asyncio
    async def test_list_chapters_includes_volume_number_when_set(self):
        """Chapters with a volume_number return it correctly."""
        from src.api.services.novel_manager import NovelManager

        manager = NovelManager()

        rows = [
            _make_chapter_row(1, "novel-1", 1, volume_number=1),
            _make_chapter_row(2, "novel-1", 2, volume_number=1),
            _make_chapter_row(3, "novel-1", 3, volume_number=2),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.novel_manager.get_db_session", return_value=mock_session):
            result = await manager.list_chapters("novel-1")

        assert len(result) == 3
        assert result[0]["volume_number"] == 1
        assert result[1]["volume_number"] == 1
        assert result[2]["volume_number"] == 2

    @pytest.mark.asyncio
    async def test_list_chapters_volume_number_none_when_not_set(self):
        """Chapters without a volume_number return None for that field."""
        from src.api.services.novel_manager import NovelManager

        manager = NovelManager()

        rows = [
            _make_chapter_row(1, "novel-2", 1, volume_number=None),
            _make_chapter_row(2, "novel-2", 2, volume_number=None),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.novel_manager.get_db_session", return_value=mock_session):
            result = await manager.list_chapters("novel-2")

        assert len(result) == 2
        for ch in result:
            assert "volume_number" in ch
            assert ch["volume_number"] is None

    @pytest.mark.asyncio
    async def test_list_chapters_returns_empty_list_when_no_chapters(self):
        """Returns empty list when novel has no chapters."""
        from src.api.services.novel_manager import NovelManager

        manager = NovelManager()

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.novel_manager.get_db_session", return_value=mock_session):
            result = await manager.list_chapters("novel-empty")

        assert result == []

    @pytest.mark.asyncio
    async def test_list_chapters_dict_contains_all_expected_keys(self):
        """Each chapter dict has the full set of expected keys."""
        from src.api.services.novel_manager import NovelManager

        manager = NovelManager()

        rows = [_make_chapter_row(1, "novel-3", 1, volume_number=1)]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.novel_manager.get_db_session", return_value=mock_session):
            result = await manager.list_chapters("novel-3")

        expected_keys = {
            "id", "chapter_number", "volume_number",
            "title", "content", "word_count", "status", "updated_at",
        }
        assert set(result[0].keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_list_chapters_mixed_volume_numbers(self):
        """Chapters from different volumes return correct volume_number each."""
        from src.api.services.novel_manager import NovelManager

        manager = NovelManager()

        rows = [
            _make_chapter_row(1, "novel-4", 1, volume_number=1),
            _make_chapter_row(2, "novel-4", 2, volume_number=None),
            _make_chapter_row(3, "novel-4", 3, volume_number=3),
        ]

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = rows

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.novel_manager.get_db_session", return_value=mock_session):
            result = await manager.list_chapters("novel-4")

        assert result[0]["volume_number"] == 1
        assert result[1]["volume_number"] is None
        assert result[2]["volume_number"] == 3


# ---------------------------------------------------------------------------
# NovelManager.get_chapter
# ---------------------------------------------------------------------------

class TestGetChapterVolumeNumber:
    """get_chapter() must include volume_number in the returned dict."""

    @pytest.mark.asyncio
    async def test_get_chapter_includes_volume_number(self):
        """Happy path: chapter with volume_number returns it."""
        from src.api.services.novel_manager import NovelManager

        manager = NovelManager()

        row = _make_chapter_row(10, "novel-5", 5, volume_number=2)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = row

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.novel_manager.get_db_session", return_value=mock_session):
            result = await manager.get_chapter("novel-5", 5)

        assert result is not None
        assert result["volume_number"] == 2
        assert result["chapter_number"] == 5

    @pytest.mark.asyncio
    async def test_get_chapter_volume_number_none(self):
        """Chapter without volume_number returns None for that field."""
        from src.api.services.novel_manager import NovelManager

        manager = NovelManager()

        row = _make_chapter_row(11, "novel-6", 1, volume_number=None)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = row

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.novel_manager.get_db_session", return_value=mock_session):
            result = await manager.get_chapter("novel-6", 1)

        assert result is not None
        assert "volume_number" in result
        assert result["volume_number"] is None

    @pytest.mark.asyncio
    async def test_get_chapter_returns_none_when_not_found(self):
        """Returns None when chapter does not exist."""
        from src.api.services.novel_manager import NovelManager

        manager = NovelManager()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.novel_manager.get_db_session", return_value=mock_session):
            result = await manager.get_chapter("novel-7", 999)

        assert result is None

    @pytest.mark.asyncio
    async def test_get_chapter_dict_contains_all_expected_keys(self):
        """Returned dict has the full set of expected keys including volume_number."""
        from src.api.services.novel_manager import NovelManager

        manager = NovelManager()

        row = _make_chapter_row(12, "novel-8", 3, volume_number=1)

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = row

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.novel_manager.get_db_session", return_value=mock_session):
            result = await manager.get_chapter("novel-8", 3)

        expected_keys = {
            "id", "chapter_number", "volume_number",
            "title", "content", "word_count", "status", "updated_at",
        }
        assert set(result.keys()) == expected_keys


# ---------------------------------------------------------------------------
# _persist_to_novel — volume_number propagation
# ---------------------------------------------------------------------------

class TestPersistToNovelVolumeNumber:
    """_persist_to_novel() must pass volume_number when constructing Chapter rows."""

    @pytest.mark.asyncio
    async def test_persist_passes_volume_number_to_chapter(self):
        """Chapter dicts with volume_number produce Chapter objects with that value.

        _persist_to_novel imports Chapter and get_db_session locally inside the
        function body, so we patch them at their source modules.
        """
        from src.api.services.novel_generator import _persist_to_novel

        result = {
            "chapters": [
                {
                    "chapter": 1,
                    "title": "第一章",
                    "content": "内容一",
                    "word_count": 500,
                    "volume_number": 1,
                },
                {
                    "chapter": 2,
                    "title": "第二章",
                    "content": "内容二",
                    "word_count": 600,
                    "volume_number": 2,
                },
            ]
        }

        created_chapters = []

        class FakeChapter:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                created_chapters.append(self)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.add = MagicMock()

        mock_manager = AsyncMock()
        mock_manager.upsert_world_setting = AsyncMock()
        mock_manager.create_character = AsyncMock()
        mock_manager.create_volume = AsyncMock()
        mock_manager.update_novel = AsyncMock()

        # Patch at source modules because _persist_to_novel uses local imports
        with patch("src.api.services.novel_generator.get_novel_manager", return_value=mock_manager), \
             patch("src.api.models.db_models.Chapter", FakeChapter), \
             patch("src.core.database.get_db_session", return_value=mock_session):
            await _persist_to_novel("novel-persist-1", result)

        # Verify volume_number was passed
        assert len(created_chapters) == 2
        assert created_chapters[0].volume_number == 1
        assert created_chapters[1].volume_number == 2

    @pytest.mark.asyncio
    async def test_persist_volume_number_none_when_missing_from_dict(self):
        """Chapter dicts without volume_number key produce Chapter with volume_number=None."""
        from src.api.services.novel_generator import _persist_to_novel

        result = {
            "chapters": [
                {
                    "chapter": 1,
                    "title": "无卷号章节",
                    "content": "内容",
                    "word_count": 300,
                    # no volume_number key — ch.get("volume_number") returns None
                },
            ]
        }

        created_chapters = []

        class FakeChapter:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
                created_chapters.append(self)

        mock_session = AsyncMock()
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)
        mock_session.add = MagicMock()

        mock_manager = AsyncMock()
        mock_manager.upsert_world_setting = AsyncMock()
        mock_manager.create_character = AsyncMock()
        mock_manager.create_volume = AsyncMock()
        mock_manager.update_novel = AsyncMock()

        with patch("src.api.services.novel_generator.get_novel_manager", return_value=mock_manager), \
             patch("src.api.models.db_models.Chapter", FakeChapter), \
             patch("src.core.database.get_db_session", return_value=mock_session):
            await _persist_to_novel("novel-persist-2", result)

        assert len(created_chapters) == 1
        assert created_chapters[0].volume_number is None
