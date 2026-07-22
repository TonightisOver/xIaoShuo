"""FastAPI 应用入口"""

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import (
    auth_router,
    book_import_router,
    careers_router,
    chapter_analysis_router,
    chapters_router,
    characters_router,
    conversations_router,
    creative_control_router,
    export_router,
    health_router,
    inspiration_router,
    knowledge_graph_router,
    llm_config_router,
    novels_router,
    outline_sync_router,
    outlines_router,
    projects_router,
    reader_simulation_router,
    review_router,
    story_bible_router,
    storylines_router,
    style_router,
    tasks_router,
    volumes_router,
    world_router,
    ws_router,
)
from src.api.services.tasks.task_manager import get_task_manager
from src.api.services.tasks.task_worker import PersistentTaskWorker, get_task_worker
from src.core.config import get_settings
from src.core.database import close_db, init_db
from src.core.langgraph.checkpointer import (
    setup_persistent_checkpointer,
    teardown_persistent_checkpointer,
)
from src.core.logging_config import setup_logging
from src.core.security.auth import validate_admin_token
from src.core.security.crypto import validate_encryption_key

# 设置日志
settings = get_settings()
setup_logging(
    log_level=settings.LOG_LEVEL,
    log_file=settings.LOG_FILE,
    log_format=settings.LOG_FORMAT,
)

logger = structlog.get_logger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


async def start_task_queue() -> PersistentTaskWorker | None:
    """恢复可执行任务，并按配置启动当前进程的队列 worker。"""
    if not settings.TASK_QUEUE_ENABLED:
        logger.info("persistent_task_queue_disabled")
        return None

    recovered = await get_task_manager().recover_interrupted_tasks()
    from src.core.creative_control.control_service import CreativeControlService

    reconciled_controls = await CreativeControlService().reconcile_terminal_generations()
    logger.info(
        "persistent_task_queue_recovered",
        queued_preserved=recovered.queued_preserved,
        stale_requeued=recovered.stale_requeued,
        stale_failed=recovered.stale_failed,
        legacy_failed=recovered.legacy_failed,
        reconciled_controls=reconciled_controls,
    )
    task_worker = get_task_worker()
    await task_worker.start()
    logger.info("persistent_task_worker_started", worker_id=task_worker.worker_id)
    return task_worker


async def shutdown_application_services(
    task_worker: PersistentTaskWorker | None,
) -> None:
    """按依赖顺序停止 worker、checkpointer 和数据库。"""
    try:
        if task_worker is not None:
            await task_worker.stop()
    finally:
        try:
            await teardown_persistent_checkpointer()
        finally:
            await close_db()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("xIaoShuo API starting up...")
    validate_encryption_key()
    validate_admin_token()
    await init_db()
    logger.info("Database initialized")

    # 初始化持久化 checkpointer（HITL interrupt/resume 必需，sqlite 模式持久化 graph 状态）
    try:
        await setup_persistent_checkpointer()
    except BaseException:
        await close_db()
        raise

    task_worker = None
    try:
        # 注入 AgentJournal 服务到 core 层记录器端口（依赖反转）
        # Sub-Agent 通过 get_journal_recorder() 访问日志记录器，无需直接依赖 api 层
        from src.api.services.agent_journal_service import get_journal_service

        get_journal_service()
        logger.info("agent_journal_recorder_registered")

        # 初始化 LLMClient 全局单例 — 优先使用数据库激活配置
        from sqlalchemy import select as _sa_select

        import src.core.llm.client as _llm_module
        from src.api.models.db_models import LLMConfig as _LLMConfig
        from src.core.database import get_db_session as _get_db_session
        from src.core.llm.client import LLMClient as _LLMClient

        try:
            async with _get_db_session() as _session:
                _result = await _session.execute(
                    _sa_select(_LLMConfig)
                    .where(_LLMConfig.is_active.is_(True))
                    .limit(1)
                )
                _active_config = _result.scalar_one_or_none()

            if _active_config is not None:
                _llm_module._client = _LLMClient(llm_config=_active_config)
                logger.info(
                    "llm_client_initialized_from_db",
                    config_name=_active_config.name,
                )
            else:
                _llm_module._client = _LLMClient()
                logger.info("llm_client_initialized_from_settings")
        except Exception as _exc:
            logger.warning(
                "llm_client_init_fallback",
                error=str(_exc),
                message="Falling back to Settings-based LLMClient",
            )
            _llm_module._client = _LLMClient()

        # Validate API Key at startup
        placeholder_keys = {
            "",
            "dummy_key_for_compilation",
            "your-api-key-here",
            "your_api_key_here",
            "sk-placeholder",
        }
        api_key = (settings.DEEPSEEK_API_KEY or "").strip()
        if not api_key or api_key.lower() in placeholder_keys:
            logger.warning(
                "api_key_not_configured",
                message=(
                    "DEEPSEEK_API_KEY is a placeholder or empty. "
                    "Chapter generation will fail. "
                    "Please set a valid API key in .env and restart."
                ),
            )

        task_worker = await start_task_queue()
        logger.info("API documentation available at http://localhost:8000/docs")
        yield
    finally:
        logger.info("xIaoShuo API shutting down...")
        await shutdown_application_services(task_worker)
        logger.info("Database connections closed")


# 创建 FastAPI 应用
app = FastAPI(
    title="xIaoShuo API",
    description="AI 中文小说生成平台 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 添加 CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(auth_router)
app.include_router(health_router)
app.include_router(inspiration_router)
app.include_router(novels_router)
app.include_router(tasks_router)
app.include_router(projects_router)
app.include_router(book_import_router)
app.include_router(careers_router)
app.include_router(characters_router)
app.include_router(chapters_router)
app.include_router(chapter_analysis_router)
app.include_router(creative_control_router)
app.include_router(conversations_router)
app.include_router(style_router)
app.include_router(outlines_router)
app.include_router(storylines_router)
app.include_router(knowledge_graph_router)
app.include_router(ws_router)
app.include_router(story_bible_router)
app.include_router(export_router)
app.include_router(outline_sync_router)
app.include_router(reader_simulation_router)
app.include_router(review_router)
app.include_router(llm_config_router)
app.include_router(volumes_router)
app.include_router(world_router)

# 挂载前端静态文件
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        """Serve frontend SPA — fallback to index.html for client-side routing.

        安全：解析路径后校验仍在 FRONTEND_DIR 内，防止目录穿越
        （如 /../../pyproject.toml 读取服务端任意文件）。
        """
        # 解析为绝对路径并校验仍在 FRONTEND_DIR 内（防穿越）
        target = (FRONTEND_DIR / path).resolve()
        try:
            target.relative_to(FRONTEND_DIR.resolve())
        except ValueError:
            # 路径逃出 FRONTEND_DIR，拒绝（返回 index.html 而非泄露文件）
            return FileResponse(FRONTEND_DIR / "index.html")
        if target.is_file():
            return FileResponse(target)
        return FileResponse(FRONTEND_DIR / "index.html")
else:

    @app.get("/")
    async def root():
        """根路径"""
        return {
            "message": "Welcome to xIaoShuo API",
            "docs": "/docs",
            "health": "/api/v1/health",
        }
