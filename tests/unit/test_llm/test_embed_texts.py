"""embed_texts 单元测试 — 验证失败时显式抛异常而非静默返回零向量。

背景：embed_texts 曾在 API 失败时返回 [[0.0]*dim] 全零向量，导致知识图谱
语义检索静默失效且可能污染落库数据。现改为抛 RuntimeError，调用方需捕获
并降级（KG service 的 retrieve_context 已有 try/except 兜底）。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.llm.client import embed_texts


class TestEmbedTexts:
    @pytest.mark.asyncio
    async def test_success_returns_embeddings(self):
        """正常响应返回 embedding 列表。"""
        fake_resp = MagicMock()
        fake_resp.raise_for_status = MagicMock()
        fake_resp.json = MagicMock(return_value={
            "data": [
                {"embedding": [0.1, 0.2, 0.3]},
                {"embedding": [0.4, 0.5, 0.6]},
            ]
        })
        fake_client = MagicMock()
        fake_client.post = AsyncMock(return_value=fake_resp)

        with patch("src.core.llm.client.get_embedding_client", return_value=fake_client):
            result = await embed_texts(["文本1", "文本2"])

        assert result == [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]]

    @pytest.mark.asyncio
    async def test_api_http_error_raises_runtime_error(self):
        """API 返回非 2xx 时抛 RuntimeError，不返回零向量。"""
        fake_resp = MagicMock()
        fake_resp.raise_for_status = MagicMock(
            side_effect=httpx.HTTPStatusError(
                "Internal Server Error",
                request=MagicMock(),
                response=MagicMock(status_code=500),
            )
        )
        fake_client = MagicMock()
        fake_client.post = AsyncMock(return_value=fake_resp)

        with patch("src.core.llm.client.get_embedding_client", return_value=fake_client):
            with pytest.raises(RuntimeError, match="embedding API 调用失败"):
                await embed_texts(["文本"])

    @pytest.mark.asyncio
    async def test_network_error_raises_runtime_error(self):
        """网络异常（超时/连接失败）时抛 RuntimeError，不返回零向量。"""
        fake_client = MagicMock()
        fake_client.post = AsyncMock(side_effect=httpx.ConnectError("connection refused"))

        with patch("src.core.llm.client.get_embedding_client", return_value=fake_client):
            with pytest.raises(RuntimeError, match="embedding API 调用失败"):
                await embed_texts(["文本"])

    @pytest.mark.asyncio
    async def test_missing_embedding_field_raises(self):
        """响应体缺失 embedding 字段时抛 RuntimeError（KeyError 包装）。"""
        fake_resp = MagicMock()
        fake_resp.raise_for_status = MagicMock()
        fake_resp.json = MagicMock(return_value={"data": [{"no_embedding": []}]})
        fake_client = MagicMock()
        fake_client.post = AsyncMock(return_value=fake_resp)

        with patch("src.core.llm.client.get_embedding_client", return_value=fake_client):
            with pytest.raises(RuntimeError, match="embedding API 调用失败"):
                await embed_texts(["文本"])

    @pytest.mark.asyncio
    async def test_count_mismatch_raises(self):
        """返回 embedding 数量与输入不匹配时抛 RuntimeError。"""
        fake_resp = MagicMock()
        fake_resp.raise_for_status = MagicMock()
        fake_resp.json = MagicMock(return_value={
            "data": [{"embedding": [0.1, 0.2]}]  # 只返回 1 个，但输入 2 个
        })
        fake_client = MagicMock()
        fake_client.post = AsyncMock(return_value=fake_resp)

        with patch("src.core.llm.client.get_embedding_client", return_value=fake_client):
            with pytest.raises(RuntimeError, match="数量与输入不匹配"):
                await embed_texts(["文本1", "文本2"])

    @pytest.mark.asyncio
    async def test_never_returns_zero_vectors(self):
        """任何失败路径都不应返回零向量（核心防污染断言）。"""
        fake_client = MagicMock()
        fake_client.post = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

        with patch("src.core.llm.client.get_embedding_client", return_value=fake_client):
            try:
                result = await embed_texts(["文本"])
            except RuntimeError:
                return  # 正确：抛异常
            # 若走到这里说明返回了值——必须是错误
            assert False, f"embed_texts 不应在失败时返回值，但返回了: {result}"
