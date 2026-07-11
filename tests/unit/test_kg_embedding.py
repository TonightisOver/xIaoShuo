"""RAG embedding 注入单元测试 — 实体 embedding 生成 helper。

验证：
- _build_entity_embedding_text: 构造用于 embedding 的文本
- _generate_entity_embedding: 成功返回向量、失败降级 None、功能关闭返回 None
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.knowledge_graph_service import (
    _build_entity_embedding_text,
    _generate_entity_embedding,
)


class TestBuildEntityEmbeddingText:
    def test_basic_character(self):
        text = _build_entity_embedding_text("张三", "character", ["小张"], {"status": "alive"})
        assert "[character] 张三" in text
        assert "小张" in text
        assert "status:alive" in text

    def test_no_aliases_no_attributes(self):
        text = _build_entity_embedding_text("长安城", "location", None, None)
        assert "[location] 长安城" in text
        assert "别名" not in text
        assert "属性" not in text

    def test_empty_aliases_skipped(self):
        text = _build_entity_embedding_text("x", "item", [], {})
        assert "别名" not in text
        assert "属性" not in text

    def test_truncates_long_attributes(self):
        long_val = "x" * 200
        text = _build_entity_embedding_text("e", "event", None, {"desc": long_val})
        assert len(text) <= 500

    def test_skips_none_attribute_values(self):
        text = _build_entity_embedding_text("e", "event", None, {"a": None, "b": "val"})
        assert "a:" not in text
        assert "b:val" in text


class TestGenerateEntityEmbedding:
    @pytest.mark.asyncio
    async def test_returns_embedding_on_success(self):
        with patch("src.api.services.knowledge_graph_service.get_settings") as ms, \
             patch("src.api.services.knowledge_graph_service._embed_texts", AsyncMock(return_value=[[0.1, 0.2, 0.3]])):
            ms.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)
            result = await _generate_entity_embedding("张三", "character", ["小张"], {"status": "alive"})
        assert result == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_returns_none_when_feature_disabled(self):
        with patch("src.api.services.knowledge_graph_service.get_settings") as ms:
            ms.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=False)
            result = await _generate_entity_embedding("张三", "character", None, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_embed_failure(self):
        """embed_texts 抛异常时返回 None，不传播（实体创建不阻断）。"""
        with patch("src.api.services.knowledge_graph_service.get_settings") as ms, \
             patch("src.api.services.knowledge_graph_service._embed_texts", AsyncMock(side_effect=RuntimeError("API down"))):
            ms.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)
            result = await _generate_entity_embedding("张三", "character", None, None)
        assert result is None
