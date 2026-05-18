"""跨小说数据隔离负例测试"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import app
from src.api.models.db_models import Character, Novel
from src.core.database import Base, get_db_session, get_engine

NOVEL_A = "isolation-novel-a"
NOVEL_B = "isolation-novel-b"


@pytest.fixture(scope="module")
async def _db_setup():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed two novels so FK constraints pass
    async with get_db_session() as session:
        for nid in (NOVEL_A, NOVEL_B):
            existing = await session.execute(
                select(Novel).where(Novel.novel_id == nid)
            )
            if not existing.scalar_one_or_none():
                session.add(Novel(
                    novel_id=nid,
                    title=f"隔离测试小说 {nid}",
                    idea="隔离测试用",
                    novel_type="玄幻",
                    target_words=10000,
                    status="draft",
                ))

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="module")
async def char_id_novel_a(_db_setup):
    """Create a character under novel_a and return its id."""
    async with get_db_session() as session:
        char = Character(novel_id=NOVEL_A, name="隔离测试角色")
        session.add(char)
        await session.flush()
        return char.id


@pytest.fixture
async def client(_db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_cross_novel_update_arc(client, char_id_novel_a):
    """跨小说改 arc：用 novel_B 的路由修改 novel_A 的 arc → 404"""
    # Create arc under novel_a
    resp = await client.post(
        f"/api/v1/projects/{NOVEL_A}/character-arcs",
        json={"character_id": char_id_novel_a, "arc_type": "growth",
              "description": "novel_a arc", "stages": []},
    )
    assert resp.status_code == 201
    arc_id = resp.json()["id"]

    # Attempt to update it via novel_b → must be 404
    resp = await client.put(
        f"/api/v1/projects/{NOVEL_B}/character-arcs/{arc_id}",
        json={"character_id": char_id_novel_a, "arc_type": "fall",
              "description": "should not update", "stages": []},
    )
    assert resp.status_code == 404, (
        f"Expected 404 updating arc {arc_id} of {NOVEL_A} via {NOVEL_B}, got {resp.status_code}"
    )

    # Verify arc is unchanged under novel_a
    arcs = await client.get(f"/api/v1/projects/{NOVEL_A}/character-arcs")
    assert arcs.status_code == 200
    arc = next((a for a in arcs.json() if a["id"] == arc_id), None)
    assert arc is not None
    assert arc["arc_type"] == "growth"


async def test_cross_novel_update_scene(client):
    """跨小说改 scene：用 novel_B 的路由修改 novel_A 的 scene → 404"""
    # Create scene under novel_a
    resp = await client.post(
        f"/api/v1/projects/{NOVEL_A}/scenes",
        json={"name": "novel_a scene", "location": "东方大陆",
              "description": "原始描述", "appearances": []},
    )
    assert resp.status_code == 201
    scene_id = resp.json()["id"]

    # Attempt to update it via novel_b → must be 404
    resp = await client.put(
        f"/api/v1/projects/{NOVEL_B}/scenes/{scene_id}",
        json={"name": "tampered", "location": "西方大陆",
              "description": "should not update", "appearances": []},
    )
    assert resp.status_code == 404, (
        f"Expected 404 updating scene {scene_id} of {NOVEL_A} via {NOVEL_B}, got {resp.status_code}"
    )

    # Verify scene is unchanged under novel_a
    scenes = await client.get(f"/api/v1/projects/{NOVEL_A}/scenes")
    assert scenes.status_code == 200
    scene = next((s for s in scenes.json() if s["id"] == scene_id), None)
    assert scene is not None
    assert scene["name"] == "novel_a scene"


async def test_cross_novel_confirm_message(client):
    """跨小说确认 message：用 novel_B 的路由确认 novel_A 的消息 → 404"""
    # Create conversation under novel_a
    resp = await client.post(
        f"/api/v1/projects/{NOVEL_A}/conversations",
        json={"topic": "隔离测试对话"},
    )
    assert resp.status_code == 201
    conv_id = resp.json()["id"]

    # Confirm with novel_b's context — conv belongs to novel_a, so must 404
    resp = await client.post(
        f"/api/v1/projects/{NOVEL_B}/conversations/{conv_id}/messages/99999/confirm",
        json={"confirm_as": "world"},
    )
    assert resp.status_code == 404, (
        f"Expected 404 confirming msg in {NOVEL_A} conv via {NOVEL_B}, got {resp.status_code}"
    )
