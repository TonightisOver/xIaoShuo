"""Unit tests for CHANGE-053 T1/T2: auto_calc_chapters ordering fix.

Verifies:
- T1: chapters_per_vol is computed BEFORE initialize_progress and update_novel
- T2: generate_master_outline receives the auto-calculated chapters_per_vol
- Fallback: auto_calc_chapters=False uses request.chapters_per_volume unchanged
"""

from __future__ import annotations

import math
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(
    *,
    auto_calc_chapters: bool = True,
    target_words: int = 1_500_000,
    words_per_chapter: int = 3_000,
    volumes: int = 10,
    chapters_per_volume: int = 10,
    idea: str = "测试小说",
    novel_type: str = "玄幻",
    writing_style: str = "",
    writing_style_prompt: str = "",
):
    req = MagicMock()
    req.auto_calc_chapters = auto_calc_chapters
    req.target_words = target_words
    req.words_per_chapter = words_per_chapter
    req.volumes = volumes
    req.chapters_per_volume = chapters_per_volume
    req.idea = idea
    req.novel_type = novel_type
    req.writing_style = writing_style
    req.writing_style_prompt = writing_style_prompt
    return req


def _expected_auto_calc(target_words, words_per_chapter, volumes):
    total = math.ceil(target_words / words_per_chapter)
    computed = math.ceil(total / volumes)
    return max(20, min(60, computed))


def _standard_mocks(mock_tm, mock_ps, mock_os):
    """Wire up the standard service mocks."""
    mock_tm.return_value.update_status = AsyncMock()
    mock_tm.return_value.complete_task = AsyncMock()
    mock_ps.return_value.initialize_progress = AsyncMock()
    mock_ps.return_value.update_volume_status = AsyncMock()
    mock_ps.return_value.complete_volume = AsyncMock()
    mock_ps.return_value.complete_all = AsyncMock()

    outline_svc = AsyncMock()
    outline_svc.upsert_volume_outline = AsyncMock()
    outline_svc.upsert_chapter_outline = AsyncMock()
    mock_os.return_value = outline_svc


# ---------------------------------------------------------------------------
# T1: chapters_per_vol computed before initialize_progress
# ---------------------------------------------------------------------------

