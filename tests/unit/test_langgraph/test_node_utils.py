"""generate_and_validate 单元测试 — LLM 调用 + 解析 + Pydantic 校验 + 重试。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.langgraph.node_utils import generate_and_validate
from src.core.langgraph.schemas import CharacterDesignResult


def _valid_response():
    return '{"characters": [{"name": "张三", "role": "主角"}], "relationships": {}}'


def _malformed_response():
    return '{"characters": "not a list", "relationships": {}}'


class TestGenerateAndValidate:
    @pytest.mark.asyncio
    async def test_success_first_attempt(self):
        """LLM 返回合法结构，首次即通过，不重试。"""
        client = MagicMock()
        client.generate = AsyncMock(return_value=_valid_response())

        result = await generate_and_validate(
            client, "prompt", CharacterDesignResult, "test",
        )
        assert result is not None
        assert len(result.characters) == 1
        assert result.characters[0].name == "张三"
        assert client.generate.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_validation_failure_then_success(self):
        """首次返回畸形结构，重试后返回合法结构，应成功。"""
        client = MagicMock()
        client.generate = AsyncMock(side_effect=[_malformed_response(), _valid_response()])

        result = await generate_and_validate(
            client, "prompt", CharacterDesignResult, "test", max_attempts=2,
        )
        assert result is not None
        assert result.characters[0].name == "张三"
        assert client.generate.call_count == 2  # 首次 + 重试

    @pytest.mark.asyncio
    async def test_all_attempts_fail_returns_fallback(self):
        """所有尝试都返回畸形结构，返回 fallback。"""
        client = MagicMock()
        client.generate = AsyncMock(return_value=_malformed_response())
        fallback = CharacterDesignResult()

        result = await generate_and_validate(
            client, "prompt", CharacterDesignResult, "test",
            fallback=fallback, max_attempts=2,
        )
        assert result is fallback
        assert client.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_json_parse_failure_triggers_retry(self):
        """LLM 返回非 JSON，重试后返回合法 JSON。"""
        client = MagicMock()
        client.generate = AsyncMock(side_effect=["not json at all", _valid_response()])

        result = await generate_and_validate(
            client, "prompt", CharacterDesignResult, "test", max_attempts=2,
        )
        assert result is not None
        assert client.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_llm_call_error_triggers_retry(self):
        """LLM 调用抛异常，重试后成功。"""
        client = MagicMock()
        client.generate = AsyncMock(
            side_effect=[ConnectionError("timeout"), _valid_response()]
        )

        result = await generate_and_validate(
            client, "prompt", CharacterDesignResult, "test", max_attempts=2,
        )
        assert result is not None
        assert client.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_llm_error_all_attempts_returns_fallback(self):
        """LLM 持续报错，返回 fallback。"""
        client = MagicMock()
        client.generate = AsyncMock(side_effect=ConnectionError("down"))
        fallback = CharacterDesignResult()

        result = await generate_and_validate(
            client, "prompt", CharacterDesignResult, "test",
            fallback=fallback, max_attempts=2,
        )
        assert result is fallback
        assert client.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_max_attempts_one_no_retry(self):
        """max_attempts=1 时不重试，失败即返回 fallback。"""
        client = MagicMock()
        client.generate = AsyncMock(return_value=_malformed_response())

        result = await generate_and_validate(
            client, "prompt", CharacterDesignResult, "test",
            max_attempts=1,
        )
        assert result is None
        assert client.generate.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_kwargs_passed_through(self):
        """generate_kwargs 透传给 client.generate。"""
        client = MagicMock()
        client.generate = AsyncMock(return_value=_valid_response())

        await generate_and_validate(
            client, "prompt", CharacterDesignResult, "test",
            max_tokens=4000, temperature=0.3,
        )
        client.generate.assert_called_once_with("prompt", max_tokens=4000, temperature=0.3)
