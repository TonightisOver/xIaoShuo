"""Unit tests for CHANGE-034: multi-dimensional quality check evaluation."""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.langgraph.nodes.quality_check import node
from src.core.langgraph.state import NovelState


class TestQualityCheckNode:
    """Tests for the multi-dimensional quality check node."""

    @pytest.mark.asyncio
    async def test_quality_check_happy_path(self):
        """Happy path: LLM returns a valid JSON structure.

        It should be successfully parsed.
        """
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

        mock_llm_response = """
        {
          "scores": {
            "advancement": 0.90,
            "conflict": 0.85,
            "character_consistency": 0.95,
            "world_consistency": 0.90,
            "foreshadowing": 0.80,
            "pacing": 0.85,
            "readability": 0.90,
            "trope_alignment": 0.85
          },
          "feedback": {
            "advancement": "主线推进非常流畅，展现了张三作为大师兄的气场。",
            "conflict": "风云涌动给出了很好的危机期待感。",
            "character_consistency": "张三心静如水符合性格设定。",
            "world_consistency": "玄幻山门设定合理。",
            "foreshadowing": "暗示了即将到来的挑战。",
            "pacing": "节奏紧凑，开篇简练。",
            "readability": "文笔干净利落。",
            "trope_alignment": "符合玄幻大师兄套路。"
          },
          "overall_score": 0.88,
          "suggestions": [
            "可以适当增加一些路人配角的惊叹以衬托大师兄。"
          ]
        }
        """

        with patch(
            "src.core.quality.evaluator.get_llm_client"
        ) as mock_get_client, patch(
            "src.core.config.get_settings"
        ) as mock_settings:

            # Disable Knowledge Graph to isolate LLM evaluation testing
            mock_cfg = AsyncMock()
            mock_cfg.KNOWLEDGE_GRAPH_ENABLED = False
            mock_settings.return_value = mock_cfg

            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=mock_llm_response)
            mock_get_client.return_value = mock_client

            updated_state = await node(state)

        # Assert correct output formatting and type mapping
        assert updated_state["current_stage"] == "quality_check_completed"
        scores = updated_state["quality_scores"]
        assert scores["overall"] == 0.88
        assert scores["advancement"] == 0.90
        assert scores["conflict"] == 0.85
        assert scores["character_consistency"] == 0.95
        assert scores["world_consistency"] == 0.90
        assert scores["foreshadowing"] == 0.80
        assert scores["pacing"] == 0.85
        assert scores["readability"] == 0.90
        assert scores["trope_alignment"] == 0.85
        assert scores["consistency"] == 1.0  # KG disabled default

        # Assert suggestions and feedback mapped to revision_requests
        assert len(updated_state["revision_requests"]) > 0
        assert any(
            "主线推进非常流畅" in r for r in updated_state["revision_requests"]
        )
        assert any(
            "修改建议: 可以适当增加一些路人配角" in r
            for r in updated_state["revision_requests"]
        )

    @pytest.mark.asyncio
    async def test_quality_check_graceful_fallback_on_llm_error(self):
        """When LLM API fails or times out, the node gracefully falls back.

        It should use default scores.
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
        assert scores["overall"] == 0.82  # Fallback score
        assert scores["advancement"] == 0.80
        assert scores["conflict"] == 0.80
        assert scores["character_consistency"] == 0.85
        assert scores["consistency"] == 1.0

    @pytest.mark.asyncio
    async def test_quality_check_malformed_json_recovery(self):
        """When LLM returns a malformed JSON string, the parser detects it.

        It should gracefully fall back to default scores.
        """
        state: NovelState = {
            "project_id": "test-project-malformed",
            "novel_type": "都市",
            "idea": "重生之神级程序员",
            "chapters": [{"chapter": 1, "title": "开局", "content": "写代码中。"}],
            "errors": [],
        }

        # Corrupt JSON block missing closing bracket
        corrupt_json = """
        {
          "scores": {
            "advancement": 0.90,
            "conflict": 0.85
        """

        with patch(
            "src.core.quality.evaluator.get_llm_client"
        ) as mock_get_client, patch(
            "src.core.config.get_settings"
        ) as mock_settings:

            mock_cfg = AsyncMock()
            mock_cfg.KNOWLEDGE_GRAPH_ENABLED = False
            mock_settings.return_value = mock_cfg

            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=corrupt_json)
            mock_get_client.return_value = mock_client

            updated_state = await node(state)

        # Should recover safely
        assert updated_state["current_stage"] == "quality_check_completed"
        scores = updated_state["quality_scores"]
        assert scores["overall"] == 0.8  # Default from evaluator fallback