class TestAutoCalcChaptersOrdering:
    """T1 — auto_calc_chapters block runs before initialize_progress."""

    @pytest.mark.asyncio
    async def test_auto_calc_chapters_before_initialize_progress(self):
        """initialize_progress must receive the auto-calculated value, not request.chapters_per_volume."""
        request = _make_request(
            auto_calc_chapters=True,
            target_words=1_500_000,
            words_per_chapter=3_000,
            volumes=10,
            chapters_per_volume=10,
        )
        expected_cpv = _expected_auto_calc(1_500_000, 3_000, 10)  # 50

        init_progress_mock = AsyncMock()

        with (
            patch("src.api.services.novel_generator.get_task_manager") as mock_tm,
            patch("src.api.services.novel_generator.get_long_form_progress_service") as mock_ps,
            patch("src.api.services.novel_generator.generate_master_outline", AsyncMock(return_value={"volumes": [], "title": "t"})),
            patch("src.api.services.novel_generator.generate_volume_outline", AsyncMock(return_value={"chapters": [], "volume_number": 1})),
            patch("src.api.services.novel_generator.generate_volume_chapters", AsyncMock(return_value=[])),
            patch("src.api.services.novel_generator.generate_volume_quality_report", AsyncMock(return_value={})),
            patch("src.api.services.novel_generator._emit_progress", AsyncMock()),
            patch("src.api.services.outline_service.get_outline_service") as mock_os,
            patch("src.api.services.novel_manager.get_novel_manager") as mock_nm,
        ):
            _standard_mocks(mock_tm, mock_ps, mock_os)
            mock_ps.return_value.initialize_progress = init_progress_mock
            mock_nm.return_value.update_novel = AsyncMock()

            from src.api.services.novel_generator import generate_long_form_background
            await generate_long_form_background("task-t1a", "novel-t1a", request)

        init_progress_mock.assert_called_once()
        _, kwargs = init_progress_mock.call_args
        assert kwargs["chapters_per_volume"] == expected_cpv, (
            f"initialize_progress got chapters_per_volume={kwargs['chapters_per_volume']}, "
            f"expected {expected_cpv}"
        )

    @pytest.mark.asyncio
    async def test_update_novel_uses_auto_calc_value(self):
        """update_novel must also receive the auto-calculated chapters_per_vol."""
        request = _make_request(
            auto_calc_chapters=True,
            target_words=1_500_000,
            words_per_chapter=3_000,
            volumes=10,
            chapters_per_volume=10,
        )
        expected_cpv = _expected_auto_calc(1_500_000, 3_000, 10)  # 50

        update_novel_mock = AsyncMock()

        with (
            patch("src.api.services.novel_generator.get_task_manager") as mock_tm,
            patch("src.api.services.novel_generator.get_long_form_progress_service") as mock_ps,
            patch("src.api.services.novel_generator.generate_master_outline", AsyncMock(return_value={"volumes": [], "title": "t"})),
            patch("src.api.services.novel_generator.generate_volume_outline", AsyncMock(return_value={"chapters": [], "volume_number": 1})),
            patch("src.api.services.novel_generator.generate_volume_chapters", AsyncMock(return_value=[])),
            patch("src.api.services.novel_generator.generate_volume_quality_report", AsyncMock(return_value={})),
            patch("src.api.services.novel_generator._emit_progress", AsyncMock()),
            patch("src.api.services.outline_service.get_outline_service") as mock_os,
            patch("src.api.services.novel_manager.get_novel_manager") as mock_nm,
        ):
            _standard_mocks(mock_tm, mock_ps, mock_os)
            mock_nm.return_value.update_novel = update_novel_mock

            from src.api.services.novel_generator import generate_long_form_background
            await generate_long_form_background("task-t1b", "novel-t1b", request)

        update_novel_mock.assert_called_once()
        _, kwargs = update_novel_mock.call_args
        assert kwargs["chapters_per_volume"] == expected_cpv

    @pytest.mark.asyncio
    async def test_auto_calc_false_uses_request_value(self):
        """When auto_calc_chapters=False, chapters_per_vol must equal request.chapters_per_volume."""
        request = _make_request(
            auto_calc_chapters=False,
            chapters_per_volume=30,
        )

        init_progress_mock = AsyncMock()

        with (
            patch("src.api.services.novel_generator.get_task_manager") as mock_tm,
            patch("src.api.services.novel_generator.get_long_form_progress_service") as mock_ps,
            patch("src.api.services.novel_generator.generate_master_outline", AsyncMock(return_value={"volumes": [], "title": "t"})),
            patch("src.api.services.novel_generator.generate_volume_outline", AsyncMock(return_value={"chapters": [], "volume_number": 1})),
            patch("src.api.services.novel_generator.generate_volume_chapters", AsyncMock(return_value=[])),
            patch("src.api.services.novel_generator.generate_volume_quality_report", AsyncMock(return_value={})),
            patch("src.api.services.novel_generator._emit_progress", AsyncMock()),
            patch("src.api.services.outline_service.get_outline_service") as mock_os,
            patch("src.api.services.novel_manager.get_novel_manager") as mock_nm,
        ):
            _standard_mocks(mock_tm, mock_ps, mock_os)
            mock_ps.return_value.initialize_progress = init_progress_mock
            mock_nm.return_value.update_novel = AsyncMock()

            from src.api.services.novel_generator import generate_long_form_background
            await generate_long_form_background("task-t1c", "novel-t1c", request)

        init_progress_mock.assert_called_once()
        _, kwargs = init_progress_mock.call_args
        assert kwargs["chapters_per_volume"] == 30


