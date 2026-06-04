"""LLM config admin auth and encryption tests."""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, text

from src.api.main import app
from src.api.models.db_models import LLMConfig
from src.core.database import Base, get_db_session, get_engine
from src.core.security import crypto

TEST_ENCRYPTION_KEY = "8bj5PGK84njNhOHlIV64dHHMh7QGgdrNKm5eozsXDKY="
ADMIN_HEADERS = {"X-Admin-Token": "secret"}


@pytest.fixture(autouse=True)
async def secure_env(monkeypatch):
    monkeypatch.setenv("LLM_ENCRYPTION_KEY", TEST_ENCRYPTION_KEY)
    monkeypatch.setenv("ADMIN_TOKEN", "secret")
    crypto._get_fernet.cache_clear()

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    crypto._get_fernet.cache_clear()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_llm_configs_unauthenticated_returns_403(client):
    response = await client.get("/api/v1/llm/configs")

    assert response.status_code == 403


async def test_llm_configs_admin_returns_200(client):
    response = await client.get("/api/v1/llm/configs", headers=ADMIN_HEADERS)

    assert response.status_code == 200
    assert response.json() == []


async def test_llm_config_api_key_encrypted_roundtrip(client):
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
        headers=ADMIN_HEADERS,
    )

    assert response.status_code == 201
    config_id = response.json()["id"]
    assert response.json()["api_key"] == "****1234"

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

    assert raw_value != payload["api_key"]
    assert raw_value.startswith("gAAAA")
    assert config.api_key == payload["api_key"]
