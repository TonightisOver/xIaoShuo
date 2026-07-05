"""LLM 配置路由测试（CHANGE-051 T6）"""

import os
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

os.environ["ADMIN_TOKEN"] = "secret"
os.environ.setdefault(
    "LLM_ENCRYPTION_KEY",
    "8bj5PGK84njNhOHlIV64dHHMh7QGgdrNKm5eozsXDKY=",
)

from src.api.main import app
from src.core.database import Base, get_engine
from src.core.security import crypto

ADMIN_HEADERS = {"X-Admin-Token": "secret"}


@pytest.fixture(scope="module")
async def _db_setup():
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
async def client(_db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(
        transport=transport,
        base_url="http://test",
        headers=ADMIN_HEADERS,
    ) as ac:
        yield ac


# ---------------------------------------------------------------------------
# GET /api/v1/llm/configs
# ---------------------------------------------------------------------------


async def test_list_configs_empty(client):
    """空列表时返回 200 和空数组"""
    response = await client.get("/api/v1/llm/configs")
    assert response.status_code == 200
    assert response.json() == []


# ---------------------------------------------------------------------------
# POST /api/v1/llm/configs
# ---------------------------------------------------------------------------


async def test_create_config(client):
    """创建配置返回 201，api_key 脱敏"""
    payload = {
        "name": "测试配置",
        "base_url": "https://api.example.com/v1",
        "api_key": "sk-secret-key-1234",
        "model_flash": "flash-model",
        "model_pro": "pro-model",
    }
    response = await client.post("/api/v1/llm/configs", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "测试配置"
    assert data["base_url"] == "https://api.example.com/v1"
    # api_key 应脱敏
    assert "sk-secret-key-1234" not in data["api_key"]
    assert data["api_key"].endswith("1234")
    assert data["api_key"].startswith("****")
    assert data["is_active"] is False
    assert "id" in data
    return data["id"]


# ---------------------------------------------------------------------------
# PUT /api/v1/llm/configs/{id}
# ---------------------------------------------------------------------------


async def test_update_config(client):
    """更新配置"""
    # 先创建
    create_resp = await client.post(
        "/api/v1/llm/configs",
        json={
            "name": "原始名称",
            "base_url": "https://api.example.com/v1",
            "api_key": "sk-abcdefgh",
            "model_flash": "flash",
            "model_pro": "pro",
        },
    )
    config_id = create_resp.json()["id"]

    # 更新名称
    update_resp = await client.put(
        f"/api/v1/llm/configs/{config_id}",
        json={"name": "新名称"},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["name"] == "新名称"


async def test_update_config_not_found(client):
    """更新不存在的配置返回 404"""
    response = await client.put(
        "/api/v1/llm/configs/99999",
        json={"name": "不存在"},
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/llm/configs/{id}/activate
# ---------------------------------------------------------------------------


async def test_activate_config(client):
    """激活配置后，其他配置 is_active 变为 False"""
    # 创建两个配置
    cfg1 = (
        await client.post(
            "/api/v1/llm/configs",
            json={
                "name": "配置A",
                "base_url": "https://a.com",
                "api_key": "key-aaaa",
                "model_flash": "flash-a",
                "model_pro": "pro-a",
            },
        )
    ).json()
    cfg2 = (
        await client.post(
            "/api/v1/llm/configs",
            json={
                "name": "配置B",
                "base_url": "https://b.com",
                "api_key": "key-bbbb",
                "model_flash": "flash-b",
                "model_pro": "pro-b",
            },
        )
    ).json()

    # 激活 cfg1
    resp = await client.post(f"/api/v1/llm/configs/{cfg1['id']}/activate")
    assert resp.status_code == 200
    assert resp.json()["is_active"] is True

    # 激活 cfg2 — cfg1 应变为非激活
    resp2 = await client.post(f"/api/v1/llm/configs/{cfg2['id']}/activate")
    assert resp2.status_code == 200
    assert resp2.json()["is_active"] is True

    # 查询列表，确认只有 cfg2 激活
    list_resp = await client.get("/api/v1/llm/configs")
    configs = list_resp.json()
    active_configs = [c for c in configs if c["is_active"]]
    assert len(active_configs) == 1
    assert active_configs[0]["id"] == cfg2["id"]


async def test_activate_config_reloads_runtime_llm_client(client):
    """激活配置后立即刷新进程内 LLMClient 单例。"""
    import src.core.llm.client as llm_module

    llm_module._client = None
    cfg = (
        await client.post(
            "/api/v1/llm/configs",
            json={
                "name": "运行时刷新",
                "base_url": "https://runtime.com",
                "api_key": "key-runtime",
                "model_flash": "flash-runtime",
                "model_pro": "pro-runtime",
            },
        )
    ).json()

    with patch("src.core.llm.client.LLMClient") as mock_client_cls:
        resp = await client.post(f"/api/v1/llm/configs/{cfg['id']}/activate")

    assert resp.status_code == 200
    mock_client_cls.assert_called_once()
    assert llm_module._client is mock_client_cls.return_value
    active_config = mock_client_cls.call_args.kwargs["llm_config"]
    assert active_config.id == cfg["id"]
    assert active_config.model_flash == "flash-runtime"


async def test_activate_config_not_found(client):
    """激活不存在的配置返回 404"""
    response = await client.post("/api/v1/llm/configs/99999/activate")
    assert response.status_code == 404


async def test_update_active_config_reloads_runtime_llm_client(client):
    """更新已激活配置后立即刷新进程内 LLMClient 单例。"""
    import src.core.llm.client as llm_module

    llm_module._client = None
    cfg = (
        await client.post(
            "/api/v1/llm/configs",
            json={
                "name": "更新刷新",
                "base_url": "https://update.com",
                "api_key": "key-update",
                "model_flash": "flash-before",
                "model_pro": "pro-before",
            },
        )
    ).json()

    await client.post(f"/api/v1/llm/configs/{cfg['id']}/activate")

    with patch("src.core.llm.client.LLMClient") as mock_client_cls:
        resp = await client.put(
            f"/api/v1/llm/configs/{cfg['id']}",
            json={"model_flash": "flash-after", "model_pro": "pro-after"},
        )

    assert resp.status_code == 200
    mock_client_cls.assert_called_once()
    assert llm_module._client is mock_client_cls.return_value
    active_config = mock_client_cls.call_args.kwargs["llm_config"]
    assert active_config.model_flash == "flash-after"
    assert active_config.model_pro == "pro-after"


# ---------------------------------------------------------------------------
# DELETE /api/v1/llm/configs/{id}
# ---------------------------------------------------------------------------


async def test_delete_inactive_config(client):
    """删除非激活配置成功"""
    cfg = (
        await client.post(
            "/api/v1/llm/configs",
            json={
                "name": "待删除",
                "base_url": "https://del.com",
                "api_key": "key-del",
                "model_flash": "flash",
                "model_pro": "pro",
            },
        )
    ).json()

    resp = await client.delete(f"/api/v1/llm/configs/{cfg['id']}")
    assert resp.status_code == 204


async def test_delete_active_config_rejected(client):
    """删除激活配置返回 400"""
    cfg = (
        await client.post(
            "/api/v1/llm/configs",
            json={
                "name": "激活配置",
                "base_url": "https://active.com",
                "api_key": "key-active",
                "model_flash": "flash",
                "model_pro": "pro",
            },
        )
    ).json()

    # 激活
    await client.post(f"/api/v1/llm/configs/{cfg['id']}/activate")

    # 尝试删除
    resp = await client.delete(f"/api/v1/llm/configs/{cfg['id']}")
    assert resp.status_code == 400


async def test_delete_config_not_found(client):
    """删除不存在的配置返回 404"""
    response = await client.delete("/api/v1/llm/configs/99999")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/v1/llm/token-stats
# ---------------------------------------------------------------------------


async def test_token_stats(client):
    """token-stats 返回 200 和正确结构"""
    response = await client.get("/api/v1/llm/token-stats")
    assert response.status_code == 200
    data = response.json()
    assert "total_calls" in data
    assert "records_skipped" in data
    assert "total_prompt_tokens" in data
    assert "total_completion_tokens" in data
    assert "total_tokens" in data
    assert "by_model" in data
    assert "recent_records" in data


# ---------------------------------------------------------------------------
# api_key 脱敏验证
# ---------------------------------------------------------------------------


async def test_api_key_masked_in_list(client):
    """GET /configs 返回的 api_key 不含完整密钥"""
    await client.post(
        "/api/v1/llm/configs",
        json={
            "name": "脱敏测试",
            "base_url": "https://mask.com",
            "api_key": "sk-very-secret-key-9999",
            "model_flash": "flash",
            "model_pro": "pro",
        },
    )
    resp = await client.get("/api/v1/llm/configs")
    configs = resp.json()
    for cfg in configs:
        assert "sk-very-secret-key-9999" not in cfg["api_key"]
        assert cfg["api_key"].startswith("****")
