# tests/unit/test_change061_quality_gate.py
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import LeaseLost
from src.core.quality.gate import run_quality_gate
from src.core.quality.risk import RiskLevel


def _make_chapter_result(content="正文内容", word_count=4, chapter_type=None,
                         generation_failed=False, paused=False):
    return {
        "chapter": 1, "title": "测试章", "content": content,
        "word_count": word_count, "chapter_type": chapter_type,
        "generation_failed": generation_failed, "paused": paused,
    }


def _make_callbacks():
    cb = MagicMock()
    cb.update_state_delta = AsyncMock()
    cb.update_quality_status = AsyncMock()
    cb.persist_quality_scores = AsyncMock()
    cb.detect_bible_conflicts = None
    return cb


@pytest.mark.asyncio
async def test_failed_chapter_skips_funnel():
    cb = _make_callbacks()
    with patch("src.core.quality.gate.extract_state_delta", new=AsyncMock()) as mock_extract, \
         patch("src.core.quality.gate.run_l0_rules") as mock_l0, \
         patch("src.core.quality.gate.evaluate_chapter_quality", new=AsyncMock()) as mock_l2:
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(generation_failed=True),
            chapter_outline=None, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, chapter_index_in_volume=0,
        )
    assert result.quality_status == "failed"
    assert result.l2_evaluated is False
    mock_extract.assert_not_called()
    mock_l0.assert_not_called()
    mock_l2.assert_not_called()


@pytest.mark.asyncio
async def test_lease_lost_from_persist_callback_is_not_swallowed():
    cb = _make_callbacks()
    cb.update_quality_status.side_effect = LeaseLost("task-stale")

    with pytest.raises(LeaseLost):
        await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(generation_failed=True),
            chapter_outline=None, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, chapter_index_in_volume=0,
        )


@pytest.mark.asyncio
async def test_paused_chapter_skips_funnel():
    cb = _make_callbacks()
    with patch("src.core.quality.gate.extract_state_delta", new=AsyncMock()) as mock_extract:
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(paused=True),
            chapter_outline=None, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, chapter_index_in_volume=0,
        )
    assert result.quality_status == "failed"
    mock_extract.assert_not_called()


@pytest.mark.asyncio
async def test_low_risk_skips_l2():
    cb = _make_callbacks()
    fake_delta = {"key_events": ["事件A"], "next_chapter_must_carry": []}
    with patch("src.core.quality.gate.extract_state_delta",
               new=AsyncMock(return_value=fake_delta)), \
         patch("src.core.quality.gate.run_l0_rules",
               return_value={"violations": [], "filler_flag": False,
                             "stalled_flag": False, "filler_score": 0,
                             "outline_coverage": 0.9}), \
         patch("src.core.quality.gate.classify_risk", return_value=RiskLevel.LOW), \
         patch("src.core.quality.gate.should_invoke_l2", return_value=False), \
         patch("src.core.quality.gate.evaluate_chapter_quality", new=AsyncMock()) as mock_l2:
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(word_count=3000),
            chapter_outline={"plot": "测试"}, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, chapter_index_in_volume=0,
        )
    assert result.quality_status == "verified"
    assert result.l2_evaluated is False
    assert result.quality_scores.get("overall") is None
    mock_l2.assert_not_called()
    cb.update_state_delta.assert_awaited_once()


@pytest.mark.asyncio
async def test_high_risk_invokes_l2_and_passes():
    cb = _make_callbacks()
    fake_result = MagicMock()
    fake_result.scores = {"advancement": 0.9}
    fake_result.overall = 0.9
    fake_result.feedback = {}
    fake_result.suggestions = []
    fake_result.to_scores_dict = lambda: {
        "advancement": 0.9, "character_consistency": 0.9,
        "world_consistency": 0.9, "overall": 0.9,
    }
    with patch("src.core.quality.gate.extract_state_delta",
               new=AsyncMock(return_value={"key_events": []})), \
         patch("src.core.quality.gate.run_l0_rules",
               return_value={"violations": [], "filler_flag": False,
                             "stalled_flag": False, "filler_score": 0,
                             "outline_coverage": 0.9}), \
         patch("src.core.quality.gate.classify_risk", return_value=RiskLevel.HIGH), \
         patch("src.core.quality.gate.should_invoke_l2", return_value=True), \
         patch("src.core.quality.gate.evaluate_chapter_quality",
               new=AsyncMock(return_value=fake_result)) as mock_l2:
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(word_count=3000),
            chapter_outline={"plot": "测试"}, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, chapter_index_in_volume=0,
        )
    assert result.quality_status == "verified"
    assert result.l2_evaluated is True
    assert result.quality_scores.get("overall") == 0.9
    mock_l2.assert_awaited_once()


@pytest.mark.asyncio
async def test_l2_failure_marks_unverified():
    cb = _make_callbacks()
    with patch("src.core.quality.gate.extract_state_delta",
               new=AsyncMock(return_value={"key_events": []})), \
         patch("src.core.quality.gate.run_l0_rules",
               return_value={"violations": [], "filler_flag": False,
                             "stalled_flag": False, "filler_score": 0,
                             "outline_coverage": 0.9}), \
         patch("src.core.quality.gate.classify_risk", return_value=RiskLevel.HIGH), \
         patch("src.core.quality.gate.should_invoke_l2", return_value=True), \
         patch("src.core.quality.gate.evaluate_chapter_quality",
               new=AsyncMock(side_effect=Exception("LLM 挂了"))):
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(content="原正文", word_count=3000),
            chapter_outline={"plot": "测试"}, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, chapter_index_in_volume=0,
        )
    assert result.quality_status == "unverified"
    assert result.final_content == "原正文"


