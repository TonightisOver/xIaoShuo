"""Unit tests for CHANGE-034: multi-dimensional quality check evaluation."""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.langgraph.nodes.quality_check import node
from src.core.langgraph.state import NovelState


class TestQualityCheckNode:
    """Tests for the multi-dimensional quality check node."""

    @pytest.mark.asyncio
    async def test_quality_check_happy_path(self):
        """Happy path：gate 返回 verified + 合法分数，节点透传并产出 state_delta。

        Ticket 04 后节点收敛到 run_quality_gate，L2 评分逻辑由 gate 负责
        （详见 test_change061_quality_gate）。本测试只验节点翻译层契约：
        gate verified → quality_scores 透传 + state_delta 入 state。
        """
        from src.core.quality.gate import GateResult

        state: NovelState = {
            "project_id": "test-project-034",
            "novel_type": "玄幻",
            "idea": "穿越到异界的宗门大师兄故事",
            "world_setting": {"rules": "玄幻修真力量体系"},
            "characters": [{"name": "张三", "role": "主角", "personality": "沉稳"}],
            "chapters": [
                {
                    "chapter": 1,
                    "title": "开篇",
                    "content": "张三站在山门之上，看着天边涌动的风云，心中毫无波澜。",
                }
            ],
            "errors": [],
        }

        fake_gate = GateResult(
            final_content="张三站在山门之上",
            quality_status="verified",
            quality_scores={
                "overall": 0.88, "advancement": 0.90, "conflict": 0.85,
                "character_consistency": 0.95, "world_consistency": 0.90,
                "foreshadowing": 0.80, "pacing": 0.85, "readability": 0.90,
                "trope_alignment": 0.85,
            },
            state_delta={"characters": ["张三"]},
            l2_evaluated=True,
        )

        rewrite_service = object()
        mock_gate = AsyncMock(return_value=fake_gate)
        config = {"configurable": {"rewrite_service": rewrite_service}}

        with patch("src.core.langgraph.nodes.quality_check.get_settings") as mock_s, \
             patch("src.core.quality.gate.run_quality_gate", new=mock_gate):
            mock_s.return_value.KNOWLEDGE_GRAPH_ENABLED = False
            updated_state = await node(state, config)

        assert updated_state["current_stage"] == "quality_check_completed"
        scores = updated_state["quality_scores"]
        assert scores["overall"] == 0.88
        assert scores["character_consistency"] == 0.95
        assert scores["consistency"] == 1.0  # KG disabled default
        assert scores.get("consistency_blocked") is not True
        # state_delta 入 state（短篇首次有 state_delta，Ticket 04 目标）
        assert updated_state["state_delta"] == {"characters": ["张三"]}
        assert mock_gate.await_args.kwargs["rewrite_service"] is rewrite_service

    @pytest.mark.asyncio
    async def test_quality_check_graceful_fallback_on_llm_error(self):
        """When LLM API fails or times out, the node gracefully falls back.

        It should mark the chapter as unverified (overall=None) rather than
        fabricating a passing score (was 0.82, which exceeded the 0.7 threshold).
        """
        state: NovelState = {
            "project_id": "test-project-fallback",
            "novel_type": "都市",
            "idea": "重生之神级程序员",
            "chapters": [{"chapter": 1, "title": "开局", "content": "写代码中。"}],
            "errors": [],
        }

        with patch(
            "src.core.quality.evaluator.get_llm_client",
            side_effect=RuntimeError("API Key Invalid or Timeout"),
        ), patch(
            "src.core.config.get_settings"
        ) as mock_settings:

            mock_cfg = AsyncMock()
            mock_cfg.KNOWLEDGE_GRAPH_ENABLED = False
            mock_settings.return_value = mock_cfg

            # Executing node should not crash the generator, it must degrade gracefully
            updated_state = await node(state)

        assert updated_state["current_stage"] == "quality_check_completed"
        scores = updated_state["quality_scores"]
        assert scores["overall"] is None  # unverified: 评估失败绝不伪造合格分
        assert scores["status"] == "unverified"
        assert scores["consistency"] == 1.0

    @pytest.mark.asyncio
    async def test_quality_check_malformed_json_recovery(self):
        """gate L2 拿到畸形 JSON 降级为 unverified 时，节点应透传 unverified 状态。

        Ticket 04 后 L2 解析容错由 gate 负责（gate.py L2 失败 → unverified）。
        本测试验节点翻译层：gate unverified → quality_scores.status=unverified。
        """
        from src.core.quality.gate import GateResult

        state: NovelState = {
            "project_id": "test-project-malformed",
            "novel_type": "都市",
            "idea": "重生之神级程序员",
            "chapters": [{"chapter": 1, "title": "开局", "content": "写代码中。"}],
            "errors": [],
        }

        fake_gate = GateResult(
            final_content="写代码中。",
            quality_status="unverified",
            quality_scores={"overall": None, "status": "unverified"},
            state_delta={"_unverified": True},
            l2_evaluated=True,
        )

        with patch("src.core.langgraph.nodes.quality_check.get_settings") as mock_s, \
             patch("src.core.quality.gate.run_quality_gate",
                   new=AsyncMock(return_value=fake_gate)):
            mock_s.return_value.KNOWLEDGE_GRAPH_ENABLED = False
            updated_state = await node(state)

        assert updated_state["current_stage"] == "quality_check_completed"
        scores = updated_state["quality_scores"]
        assert scores["overall"] is None
        assert scores["status"] == "unverified"
