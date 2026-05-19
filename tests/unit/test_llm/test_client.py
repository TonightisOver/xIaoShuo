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
        """测试初始化"""
        client = LLMClient()

        # 验证 ChatOpenAI 被正确调用
        mock_chat_openai.assert_called_once()
        call_kwargs = mock_chat_openai.call_args[1]

        assert call_kwargs["model"] == "deepseek-v4-pro"
        assert call_kwargs["api_key"] == "test-api-key"
        assert call_kwargs["base_url"] == "https://api.deepseek.com/v1"
        assert call_kwargs["temperature"] == 0.7
        assert call_kwargs["timeout"] == 30
        assert call_kwargs["model_kwargs"] == {"max_tokens": 2000}

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
        assert mock_chat_openai.call_count == 1


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
