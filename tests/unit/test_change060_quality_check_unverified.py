# tests/unit/test_change060_quality_check_unverified.py
from unittest.mock import AsyncMock, patch

import pytest

from src.core.langgraph.nodes import quality_check


@pytest.mark.asyncio
async def test_eval_failure_marks_unverified_not_fake_score():
    """evaluate_chapter_quality 抛异常时，节点应标记 unverified，overall=None，绝不返回 0.82 兜底。"""
    state = {
        "chapters": [{"chapter": 1, "title": "测试", "content": "正文内容", "word_count": 4}],
        "novel_type": "玄幻",
        "idea": "测试",
        "world_setting": None,
        "characters": [],
        "novel_id": "novel-1",
    }
    config = {"configurable": {}}

    with patch("src.core.langgraph.nodes.quality_check.evaluate_chapter_quality",
               new=AsyncMock(side_effect=Exception("LLM 挂了"))):
        result = await quality_check.node(state, config)

    scores = result["quality_scores"]
    assert scores.get("overall") is None, "评估失败不应给假分，应为 None(unverified)"
    assert scores.get("status") == "unverified"


@pytest.mark.asyncio
async def test_consistency_block_blocks_pass_regardless_of_overall():
    """一致性被判定 block 时，无论 overall 多高，路由都应判定不通过。"""
    from src.core.langgraph.graph import _quality_loop_decision
    state = {
        "quality_scores": {"overall": 0.95, "consistency": 0.3, "consistency_blocked": True},
        "_regeneration_count": 0,
    }
    # overall 0.95 >> 阈值 0.7，但一致性 block → 应走 regenerate
    decision = _quality_loop_decision(state, "human_review")
    assert decision == "regenerate"


@pytest.mark.asyncio
async def test_unverified_blocks_pass_until_max_retries():
    """unverified 状态在未达重试上限时应走 regenerate。"""
    from src.core.langgraph.graph import _quality_loop_decision
    state = {
        "quality_scores": {"overall": None, "status": "unverified"},
        "_regeneration_count": 0,
    }
    decision = _quality_loop_decision(state, "human_review")
    assert decision == "regenerate"


@pytest.mark.asyncio
async def test_bible_severe_conflict_triggers_hard_gate():
    """StoryBible 严重冲突(bible_errors>0)应触发一致性硬门禁(consistency_blocked=True)。"""
    state = {
        "chapters": [{"chapter": 1, "title": "测试", "content": "正文内容较长", "word_count": 8}],
        "novel_type": "玄幻",
        "idea": "测试",
        "world_setting": None,
        "characters": [],
        "novel_id": "novel-1",
    }
    # mock: evaluate_chapter_quality 返回高分(0.9),detect_bible_conflicts 返回 error 级冲突
    fake_result = AsyncMock()
    fake_result.to_scores_dict = lambda: {
        "overall": 0.9, "advancement": 0.9, "conflict": 0.9,
        "character_consistency": 0.9, "world_consistency": 0.9,
        "foreshadowing": 0.9, "pacing": 0.9, "readability": 0.9,
        "trope_alignment": 0.9, "consistency": 1.0,
    }
    fake_result.feedback = {}
    fake_result.suggestions = []

    async def fake_detect_bible(novel_id, chapter_number, chapter_content):
        return [{"severity": "error", "type": "character_inconsistency", "message": "人物行为矛盾"}]

    config = {
        "configurable": {
            "detect_bible_conflicts": fake_detect_bible,
            # 不传 kg_service，跳过 KG 检查
        }
    }

    with patch("src.core.langgraph.nodes.quality_check.evaluate_chapter_quality",
               new=AsyncMock(return_value=fake_result)), \
         patch("src.core.langgraph.nodes.quality_check.get_settings") as mock_s:
        mock_s.return_value.KNOWLEDGE_GRAPH_ENABLED = False  # 跳过 KG
        mock_s.return_value.QUALITY_LOOP_ENABLED = True
        result = await quality_check.node(state, config)

    scores = result["quality_scores"]
    # bible_errors>0 应触发硬门禁
    assert scores.get("consistency_blocked") is True
    assert scores.get("status") == "consistency_blocked"
