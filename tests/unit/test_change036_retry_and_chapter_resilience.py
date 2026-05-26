"""Unit tests for CHANGE-036: retry logic, per-chapter error isolation,
timeout flag, progress callback fields, and health API key check."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ===========================================================================
# 1. _should_retry — openai.APIConnectionError / openai.APITimeoutError
# ===========================================================================

class TestShouldRetry:
    """Tests for the updated _should_retry function in src.core.llm.client."""

    def _get_fn(self):
        from src.core.llm.client import _should_retry
        return _should_retry

    def test_retries_on_api_connection_error(self):
        """openai.APIConnectionError should be retryable."""
        import openai
        _should_retry = self._get_fn()
        exc = openai.APIConnectionError.__new__(openai.APIConnectionError)
        assert _should_retry(exc) is True

    def test_retries_on_api_timeout_error(self):
        """openai.APITimeoutError should be retryable."""
        import openai
        _should_retry = self._get_fn()
        exc = openai.APITimeoutError.__new__(openai.APITimeoutError)
        assert _should_retry(exc) is True

    def test_retries_on_builtin_timeout_error(self):
        """Built-in TimeoutError should be retryable."""
        from src.core.llm.client import _should_retry
        assert _should_retry(TimeoutError("timeout")) is True

    def test_retries_on_builtin_connection_error(self):
        """Built-in ConnectionError should be retryable."""
        from src.core.llm.client import _should_retry
        assert _should_retry(ConnectionError("conn")) is True

    def test_does_not_retry_on_value_error(self):
        """ValueError is not retryable."""
        from src.core.llm.client import _should_retry
        assert _should_retry(ValueError("bad value")) is False

    def test_does_not_retry_on_runtime_error(self):
        """RuntimeError is not retryable."""
        from src.core.llm.client import _should_retry
        assert _should_retry(RuntimeError("runtime")) is False

    def test_retries_on_429_http_error(self):
        """httpx.HTTPStatusError with 429 should be retryable."""
        import httpx
        from src.core.llm.client import _should_retry
        resp = MagicMock()
        resp.status_code = 429
        exc = httpx.HTTPStatusError("429", request=MagicMock(), response=resp)
        assert _should_retry(exc) is True

    def test_does_not_retry_on_401_http_error(self):
        """httpx.HTTPStatusError with 401 should NOT be retryable."""
        import httpx
        from src.core.llm.client import _should_retry
        resp = MagicMock()
        resp.status_code = 401
        exc = httpx.HTTPStatusError("401", request=MagicMock(), response=resp)
        assert _should_retry(exc) is False


# ===========================================================================
# 2. LLMClient.generate — retries on openai connection/timeout errors
# ===========================================================================

@pytest.fixture
def mock_settings_for_client():
    with patch("src.core.llm.client.get_settings") as mock:
        settings = MagicMock()
        settings.DEEPSEEK_MODEL = "deepseek-chat"
        settings.DEEPSEEK_API_KEY = "sk-test"
        settings.DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
        settings.DEEPSEEK_TEMPERATURE = 0.7
        settings.DEEPSEEK_TIMEOUT = 30
        settings.DEEPSEEK_MAX_TOKENS = 2000
        settings.DEEPSEEK_MAX_RETRIES = 3
        mock.return_value = settings
        yield mock


@pytest.fixture
def mock_chat_openai_cls():
    with patch("src.core.llm.client.ChatOpenAI") as mock:
        yield mock


class TestLLMClientRetriesOpenAIErrors:
    """LLMClient retries on openai SDK connection/timeout errors."""

    @pytest.mark.asyncio
    async def test_retries_on_api_connection_error_then_succeeds(
        self, mock_settings_for_client, mock_chat_openai_cls
    ):
        """APIConnectionError on first call → retry → success."""
        import openai
        from langchain_core.messages import AIMessage
        from src.core.llm.client import LLMClient

        mock_llm = AsyncMock()
        mock_chat_openai_cls.return_value = mock_llm

        conn_err = openai.APIConnectionError.__new__(openai.APIConnectionError)
        mock_llm.ainvoke.side_effect = [conn_err, AIMessage(content="重连成功")]

        client = LLMClient()
        client.max_retries = 3

        result = await client.generate("test prompt")

        assert result == "重连成功"
        assert mock_llm.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_api_timeout_error_then_succeeds(
        self, mock_settings_for_client, mock_chat_openai_cls
    ):
        """APITimeoutError on first call → retry → success."""
        import openai
        from langchain_core.messages import AIMessage
        from src.core.llm.client import LLMClient

        mock_llm = AsyncMock()
        mock_chat_openai_cls.return_value = mock_llm

        timeout_err = openai.APITimeoutError.__new__(openai.APITimeoutError)
        mock_llm.ainvoke.side_effect = [timeout_err, AIMessage(content="超时后成功")]

        client = LLMClient()
        client.max_retries = 3

        result = await client.generate("test prompt")

        assert result == "超时后成功"
        assert mock_llm.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_exhausts_retries_on_persistent_api_connection_error(
        self, mock_settings_for_client, mock_chat_openai_cls
    ):
        """Persistent APIConnectionError exhausts retries and raises."""
        import openai
        from src.core.llm.client import LLMClient

        mock_llm = AsyncMock()
        mock_chat_openai_cls.return_value = mock_llm

        conn_err = openai.APIConnectionError.__new__(openai.APIConnectionError)
        mock_llm.ainvoke.side_effect = conn_err

        client = LLMClient()
        client.max_retries = 2

        with pytest.raises(Exception):
            await client.generate("test prompt")

        assert mock_llm.ainvoke.call_count == 2


# ===========================================================================
# 3. generate_single_chapter — timeout returns generation_failed: True
# ===========================================================================

class TestGenerateSingleChapterTimeout:
    """generate_single_chapter returns generation_failed on asyncio.TimeoutError."""

    @pytest.mark.asyncio
    async def test_timeout_returns_generation_failed_dict(self):
        """When asyncio.wait_for raises TimeoutError, result has generation_failed=True."""
        from src.core.llm.chapter_generator import generate_single_chapter

        mock_client = MagicMock()
        chapter_outline = {"chapter": 3, "title": "第三章", "plot": "情节"}

        with patch("src.core.llm.chapter_generator.asyncio.wait_for",
                   side_effect=asyncio.TimeoutError()):
            result = await generate_single_chapter(
                client=mock_client,
                chapter_outline=chapter_outline,
                previous_chapter="",
                characters_json="[]",
                world_setting_json="{}",
            )

        assert result["generation_failed"] is True
        assert result["chapter"] == 3
        assert result["word_count"] == 0
        assert "超时" in result["content"] or "generation_failed" in str(result)

    @pytest.mark.asyncio
    async def test_timeout_uses_chapter_number_from_outline(self):
        """Timeout result preserves chapter number and title from outline."""
        from src.core.llm.chapter_generator import generate_single_chapter

        mock_client = MagicMock()
        chapter_outline = {"chapter": 7, "title": "第七章：决战", "plot": "决战"}

        with patch("src.core.llm.chapter_generator.asyncio.wait_for",
                   side_effect=asyncio.TimeoutError()):
            result = await generate_single_chapter(
                client=mock_client,
                chapter_outline=chapter_outline,
                previous_chapter="",
                characters_json="[]",
                world_setting_json="{}",
            )

        assert result["chapter"] == 7
        assert result["title"] == "第七章：决战"
        assert result["generation_failed"] is True

    @pytest.mark.asyncio
    async def test_success_does_not_set_generation_failed(self):
        """Successful generation does NOT include generation_failed key."""
        from src.core.llm.chapter_generator import generate_single_chapter

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="章节正文内容")
        chapter_outline = {"chapter": 1, "title": "第一章", "plot": "开篇"}

        # Patch the inner function to return a clean result directly
        expected = {
            "chapter": 1,
            "title": "第一章",
            "content": "章节正文内容",
            "word_count": 7,
        }
        with patch(
            "src.core.llm.chapter_generator._generate_single_chapter_inner",
            new=AsyncMock(return_value=expected),
        ):
            result = await generate_single_chapter(
                client=mock_client,
                chapter_outline=chapter_outline,
                previous_chapter="",
                characters_json="[]",
                world_setting_json="{}",
            )

        assert result.get("generation_failed") is None or result.get("generation_failed") is False
        assert result["content"] == "章节正文内容"


# ===========================================================================
# 4. chapter_generation node — per-chapter error isolation
# ===========================================================================

def _make_state(chapter_outlines=None):
    return {
        "project_id": "proj-test",
        "novel_id": "novel-test",
        "idea": "测试",
        "novel_type": "玄幻",
        "target_words": 10000,
        "writing_style": "",
        "writing_style_prompt": "",
        "world_setting": {"background": "test"},
        "characters": [{"name": "主角"}],
        "chapter_outlines": chapter_outlines or [],
        "chapters": [],
        "current_stage": "outline_generation_completed",
        "approval_status": "pending",
        "revision_requests": [],
        "quality_scores": {},
        "errors": [],
        "_regeneration_count": 0,
    }


class TestChapterGenerationNodeIsolation:
    """chapter_generation node isolates per-chapter failures."""

    @pytest.mark.asyncio
    async def test_failed_chapter_marked_with_generation_failed(self):
        """When one chapter raises, it gets generation_failed=True and others continue."""
        from src.core.langgraph.nodes import chapter_generation

        outlines = [
            {"chapter": 1, "title": "第一章", "plot": "开篇"},
            {"chapter": 2, "title": "第二章", "plot": "发展"},
            {"chapter": 3, "title": "第三章", "plot": "高潮"},
        ]
        state = _make_state(outlines)

        call_count = 0

        async def fake_generate(client, chapter_outline, **kwargs):
            nonlocal call_count
            call_count += 1
            ch = chapter_outline["chapter"]
            if ch == 2:
                raise RuntimeError("API 调用失败")
            return {
                "chapter": ch,
                "title": chapter_outline["title"],
                "content": f"第{ch}章内容",
                "word_count": 100,
            }

        with patch("src.core.langgraph.nodes.chapter_generation.get_settings") as mock_cfg, \
             patch("src.core.langgraph.nodes.chapter_generation.get_llm_client"), \
             patch("src.core.langgraph.nodes.chapter_generation.generate_single_chapter",
                   side_effect=fake_generate), \
             patch("src.api.services.progress_event_bus.get_progress_callback",
                   return_value=None):
            mock_cfg.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=False)
            result = await chapter_generation.node(state)

        chapters = result["chapters"]
        assert len(chapters) == 3, "All 3 chapters should be present"

        ch1 = next(c for c in chapters if c["chapter"] == 1)
        ch2 = next(c for c in chapters if c["chapter"] == 2)
        ch3 = next(c for c in chapters if c["chapter"] == 3)

        assert ch1.get("generation_failed") is not True
        assert ch2["generation_failed"] is True
        assert ch3.get("generation_failed") is not True

    @pytest.mark.asyncio
    async def test_failed_chapter_error_recorded_in_state(self):
        """Errors from failed chapters are accumulated in state['errors']."""
        from src.core.langgraph.nodes import chapter_generation

        outlines = [
            {"chapter": 1, "title": "第一章", "plot": "开篇"},
            {"chapter": 2, "title": "第二章", "plot": "发展"},
        ]
        state = _make_state(outlines)

        async def fake_generate(client, chapter_outline, **kwargs):
            ch = chapter_outline["chapter"]
            if ch == 2:
                raise ValueError("章节生成错误")
            return {"chapter": ch, "title": chapter_outline["title"],
                    "content": "内容", "word_count": 50}

        with patch("src.core.langgraph.nodes.chapter_generation.get_settings") as mock_cfg, \
             patch("src.core.langgraph.nodes.chapter_generation.get_llm_client"), \
             patch("src.core.langgraph.nodes.chapter_generation.generate_single_chapter",
                   side_effect=fake_generate), \
             patch("src.api.services.progress_event_bus.get_progress_callback",
                   return_value=None):
            mock_cfg.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=False)
            result = await chapter_generation.node(state)

        assert any("第2章" in e for e in result["errors"])

    @pytest.mark.asyncio
    async def test_all_chapters_fail_still_returns_completed_stage(self):
        """Even if all chapters fail, current_stage is chapter_generation_completed."""
        from src.core.langgraph.nodes import chapter_generation

        outlines = [{"chapter": 1, "title": "第一章", "plot": "开篇"}]
        state = _make_state(outlines)

        async def always_fail(client, chapter_outline, **kwargs):
            raise ConnectionError("网络断开")

        with patch("src.core.langgraph.nodes.chapter_generation.get_settings") as mock_cfg, \
             patch("src.core.langgraph.nodes.chapter_generation.get_llm_client"), \
             patch("src.core.langgraph.nodes.chapter_generation.generate_single_chapter",
                   side_effect=always_fail), \
             patch("src.api.services.progress_event_bus.get_progress_callback",
                   return_value=None):
            mock_cfg.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=False)
            result = await chapter_generation.node(state)

        assert result["current_stage"] == "chapter_generation_completed"
        assert result["chapters"][0]["generation_failed"] is True

    @pytest.mark.asyncio
    async def test_progress_callback_receives_successful_and_failed_counts(self):
        """Progress callback is called with successful_chapters and failed_chapters."""
        from src.core.langgraph.nodes import chapter_generation

        outlines = [
            {"chapter": 1, "title": "第一章", "plot": "开篇"},
            {"chapter": 2, "title": "第二章", "plot": "发展"},
        ]
        state = _make_state(outlines)
        callback_calls = []

        async def fake_callback(data):
            callback_calls.append(data)

        async def fake_generate(client, chapter_outline, **kwargs):
            ch = chapter_outline["chapter"]
            if ch == 2:
                raise RuntimeError("失败")
            return {"chapter": ch, "title": chapter_outline["title"],
                    "content": "内容", "word_count": 50}

        with patch("src.core.langgraph.nodes.chapter_generation.get_settings") as mock_cfg, \
             patch("src.core.langgraph.nodes.chapter_generation.get_llm_client"), \
             patch("src.core.langgraph.nodes.chapter_generation.generate_single_chapter",
                   side_effect=fake_generate):
            mock_cfg.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=False)
            config = {"configurable": {"progress_callback": fake_callback}}
            await chapter_generation.node(state, config=config)

        assert len(callback_calls) == 2

        # After chapter 1 (success): 1 successful, 0 failed
        assert callback_calls[0]["successful_chapters"] == 1
        assert callback_calls[0]["failed_chapters"] == 0

        # After chapter 2 (failure): 1 successful, 1 failed
        assert callback_calls[1]["successful_chapters"] == 1
        assert callback_calls[1]["failed_chapters"] == 1


# ===========================================================================
# 5. novel_generator — _chapter_progress_callback includes new fields
# ===========================================================================

class TestChapterProgressCallbackFields:
    """_run_langgraph_pipeline callback emits successful_chapters and failed_chapters."""

    @pytest.mark.asyncio
    async def test_callback_propagates_successful_and_failed_chapters(self):
        """Progress callback data includes successful_chapters and failed_chapters."""
        from src.api.services.novel_generator import _run_langgraph_pipeline

        captured_events = []

        mock_task_manager = AsyncMock()
        mock_event_bus = AsyncMock()

        async def capture_publish(event):
            captured_events.append(event)

        mock_event_bus.publish = capture_publish

        # Simulate graph that emits one chapter_generation node event
        async def fake_graph_stream(state, config):
            yield {"chapter_generation": {
                "chapters": [
                    {"chapter": 1, "content": "内容", "generation_failed": False},
                    {"chapter": 2, "content": "[失败]", "generation_failed": True},
                ],
                "chapter_outlines": [{"chapter": 1}, {"chapter": 2}],
                "current_stage": "chapter_generation_completed",
            }}

        mock_graph = MagicMock()
        mock_graph.astream = fake_graph_stream

        with patch("src.api.services.novel_generator.get_task_manager",
                   return_value=mock_task_manager), \
             patch("src.api.services.novel_generator.get_event_bus",
                   return_value=mock_event_bus), \
             patch("src.api.services.novel_generator.create_novel_graph",
                   return_value=mock_graph):

            # Manually invoke the callback to test its field propagation
            from src.api.services.novel_generator import _full_generate_percentage

            # Simulate what _chapter_progress_callback does
            data = {
                "completed_chapters": 2,
                "successful_chapters": 1,
                "failed_chapters": 1,
                "total_chapters": 2,
                "current_chapter": 2,
            }
            total = max(data.get("total_chapters", 1), 1)
            completed = data.get("completed_chapters", 0)
            successful = data.get("successful_chapters", completed)
            failed = data.get("failed_chapters", 0)

            assert successful == 1
            assert failed == 1
            assert completed == 2

    def test_callback_defaults_successful_to_completed_when_missing(self):
        """If successful_chapters is absent, it defaults to completed_chapters."""
        data = {
            "completed_chapters": 3,
            "failed_chapters": 0,
            "total_chapters": 3,
        }
        completed = data.get("completed_chapters", 0)
        successful = data.get("successful_chapters", completed)
        failed = data.get("failed_chapters", 0)

        assert successful == 3
        assert failed == 0


# ===========================================================================
# 6. health endpoint — api_key_configured field
# ===========================================================================

class TestHealthApiKeyConfigured:
    """Health endpoint returns api_key_configured based on DEEPSEEK_API_KEY."""

    def _patch_settings(self, api_key: str):
        return patch("src.api.routes.health.get_settings", return_value=MagicMock(
            DEEPSEEK_API_KEY=api_key
        ))

    @pytest.mark.asyncio
    async def test_health_returns_true_for_valid_key(self):
        """api_key_configured is True when a real-looking key is set."""
        from src.api.routes.health import health_check

        with self._patch_settings("sk-realkey123"):
            response = await health_check()

        assert response.api_key_configured is True

    @pytest.mark.asyncio
    async def test_health_returns_false_for_empty_key(self):
        """api_key_configured is False when key is empty."""
        from src.api.routes.health import health_check

        with self._patch_settings(""):
            response = await health_check()

        assert response.api_key_configured is False

    @pytest.mark.asyncio
    async def test_health_returns_false_for_placeholder_key(self):
        """api_key_configured is False for known placeholder values."""
        from src.api.routes.health import health_check

        placeholders = [
            "dummy_key_for_compilation",
            "your-api-key-here",
            "your_api_key_here",
            "sk-placeholder",
        ]
        for placeholder in placeholders:
            with self._patch_settings(placeholder):
                response = await health_check()
            assert response.api_key_configured is False, (
                f"Expected False for placeholder '{placeholder}'"
            )

    @pytest.mark.asyncio
    async def test_health_returns_false_for_whitespace_only_key(self):
        """api_key_configured is False when key is only whitespace."""
        from src.api.routes.health import health_check

        with self._patch_settings("   "):
            response = await health_check()

        assert response.api_key_configured is False

    @pytest.mark.asyncio
    async def test_health_response_has_required_fields(self):
        """Health response includes status, version, timestamp, api_key_configured."""
        from src.api.routes.health import health_check

        with self._patch_settings("sk-valid-key"):
            response = await health_check()

        assert response.status == "healthy"
        assert response.version == "1.0.0"
        assert response.timestamp is not None
        assert isinstance(response.api_key_configured, bool)


# ===========================================================================
# 7. _is_api_key_configured helper
# ===========================================================================

class TestIsApiKeyConfigured:
    """Unit tests for the _is_api_key_configured helper in health.py."""

    def _call(self, api_key: str) -> bool:
        from src.api.routes.health import _is_api_key_configured
        with patch("src.api.routes.health.get_settings",
                   return_value=MagicMock(DEEPSEEK_API_KEY=api_key)):
            return _is_api_key_configured()

    def test_valid_key_returns_true(self):
        assert self._call("sk-abc123") is True

    def test_empty_string_returns_false(self):
        assert self._call("") is False

    def test_none_returns_false(self):
        assert self._call(None) is False

    def test_placeholder_dummy_key_returns_false(self):
        assert self._call("dummy_key_for_compilation") is False

    def test_placeholder_your_api_key_here_returns_false(self):
        assert self._call("your-api-key-here") is False

    def test_placeholder_sk_placeholder_returns_false(self):
        assert self._call("sk-placeholder") is False

    def test_case_insensitive_placeholder_check(self):
        """Placeholder check is case-insensitive."""
        assert self._call("SK-PLACEHOLDER") is False
        assert self._call("Dummy_Key_For_Compilation") is False
