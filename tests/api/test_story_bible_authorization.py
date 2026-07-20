"""故事圣经鉴权回归测试（Task 4.1）。

story_bible GET/PUT 原无鉴权，任意用户可读写他人小说的设定（世界观/角色/伏笔等核心资产）。
覆盖：owner 读写 200、跨用户 GET 403、跨用户 PUT 403、匿名 GET/PUT 401。
"""

import secrets

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.api.models.db_models import Novel
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
        a = User(username=f"bible_a_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        b = User(username=f"bible_b_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        session.add(a)
        session.add(b)
        await session.flush()
        a_id, b_id = a.id, b.id
        novel_id = f"bible-novel-{suffix}"
        session.add(Novel(novel_id=novel_id, title="圣经测试", idea="t",
                         novel_type="玄幻", target_words=10000, status="draft", owner_id=a_id))
    token_a = await create_session(a_id)
    token_b = await create_session(b_id)
    return {"a_id": a_id, "token_a": token_a, "b_id": b_id,
            "token_b": token_b, "novel_id": novel_id}


@pytest.fixture
async def client(_db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_owner_can_read_and_write_bible(client, two_users):
    """owner GET 自动初始化空记录 → 200；PUT 写入 → 200。"""
    novel_id = two_users["novel_id"]
    r = await client.get(f"/api/v1/projects/{novel_id}/story-bible", headers=_bearer(two_users["token_a"]))
    assert r.status_code == 200, r.text
    r = await client.put(
        f"/api/v1/projects/{novel_id}/story-bible",
        headers=_bearer(two_users["token_a"]),
        json={"worldview_rules": "测试世界观"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["worldview_rules"] == "测试世界观"


async def test_cross_user_get_bible_forbidden(client, two_users):
    """user B 读 user A 的故事圣经 → 403。"""
    r = await client.get(
        f"/api/v1/projects/{two_users['novel_id']}/story-bible",
        headers=_bearer(two_users["token_b"]),
    )
    assert r.status_code == 403, r.text


async def test_cross_user_put_bible_forbidden(client, two_users):
    """user B 写 user A 的故事圣经 → 403。"""
    r = await client.put(
        f"/api/v1/projects/{two_users['novel_id']}/story-bible",
        headers=_bearer(two_users["token_b"]),
        json={"worldview_rules": "劫持"},
    )
    assert r.status_code == 403, r.text


async def test_anonymous_get_bible_unauthorized(client, two_users):
    """匿名 GET → 401。"""
    from src.api.main import app
    from src.core.security.auth import get_current_user

    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        r = await client.get(f"/api/v1/projects/{two_users['novel_id']}/story-bible")
        assert r.status_code == 401, r.text
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved
