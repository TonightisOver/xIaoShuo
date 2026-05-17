"""FastAPI 应用入口"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.api.routes import (
    conversations_router,
    health_router,
    novels_router,
    outlines_router,
    projects_router,
    storylines_router,
    style_router,
    ws_router,
)
from src.core.config import get_settings
from src.core.database import close_db, init_db
from src.core.logging_config import setup_logging

# 设置日志
settings = get_settings()
setup_logging(log_level=settings.LOG_LEVEL, log_file=settings.LOG_FILE)

logger = logging.getLogger(__name__)

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("xIaoShuo API starting up...")
    await init_db()
    logger.info("Database initialized")
    logger.info(f"API documentation available at http://localhost:8000/docs")

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(health_router)
app.include_router(novels_router)
app.include_router(projects_router)
app.include_router(conversations_router)
app.include_router(style_router)
app.include_router(outlines_router)
app.include_router(storylines_router)
app.include_router(ws_router)

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
