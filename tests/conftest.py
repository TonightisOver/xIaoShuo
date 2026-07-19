"""Pytest configuration and fixtures"""

import asyncio
import os
import socket

import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

# Test Fernet key for LLM_ENCRYPTION_KEY
TEST_FERNET_KEY = "8bj5PGK84njNhOHlIV64dHHMh7QGgdrNKm5eozsXDKY="

# 候选测试 DB URL：环境变量优先；其后按本机常见配置逐一探测。
# 注意：写死条目仅为兼容多种本机/容器环境，不可在"环境变量已设"时被覆盖。
_CANDIDATE_DB_URLS = [
    os.environ.get("TEST_DATABASE_URL"),
    "postgresql+asyncpg://a1@localhost:5432/xiaoshuo_test",
    "postgresql+asyncpg://xiaoshuo:xiaoshuo2026@localhost:5432/xiaoshuo_test",
    "postgresql+asyncpg://xiaoshuo:xiaoshuo2026@localhost:5433/xiaoshuo_test",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
]


def _host_port_from_pg_url(url: str) -> tuple[str, int] | None:
    """从 postgresql+asyncpg://user:pwd@host:port/db 抽取 host/port。"""
    try:
        rest = url.split("://", 1)[1]
        authority = rest.split("/", 1)[0]
        host, _, port = authority.rpartition(":")
        port = port.split("?")[0]
        return host, int(port)
    except (IndexError, ValueError):
        return None


def _tcp_reachable(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _pg_login_ok(url: str) -> bool:
    """用 asyncpg 直接连一次确认登录/库存在。url 须是 asyncpg 可用的。"""
    pg_url = url.replace("postgresql+asyncpg://", "postgresql://")

    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(pg_url, timeout=2)
            await conn.close()
            return True
        except Exception:
            return False

    try:
        return asyncio.run(_check())
    except RuntimeError:
        return False


def _resolve_test_db_url() -> str:
    # 1) 环境变量优先（用户显式指定，不探测、不覆盖）
    env_url = os.environ.get("TEST_DATABASE_URL")
    if env_url:
        return env_url
    # 2) 逐一探测候选 URL：TCP 可达 + 登录成功
    for url in _CANDIDATE_DB_URLS:
        if not url:
            continue
        hp = _host_port_from_pg_url(url)
        if not hp or not _tcp_reachable(*hp):
            continue
        if _pg_login_ok(url):
            return url
    # 3) 全部不可达：给出可操作的报错，不要静默跑测试
    raise RuntimeError(
        "未找到可用的测试数据库。请二选一：\n"
        "  (a) export TEST_DATABASE_URL='postgresql+asyncpg://<user>@localhost:5432/xiaoshuo_test'\n"
        "  (b) 在本机 PostgreSQL 建库：createdb xiaoshuo_test\n"
        "确认 PostgreSQL 已启动且用户对该库有建表权限。"
    )


TEST_DATABASE_URL = _resolve_test_db_url()


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

