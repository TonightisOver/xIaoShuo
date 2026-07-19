"""Unit tests for CHANGE-044: long-form novel services.

Covers:
- LongFormProgressService (long_form_progress_service.py)
- QualityReportService (quality_report_service.py)
- FillerDetectionService (filler_detection_service.py)
- ForeshadowTrackerService (foreshadow_tracker_service.py)

All database interactions are mocked; tests exercise pure business logic.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _novel_id() -> str:
    return f"novel-{uuid.uuid4().hex[:8]}"


def _make_novel(**overrides):
    """Create a mock Novel ORM object with sensible defaults."""
    m = MagicMock()
    m.novel_id = overrides.get("novel_id", _novel_id())
    m.total_volumes = overrides.get("total_volumes", 3)
    m.chapters_per_volume = overrides.get("chapters_per_volume", 40)
    m.target_words = overrides.get("target_words", 1_000_000)
    m.is_long_form = overrides.get("is_long_form", True)
    m.status = overrides.get("status", "draft")
    return m


def _make_lfp(**overrides):
    """Create a mock LongFormProgress ORM object."""
    m = MagicMock()
    m.novel_id = overrides.get("novel_id", _novel_id())
    m.volume_number = overrides.get("volume_number", 1)
    m.status = overrides.get("status", "pending")
    m.chapter_start = overrides.get("chapter_start", 1)
    m.chapter_end = overrides.get("chapter_end", 40)
    m.chapters_completed = overrides.get("chapters_completed", 0)
    m.current_chapter = overrides.get("current_chapter", None)
    m.quality_report = overrides.get("quality_report", None)
    m.filler_report = overrides.get("filler_report", None)
    m.errors = overrides.get("errors", [])
    m.created_at = overrides.get("created_at", datetime.now(UTC))
    m.completed_at = overrides.get("completed_at", None)
    return m


def _make_chapter(**overrides):
    """Create a mock Chapter ORM object."""
    m = MagicMock()
    m.novel_id = overrides.get("novel_id", _novel_id())
    m.volume_number = overrides.get("volume_number", 1)
    m.chapter_number = overrides.get("chapter_number", 1)
    m.title = overrides.get("title", "Chapter 1")
    m.word_count = overrides.get("word_count", 3000)
    m.chapter_type = overrides.get("chapter_type", None)
    m.status = overrides.get("status", "completed")
    m.content = overrides.get("content", "")
    return m


def _make_volume(**overrides):
    """Create a mock Volume ORM object."""
    m = MagicMock()
    m.novel_id = overrides.get("novel_id", _novel_id())
    m.volume_number = overrides.get("volume_number", 1)
    m.status = overrides.get("status", "completed")
    m.title = overrides.get("title", "Volume 1")
    return m


def _make_story_bible(**overrides):
    """Create a mock StoryBible ORM object."""
    m = MagicMock()
    m.novel_id = overrides.get("novel_id", _novel_id())
    m.foreshadowing_list = overrides.get("foreshadowing_list", [])
    m.unresolved_hooks = overrides.get("unresolved_hooks", [])
    return m


def _fake_session(result=None):
    """Return a mock session factory context manager that yields a session.

    The session.execute().scalars().all() or scalar_one_or_none() chain
    returns *result*.
    """
    session = AsyncMock()

    # Build the chain: execute -> result -> scalars() -> all()
    mock_result = MagicMock()
    if isinstance(result, list):
        mock_result.scalars.return_value.all.return_value = result
    else:
        # scalar_one_or_none
        mock_result.scalar_one_or_none.return_value = result

    session.execute = AsyncMock(return_value=mock_result)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx, session


# ===========================================================================
# 1. LongFormProgressService
# ===========================================================================

class TestLongFormProgressService:
    """Tests for LongFormProgressService."""

    # --- initialize_progress ---

    @pytest.mark.asyncio
    async def test_initialize_progress_creates_records(self):
        """initialize_progress should create one record per volume with correct chapter ranges."""

        nid = _novel_id()

        @asynccontextmanager
        async def _ctx():
            session = AsyncMock()
            session.add = MagicMock()
            yield session

        with patch("src.api.services.generation.long_form_progress_service.get_db_session", _ctx):
            from src.api.services.generation.long_form_progress_service import (
                LongFormProgressService,
            )
            svc = LongFormProgressService()
            records = await svc.initialize_progress(nid, total_volumes=3, chapters_per_volume=20)

        assert len(records) == 3
        assert records[0]["volume_number"] == 1
        assert records[0]["chapter_start"] == 1
        assert records[0]["chapter_end"] == 20
        assert records[1]["chapter_start"] == 21
        assert records[1]["chapter_end"] == 40
        assert records[2]["chapter_start"] == 41
        assert records[2]["chapter_end"] == 60
        for r in records:
            assert r["status"] == "pending"

    @pytest.mark.asyncio
    async def test_initialize_progress_single_volume(self):
        """Single volume still works correctly."""
        nid = _novel_id()

        @asynccontextmanager
        async def _ctx():
            session = AsyncMock()
            session.add = MagicMock()
            yield session

        with patch("src.api.services.generation.long_form_progress_service.get_db_session", _ctx):
            from src.api.services.generation.long_form_progress_service import (
                LongFormProgressService,
            )
            svc = LongFormProgressService()
            records = await svc.initialize_progress(nid, total_volumes=1, chapters_per_volume=50)

        assert len(records) == 1
        assert records[0]["chapter_start"] == 1
        assert records[0]["chapter_end"] == 50

    # --- update_volume_status ---

    @pytest.mark.asyncio
    async def test_update_volume_status_found(self):
        """update_volume_status updates record fields when found."""
        nid = _novel_id()
        record = _make_lfp(nid=nid, volume_number=1, status="pending", errors=[])
        ctx_fn, session = _fake_session(record)

        with patch("src.api.services.generation.long_form_progress_service.get_db_session", ctx_fn):
            from src.api.services.generation.long_form_progress_service import (
                LongFormProgressService,
            )
            svc = LongFormProgressService()
            await svc.update_volume_status(
                nid, 1, "generating", chapters_completed=5, current_chapter=10,
                errors=["test error"],
            )

        assert record.status == "generating"
        assert record.chapters_completed == 5
        assert record.current_chapter == 10
        assert record.errors == ["test error"]

    @pytest.mark.asyncio
    async def test_update_volume_status_not_found(self):
        """update_volume_status silently returns when record not found."""
        ctx_fn, session = _fake_session(None)

        with patch("src.api.services.generation.long_form_progress_service.get_db_session", ctx_fn):
            from src.api.services.generation.long_form_progress_service import (
                LongFormProgressService,
            )
            svc = LongFormProgressService()
            # Should not raise
            await svc.update_volume_status("nonexistent", 1, "completed")

    @pytest.mark.asyncio
    async def test_update_volume_status_sets_completed_at(self):
        """When status='completed', completed_at should be set."""
        nid = _novel_id()
        record = _make_lfp(nid=nid, volume_number=1, status="generating", completed_at=None)
        ctx_fn, _ = _fake_session(record)

        with patch("src.api.services.generation.long_form_progress_service.get_db_session", ctx_fn):
            from src.api.services.generation.long_form_progress_service import (
                LongFormProgressService,
            )
            svc = LongFormProgressService()
            await svc.update_volume_status(nid, 1, "completed")

        assert record.completed_at is not None

    @pytest.mark.asyncio
    async def test_update_volume_status_appends_errors(self):
        """Existing errors should be preserved and new ones appended."""
        nid = _novel_id()
        record = _make_lfp(nid=nid, volume_number=1, errors=["old error"])
        ctx_fn, _ = _fake_session(record)

        with patch("src.api.services.generation.long_form_progress_service.get_db_session", ctx_fn):
            from src.api.services.generation.long_form_progress_service import (
                LongFormProgressService,
            )
            svc = LongFormProgressService()
            await svc.update_volume_status(nid, 1, "generating", errors=["new error"])

        assert record.errors == ["old error", "new error"]

    @pytest.mark.asyncio
    async def test_update_quality_and_filler_report(self):
        """Quality and filler reports are updated."""
        nid = _novel_id()
        record = _make_lfp(nid=nid, volume_number=1)
        ctx_fn, _ = _fake_session(record)

        qr = {"avg_quality_score": 0.8}
        fr = {"filler_ratio": 0.1}

        with patch("src.api.services.generation.long_form_progress_service.get_db_session", ctx_fn):
            from src.api.services.generation.long_form_progress_service import (
                LongFormProgressService,
            )
            svc = LongFormProgressService()
            await svc.update_volume_status(
                nid, 1, "completed", quality_report=qr, filler_report=fr,
            )

        assert record.quality_report == qr
        assert record.filler_report == fr

    # --- get_progress ---

    @pytest.mark.asyncio
    async def test_get_progress_returns_novel_not_found(self):
        """get_progress returns error when novel not found."""
        ctx_fn, _ = _fake_session(None)

        with patch("src.api.services.generation.long_form_progress_service.get_db_session", ctx_fn):
            from src.api.services.generation.long_form_progress_service import (
                LongFormProgressService,
            )
            svc = LongFormProgressService()
            result = await svc.get_progress("nonexistent")

        assert "error" in result

    @pytest.mark.asyncio
    async def test_get_progress_computes_summary(self):
        """get_progress aggregates progress across volumes."""
        nid = _novel_id()
        novel = _make_novel(nid=nid, total_volumes=2, chapters_per_volume=10, target_words=100000)
        records = [
            _make_lfp(nid=nid, volume_number=1, status="completed", chapters_completed=10,
                       quality_report={"total_word_count": 30000}),
            _make_lfp(nid=nid, volume_number=2, status="generating", chapters_completed=5,
                       quality_report={"total_word_count": 15000}),
        ]

        # We need two session calls: first for novel, second for progress records
        call_count = 0
        novel_result = MagicMock()
        novel_result.scalar_one_or_none.return_value = novel

        records_result = MagicMock()
        records_result.scalars.return_value.all.return_value = records

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[novel_result, records_result])

        @asynccontextmanager
        async def _ctx():
            yield session

        with patch("src.api.services.generation.long_form_progress_service.get_db_session", _ctx):
            from src.api.services.generation.long_form_progress_service import (
                LongFormProgressService,
            )
            svc = LongFormProgressService()
            result = await svc.get_progress(nid)

        assert result["novel_id"] == nid
        assert result["total_volumes"] == 2
        assert result["completed_volumes"] == 1
        assert result["chapters_completed"] == 15
        assert result["total_word_count"] == 45000
        assert result["current_volume"] == 2
        assert result["target_words"] == 100000
        assert result["progress_percentage"] > 0
        assert len(result["volume_details"]) == 2

    # --- get_volume_progress ---

    @pytest.mark.asyncio
    async def test_get_volume_progress_found(self):
        """Returns volume detail dict when found."""
        nid = _novel_id()
        record = _make_lfp(nid=nid, volume_number=1, status="completed", chapters_completed=10)
        ctx_fn, _ = _fake_session(record)

        with patch("src.api.services.generation.long_form_progress_service.get_db_session", ctx_fn):
            from src.api.services.generation.long_form_progress_service import (
                LongFormProgressService,
            )
            svc = LongFormProgressService()
            result = await svc.get_volume_progress(nid, 1)

        assert result is not None
        assert result["novel_id"] == nid
        assert result["volume_number"] == 1
        assert result["status"] == "completed"
        assert result["chapters_completed"] == 10

    @pytest.mark.asyncio
    async def test_get_volume_progress_not_found(self):
        """Returns None when record not found."""
        ctx_fn, _ = _fake_session(None)

        with patch("src.api.services.generation.long_form_progress_service.get_db_session", ctx_fn):
            from src.api.services.generation.long_form_progress_service import (
                LongFormProgressService,
            )
            svc = LongFormProgressService()
            result = await svc.get_volume_progress("nonexistent", 1)

        assert result is None

    # --- singleton factory ---

    def test_get_long_form_progress_service_singleton(self):
        """get_long_form_progress_service returns singleton."""
        import src.api.services.generation.long_form_progress_service as mod
        original = mod._progress_service
        try:
            mod._progress_service = None
            svc1 = mod.get_long_form_progress_service()
            svc2 = mod.get_long_form_progress_service()
            assert svc1 is svc2
        finally:
            mod._progress_service = original

    def test_get_long_form_progress_service_with_session(self):
        """Passing a session creates a new instance."""
        import src.api.services.generation.long_form_progress_service as mod
        original = mod._progress_service
        try:
            mod._progress_service = None
            svc1 = mod.get_long_form_progress_service()
            svc2 = mod.get_long_form_progress_service(session=AsyncMock())
            assert svc2 is not svc1
        finally:
            mod._progress_service = original


# ===========================================================================
# 2. QualityReportService
# ===========================================================================

class TestQualityReportService:
    """Tests for QualityReportService."""

    def _make_chapters(self, count=5, word_count=3000, novel_id=None):
        """Create a list of mock Chapter objects."""
        nid = novel_id or _novel_id()
        return [
            _make_chapter(nid=nid, volume_number=1, chapter_number=i + 1,
                          word_count=word_count, title=f"Ch {i+1}")
            for i in range(count)
        ]

    # --- _build_volume_report ---

    def test_build_volume_report_empty_chapters(self):
        """Empty chapter list returns zeroed report."""
        from src.api.services.quality.quality_report_service import QualityReportService
        svc = QualityReportService()
        report = svc._build_volume_report(1, [], {}, {})  # volume_number, chapters, version_map, overall_score_map

        assert report["volume_number"] == 1
        assert report["chapter_count"] == 0
        assert report["total_word_count"] == 0
        assert report["avg_scores"] == {}
        assert report["filler_chapters"] == []

    def test_build_volume_report_with_chapters(self):
        """Report includes scores, word count, and trends."""
        from src.api.services.quality.quality_report_service import QualityReportService
        svc = QualityReportService()
        chapters = self._make_chapters(3, word_count=4000)
        report = svc._build_volume_report(1, chapters, {}, {})  # volume_number, chapters, version_map, overall_score_map

        assert report["chapter_count"] == 3
        assert report["total_word_count"] == 12000
        assert len(report["score_trends"]) == 8  # 8 quality dimensions
        # All default scores are 0.7
        for dim_scores in report["score_trends"].values():
            assert all(s == 0.7 for s in dim_scores)

    def test_build_volume_report_has_unverified_when_no_scores(self):
        """无任何评分的章节应标记 has_unverified=True（供前端诚实提示）。"""
        from src.api.services.quality.quality_report_service import QualityReportService
        svc = QualityReportService()
        chapters = self._make_chapters(2, word_count=4000)
        # 空 version_map + 空 overall_score_map → 从未评估
        report = svc._build_volume_report(1, chapters, {}, {})
        assert report["has_unverified"] is True

    def test_build_volume_report_no_unverified_when_scored(self):
        """所有章节有评分时 has_unverified=False。"""
        from src.api.services.quality.quality_report_service import QualityReportService
        svc = QualityReportService()
        chapters = self._make_chapters(2, word_count=4000)
        # 每章都有 overall 分 → 已评估
        overall_map = {ch.chapter_number: 0.8 for ch in chapters}
        report = svc._build_volume_report(1, chapters, {}, overall_map)
        assert report["has_unverified"] is False

    def test_build_volume_report_empty_no_unverified(self):
        """空卷 has_unverified=False。"""
        from src.api.services.quality.quality_report_service import QualityReportService
        svc = QualityReportService()
        report = svc._build_volume_report(1, [], {}, {})
        assert report["has_unverified"] is False

    def test_build_volume_report_detects_low_word_count_warning(self):
        """Warning generated when a chapter has abnormally low word count."""
        from src.api.services.quality.quality_report_service import QualityReportService
        svc = QualityReportService()
        chapters = [
            _make_chapter(volume_number=1, chapter_number=1, word_count=4000),
            _make_chapter(volume_number=1, chapter_number=2, word_count=4000),
            _make_chapter(volume_number=1, chapter_number=3, word_count=500),  # much lower
        ]
        report = svc._build_volume_report(1, chapters, {}, {})

        # Should detect the low word count chapter
        word_warnings = [w for w in report["warnings"] if "字数异常偏少" in w]
        assert len(word_warnings) == 1

    # --- _detect_warnings ---

    def test_detect_warnings_consecutive_low_advancement(self):
        """Consecutive low advancement scores trigger warning."""
        from src.api.services.quality.quality_report_service import (
            CONSECUTIVE_LOW_THRESHOLD,
            QualityReportService,
        )
        svc = QualityReportService()
        low_score = {"advancement": 0.3, "pacing": 0.7}  # below 0.5 threshold
        scores = [low_score] * CONSECUTIVE_LOW_THRESHOLD

        warnings = svc._detect_warnings([], scores, {"advancement": 0.3})
        adv_warnings = [w for w in warnings if "连续" in w and "主线推进" in w]
        assert len(adv_warnings) >= 1

    def test_detect_warnings_no_issues(self):
        """No warnings when scores are all healthy."""
        from src.api.services.quality.quality_report_service import QualityReportService
        svc = QualityReportService()
        scores = [{"advancement": 0.8, "pacing": 0.9} for _ in range(5)]
        avg_scores = {"advancement": 0.8, "pacing": 0.9, "character_consistency": 0,
                       "world_consistency": 0, "conflict": 0, "foreshadowing": 0,
                       "dialogue_quality": 0, "emotional_impact": 0}

        warnings = svc._detect_warnings([], scores, avg_scores)
        # No word count warnings (empty chapters list), no low score warnings
        assert warnings == []

    # --- _detect_filler_chapters ---

    def test_detect_filler_chapters_none_below_threshold(self):
        """No filler when all chapters score above threshold."""
        from src.api.services.quality.quality_report_service import QualityReportService
        svc = QualityReportService()
        chapters = self._make_chapters(3)
        scores = [{"advancement": 0.7, "pacing": 0.7} for _ in range(3)]

        filler = svc._detect_filler_chapters(chapters, scores)
        assert filler == []

    # --- _detect_stalled_chapters ---

    def test_detect_stalled_chapters(self):
        """Chapters with low advancement are detected as stalled."""
        from src.api.services.quality.quality_report_service import QualityReportService
        svc = QualityReportService()
        scores = [
            {"advancement": 0.8},  # fine
            {"advancement": 0.3},  # stalled
            {"advancement": 0.9},  # fine
        ]

        stalled = svc._detect_stalled_chapters(scores)
        assert 2 in stalled  # chapter_number = index+1 = 2
        assert 1 not in stalled
        assert 3 not in stalled

    # --- _extract_chapter_scores ---

    def test_extract_chapter_scores_returns_default(self):
        """Default scores are all 0.7 when no version data available."""
        from src.api.services.quality.quality_report_service import (
            QUALITY_DIMENSIONS,
            QualityReportService,
        )
        svc = QualityReportService()
        scores = svc._extract_chapter_scores(1, {}, {})  # chapter_number, version_map, overall_score_map

        assert len(scores) == len(QUALITY_DIMENSIONS)
        assert all(v == 0.7 for v in scores.values())

    # --- _get_foreshadow_summary / _get_character_appearance ---

    def test_foreshadow_summary_returns_zeros(self):
        from src.api.services.quality.quality_report_service import QualityReportService
        svc = QualityReportService()
        result = svc._get_foreshadow_summary([])
        assert result["total_planted"] == 0
        assert result["total_resolved"] == 0
        assert result["dangling_count"] == 0

    def test_character_appearance_returns_zeros(self):
        from src.api.services.quality.quality_report_service import QualityReportService
        svc = QualityReportService()
        result = svc._get_character_appearance([])
        assert result["total_characters"] == 0

    # --- generate_novel_quality_report ---

    @pytest.mark.asyncio
    async def test_generate_novel_quality_report_empty(self):
        """Report for novel with no volumes/chapters returns zeros."""
        novel = _make_novel(total_volumes=0)
        empty_list_result = MagicMock()
        empty_list_result.scalars.return_value.all.return_value = []

        session = AsyncMock()
        session.execute = AsyncMock(return_value=empty_list_result)

        @asynccontextmanager
        async def _ctx():
            yield session

        with patch("src.api.services.quality.quality_report_service.get_db_session", _ctx):
            from src.api.services.quality.quality_report_service import (
                QualityReportService,
            )
            svc = QualityReportService()
            report = await svc.generate_novel_quality_report("test-novel")

        assert report["total_volumes"] == 0
        assert report["completed_volumes"] == 0
        assert report["volume_reports"] == []

    @pytest.mark.asyncio
    async def test_generate_novel_quality_report_with_data(self):
        """Report aggregates scores from volumes and chapters."""
        novel = _make_novel(total_volumes=2)
        volumes = [
            _make_volume(volume_number=1, status="completed"),
            _make_volume(volume_number=2, status="completed"),
        ]
        chapters = self._make_chapters(4, novel_id=novel.novel_id)

        vol_result = MagicMock()
        vol_result.scalars.return_value.all.return_value = volumes
        ch_result = MagicMock()
        ch_result.scalars.return_value.all.return_value = chapters
        # Empty version result for ChapterVersion query
        ver_result = MagicMock()
        ver_result.scalars.return_value.all.return_value = []

        session = AsyncMock()
        session.execute = AsyncMock(side_effect=[vol_result, ch_result, ver_result])

        @asynccontextmanager
        async def _ctx():
            yield session

        with patch("src.api.services.quality.quality_report_service.get_db_session", _ctx):
            from src.api.services.quality.quality_report_service import (
                QualityReportService,
            )
            svc = QualityReportService()
            report = await svc.generate_novel_quality_report(novel.novel_id)

        assert report["total_volumes"] == 2
        assert report["completed_volumes"] == 2
        assert len(report["volume_reports"]) == 2
        # Default scores should be present
        for dim, val in report["overall_avg_scores"].items():
            assert val == 0.7

    # --- singleton factory ---

    def test_get_quality_report_service_singleton(self):
        import src.api.services.quality.quality_report_service as mod
        original = mod._quality_report_service
        try:
            mod._quality_report_service = None
            svc1 = mod.get_quality_report_service()
            svc2 = mod.get_quality_report_service()
            assert svc1 is svc2
        finally:
            mod._quality_report_service = original


# ===========================================================================
# 3. FillerDetectionService
# ===========================================================================

class TestFillerDetectionService:
    """Tests for FillerDetectionService."""

    # --- _calculate_filler_score ---

    def test_filler_score_normal_chapter(self):
        """Normal chapter (avg word count) should have low filler score."""
        from src.api.services.quality.filler_detection_service import (
            FillerDetectionService,
        )
        svc = FillerDetectionService()
        ch = _make_chapter(word_count=3000)
        score = svc._calculate_filler_score(ch, avg_word_count=3000)
        assert score < 0.5  # Not considered filler

    def test_filler_score_short_chapter(self):
        """Very short chapter gets high filler score."""
        from src.api.services.quality.filler_detection_service import (
            FillerDetectionService,
        )
        svc = FillerDetectionService()
        ch = _make_chapter(word_count=500)
        score = svc._calculate_filler_score(ch, avg_word_count=3000)
        assert score > 0.3  # At least moderately suspicious

    def test_filler_score_marked_filler(self):
        """Chapter explicitly marked as 'filler' type gets bonus score (L0 分 + 显式标记 +0.5)。"""
        from src.api.services.quality.filler_detection_service import (
            FillerDetectionService,
        )
        svc = FillerDetectionService()
        ch = _make_chapter(word_count=5000, chapter_type="filler")
        score = svc._calculate_filler_score(ch, avg_word_count=3000)
        # 5000 字正文 L0 不报违规(0.0)，但显式 filler 标记叠加 +0.6，须越过 detect 的 >0.5 阈值
        assert score > 0.5

    def test_filler_score_very_low_word_count(self):
        """Chapter with < 1000 words gets additional penalty."""
        from src.api.services.quality.filler_detection_service import (
            FillerDetectionService,
        )
        svc = FillerDetectionService()
        ch = _make_chapter(word_count=500)
        score = svc._calculate_filler_score(ch, avg_word_count=3000)
        assert score >= 0.3

    def test_filler_score_zero_avg_no_division_error(self):
        """Zero average word count should not cause division error."""
        from src.api.services.quality.filler_detection_service import (
            FillerDetectionService,
        )
        svc = FillerDetectionService()
        ch = _make_chapter(word_count=0)
        score = svc._calculate_filler_score(ch, avg_word_count=0)
        assert 0.0 <= score <= 1.0

    # --- _get_filler_reasons ---

    def test_get_filler_reasons_short_word_count(self):
        """Reason includes word count for short chapters."""
        from src.api.services.quality.filler_detection_service import (
            FillerDetectionService,
        )
        svc = FillerDetectionService()
        ch = _make_chapter(word_count=500)
        reasons = svc._get_filler_reasons(ch, avg_word_count=3000)
        assert any("字数过少" in r for r in reasons)

    def test_get_filler_reasons_filler_type(self):
        """Reason includes filler type when marked."""
        from src.api.services.quality.filler_detection_service import (
            FillerDetectionService,
        )
        svc = FillerDetectionService()
        ch = _make_chapter(word_count=5000, chapter_type="filler")
        reasons = svc._get_filler_reasons(ch, avg_word_count=3000)
        assert any("filler" in r for r in reasons)

    def test_get_filler_reasons_low_word_count(self):
        """Reason includes low word count."""
        from src.api.services.quality.filler_detection_service import (
            FillerDetectionService,
        )
        svc = FillerDetectionService()
        ch = _make_chapter(word_count=800)
        reasons = svc._get_filler_reasons(ch, avg_word_count=3000)
        assert any("字数极低" in r for r in reasons)

    # --- _generate_recommendations ---

    def test_recommendations_no_filler(self):
        """Empty filler list yields 'quality good' recommendation."""
        from src.api.services.quality.filler_detection_service import (
            FillerDetectionService,
        )
        svc = FillerDetectionService()
        recs = svc._generate_recommendations([], 0.0, 100)
        assert len(recs) == 1
        assert "质量良好" in recs[0]

    def test_recommendations_high_ratio(self):
        """High filler ratio triggers ratio warning."""
        from src.api.services.quality.filler_detection_service import (
            FillerDetectionService,
        )
        svc = FillerDetectionService()
        filler_chapters = [{"chapter_number": i, "reasons": []} for i in range(1, 6)]
        recs = svc._generate_recommendations(filler_chapters, 0.3, 20)
        assert any("注水比例较高" in r for r in recs)

    def test_recommendations_many_filler(self):
        """More than 5 filler chapters triggers batch regeneration suggestion."""
        from src.api.services.quality.filler_detection_service import (
            FillerDetectionService,
        )
        svc = FillerDetectionService()
        filler_chapters = [{"chapter_number": i, "reasons": ["reason"]} for i in range(1, 8)]
        recs = svc._generate_recommendations(filler_chapters, 0.35, 20)
        assert any("批量重新生成" in r for r in recs)

    # --- detect_filler_chapters (integration of internal methods) ---

    @pytest.mark.asyncio
    async def test_detect_filler_chapters_empty_novel(self):
        """Novel with no chapters returns empty filler list."""
        ctx_fn, _ = _fake_session([])

        with patch("src.api.services.quality.filler_detection_service.get_db_session", ctx_fn):
            from src.api.services.quality.filler_detection_service import (
                FillerDetectionService,
            )
            svc = FillerDetectionService()
            result = await svc.detect_filler_chapters("novel-123")

        assert result["total_chapters"] == 0
        assert result["filler_chapters"] == []
        assert result["filler_ratio"] == 0.0

    @pytest.mark.asyncio
    async def test_detect_filler_chapters_with_normal_chapters(self):
        """Normal chapters have no filler detected."""
        chapters = [
            _make_chapter(volume_number=1, chapter_number=i, word_count=3000)
            for i in range(1, 6)
        ]
        ctx_fn, _ = _fake_session(chapters)

        with patch("src.api.services.quality.filler_detection_service.get_db_session", ctx_fn):
            from src.api.services.quality.filler_detection_service import (
                FillerDetectionService,
            )
            svc = FillerDetectionService()
            result = await svc.detect_filler_chapters("novel-123")

        assert result["total_chapters"] == 5
        # Normal chapters should not be flagged
        assert result["filler_ratio"] < 0.5

    @pytest.mark.asyncio
    async def test_detect_filler_chapters_marked_filler_is_detected(self):
        """被显式标记 filler 且正文够长的章节，必须出现在检出列表（集成层验证越过 >0.5 阈值）。"""
        chapters = [
            _make_chapter(volume_number=1, chapter_number=1, word_count=3000),
            _make_chapter(volume_number=1, chapter_number=2, word_count=5000, chapter_type="filler"),
            _make_chapter(volume_number=1, chapter_number=3, word_count=3000),
        ]
        ctx_fn, _ = _fake_session(chapters)

        with patch("src.api.services.quality.filler_detection_service.get_db_session", ctx_fn):
            from src.api.services.quality.filler_detection_service import (
                FillerDetectionService,
            )
            svc = FillerDetectionService()
            result = await svc.detect_filler_chapters("novel-123")

        flagged = [c["chapter_number"] for c in result["filler_chapters"]]
        assert 2 in flagged, "被标记 filler 的长章应被检出"

    # --- singleton factory ---

    def test_get_filler_detection_service_singleton(self):
        import src.api.services.quality.filler_detection_service as mod
        original = mod._filler_detection_service
        try:
            mod._filler_detection_service = None
            svc1 = mod.get_filler_detection_service()
            svc2 = mod.get_filler_detection_service()
            assert svc1 is svc2
        finally:
            mod._filler_detection_service = original


# ===========================================================================
# 4. ForeshadowTrackerService
# ===========================================================================

class TestForeshadowTrackerService:
    """Tests for ForeshadowTrackerService."""

    # --- track_foreshadows ---

    @pytest.mark.asyncio
    async def test_track_foreshadows_no_bible(self):
        """When story bible not found, returns zero counts."""
        ctx_fn, _ = _fake_session(None)

        with patch("src.api.services.quality.foreshadow_tracker_service.get_db_session", ctx_fn):
            from src.api.services.quality.foreshadow_tracker_service import (
                ForeshadowTrackerService,
            )
            svc = ForeshadowTrackerService()
            result = await svc.track_foreshadows("novel-123")

        assert result["total_foreshadows"] == 0
        assert result["planted"] == []
        assert result["resolved"] == []
        assert result["dangling"] == []
        assert result["resolution_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_track_foreshadows_with_data(self):
        """Correctly categorizes foreshadows into planted/resolved/dangling."""
        nid = _novel_id()
        bible = _make_story_bible(
            nid=nid,
            foreshadowing_list=[
                {"name": "剑的秘密", "description": "一把古剑", "planted_chapter": 1, "status": "active"},
                {"name": "身世之谜", "description": "主角身世", "planted_chapter": 3, "resolved_chapter": 10,
                 "status": "resolved"},
            ],
            unresolved_hooks=[
                {"name": "神秘人", "description": "跟踪主角", "chapter": 5},
            ],
        )
        ctx_fn, _ = _fake_session(bible)

        with patch("src.api.services.quality.foreshadow_tracker_service.get_db_session", ctx_fn):
            from src.api.services.quality.foreshadow_tracker_service import (
                ForeshadowTrackerService,
            )
            svc = ForeshadowTrackerService()
            result = await svc.track_foreshadows(nid)

        assert result["total_foreshadows"] == 3
        assert len(result["planted"]) == 1
        assert result["planted"][0]["name"] == "剑的秘密"
        assert len(result["resolved"]) == 1
        assert result["resolved"][0]["name"] == "身世之谜"
        assert len(result["dangling"]) == 1
        assert result["dangling"][0]["name"] == "神秘人"

    @pytest.mark.asyncio
    async def test_track_foreshadows_resolution_rate(self):
        """Resolution rate = resolved / total."""
        nid = _novel_id()
        bible = _make_story_bible(
            nid=nid,
            foreshadowing_list=[
                {"name": "A", "status": "resolved", "resolved_chapter": 5},
                {"name": "B", "status": "resolved", "resolved_chapter": 8},
                {"name": "C", "status": "active"},
            ],
            unresolved_hooks=[],
        )
        ctx_fn, _ = _fake_session(bible)

        with patch("src.api.services.quality.foreshadow_tracker_service.get_db_session", ctx_fn):
            from src.api.services.quality.foreshadow_tracker_service import (
                ForeshadowTrackerService,
            )
            svc = ForeshadowTrackerService()
            result = await svc.track_foreshadows(nid)

        # 2 resolved / 3 total = 0.667
        assert abs(result["resolution_rate"] - 0.667) < 0.01

    @pytest.mark.asyncio
    async def test_track_foreshadows_empty_lists(self):
        """Empty foreshadowing and hooks lists produce zero totals."""
        nid = _novel_id()
        bible = _make_story_bible(nid=nid, foreshadowing_list=[], unresolved_hooks=[])
        ctx_fn, _ = _fake_session(bible)

        with patch("src.api.services.quality.foreshadow_tracker_service.get_db_session", ctx_fn):
            from src.api.services.quality.foreshadow_tracker_service import (
                ForeshadowTrackerService,
            )
            svc = ForeshadowTrackerService()
            result = await svc.track_foreshadows(nid)

        assert result["total_foreshadows"] == 0
        assert result["resolution_rate"] == 0.0

    # --- get_dangling_foreshadows ---

    @pytest.mark.asyncio
    async def test_get_dangling_foreshadows(self):
        """Returns only dangling foreshadows (unresolved_hooks only)."""
        nid = _novel_id()
        bible = _make_story_bible(
            nid=nid,
            foreshadowing_list=[
                {"name": "A", "status": "active"},           # -> planted, NOT dangling
                {"name": "B", "status": "resolved", "resolved_chapter": 5},  # -> resolved
            ],
            unresolved_hooks=[
                {"name": "hook1", "description": "dangling hook", "chapter": 3},
            ],
        )
        ctx_fn, _ = _fake_session(bible)

        with patch("src.api.services.quality.foreshadow_tracker_service.get_db_session", ctx_fn):
            from src.api.services.quality.foreshadow_tracker_service import (
                ForeshadowTrackerService,
            )
            svc = ForeshadowTrackerService()
            dangling = await svc.get_dangling_foreshadows(nid)

        # Only unresolved_hooks go to dangling; active foreshadows go to planted
        assert len(dangling) == 1
        assert dangling[0]["name"] == "hook1"
        assert dangling[0]["status"] == "dangling"

    # --- check_foreshadow_health ---

    @pytest.mark.asyncio
    async def test_check_foreshadow_health_no_foreshadows(self):
        """Health check warns when no foreshadows exist."""
        nid = _novel_id()
        bible = _make_story_bible(nid=nid, foreshadowing_list=[], unresolved_hooks=[])
        ctx_fn, _ = _fake_session(bible)

        with patch("src.api.services.quality.foreshadow_tracker_service.get_db_session", ctx_fn):
            from src.api.services.quality.foreshadow_tracker_service import (
                ForeshadowTrackerService,
            )
            svc = ForeshadowTrackerService()
            health = await svc.check_foreshadow_health(nid)

        assert health["health_status"] in ("warning", "critical")
        assert any("未发现伏笔" in i for i in health["issues"])

    @pytest.mark.asyncio
    async def test_check_foreshadow_health_too_many_dangling(self):
        """Health check warns when dangling > 10."""
        nid = _novel_id()
        hooks = [{"name": f"hook{i}", "description": f"d{i}", "chapter": i} for i in range(1, 15)]
        bible = _make_story_bible(nid=nid, foreshadowing_list=[], unresolved_hooks=hooks)
        ctx_fn, _ = _fake_session(bible)

        with patch("src.api.services.quality.foreshadow_tracker_service.get_db_session", ctx_fn):
            from src.api.services.quality.foreshadow_tracker_service import (
                ForeshadowTrackerService,
            )
            svc = ForeshadowTrackerService()
            health = await svc.check_foreshadow_health(nid)

        assert health["dangling_count"] == 14
        assert any("悬挂伏笔过多" in i for i in health["issues"])

    @pytest.mark.asyncio
    async def test_check_foreshadow_health_low_resolution_rate(self):
        """Health check warns when resolution rate < 30%."""
        nid = _novel_id()
        # 1 resolved, 3 active = 25% resolution
        foreshadows = [
            {"name": "A", "status": "resolved", "resolved_chapter": 5},
            {"name": "B", "status": "active"},
            {"name": "C", "status": "active"},
            {"name": "D", "status": "active"},
        ]
        bible = _make_story_bible(nid=nid, foreshadowing_list=foreshadows, unresolved_hooks=[])
        ctx_fn, _ = _fake_session(bible)

        with patch("src.api.services.quality.foreshadow_tracker_service.get_db_session", ctx_fn):
            from src.api.services.quality.foreshadow_tracker_service import (
                ForeshadowTrackerService,
            )
            svc = ForeshadowTrackerService()
            health = await svc.check_foreshadow_health(nid)

        assert any("回收率过低" in i for i in health["issues"])

    @pytest.mark.asyncio
    async def test_check_foreshadow_health_good(self):
        """Good health when enough foreshadows and decent resolution rate."""
        nid = _novel_id()
        foreshadows = [
            {"name": f"F{i}", "status": "resolved", "resolved_chapter": i * 2}
            for i in range(1, 8)
        ] + [
            {"name": f"F{i}", "status": "active"}
            for i in range(8, 12)
        ]
        bible = _make_story_bible(nid=nid, foreshadowing_list=foreshadows, unresolved_hooks=[])
        ctx_fn, _ = _fake_session(bible)

        with patch("src.api.services.quality.foreshadow_tracker_service.get_db_session", ctx_fn):
            from src.api.services.quality.foreshadow_tracker_service import (
                ForeshadowTrackerService,
            )
            svc = ForeshadowTrackerService()
            health = await svc.check_foreshadow_health(nid)

        assert health["health_status"] == "good"
        assert health["issues"] == []

    # --- singleton factory ---

    def test_get_foreshadow_tracker_service_singleton(self):
        import src.api.services.quality.foreshadow_tracker_service as mod
        original = mod._foreshadow_tracker_service
        try:
            mod._foreshadow_tracker_service = None
            svc1 = mod.get_foreshadow_tracker_service()
            svc2 = mod.get_foreshadow_tracker_service()
            assert svc1 is svc2
        finally:
            mod._foreshadow_tracker_service = original
