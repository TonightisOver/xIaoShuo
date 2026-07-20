"""LLM config auth and encryption tests.

安全模型（Task 5 后）：所有 LLM 配置端点（含 GET list/token-stats）均 require_admin_user。
测试注册的 llmadmin 用户通过 ADMIN_USERNAME 匹配标记为 admin。
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from src.api.main import app
from src.api.models.db_models import LLMConfig
from src.core.database import Base, get_db_session, get_engine
from src.core.security import crypto

TEST_ENCRYPTION_KEY = "8bj5PGK84njNhOHlIV64dHHMh7QGgdrNKm5eozsXDKY="


@pytest.fixture(autouse=True)
async def secure_env(monkeypatch):
    monkeypatch.setenv("LLM_ENCRYPTION_KEY", TEST_ENCRYPTION_KEY)
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    # 注册 username=llmadmin 的用户会被标记为 admin（auth.py register 逻辑）
    monkeypatch.setenv("ADMIN_USERNAME", "llmadmin")
    crypto._get_fernet.cache_clear()
    from src.core.config import get_settings
    get_settings.cache_clear()

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    crypto._get_fernet.cache_clear()
    get_settings.cache_clear()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _register_and_login(client, username="llmadmin", password="pass1234"):
    """注册并登录，返回 session token。"""
    await client.post(
        "/api/v1/auth/register",
        json={"username": username, "password": password},
    )
    res = await client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": password},
    )
    return res.json()["session_token"]


async def test_list_configs_requires_admin(client):
    """GET /configs 需 admin（Task 5.2）。匿名 401。"""
    from src.api.main import app
    from src.core.security.auth import get_current_user

    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await client.get("/api/v1/llm/configs")
        assert response.status_code == 401
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved


async def test_create_config_without_session_returns_401(client):
    """POST /configs 无 session token 返回 401。

    conftest 全局 mock 了 get_current_user，这里临时清除 override 验证真实认证。
    """
    from src.api.main import app
    from src.core.security.auth import get_current_user

    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        response = await client.post(
            "/api/v1/llm/configs",
            json={
                "name": "x", "base_url": "https://api.example.com/v1",
                "api_key": "sk-x", "model_flash": "f", "model_pro": "p",
            },
        )
        assert response.status_code == 401
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved


async def test_create_config_with_session_returns_201(client):
    """登录用户可创建 LLM 配置。"""
    token = await _register_and_login(client)
    payload = {
        "name": "secure-config",
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-secret-key-1234",
        "model_flash": "flash-model",
        "model_pro": "pro-model",
    }
    response = await client.post(
        "/api/v1/llm/configs",
        json=payload,
        headers={"x-session-token": token},
    )
    assert response.status_code == 201
    assert response.json()["api_key"] == "****1234"  # 脱敏


async def test_llm_config_api_key_encrypted_roundtrip(client):
    """api_key 在 DB 中加密存储，读取时解密。"""
    token = await _register_and_login(client)
    payload = {
        "name": "secure-config",
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-secret-key-1234",
        "model_flash": "flash-model",
        "model_pro": "pro-model",
    }
    response = await client.post(
        "/api/v1/llm/configs",
        json=payload,
        headers={"x-session-token": token},
    )
    assert response.status_code == 201
    config_id = response.json()["id"]

    async with get_db_session() as session:
        raw_value = (
            await session.execute(
                text("SELECT api_key FROM llm_configs WHERE id = :id"),
                {"id": config_id},
            )
        ).scalar_one()
        config = (
            await session.execute(select(LLMConfig).where(LLMConfig.id == config_id))
        ).scalar_one()

    assert raw_value != payload["api_key"]  # DB 中非明文
    assert raw_value.startswith("gAAAA")  # Fernet 加密前缀
    assert config.api_key == payload["api_key"]  # 解密后还原


async def test_activate_config_requires_session(client):
    """激活配置需登录（无 token 返回 401）。"""
    from src.api.main import app
    from src.core.security.auth import get_current_user

    token = await _register_and_login(client)
    # 先创建一个配置（用 session token）
    create = await client.post(
        "/api/v1/llm/configs",
        json={
            "name": "c1", "base_url": "u", "api_key": "k",
            "model_flash": "f", "model_pro": "p",
        },
        headers={"x-session-token": token},
    )
    cid = create.json()["id"]

    # 临时清除 auth override，验证无 token 激活 → 401
    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        no_auth = await client.post(f"/api/v1/llm/configs/{cid}/activate")
        assert no_auth.status_code == 401
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved

    # 带 token 激活 → 200
    ok = await client.post(
        f"/api/v1/llm/configs/{cid}/activate",
        headers={"x-session-token": token},
    )
    assert ok.status_code == 200
    assert ok.json()["is_active"] is True
