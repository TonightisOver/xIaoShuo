"""FastAPI 应用入口"""

from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import (
    book_import_router,
    careers_router,
    conversations_router,
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
    story_bible_router,
    storylines_router,
    style_router,
    tasks_router,
    ws_router,
)
from src.core.config import get_settings
from src.core.database import close_db, init_db
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("xIaoShuo API starting up...")
    validate_encryption_key()
    validate_admin_token()
    await init_db()
    logger.info("Database initialized")

    # 初始化 LLMClient 全局单例 — 优先使用数据库激活配置
    from sqlalchemy import select as _sa_select

    import src.core.llm.client as _llm_module
    from src.api.models.db_models import LLMConfig as _LLMConfig
    from src.core.database import get_db_session as _get_db_session
    from src.core.llm.client import LLMClient as _LLMClient

    try:
        async with _get_db_session() as _session:
            _result = await _session.execute(
                _sa_select(_LLMConfig).where(_LLMConfig.is_active.is_(True)).limit(1)
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

    logger.info("API documentation available at http://localhost:8000/docs")

    yield

    # Shutdown
    logger.info("xIaoShuo API shutting down...")
    await close_db()
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
app.include_router(health_router)
app.include_router(inspiration_router)
app.include_router(novels_router)
app.include_router(tasks_router)
app.include_router(projects_router)
app.include_router(book_import_router)
app.include_router(careers_router)
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
app.include_router(llm_config_router)

# 挂载前端静态文件
if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=FRONTEND_DIR / "assets"), name="static")

    @app.get("/{path:path}")
    async def serve_frontend(path: str):
        """Serve frontend SPA — fallback to index.html for client-side routing"""
        file = FRONTEND_DIR / path
        if file.exists() and file.is_file():
            return FileResponse(file)
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