# ---------------------------------------------------------------------------
# T2: generate_master_outline receives correct chapters_per_vol
# ---------------------------------------------------------------------------

class TestMasterOutlineChaptersPerVol:
    """T2 — generate_master_outline is called with the auto-calculated chapters_per_vol."""

    @pytest.mark.asyncio
    async def test_auto_calc_chapters_master_outline_uses_correct_value(self):
        """generate_master_outline must receive chapters_per_vol=50, not request.chapters_per_volume=10."""
        request = _make_request(
            auto_calc_chapters=True,
            target_words=1_500_000,
            words_per_chapter=3_000,
            volumes=10,
            chapters_per_volume=10,
        )
        expected_cpv = _expected_auto_calc(1_500_000, 3_000, 10)  # 50

        master_outline_mock = AsyncMock(return_value={"volumes": [], "title": "t"})

        with (
            patch("src.api.services.novel_generator.get_task_manager") as mock_tm,
            patch("src.api.services.novel_generator.get_long_form_progress_service") as mock_ps,
            patch("src.api.services.novel_generator.generate_master_outline", master_outline_mock),
            patch("src.api.services.novel_generator.generate_volume_outline", AsyncMock(return_value={"chapters": [], "volume_number": 1})),
            patch("src.api.services.novel_generator.generate_volume_chapters", AsyncMock(return_value=[])),
            patch("src.api.services.novel_generator.generate_volume_quality_report", AsyncMock(return_value={})),
            patch("src.api.services.novel_generator._emit_progress", AsyncMock()),
            patch("src.api.services.outline_service.get_outline_service") as mock_os,
            patch("src.api.services.novel_manager.get_novel_manager") as mock_nm,
        ):
            _standard_mocks(mock_tm, mock_ps, mock_os)
            mock_nm.return_value.update_novel = AsyncMock()

            from src.api.services.novel_generator import generate_long_form_background
            await generate_long_form_background("task-t2a", "novel-t2a", request)

        master_outline_mock.assert_called_once()
        _, kwargs = master_outline_mock.call_args
        assert kwargs["chapters_per_vol"] == expected_cpv, (
            f"generate_master_outline got chapters_per_vol={kwargs.get('chapters_per_vol')}, "
            f"expected {expected_cpv}"
        )

    @pytest.mark.asyncio
    async def test_auto_calc_false_master_outline_uses_request_value(self):
        """When auto_calc_chapters=False, generate_master_outline gets request.chapters_per_volume."""
        request = _make_request(
            auto_calc_chapters=False,
            chapters_per_volume=25,
        )

        master_outline_mock = AsyncMock(return_value={"volumes": [], "title": "t"})

        with (
            patch("src.api.services.novel_generator.get_task_manager") as mock_tm,
            patch("src.api.services.novel_generator.get_long_form_progress_service") as mock_ps,
            patch("src.api.services.novel_generator.generate_master_outline", master_outline_mock),
            patch("src.api.services.novel_generator.generate_volume_outline", AsyncMock(return_value={"chapters": [], "volume_number": 1})),
            patch("src.api.services.novel_generator.generate_volume_chapters", AsyncMock(return_value=[])),
            patch("src.api.services.novel_generator.generate_volume_quality_report", AsyncMock(return_value={})),
            patch("src.api.services.novel_generator._emit_progress", AsyncMock()),
            patch("src.api.services.outline_service.get_outline_service") as mock_os,
            patch("src.api.services.novel_manager.get_novel_manager") as mock_nm,
        ):
            _standard_mocks(mock_tm, mock_ps, mock_os)
            mock_nm.return_value.update_novel = AsyncMock()

            from src.api.services.novel_generator import generate_long_form_background
            await generate_long_form_background("task-t2b", "novel-t2b", request)

        _, kwargs = master_outline_mock.call_args
        assert kwargs["chapters_per_vol"] == 25
