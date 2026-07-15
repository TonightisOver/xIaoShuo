"""Pytest configuration and fixtures"""

import os

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

# Allow override via env var for Docker/nonstandard setups
# Try multiple database URLs for local vs Docker environments
_TEST_DB_URLS = [
    os.environ.get("TEST_DATABASE_URL"),
    "postgresql+asyncpg://xiaoshuo:xiaoshuo2026@localhost:5432/xiaoshuo_test",
    "postgresql+asyncpg://xiaoshuo:xiaoshuo2026@localhost:5433/xiaoshuo_test?ssl=disable",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
    "postgresql+asyncpg://a1:@localhost:5432/postgres",
]

TEST_DATABASE_URL = None
for url in _TEST_DB_URLS:
    if url:
        TEST_DATABASE_URL = url
        break

# Test Fernet key for LLM_ENCRYPTION_KEY
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

    # Override authentication globally for integration tests
    from src.api.main import app
    from src.core.auth_models import User
    from src.core.database import get_db_session
    from src.core.security.auth import get_current_user

    async def mock_get_current_user():
        user = User(id=1, username="test_user", hashed_password="mocked_password", is_admin=True)
        try:
            async with get_db_session() as session:
                db_user = await session.get(User, 1)
                if not db_user:
                    session.add(User(id=1, username="test_user", hashed_password="mocked_password", is_admin=True))
        except Exception:
            pass
        return user

    app.dependency_overrides[get_current_user] = mock_get_current_user


def pytest_unconfigure(config):
    """Cleanup after tests"""
    from src.core.security import crypto
    crypto._get_fernet.cache_clear()

    from src.api.main import app
    app.dependency_overrides.clear()

