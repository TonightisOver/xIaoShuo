"""Unit tests for CHANGE-053 T3: volume outline persistence.

Verifies:
- upsert_volume_outline is called once per volume after generate_volume_outline
- upsert_chapter_outline is called once per chapter in the volume outline
- A persistence failure does NOT interrupt the chapter generation flow
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_request(volumes: int = 2, chapters_per_volume: int = 3):
    req = MagicMock()
    req.auto_calc_chapters = False
    req.target_words = 300_000
    req.words_per_chapter = 3_000
    req.volumes = volumes
    req.chapters_per_volume = chapters_per_volume
    req.idea = "测试小说"
    req.novel_type = "玄幻"
    req.writing_style = ""
    req.writing_style_prompt = ""
    return req


def _make_vol_outline(volume_number: int, chapter_count: int) -> dict:
    return {
        "volume_number": volume_number,
        "title": f"第{volume_number}卷",
        "chapters": [
            {"chapter": i + 1, "title": f"第{i + 1}章", "plot": "情节"}
            for i in range(chapter_count)
        ],
    }


def _standard_mocks(mock_tm, mock_ps):
    mock_tm.return_value.update_status = AsyncMock()
    mock_tm.return_value.complete_task = AsyncMock()
    mock_ps.return_value.initialize_progress = AsyncMock()
    mock_ps.return_value.update_volume_status = AsyncMock()
    mock_ps.return_value.complete_volume = AsyncMock()
    mock_ps.return_value.complete_all = AsyncMock()


# ---------------------------------------------------------------------------
# T3 tests
# ---------------------------------------------------------------------------

class TestVolumeOutlinePersistence:
    """T3 — outline persistence after generate_volume_outline."""

    @pytest.mark.asyncio
    async def test_volume_outline_persisted_after_generation(self):
        """upsert_volume_outline is called exactly once per volume."""
        request = _make_request(volumes=2, chapters_per_volume=3)

        outline_svc = AsyncMock()
        outline_svc.upsert_volume_outline = AsyncMock()
        outline_svc.upsert_chapter_outline = AsyncMock()

        vol_outline_mock = AsyncMock(side_effect=[
            _make_vol_outline(1, 3),
            _make_vol_outline(2, 3),
        ])

        with (
            patch("src.api.services.novel_generator.get_task_manager") as mock_tm,
            patch("src.api.services.novel_generator.get_long_form_progress_service") as mock_ps,
            patch("src.api.services.novel_generator.generate_master_outline", AsyncMock(return_value={"volumes": [], "title": "t"})),
            patch("src.api.services.novel_generator.generate_volume_outline", vol_outline_mock),
            patch("src.api.services.novel_generator.generate_volume_chapters", AsyncMock(return_value=[])),
            patch("src.api.services.novel_generator.generate_volume_quality_report", AsyncMock(return_value={})),
            patch("src.api.services.novel_generator._emit_progress", AsyncMock()),
            patch("src.api.services.outline_service.get_outline_service", return_value=outline_svc),
            patch("src.api.services.novel_manager.get_novel_manager") as mock_nm,
        ):
            _standard_mocks(mock_tm, mock_ps)
            mock_nm.return_value.update_novel = AsyncMock()

            from src.api.services.novel_generator import generate_long_form_background
            await generate_long_form_background("task-p1", "novel-p1", request)

        assert outline_svc.upsert_volume_outline.call_count == 2
        calls = outline_svc.upsert_volume_outline.call_args_list
        assert calls[0].args[1] == 1
        assert calls[1].args[1] == 2

    @pytest.mark.asyncio
    async def test_chapter_outlines_persisted_after_generation(self):
        """upsert_chapter_outline is called once per chapter across all volumes."""
        request = _make_request(volumes=2, chapters_per_volume=3)

        outline_svc = AsyncMock()
        outline_svc.upsert_volume_outline = AsyncMock()
        outline_svc.upsert_chapter_outline = AsyncMock()

        vol_outline_mock = AsyncMock(side_effect=[
            _make_vol_outline(1, 3),
            _make_vol_outline(2, 3),
        ])

        with (
            patch("src.api.services.novel_generator.get_task_manager") as mock_tm,
            patch("src.api.services.novel_generator.get_long_form_progress_service") as mock_ps,
            patch("src.api.services.novel_generator.generate_master_outline", AsyncMock(return_value={"volumes": [], "title": "t"})),
            patch("src.api.services.novel_generator.generate_volume_outline", vol_outline_mock),
            patch("src.api.services.novel_generator.generate_volume_chapters", AsyncMock(return_value=[])),
            patch("src.api.services.novel_generator.generate_volume_quality_report", AsyncMock(return_value={})),
            patch("src.api.services.novel_generator._emit_progress", AsyncMock()),
            patch("src.api.services.outline_service.get_outline_service", return_value=outline_svc),
            patch("src.api.services.novel_manager.get_novel_manager") as mock_nm,
        ):
            _standard_mocks(mock_tm, mock_ps)
            mock_nm.return_value.update_novel = AsyncMock()

            from src.api.services.novel_generator import generate_long_form_background
            await generate_long_form_background("task-p2", "novel-p2", request)

        # 2 volumes × 3 chapters = 6 calls
        assert outline_svc.upsert_chapter_outline.call_count == 6
        chapter_nums = [c.args[2] for c in outline_svc.upsert_chapter_outline.call_args_list]
        assert chapter_nums == [1, 2, 3, 1, 2, 3]

    @pytest.mark.asyncio
    async def test_persist_failure_does_not_interrupt_generation(self):
        """If upsert_volume_outline raises, chapter generation must still complete."""
        request = _make_request(volumes=1, chapters_per_volume=2)

        failing_outline_svc = AsyncMock()
        failing_outline_svc.upsert_volume_outline = AsyncMock(
            side_effect=RuntimeError("DB connection lost")
        )
        failing_outline_svc.upsert_chapter_outline = AsyncMock()

        vol_chapters_mock = AsyncMock(return_value=[{"chapter": 1}, {"chapter": 2}])

        with (
            patch("src.api.services.novel_generator.get_task_manager") as mock_tm,
            patch("src.api.services.novel_generator.get_long_form_progress_service") as mock_ps,
            patch("src.api.services.novel_generator.generate_master_outline", AsyncMock(return_value={"volumes": [], "title": "t"})),
            patch("src.api.services.novel_generator.generate_volume_outline", AsyncMock(return_value=_make_vol_outline(1, 2))),
            patch("src.api.services.novel_generator.generate_volume_chapters", vol_chapters_mock),
            patch("src.api.services.novel_generator.generate_volume_quality_report", AsyncMock(return_value={})),
            patch("src.api.services.novel_generator._emit_progress", AsyncMock()),
            patch("src.api.services.outline_service.get_outline_service", return_value=failing_outline_svc),
            patch("src.api.services.novel_manager.get_novel_manager") as mock_nm,
        ):
            _standard_mocks(mock_tm, mock_ps)
            mock_nm.return_value.update_novel = AsyncMock()

            from src.api.services.novel_generator import generate_long_form_background
            # Must NOT raise despite persistence failure
            await generate_long_form_background("task-p3", "novel-p3", request)

        # Chapter generation still ran
        vol_chapters_mock.assert_called_once()
        # Task completed normally
        mock_tm.return_value.complete_task.assert_called_once()
