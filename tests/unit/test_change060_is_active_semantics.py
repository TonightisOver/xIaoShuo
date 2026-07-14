# tests/unit/test_change060_is_active_semantics.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.api.services.chapter_service import ChapterService


@pytest.mark.asyncio
async def test_create_version_inactive_does_not_overwrite_chapter_content():
    svc = ChapterService()
    with patch("src.api.services.chapter_service.get_db_session") as mock_session:
        session = AsyncMock()

        ch = MagicMock(spec=["content", "word_count", "updated_at"])
        ch.content = "原正文"
        ch.word_count = 3
        ch.updated_at = None

        # First execute returns chapter row
        ch_res = MagicMock()
        ch_res.scalar_one_or_none = MagicMock(return_value=ch)

        # Second execute returns max version
        max_ver_res = MagicMock()
        max_ver_res.scalar_one_or_none = MagicMock(return_value=0)

        session.execute = AsyncMock(side_effect=[ch_res, max_ver_res])
        session.add = MagicMock()
        session.flush = AsyncMock()
        mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
        await svc.create_chapter_version(
            novel_id="n1", chapter_number=1, content="候选正文",
            source="ai_rewrite", is_active=False,
        )
    assert ch.content == "原正文"
