"""应用配置管理"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    # DeepSeek API 配置
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-v4-pro"
    DEEPSEEK_TEMPERATURE: float = 0.7
    DEEPSEEK_MAX_TOKENS: int = 2000
    DEEPSEEK_TIMEOUT: int = 120
    DEEPSEEK_MAX_RETRIES: int = 3

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_FILE: str | None = "logs/xiaoshuo.log"
    LOG_FORMAT: str = "console"  # "console" | "json"

    # CORS 配置
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # API 配置
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_WORKERS: int = 1
    API_RELOAD: bool = False

    # Database configuration
    DATABASE_URL: str = "postgresql+asyncpg://xiaoshuo:password@localhost:5432/xiaoshuo"
    DATABASE_POOL_SIZE: int = 5
    DATABASE_MAX_OVERFLOW: int = 10
    DATABASE_ECHO: bool = False

    # Knowledge Graph
    KNOWLEDGE_GRAPH_ENABLED: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    """获取配置单例

    Returns:
        Settings 实例

    Note:
        使用 lru_cache 缓存配置对象。如果需要重新加载配置，
        可以调用 get_settings.cache_clear()
    """
    return Settings()  # type: ignore[call-arg]
