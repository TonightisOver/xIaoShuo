"""API 路由测试"""

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.core.database import Base, get_engine


@pytest.fixture(scope="session")
async def _db_setup():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(_db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_root(client):
    """测试根路径"""
    response = await client.get("/")
    assert response.status_code == 200


async def test_health_check(client):
    """测试健康检查"""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "timestamp" in data


async def test_create_novel_task(client):
    """测试创建小说任务"""
    response = await client.post(
        "/api/v1/novels",
        json={
            "idea": "测试创意：一个程序员的修仙之路",
            "novel_type": "玄幻",
            "target_words": 50000,
        },
    )
    assert response.status_code == 202
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"
    assert data["estimated_duration_minutes"] == 70


async def test_create_novel_task_invalid_idea(client):
    """测试创建任务 - 无效创意"""
    response = await client.post(
        "/api/v1/novels",
        json={
            "idea": "短",
            "novel_type": "玄幻",
            "target_words": 50000,
        },
    )
    assert response.status_code == 422

    response = await client.post(
        "/api/v1/novels",
        json={
            "idea": "a" * 1001,
            "novel_type": "玄幻",
            "target_words": 50000,
        },
    )
    assert response.status_code == 422


async def test_create_novel_task_invalid_type(client):
    """测试创建任务 - 无效类型"""
    response = await client.post(
        "/api/v1/novels",
        json={
            "idea": "测试创意：一个程序员的修仙之路",
            "novel_type": "无效类型",
            "target_words": 50000,
        },
    )
    assert response.status_code == 400


async def test_get_novel_task(client):
    """测试查询任务"""
    create_response = await client.post(
        "/api/v1/novels",
        json={
            "idea": "测试创意：一个程序员的修仙之路",
            "novel_type": "玄幻",
            "target_words": 50000,
        },
    )
    task_id = create_response.json()["task_id"]

    response = await client.get(f"/api/v1/novels/{task_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert data["status"] in ["pending", "running", "completed", "failed"]


async def test_get_novel_task_not_found(client):
    """测试查询任务 - 任务不存在"""
    response = await client.get("/api/v1/novels/nonexistent-task-id")
    assert response.status_code == 404


async def test_list_novel_tasks(client):
    """测试列出任务"""
    response = await client.get("/api/v1/novels")
    assert response.status_code == 200
    data = response.json()
    assert "tasks" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert isinstance(data["tasks"], list)


async def test_list_novel_tasks_with_filters(client):
    """测试列出任务 - 带过滤条件"""
    response = await client.get("/api/v1/novels?status=completed")
    assert response.status_code == 200

    response = await client.get("/api/v1/novels?limit=5&offset=0")
    assert response.status_code == 200
    data = response.json()
    assert data["limit"] == 5
    assert data["offset"] == 0
