"""Pytest configuration and fixtures"""

import os

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

TEST_DATABASE_URL = "postgresql+asyncpg://xiaoshuo:xiaoshuo2026@localhost:5433/xiaoshuo_test?ssl=disable"


def pytest_configure(config):
    """Override database URL and engine for all tests"""
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    from src.core.config import get_settings
    get_settings.cache_clear()

    from src.core import database

    # Replace engine with NullPool version to avoid event loop issues
    database._engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    database._async_session_factory = None
