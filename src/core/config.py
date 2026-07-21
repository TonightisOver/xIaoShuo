"""应用配置管理"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置"""

    # DeepSeek API 配置
    DEEPSEEK_API_KEY: str
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com/v1"
    DEEPSEEK_MODEL: str = "deepseek-v4-pro"
    DEEPSEEK_MODEL_FLASH: str = "deepseek-v4-flash"
    DEEPSEEK_MODEL_PRO: str = "deepseek-v4-pro"
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
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_ECHO: bool = False

    # 持久化生成任务队列
    TASK_QUEUE_ENABLED: bool = True
    TASK_QUEUE_POLL_SECONDS: float = 1.0
    TASK_QUEUE_LEASE_SECONDS: int = 120
    TASK_QUEUE_RETRY_DELAY_SECONDS: int = 5
    # 长篇任务断点重试预算（配合 task_checkpoints 从断点续跑，而非从头重生成）
    LONG_FORM_MAX_ATTEMPTS: int = 3

    # Knowledge Graph
    KNOWLEDGE_GRAPH_ENABLED: bool = True
    KG_SUBAGENT_ENABLED: bool = True
    EMBEDDING_MODEL: str = "text-embedding-ada-002"
    EMBEDDING_DIM: int = 1536
    EMBEDDING_BASE_URL: str | None = None  # 默认 None 时使用 DEEPSEEK_BASE_URL
    # DeepSeek API 不提供 embedding 接口（/v1/embeddings 返回 404），默认关闭
    # 实体 embedding 生成与语义检索；retrieve_context 降级为精确匹配（已足够）。
    # 仅当配置了支持 embedding 的供应商（如 OpenAI/智谱）时设为 True 启用向量检索。
    EMBEDDING_ENABLED: bool = False

    # HITL 人工审核
    # True：human_review 节点自动通过（不 interrupt），管线端到端跑通
    # False：启用真 interrupt() 阻塞等待人工决策（已实现，配合持久化 checkpointer + resume 路径）
    HITL_AUTO_APPROVE: bool = True

    # 质量优化循环
    # quality_check 后若 overall < QUALITY_THRESHOLD 且重试次数 < MAX_REGENERATION_ATTEMPTS，
    # 回到 chapter_generation 重新生成（提升质量）。设 QUALITY_LOOP_ENABLED=False 可跳过
    # 直接进入审核（追求速度/节省 token 时用）。
    QUALITY_LOOP_ENABLED: bool = True
    QUALITY_THRESHOLD: float = 0.7  # 质量达标线，低于此值触发重生成（LLM 给分偏严，0.8 常误触发）
    MAX_REGENERATION_ATTEMPTS: int = 2  # 最多重生成次数（避免无限循环/浪费 token）

    # 质量门禁成本模式：economy(成本优先) / balanced(均衡) / high(质量优先)
    QUALITY_MODE: str = "balanced"
    # 【预留】L2 LLM 评审抽检比例(0-1)。当前 should_invoke_l2 用固定取模(%3/%5)，
    # 本配置预留给未来按比例随机抽检策略接入；当前未使用，调整它不会改变抽检行为。
    QUALITY_SAMPLE_RATIO: float = 0.2
    # 单章最大 L3 改写次数（避免无限循环）
    QUALITY_MAX_REWRITE_PER_CHAPTER: int = 2
    # 单章评审 Token 预算上限（达到即转人工）
    QUALITY_TOKEN_BUDGET_PER_CHAPTER: int = 20000
    # 关键章节类型（开篇/高潮/反转/卷末/结局）必审 L2
    QUALITY_CRITICAL_CHAPTER_TYPES: list[str] = [
        "opening", "climax", "twist", "volume_end", "ending", "key_milestone",
    ]

    # Encryption
    LLM_ENCRYPTION_KEY: str = ""
    ADMIN_TOKEN: str = "change-this-admin-token"
    # 注册时 username 匹配此值的用户自动标记 is_admin=True（管理 LLM 配置等敏感操作）
    ADMIN_USERNAME: str = ""

    # 开发期自动登录：DEV_AUTO_LOGIN=1 时无 token 直接返回 DEV_USERNAME 用户（带 admin）。
    # 前端免登录即可用全部受保护 API。生产环境严禁开启。
    DEV_AUTO_LOGIN: bool = False
    DEV_USERNAME: str = "dev"

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
