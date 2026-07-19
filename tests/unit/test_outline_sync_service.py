"""大纲同步服务单元测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.content.outline_sync_service import OutlineSyncService


@pytest.fixture
def service():
    return OutlineSyncService()


class TestAnalyzeImpact:
    @pytest.mark.asyncio
    async def test_no_chapters_returns_empty(self, service):
        with patch(
            "src.api.services.content.outline_sync_service.get_db_session"
        ) as mock_db:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = []
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_db.return_value = mock_session

            result = await service.analyze_impact(
                "novel-1", "master", None, None, {}, {"premise": "new"}
            )
            assert result == []

    @pytest.mark.asyncio
    async def test_llm_timeout_returns_empty(self, service):
        with (
            patch(
                "src.api.services.content.outline_sync_service.get_db_session"
            ) as mock_db,
            patch(
                "src.api.services.content.outline_sync_service.get_llm_client"
            ) as mock_llm_fn,
        ):
            mock_ch = MagicMock()
            mock_ch.chapter_number = 1
            mock_ch.title = "Test"
            mock_ch.word_count = 3000

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalars.return_value.all.return_value = [mock_ch]
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_db.return_value = mock_session

            mock_llm = MagicMock()
            mock_llm.generate = AsyncMock(side_effect=TimeoutError())
            mock_llm_fn.return_value = mock_llm

            result = await service.analyze_impact(
                "novel-1", "master", None, None,
                {"premise": "old"}, {"premise": "new"}
            )
            assert result == []


class TestSuggestionManagement:
    @pytest.mark.asyncio
    async def test_accept_updates_status(self, service):
        with patch(
            "src.api.services.content.outline_sync_service.get_db_session"
        ) as mock_db:
            mock_sug = MagicMock()
            mock_sug.status = "pending"
            mock_sug.novel_id = "novel-1"
            mock_sug.affected_chapter = 3

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_sug
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_db.return_value = mock_session

            ok = await service.accept_suggestion(1)
            assert ok is True
            assert mock_sug.status == "accepted"

    @pytest.mark.asyncio
    async def test_reject_updates_status(self, service):
        with patch(
            "src.api.services.content.outline_sync_service.get_db_session"
        ) as mock_db:
            mock_sug = MagicMock()
            mock_sug.status = "pending"

            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_sug
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_db.return_value = mock_session

            ok = await service.reject_suggestion(1)
            assert ok is True
            assert mock_sug.status == "rejected"

    @pytest.mark.asyncio
    async def test_accept_nonexistent_returns_false(self, service):
        with patch(
            "src.api.services.content.outline_sync_service.get_db_session"
        ) as mock_db:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_db.return_value = mock_session

            ok = await service.accept_suggestion(999)
            assert ok is False

    @pytest.mark.asyncio
    async def test_batch_action(self, service):
        with patch.object(
            service, "accept_suggestion", new_callable=AsyncMock
        ) as mock_accept:
            mock_accept.side_effect = [True, True, False]
            count = await service.batch_action([1, 2, 3], "accept")
            assert count == 2


class TestDeviationDetection:
    @pytest.mark.asyncio
    async def test_low_deviation_marks_completed(self, service):
        with (
            patch(
                "src.api.services.content.outline_sync_service.get_db_session"
            ) as mock_db,
            patch(
                "src.api.services.content.outline_sync_service.get_llm_client"
            ) as mock_llm_fn,
        ):
            mock_chapter = MagicMock()
            mock_chapter.content = "章节正文内容..."

            mock_outline = MagicMock()
            mock_outline.content = {"title": "测试", "scenes": []}
            mock_outline.status = "draft"
            mock_outline.deviation_summary = None

            mock_session = AsyncMock()
            results = [MagicMock(), MagicMock()]
            results[0].scalar_one_or_none.return_value = mock_chapter
            results[1].scalar_one_or_none.return_value = mock_outline
            mock_session.execute = AsyncMock(side_effect=results)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_db.return_value = mock_session

            mock_llm = MagicMock()
            mock_llm.generate = AsyncMock(
                return_value='{"deviation_score": 0.1, "deviation_summary": ""}'
            )
            mock_llm_fn.return_value = mock_llm

            result = await service.detect_deviation("novel-1", 1)
            assert result["outline_status"] == "completed"
            assert result["deviation_score"] == 0.1

    @pytest.mark.asyncio
    async def test_high_deviation_marks_deviated(self, service):
        with (
            patch(
                "src.api.services.content.outline_sync_service.get_db_session"
            ) as mock_db,
            patch(
                "src.api.services.content.outline_sync_service.get_llm_client"
            ) as mock_llm_fn,
        ):
            mock_chapter = MagicMock()
            mock_chapter.content = "完全不同的内容..."

            mock_outline = MagicMock()
            mock_outline.content = {"title": "测试"}
            mock_outline.status = "draft"
            mock_outline.deviation_summary = None

            mock_session = AsyncMock()
            results = [MagicMock(), MagicMock()]
            results[0].scalar_one_or_none.return_value = mock_chapter
            results[1].scalar_one_or_none.return_value = mock_outline
            mock_session.execute = AsyncMock(side_effect=results)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_db.return_value = mock_session

            mock_llm = MagicMock()
            mock_llm.generate = AsyncMock(
                return_value='{"deviation_score": 0.7, "deviation_summary": "严重偏离"}'
            )
            mock_llm_fn.return_value = mock_llm

            result = await service.detect_deviation("novel-1", 1)
            assert result["outline_status"] == "deviated"
            assert result["deviation_score"] == 0.7
            assert "严重偏离" in result["deviation_summary"]

    @pytest.mark.asyncio
    async def test_missing_chapter_returns_error(self, service):
        with patch(
            "src.api.services.content.outline_sync_service.get_db_session"
        ) as mock_db:
            mock_session = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute = AsyncMock(return_value=mock_result)
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_db.return_value = mock_session

            result = await service.detect_deviation("novel-1", 99)
            assert "error" in result
