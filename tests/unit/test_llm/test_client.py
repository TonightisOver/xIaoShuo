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
