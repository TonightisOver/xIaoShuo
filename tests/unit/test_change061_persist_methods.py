# tests/unit/test_change061_persist_methods.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.chapter_service import ChapterService


@pytest.mark.asyncio
async def test_update_state_delta_writes_json():
    """update_state_delta 应把 state_delta JSON 写入 Chapter，不污染 status。"""
    svc = ChapterService()
    with patch("src.api.services.chapter_service.get_db_session") as mock_db:
        session = AsyncMock()
        ch = MagicMock()
        ch.state_delta = None
        ch.status = "completed"
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=ch)))
        session.commit = AsyncMock()
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        await svc.update_state_delta("n1", 1, {"key_events": ["事件A"]})
    assert ch.state_delta == {"key_events": ["事件A"]}
    assert ch.status == "completed"


@pytest.mark.asyncio
async def test_update_quality_status_writes_status():
    svc = ChapterService()
    with patch("src.api.services.chapter_service.get_db_session") as mock_db:
        session = AsyncMock()
        ch = MagicMock()
        ch.quality_status = None
        ch.status = "completed"
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=ch)))
        session.commit = AsyncMock()
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        await svc.update_quality_status("n1", 1, "unverified")
    assert ch.quality_status == "unverified"
    assert ch.status == "completed"


@pytest.mark.asyncio
async def test_update_state_delta_chapter_not_found_returns_false():
    svc = ChapterService()
    with patch("src.api.services.chapter_service.get_db_session") as mock_db:
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await svc.update_state_delta("n1", 999, {})
    assert result is False
