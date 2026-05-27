"""LLMClient 数据库配置初始化测试（CHANGE-051 T8）"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage


def _make_mock_llm_config(
    base_url="https://custom.api.com/v1",
    api_key="custom-key-1234",
    model_flash="custom-flash",
    model_pro="custom-pro",
):
    """构造一个模拟 LLMConfig 对象"""
    cfg = MagicMock()
    cfg.base_url = base_url
    cfg.api_key = api_key
    cfg.model_flash = model_flash
    cfg.model_pro = model_pro
    cfg.name = "test-config"
    return cfg


@pytest.fixture
def mock_settings():
    with patch("src.core.llm.client.get_settings") as mock:
        settings = MagicMock()
        settings.DEEPSEEK_MODEL = "deepseek-v4-pro"
        settings.DEEPSEEK_MODEL_FLASH = "deepseek-v4-flash"
        settings.DEEPSEEK_MODEL_PRO = "deepseek-v4-pro"
        settings.DEEPSEEK_API_KEY = "settings-api-key"
        settings.DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"
        settings.DEEPSEEK_TEMPERATURE = 0.7
        settings.DEEPSEEK_TIMEOUT = 30
        settings.DEEPSEEK_MAX_TOKENS = 2000
        settings.DEEPSEEK_MAX_RETRIES = 3
        mock.return_value = settings
        yield mock


@pytest.fixture
def mock_chat_openai():
    with patch("src.core.llm.client.ChatOpenAI") as mock:
        yield mock


class TestLLMClientDbConfig:
    """LLMClient 使用数据库配置初始化"""

    def test_init_with_llm_config_uses_db_values(self, mock_settings, mock_chat_openai):
        """传入 llm_config 时，使用数据库中的 base_url、api_key、model_flash、model_pro"""
        from src.core.llm.client import LLMClient

        db_config = _make_mock_llm_config()
        client = LLMClient(llm_config=db_config)

        # ChatOpenAI 应被调用两次（flash + pro）
        assert mock_chat_openai.call_count == 2

        calls = mock_chat_openai.call_args_list
        models_used = {c[1]["model"] for c in calls}
        assert "custom-flash" in models_used
        assert "custom-pro" in models_used

        for call in calls:
            assert call[1]["api_key"] == "custom-key-1234"
            assert call[1]["base_url"] == "https://custom.api.com/v1"

    def test_init_without_llm_config_uses_settings(self, mock_settings, mock_chat_openai):
        """不传 llm_config 时，回退到 Settings"""
        from src.core.llm.client import LLMClient

        client = LLMClient()

        assert mock_chat_openai.call_count == 2
        calls = mock_chat_openai.call_args_list
        for call in calls:
            assert call[1]["api_key"] == "settings-api-key"
            assert call[1]["base_url"] == "https://api.deepseek.com/v1"

        models_used = {c[1]["model"] for c in calls}
        assert "deepseek-v4-flash" in models_used
        assert "deepseek-v4-pro" in models_used

    def test_init_with_none_llm_config_uses_settings(self, mock_settings, mock_chat_openai):
        """显式传入 None 时，回退到 Settings"""
        from src.core.llm.client import LLMClient

        client = LLMClient(llm_config=None)

        assert mock_chat_openai.call_count == 2
        calls = mock_chat_openai.call_args_list
        for call in calls:
            assert call[1]["api_key"] == "settings-api-key"

    @pytest.mark.asyncio
    async def test_generate_uses_db_model_name_in_tracker(self, mock_settings, mock_chat_openai):
        """使用数据库配置时，token tracker 记录的 model 名来自数据库配置"""
        import src.core.llm.token_tracker as tt_module
        from src.core.llm.client import LLMClient

        # 重置 tracker
        tt_module._tracker = None

        mock_llm_instance = AsyncMock()
        mock_response = AIMessage(content="test")
        mock_response.response_metadata = {
            "token_usage": {
                "prompt_tokens": 5,
                "completion_tokens": 10,
                "total_tokens": 15,
            }
        }
        mock_llm_instance.ainvoke.return_value = mock_response
        mock_chat_openai.return_value = mock_llm_instance

        db_config = _make_mock_llm_config(model_flash="my-flash", model_pro="my-pro")
        client = LLMClient(llm_config=db_config)

        await client.generate("test prompt", use_flash=True)

        tracker = tt_module.get_token_tracker()
        stats = tracker.get_stats()
        assert stats["total_calls"] == 1
        assert "my-flash" in stats["by_model"]