@pytest.mark.asyncio
async def test_consistency_block_marks_blocked():
    cb = _make_callbacks()
    fake_result = MagicMock()
    fake_result.scores = {"character_consistency": 0.3, "world_consistency": 0.9}
    fake_result.overall = 0.9
    fake_result.feedback = {}
    fake_result.suggestions = []
    fake_result.to_scores_dict = lambda: {
        "character_consistency": 0.3, "world_consistency": 0.9, "overall": 0.9,
    }
    mock_rewrite = AsyncMock()
    with patch("src.core.quality.gate.extract_state_delta",
               new=AsyncMock(return_value={"key_events": []})), \
         patch("src.core.quality.gate.run_l0_rules",
               return_value={"violations": [], "filler_flag": False,
                             "stalled_flag": False, "filler_score": 0,
                             "outline_coverage": 0.9}), \
         patch("src.core.quality.gate.classify_risk", return_value=RiskLevel.HIGH), \
         patch("src.core.quality.gate.should_invoke_l2", return_value=True), \
         patch("src.core.quality.gate.evaluate_chapter_quality",
               new=AsyncMock(return_value=fake_result)):
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(word_count=3000),
            chapter_outline={"plot": "测试"}, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, rewrite_service=mock_rewrite,
            chapter_index_in_volume=0,
        )
    assert result.quality_status == "consistency_blocked"
    assert result.rewrite_attempted is False
    mock_rewrite.auto_improve_chapter.assert_not_called()


@pytest.mark.asyncio
async def test_l2_below_threshold_triggers_l3_improvement():
    cb = _make_callbacks()
    fake_result = MagicMock()
    fake_result.scores = {"character_consistency": 0.9, "world_consistency": 0.9}
    fake_result.overall = 0.5
    fake_result.feedback = {}
    fake_result.suggestions = []
    fake_result.to_scores_dict = lambda: {
        "character_consistency": 0.9, "world_consistency": 0.9, "overall": 0.5,
    }
    mock_rewrite = AsyncMock()
    mock_rewrite.auto_improve_chapter = AsyncMock(return_value={
        "iterations_done": 1, "reached_target": True,
        "final_scores": {"overall": 0.9, "character_consistency": 0.9, "world_consistency": 0.9},
        "improvement_history": [{"activated": True, "candidate_version": 2}],
    })
    with patch("src.core.quality.gate.extract_state_delta",
               new=AsyncMock(return_value={"key_events": []})), \
         patch("src.core.quality.gate.run_l0_rules",
               return_value={"violations": [], "filler_flag": False,
                             "stalled_flag": False, "filler_score": 0,
                             "outline_coverage": 0.9}), \
         patch("src.core.quality.gate.classify_risk", return_value=RiskLevel.HIGH), \
         patch("src.core.quality.gate.should_invoke_l2", return_value=True), \
         patch("src.core.quality.gate.evaluate_chapter_quality",
               new=AsyncMock(return_value=fake_result)):
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(content="原正文", word_count=3000),
            chapter_outline={"plot": "测试"}, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, rewrite_service=mock_rewrite,
            chapter_index_in_volume=0,
        )
    assert result.rewrite_attempted is True
    assert result.rewrite_improved is True
    assert result.quality_status == "verified"


@pytest.mark.asyncio
async def test_l3_no_improvement_keeps_baseline():
    cb = _make_callbacks()
    fake_result = MagicMock()
    fake_result.scores = {"character_consistency": 0.9, "world_consistency": 0.9}
    fake_result.overall = 0.5
    fake_result.feedback = {}
    fake_result.suggestions = []
    fake_result.to_scores_dict = lambda: {"overall": 0.5}
    mock_rewrite = AsyncMock()
    mock_rewrite.auto_improve_chapter = AsyncMock(return_value={
        "iterations_done": 1, "reached_target": False,
        "final_scores": {"overall": 0.5},
        "improvement_history": [{"activated": False}],
    })
    with patch("src.core.quality.gate.extract_state_delta",
               new=AsyncMock(return_value={"key_events": []})), \
         patch("src.core.quality.gate.run_l0_rules",
               return_value={"violations": [], "filler_flag": False,
                             "stalled_flag": False, "filler_score": 0,
                             "outline_coverage": 0.9}), \
         patch("src.core.quality.gate.classify_risk", return_value=RiskLevel.HIGH), \
         patch("src.core.quality.gate.should_invoke_l2", return_value=True), \
         patch("src.core.quality.gate.evaluate_chapter_quality",
               new=AsyncMock(return_value=fake_result)):
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(content="原正文", word_count=3000),
            chapter_outline={"plot": "测试"}, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, rewrite_service=mock_rewrite,
            chapter_index_in_volume=0,
        )
    assert result.rewrite_attempted is True
    assert result.rewrite_improved is False
    assert result.final_content == "原正文"
    assert result.quality_status == "unverified"
