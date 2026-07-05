"""Pytest configuration and fixtures"""

import os

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

# Allow override via env var for Docker/nonstandard setups
TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://xiaoshuo:xiaoshuo2026@localhost:5433/xiaoshuo_test?ssl=disable",
)

# Test Fernet key for LLM_ENCRYPTION_KEY
# Must match the key used in test files (e.g., test_llm_config.py)
TEST_FERNET_KEY = "8bj5PGK84njNhOHlIV64dHHMh7QGgdrNKm5eozsXDKY="


def pytest_configure(config):
    """Override database URL and engine for all tests"""
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL
    # Set LLM_ENCRYPTION_KEY for tests (overwrite any existing value)
    os.environ["LLM_ENCRYPTION_KEY"] = TEST_FERNET_KEY

    from src.core.config import get_settings
    get_settings.cache_clear()

    from src.core import database
    from src.core.security import crypto

    # Replace engine with NullPool version to avoid event loop issues
    database._engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
    database._async_session_factory = None

    # Clear Fernet cache so new key takes effect
    crypto._get_fernet.cache_clear()


def pytest_unconfigure(config):
    """Cleanup after tests"""
    from src.core.security import crypto
    crypto._get_fernet.cache_clear()
