"""任务/长篇接口鉴权回归测试（Task 3）。

使用真实双用户 + 真实 session token（不依赖 conftest 的 admin override），
覆盖：任务详情跨用户 403、任务列表按 owner 过滤、cleanup/stale 非管理员 403、
任务取消跨用户 403。匿名请求返回 401。
"""

import secrets
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.api.models.db_models import Novel, Task
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
async def two_users(_db_setup):
    """创建两个真实用户 + session token + user_a 的 novel/task。

    返回 dict: a_id, token_a, b_id, token_b, task_id, novel_id
    """
    suffix = secrets.token_hex(4)
    async with get_db_session() as session:
        a = User(username=f"auth_a_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        b = User(username=f"auth_b_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        session.add(a)
        session.add(b)
        await session.flush()
        a_id, b_id = a.id, b.id
        novel_id = f"auth-test-novel-{suffix}"
        task_id = f"auth-task-{suffix}"
        session.add(Novel(novel_id=novel_id, title="鉴权测试小说", idea="测试",
                         novel_type="玄幻", target_words=10000, status="draft", owner_id=a_id))
        await session.flush()
        session.add(Task(task_id=task_id, novel_id=novel_id, owner_id=a_id,
                         status="pending", idea="测试", novel_type="玄幻",
                         target_words=10000, created_at=datetime.now(UTC)))
    token_a = await create_session(a_id)
    token_b = await create_session(b_id)
    return {"a_id": a_id, "token_a": token_a, "b_id": b_id,
            "token_b": token_b, "task_id": task_id, "novel_id": novel_id}


@pytest.fixture
async def client(_db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_get_task_detail_cross_user_forbidden(client, two_users):
    """user B 读 user A 的任务详情 → 403。"""
    r = await client.get(f"/api/v1/novels/{two_users['task_id']}", headers=_bearer(two_users["token_a"]))
    assert r.status_code == 200, r.text
    r = await client.get(f"/api/v1/novels/{two_users['task_id']}", headers=_bearer(two_users["token_b"]))
    assert r.status_code == 403, r.text


async def test_anonymous_get_task_detail_unauthorized(client, two_users):
    """匿名请求 → 401（临时移除 conftest 的 admin override，测真实认证）。"""
    from src.api.main import app
    from src.core.security.auth import get_current_user

    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        r = await client.get(f"/api/v1/novels/{two_users['task_id']}")
        assert r.status_code == 401, r.text
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved


async def test_list_tasks_filtered_by_owner(client, two_users):
    """GET /api/v1/novels 只返回调用者自己的任务。"""
    r_a = await client.get("/api/v1/novels", headers=_bearer(two_users["token_a"]))
    assert r_a.status_code == 200
    a_ids = [t["task_id"] for t in r_a.json()["tasks"]]
    assert two_users["task_id"] in a_ids, f"user A 应看到自己的任务，实际 {a_ids}"
    r_b = await client.get("/api/v1/novels", headers=_bearer(two_users["token_b"]))
    assert r_b.status_code == 200
    b_ids = [t["task_id"] for t in r_b.json()["tasks"]]
    assert two_users["task_id"] not in b_ids, f"user B 不应看到 A 的任务，实际 {b_ids}"


async def test_cleanup_stale_requires_admin(client, two_users):
    """cleanup/stale 影响所有用户任务 → 非管理员 403。"""
    r = await client.post("/api/v1/novels/cleanup/stale", headers=_bearer(two_users["token_b"]))
    assert r.status_code == 403, r.text


async def test_cancel_task_cross_user_forbidden(client, two_users):
    """user B 取消 user A 的任务 → 403。"""
    r = await client.post(f"/api/v1/novels/{two_users['task_id']}/cancel", headers=_bearer(two_users["token_b"]))
    assert r.status_code == 403, r.text
