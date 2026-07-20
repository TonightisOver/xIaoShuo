"""灵感向导 session 跨用户隔离测试（Task 4.3）。

inspiration session 原不绑 owner，session_id 已知即可被他人接续操作污染内容。
覆盖：service 层 start 绑 owner、process_step 跨用户抛 PermissionError、
路由层跨用户 step → 403（用非法 step 绕开 LLM 调用，避免外部依赖）。
"""

import secrets

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.api.services.content.inspiration_service import get_inspiration_wizard
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


@pytest.fixture(autouse=True)
def _clear_sessions():
    get_inspiration_wizard().clear()


@pytest.fixture
async def two_users(_db_setup):
    suffix = secrets.token_hex(4)
    async with get_db_session() as session:
        a = User(username=f"insp_a_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        b = User(username=f"insp_b_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
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


async def test_session_bound_to_owner(two_users):
    """start_session 带 owner_id → session["owner_id"] == a_id。"""
    wizard = get_inspiration_wizard()
    result = wizard.start_session(owner_id=two_users["a_id"])
    session_id = result["session_id"]
    session = wizard._sessions[session_id]
    assert session["owner_id"] == two_users["a_id"]


async def test_cross_user_process_step_raises_permission_error(two_users):
    """service 层：B 对 A 的 session 调 process_step → PermissionError。"""
    wizard = get_inspiration_wizard()
    wizard.start_session(owner_id=two_users["a_id"])
    # 取 A 创建的 session_id
    session_id = next(iter(wizard._sessions.keys()))
    with pytest.raises(PermissionError):
        await wizard.process_step(
            session_id=session_id,
            step="idea",
            user_input="劫持",
            owner_id=two_users["b_id"],
        )


async def test_cross_user_step_route_returns_403(client, two_users):
    """路由层：B 用 A 的 session_id step → 403（非法 step 绕开 LLM，只验 owner）。"""
    r = await client.post("/api/v1/inspiration/start", headers=_bearer(two_users["token_a"]))
    session_id = r.json()["session_id"]

    r_b = await client.post(
        f"/api/v1/inspiration/{session_id}/step",
        headers=_bearer(two_users["token_b"]),
        # 非法 step：owner 校验在 step 合法性之前，应先 403 而非 400
        json={"step": "bogus", "user_input": "x"},
    )
    assert r_b.status_code == 403, r_b.text


async def test_anonymous_start_unauthorized(client, two_users):
    """匿名 start → 401。"""
    from src.api.main import app
    from src.core.security.auth import get_current_user

    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        r = await client.post("/api/v1/inspiration/start")
        assert r.status_code == 401, r.text
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved
