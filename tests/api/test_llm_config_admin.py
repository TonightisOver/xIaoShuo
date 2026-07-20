"""LLM 配置 GET 端点 admin 门禁测试（Task 5.2）。

list_configs / get_token_stats 原任意登录用户可读，泄露全局配置与用量。
覆盖：admin 200、普通用户 403、匿名 401。
"""

import secrets

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.core.auth_models import User
from src.core.database import Base, get_db_session, get_engine
from src.core.security.users import create_session, hash_password


@pytest.fixture(scope="module")
async def _db_setup():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def admin_and_user(_db_setup):
    suffix = secrets.token_hex(4)
    async with get_db_session() as session:
        admin = User(username=f"llmadmin_{suffix}", hashed_password=hash_password("pass1234"), is_admin=True)
        plain = User(username=f"llmuser_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        session.add(admin)
        session.add(plain)
        await session.flush()
        admin_id, plain_id = admin.id, plain.id
    token_admin = await create_session(admin_id)
    token_plain = await create_session(plain_id)
    return {"token_admin": token_admin, "token_plain": token_plain}


@pytest.fixture
async def client(_db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_list_configs_admin_ok(client, admin_and_user):
    r = await client.get("/api/v1/llm/configs", headers=_bearer(admin_and_user["token_admin"]))
    assert r.status_code == 200, r.text


async def test_list_configs_plain_user_forbidden(client, admin_and_user):
    r = await client.get("/api/v1/llm/configs", headers=_bearer(admin_and_user["token_plain"]))
    assert r.status_code == 403, r.text


async def test_token_stats_plain_user_forbidden(client, admin_and_user):
    r = await client.get("/api/v1/llm/token-stats", headers=_bearer(admin_and_user["token_plain"]))
    assert r.status_code == 403, r.text


async def test_anonymous_list_configs_unauthorized(client, admin_and_user):
    from src.api.main import app
    from src.core.security.auth import get_current_user

    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        r = await client.get("/api/v1/llm/configs")
        assert r.status_code == 401, r.text
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved
