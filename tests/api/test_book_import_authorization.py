"""拆书导入鉴权回归测试（Task 4.2）。

book_import 原仅 create_task 不传 owner_id，get_status/apply 无 owner 校验，
导致跨用户访问他人导入任务、导入产生的小说成孤儿项目。
覆盖：导入任务绑定 owner、跨用户读 status/apply 抛权限错误、apply 产生的 novel owner 正确。
"""

import secrets

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.api.services.book_import_service import get_book_import_service
from src.api.services.content.novel_manager import get_novel_manager
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
    suffix = secrets.token_hex(4)
    async with get_db_session() as session:
        a = User(username=f"imp_a_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        b = User(username=f"imp_b_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        session.add(a)
        session.add(b)
        await session.flush()
        a_id, b_id = a.id, b.id
    token_a = await create_session(a_id)
    token_b = await create_session(b_id)
    return {"a_id": a_id, "token_a": token_a, "b_id": b_id, "token_b": token_b}


@pytest.fixture
async def client(_db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_import_task_bound_to_owner(two_users):
    """create_task 带 owner_id → status["owner_id"] == a_id。"""
    service = get_book_import_service()
    service.clear()
    task_id = service.create_task(
        [{"index": 1, "title": "序章", "content": "x"}], owner_id=two_users["a_id"]
    )
    status = service.get_status(task_id, owner_id=two_users["a_id"])
    assert status["owner_id"] == two_users["a_id"]


async def test_cross_user_get_status_forbidden(two_users):
    """user B 读 user A 的导入 status → PermissionError（路由转 403）。"""
    service = get_book_import_service()
    service.clear()
    task_id = service.create_task(
        [{"index": 1, "title": "序章", "content": "x"}], owner_id=two_users["a_id"]
    )
    with pytest.raises(PermissionError):
        service.get_status(task_id, owner_id=two_users["b_id"])


async def test_cross_user_apply_forbidden(two_users):
    """user B 应用 user A 的导入任务 → PermissionError。"""
    service = get_book_import_service()
    service.clear()
    task_id = service.create_task(
        [{"index": 1, "title": "序章", "content": "x"}], owner_id=two_users["a_id"]
    )
    # 手动置为 completed 以越过 status 检查，单测 owner 校验本身
    service._set_task(task_id, status="completed", analysis={"title": "t", "genre": "玄幻"})
    with pytest.raises(PermissionError):
        await service.apply_task(task_id, owner_id=two_users["b_id"])


async def test_cross_user_get_status_route_returns_403(client, two_users):
    """路由层：B 读 A 的导入 status → 403。"""
    service = get_book_import_service()
    service.clear()
    task_id = service.create_task(
        [{"index": 1, "title": "序章", "content": "x"}], owner_id=two_users["a_id"]
    )
    r = await client.get(
        f"/api/v1/projects/import-book/{task_id}/status",
        headers=_bearer(two_users["token_b"]),
    )
    assert r.status_code == 403, r.text


async def test_apply_project_inherits_owner(two_users):
    """apply 产生的 novel owner_id == 调用者（a）。"""
    service = get_book_import_service()
    service.clear()
    task_id = service.create_task(
        [{"index": 1, "title": "序章", "content": "x"}], owner_id=two_users["a_id"]
    )
    service._set_task(
        task_id, status="completed",
        analysis={"title": "孤儿测试", "genre": "玄幻", "characters": [],
                  "worldview": {"background": "", "rules": "", "geography": ""},
                  "foreshadows": [], "writing_style": {
                      "narrative_perspective": "", "language_features": "", "pacing_preference": ""}},
    )
    project = await service.apply_task(task_id, owner_id=two_users["a_id"])
    novel = await get_novel_manager().get_novel(project["novel_id"])
    assert novel is not None, "apply 应创建 novel"
    assert novel.get("owner_id") == two_users["a_id"], \
        f"导入产生的 novel 应归属 a，实际 owner_id={novel.get('owner_id')}"
