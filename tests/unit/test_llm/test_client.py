"""LLM 客户端单元测试"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from src.core.llm.client import LLMClient, get_llm_client


@pytest.fixture
def mock_settings():
    """Mock 配置"""
    with patch("src.core.llm.client.get_settings") as mock:
        settings = MagicMock()
        settings.DEEPSEEK_MODEL = "deepseek-v4-pro"
        settings.DEEPSEEK_MODEL_FLASH = "deepseek-v4-flash"
        settings.DEEPSEEK_MODEL_PRO = "deepseek-v4-pro"
        settings.DEEPSEEK_API_KEY = "test-api-key"
        settings.DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
        settings.DEEPSEEK_TEMPERATURE = 0.7
        settings.DEEPSEEK_TIMEOUT = 30
        settings.DEEPSEEK_MAX_TOKENS = 2000
        settings.DEEPSEEK_MAX_RETRIES = 3
        mock.return_value = settings
        yield mock


@pytest.fixture
def mock_chat_openai():
    """Mock ChatOpenAI"""
    with patch("src.core.llm.client.ChatOpenAI") as mock:
        yield mock


class TestLLMClient:
    """LLM 客户端测试"""

    def test_init(self, mock_settings, mock_chat_openai):
        """测试初始化 — 双模型策略：ChatOpenAI 被调用两次（flash + pro）"""
        mock_settings.return_value.DEEPSEEK_MODEL_FLASH = "deepseek-v4-flash"
        mock_settings.return_value.DEEPSEEK_MODEL_PRO = "deepseek-v4-pro"
        client = LLMClient()

        # 双模型：ChatOpenAI 被调用两次
        assert mock_chat_openai.call_count == 2

        calls = mock_chat_openai.call_args_list
        models_used = {c[1]["model"] for c in calls}
        assert "deepseek-v4-flash" in models_used
        assert "deepseek-v4-pro" in models_used

        for call in calls:
            assert call[1]["api_key"] == "test-api-key"
            assert call[1]["base_url"] == "https://api.deepseek.com/v1"
            assert call[1]["temperature"] == 0.7
            assert call[1]["timeout"] == 30
            assert call[1]["model_kwargs"] == {"max_tokens": 2000}

        assert client.max_retries == 3

    @pytest.mark.asyncio
    async def test_generate_success(self, mock_settings, mock_chat_openai):
        """测试成功生成"""
        # Mock LLM 响应
        mock_llm_instance = AsyncMock()
        mock_response = AIMessage(content="这是生成的文本")
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm_instance

        client = LLMClient()
        result = await client.generate("测试 prompt")

        assert result == "这是生成的文本"
        mock_llm_instance.ainvoke.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_with_custom_params(self, mock_settings, mock_chat_openai):
        """测试使用自定义参数生成"""
        mock_llm_instance = AsyncMock()
        mock_response = AIMessage(content="自定义参数生成")
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm_instance

        client = LLMClient()
        result = await client.generate(
            "测试 prompt", temperature=0.9, max_tokens=1000
        )

        assert result == "自定义参数生成"

        # 验证调用参数
        call_args = mock_llm_instance.ainvoke.call_args
        kwargs = call_args[1]
        assert kwargs["temperature"] == 0.9
        assert kwargs["max_tokens"] == 1000

    @pytest.mark.asyncio
    async def test_generate_failure(self, mock_settings, mock_chat_openai):
        """测试生成失败"""
        mock_llm_instance = AsyncMock()
        mock_llm_instance.ainvoke.side_effect = Exception("API 调用失败")
        mock_chat_openai.return_value = mock_llm_instance

        client = LLMClient()

        with pytest.raises(Exception, match="API 调用失败"):
            await client.generate("测试 prompt")

    def test_get_llm_client_singleton(self, mock_settings, mock_chat_openai):
        """测试单例模式"""
        # 清除全局单例
        import src.core.llm.client as client_module

        client_module._client = None

        client1 = get_llm_client()
        client2 = get_llm_client()

        assert client1 is client2
        # 双模型：每次初始化调用 ChatOpenAI 两次，单例只初始化一次
        assert mock_chat_openai.call_count == 2


# ============================================================
#  CHANGE-027: 重试逻辑测试
# ============================================================

class TestLLMClientRetry:
    """测试 AsyncRetrying 重试逻辑（CHANGE-027）"""

    @pytest.mark.asyncio
    async def test_retries_on_429(self, mock_settings, mock_chat_openai):
        """429 错误应触发重试，最终成功返回"""
        import httpx
        from langchain_core.messages import AIMessage

        mock_llm_instance = AsyncMock()
        mock_chat_openai.return_value = mock_llm_instance

        # 第一次 429，第二次成功
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_error = httpx.HTTPStatusError(
            "429 Too Many Requests",
            request=MagicMock(),
            response=rate_limit_response,
        )
        mock_llm_instance.ainvoke.side_effect = [
            rate_limit_error,
            AIMessage(content="重试后成功"),
        ]

        client = LLMClient()
        client.max_retries = 3

        # 跳过真实等待
        with patch("src.core.llm.client.wait_exponential", return_value=MagicMock()):
            with patch("tenacity.wait_exponential") as mock_wait:
                mock_wait.return_value = lambda retry_state: 0
                # 直接 patch AsyncRetrying 的 wait 参数
                result = await client.generate("测试 prompt")

        assert result == "重试后成功"
        assert mock_llm_instance.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_does_not_retry_on_401(self, mock_settings, mock_chat_openai):
        """401 认证错误不应重试，直接抛出"""
        import httpx

        mock_llm_instance = AsyncMock()
        mock_chat_openai.return_value = mock_llm_instance

        auth_response = MagicMock()
        auth_response.status_code = 401
        auth_error = httpx.HTTPStatusError(
            "401 Unauthorized",
            request=MagicMock(),
            response=auth_response,
        )
        mock_llm_instance.ainvoke.side_effect = auth_error

        client = LLMClient()
        client.max_retries = 3

        with pytest.raises(httpx.HTTPStatusError) as exc_info:
            await client.generate("测试 prompt")

        # 401 不重试，ainvoke 只调用一次
        assert mock_llm_instance.ainvoke.call_count == 1
        assert exc_info.value.response.status_code == 401

    @pytest.mark.asyncio
    async def test_max_retries_exhausted_raises(self, mock_settings, mock_chat_openai):
        """超过 max_retries 次数后应抛出异常"""
        mock_llm_instance = AsyncMock()
        mock_chat_openai.return_value = mock_llm_instance

        # 每次都抛出 ConnectionError（可重试）
        mock_llm_instance.ainvoke.side_effect = ConnectionError("连接失败")

        client = LLMClient()
        client.max_retries = 2  # 最多重试 2 次

        with pytest.raises(Exception):
            await client.generate("测试 prompt")

        # max_retries=2 意味着最多尝试 2 次
        assert mock_llm_instance.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_500(self, mock_settings, mock_chat_openai):
        """5xx 服务器错误应触发重试"""
        import httpx
        from langchain_core.messages import AIMessage

        mock_llm_instance = AsyncMock()
        mock_chat_openai.return_value = mock_llm_instance

        server_error_response = MagicMock()
        server_error_response.status_code = 500
        server_error = httpx.HTTPStatusError(
            "500 Internal Server Error",
            request=MagicMock(),
            response=server_error_response,
        )
        mock_llm_instance.ainvoke.side_effect = [
            server_error,
            AIMessage(content="服务器恢复后成功"),
        ]

        client = LLMClient()
        client.max_retries = 3

        result = await client.generate("测试 prompt")

        assert result == "服务器恢复后成功"
        assert mock_llm_instance.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_timeout(self, mock_settings, mock_chat_openai):
        """TimeoutError 应触发重试"""
        from langchain_core.messages import AIMessage

        mock_llm_instance = AsyncMock()
        mock_chat_openai.return_value = mock_llm_instance

        mock_llm_instance.ainvoke.side_effect = [
            TimeoutError("请求超时"),
            AIMessage(content="超时后重试成功"),
        ]

        client = LLMClient()
        client.max_retries = 3

        result = await client.generate("测试 prompt")

        assert result == "超时后重试成功"
        assert mock_llm_instance.ainvoke.call_count == 2

    def test_is_retryable_http_error_429(self):
        """_is_retryable_http_error 对 429 返回 True"""
        import httpx

        from src.core.llm.client import _is_retryable_http_error

        response = MagicMock()
        response.status_code = 429
        exc = httpx.HTTPStatusError("429", request=MagicMock(), response=response)

        assert _is_retryable_http_error(exc) is True

    def test_is_retryable_http_error_500(self):
        """_is_retryable_http_error 对 5xx 返回 True"""
        import httpx

        from src.core.llm.client import _is_retryable_http_error

        for status in (500, 502, 503, 504):
            response = MagicMock()
            response.status_code = status
            exc = httpx.HTTPStatusError(str(status), request=MagicMock(), response=response)
            assert _is_retryable_http_error(exc) is True, f"Expected True for {status}"

    def test_is_retryable_http_error_401(self):
        """_is_retryable_http_error 对 401 返回 False"""
        import httpx

        from src.core.llm.client import _is_retryable_http_error

        response = MagicMock()
        response.status_code = 401
        exc = httpx.HTTPStatusError("401", request=MagicMock(), response=response)

        assert _is_retryable_http_error(exc) is False

    def test_is_retryable_http_error_non_http(self):
        """_is_retryable_http_error 对非 HTTPStatusError 返回 False"""
        from src.core.llm.client import _is_retryable_http_error

        assert _is_retryable_http_error(ValueError("not http")) is False
        assert _is_retryable_http_error(ConnectionError("conn")) is False


# ============================================================
#  CHANGE-051: 双模型策略 + token 追踪测试
# ============================================================


class TestLLMClientDualModel:
    """测试 use_flash 参数路由到正确的模型实例"""

    @pytest.mark.asyncio
    async def test_use_flash_true_uses_llm_flash(self, mock_settings, mock_chat_openai):
        """use_flash=True 时使用 llm_flash 实例"""
        flash_instance = AsyncMock()
        pro_instance = AsyncMock()
        flash_instance.ainvoke.return_value = AIMessage(content="flash response")
        pro_instance.ainvoke.return_value = AIMessage(content="pro response")

        # ChatOpenAI 第一次调用返回 flash，第二次返回 pro（按 __init__ 中的顺序）
        mock_chat_openai.side_effect = [flash_instance, pro_instance]

        client = LLMClient()
        result = await client.generate("test prompt", use_flash=True)

        assert result == "flash response"
        flash_instance.ainvoke.assert_called_once()
        pro_instance.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_use_flash_false_uses_llm_pro(self, mock_settings, mock_chat_openai):
        """use_flash=False（默认）时使用 llm_pro 实例"""
        flash_instance = AsyncMock()
        pro_instance = AsyncMock()
        flash_instance.ainvoke.return_value = AIMessage(content="flash response")
        pro_instance.ainvoke.return_value = AIMessage(content="pro response")

        mock_chat_openai.side_effect = [flash_instance, pro_instance]

        client = LLMClient()
        result = await client.generate("test prompt", use_flash=False)

        assert result == "pro response"
        pro_instance.ainvoke.assert_called_once()
        flash_instance.ainvoke.assert_not_called()

    @pytest.mark.asyncio
    async def test_use_flash_default_uses_llm_pro(self, mock_settings, mock_chat_openai):
        """use_flash 默认值为 False，使用 llm_pro"""
        flash_instance = AsyncMock()
        pro_instance = AsyncMock()
        flash_instance.ainvoke.return_value = AIMessage(content="flash response")
        pro_instance.ainvoke.return_value = AIMessage(content="pro response")

        mock_chat_openai.side_effect = [flash_instance, pro_instance]

        client = LLMClient()
        # 不传 use_flash，验证默认走 pro
        result = await client.generate("test prompt")

        assert result == "pro response"
        pro_instance.ainvoke.assert_called_once()
        flash_instance.ainvoke.assert_not_called()


class TestLLMClientTokenTracking:
    """测试 token 追踪逻辑：record() 和 skip()"""

    @pytest.mark.asyncio
    async def test_token_record_called_on_success_with_metadata(
        self, mock_settings, mock_chat_openai
    ):
        """response_metadata 含 token_usage 时调用 tracker.record()"""
        import src.core.llm.token_tracker as tt_module

        tt_module._tracker = None  # 重置单例

        mock_llm_instance = AsyncMock()
        mock_response = AIMessage(content="ok")
        mock_response.response_metadata = {
            "token_usage": {
                "prompt_tokens": 10,
                "completion_tokens": 20,
                "total_tokens": 30,
            }
        }
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm_instance

        client = LLMClient()
        await client.generate("test prompt")

        tracker = tt_module.get_token_tracker()
        stats = tracker.get_stats()
        assert stats["total_calls"] == 1
        assert stats["records_skipped"] == 0
        assert stats["total_prompt_tokens"] == 10
        assert stats["total_completion_tokens"] == 20
        assert stats["total_tokens"] == 30

    @pytest.mark.asyncio
    async def test_token_skip_called_when_no_response_metadata(
        self, mock_settings, mock_chat_openai
    ):
        """response 无 response_metadata 属性时调用 tracker.skip()"""
        import src.core.llm.token_tracker as tt_module

        tt_module._tracker = None

        mock_llm_instance = AsyncMock()
        # AIMessage 默认没有 response_metadata，或者为空 dict
        mock_response = AIMessage(content="ok")
        # 确保 response_metadata 不含 token_usage
        mock_response.response_metadata = {}
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm_instance

        client = LLMClient()
        await client.generate("test prompt")

        tracker = tt_module.get_token_tracker()
        stats = tracker.get_stats()
        assert stats["total_calls"] == 0
        assert stats["records_skipped"] == 1

    @pytest.mark.asyncio
    async def test_token_skip_called_when_token_usage_missing_prompt_tokens(
        self, mock_settings, mock_chat_openai
    ):
        """token_usage 存在但缺少 prompt_tokens 时调用 tracker.skip()"""
        import src.core.llm.token_tracker as tt_module

        tt_module._tracker = None

        mock_llm_instance = AsyncMock()
        mock_response = AIMessage(content="ok")
        # token_usage 存在但不含 prompt_tokens
        mock_response.response_metadata = {"token_usage": {"total_tokens": 30}}
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm_instance

        client = LLMClient()
        await client.generate("test prompt")

        tracker = tt_module.get_token_tracker()
        stats = tracker.get_stats()
        assert stats["total_calls"] == 0
        assert stats["records_skipped"] == 1

    @pytest.mark.asyncio
    async def test_token_record_uses_correct_model_name(
        self, mock_settings, mock_chat_openai
    ):
        """tracker.record() 记录的 model 名与实际使用的模型一致"""
        import src.core.llm.token_tracker as tt_module

        tt_module._tracker = None

        flash_instance = AsyncMock()
        pro_instance = AsyncMock()

        flash_response = AIMessage(content="flash ok")
        flash_response.response_metadata = {
            "token_usage": {
                "prompt_tokens": 5,
                "completion_tokens": 10,
                "total_tokens": 15,
            }
        }
        flash_instance.ainvoke.return_value = flash_response
        pro_instance.ainvoke.return_value = AIMessage(content="pro ok")

        mock_chat_openai.side_effect = [flash_instance, pro_instance]

        client = LLMClient()
        await client.generate("test prompt", use_flash=True)

        tracker = tt_module.get_token_tracker()
        stats = tracker.get_stats()
        assert stats["total_calls"] == 1
        # flash 模型名应出现在 by_model 中
        assert "deepseek-v4-flash" in stats["by_model"]
