"""Database connection and session management"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from src.core.config import get_settings

logger = logging.getLogger(__name__)

Base = declarative_base()

# Global engine and session factory
_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """Get or create database engine"""
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.DATABASE_URL,
            pool_size=settings.DATABASE_POOL_SIZE,
            max_overflow=settings.DATABASE_MAX_OVERFLOW,
            echo=settings.DATABASE_ECHO,
            pool_pre_ping=True,
            pool_timeout=30,
            pool_recycle=1800,
        )
        logger.info("Database engine created")
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Get or create session factory"""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_engine()
        _async_session_factory = async_sessionmaker(
            engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_session_factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get database session context manager"""
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize database (create tables if not exist)"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 幂等添加 is_admin 列（P1-1 LLM 配置权限：标记 admin 用户）
        # 用 try/except 因为列已存在时 ALTER 会报错
        try:
            await conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT false"
                )
            )
        except Exception:
            pass  # 列已存在或语法不兼容（如旧 SQLite），忽略
    logger.info("Database tables initialized")


async def close_db() -> None:
    """Close database connections gracefully.

    Disposes the engine and clears the session factory. The application lifespan
    must stop ``PersistentTaskWorker`` before calling this function so an active
    generation handler and its lease heartbeat are cancelled before the pool is
    disposed. The engine's ``pool_pre_ping`` and connection recycling ensure stale
    connections are dropped cleanly.

    After this call, any subsequent ``get_db_session()`` will lazily recreate a
    fresh engine (useful in tests). Other long-running background coroutines must
    likewise drain themselves before shutdown to avoid ``ClosedPoolError``.
    """
    global _engine, _async_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _async_session_factory = None
        logger.info("Database connections closed")
