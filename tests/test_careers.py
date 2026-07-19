"""Career system API tests."""

import sys
import types

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

crypto_stub = types.ModuleType("src.core.security.crypto")
crypto_stub.decrypt_string = lambda value: value
crypto_stub.encrypt_string = lambda value: value
crypto_stub.validate_encryption_key = lambda: None
sys.modules.setdefault("src.core.security.crypto", crypto_stub)

from src.api.main import app  # noqa: E402
from src.api.models.db_models import (  # noqa: E402
    CareerSystem,
    Character,
    CharacterCareer,
    Novel,
)
from src.core.auth_models import User  # noqa: E402
from src.core.database import Base, get_db_session, get_engine  # noqa: E402

NOVEL_ID = "career-test-novel"


@pytest.fixture(scope="module")
async def _db_setup():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with get_db_session() as session:
        if not await session.get(User, 1):
            session.add(User(id=1, username="test_user", hashed_password="mocked", is_admin=True))
        existing = await session.execute(
            select(Novel).where(Novel.novel_id == NOVEL_ID)
        )
        if not existing.scalar_one_or_none():
            session.add(Novel(
                novel_id=NOVEL_ID,
                title="职业体系测试小说",
                idea="主角在灵能都市中通过职业与阶段成长破局",
                novel_type="玄幻",
                target_words=100000,
                status="draft",
                owner_id=1,
            ))

    yield

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(_db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_generate_careers_persists_generated_systems(client, monkeypatch):
    async def fake_generate(client, project_context, main_count=2, sub_count=6):
        assert project_context["novel_id"] == NOVEL_ID
        assert main_count == 1
        assert sub_count == 1
        return [
            {
                "name": "灵能战士",
                "category": "main",
                "description": "以灵能强化战斗",
                "stages": [{"level": 1, "name": "启灵", "description": "觉醒"}],
                "max_stage": 1,
                "requirements": "灵能亲和",
                "special_abilities": "灵刃",
                "worldview_rules": "消耗灵压",
                "attribute_bonuses": {"strength": "+10%"},
            },
            {
                "name": "符文匠",
                "category": "sub",
                "description": "制作符文器具",
                "stages": [{"level": 1, "name": "学徒", "description": "刻符"}],
                "max_stage": 1,
                "requirements": "识字",
                "special_abilities": "刻印",
                "worldview_rules": "依赖材料",
                "attribute_bonuses": {"crafting": "+10%"},
            },
        ]

    monkeypatch.setattr("src.api.routes.careers.generate_career_system", fake_generate)

    response = await client.post(
        f"/api/v1/projects/{NOVEL_ID}/careers/generate",
        json={"main_count": 1, "sub_count": 1},
    )

    assert response.status_code == 201
    data = response.json()
    assert [career["name"] for career in data] == ["灵能战士", "符文匠"]
    assert data[0]["attribute_bonuses"] == {"strength": "+10%"}


@pytest.mark.asyncio
async def test_list_and_update_career(client):
    async with get_db_session() as session:
        career = CareerSystem(
            novel_id=NOVEL_ID,
            name="影行者",
            category="main",
            description="潜行职业",
            stages=[{"level": 1, "name": "潜影", "description": "隐匿"}],
            max_stage=3,
            requirements="敏捷",
            special_abilities="影步",
            worldview_rules="不能在强光下发动",
            attribute_bonuses={"agility": "+8%"},
        )
        session.add(career)
        await session.flush()
        career_id = career.id

    response = await client.get(f"/api/v1/projects/{NOVEL_ID}/careers")
    assert response.status_code == 200
    assert "影行者" in [career["name"] for career in response.json()]

    response = await client.put(
        f"/api/v1/projects/{NOVEL_ID}/careers/{career_id}",
        json={"description": "更新后的潜行职业", "max_stage": 4},
    )
    assert response.status_code == 200

    response = await client.get(f"/api/v1/projects/{NOVEL_ID}/careers")
    updated = next(c for c in response.json() if c["id"] == career_id)
    assert updated["description"] == "更新后的潜行职业"
    assert updated["max_stage"] == 4


@pytest.mark.asyncio
async def test_assign_character_career(client):
    async with get_db_session() as session:
        character = Character(novel_id=NOVEL_ID, name="林澈", role="主角")
        career = CareerSystem(
            novel_id=NOVEL_ID,
            name="灵契师",
            category="main",
            description="与灵体签订契约",
            stages=[
                {"level": 1, "name": "初契", "description": "完成契约"},
                {"level": 2, "name": "共鸣", "description": "同步灵体"},
            ],
            max_stage=2,
            attribute_bonuses={"spirit": "+12%"},
        )
        session.add(character)
        session.add(career)
        await session.flush()
        char_id = character.id
        career_id = career.id

    response = await client.post(
        f"/api/v1/projects/{NOVEL_ID}/characters/{char_id}/careers",
        json={"career_id": career_id, "current_stage": 2},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["character_id"] == char_id
    assert data["career_id"] == career_id
    assert data["current_stage"] == 2
    assert data["status"] == "created"


@pytest.mark.asyncio
async def test_bulk_save_careers_upserts_by_name(client):
    """Frontend posts the full career list (with string pseudo-ids)."""
    payload = [
        {
            "id": "def-xiuxian",  # frontend LocalStorage pseudo-id
            "name": "九天御雷真仙",
            "category": "修仙",
            "description": "御雷真仙体系",
            "stages": [
                {"level": 1, "name": "感气引雷", "description": "吞吐灵气"},
                {"level": 2, "name": "凝雷入脉", "description": "雷霆游走"},
            ],
        },
        {
            "name": "符文匠",
            "category": "魔法",
            "description": "刻符",
            "stages": [{"level": 1, "name": "学徒", "description": "刻符"}],
        },
    ]

    response = await client.post(
        f"/api/v1/projects/{NOVEL_ID}/careers", json=payload
    )
    assert response.status_code == 200
    saved = response.json()
    assert [c["name"] for c in saved] == ["九天御雷真仙", "符文匠"]
    # Stable integer ids assigned by the DB (not the string pseudo-id).
    assert all(isinstance(c["id"], int) for c in saved)
    lei_id = next(c["id"] for c in saved if c["name"] == "九天御雷真仙")

    # Second post updates an existing name (upsert) and adds no duplicate.
    updated_payload = [
        {
            "id": "def-xiuxian",
            "name": "九天御雷真仙",
            "category": "修仙",
            "description": "更新后的描述",
            "stages": [{"level": 1, "name": "感气引雷", "description": "新描述"}],
        },
    ]
    response = await client.post(
        f"/api/v1/projects/{NOVEL_ID}/careers", json=updated_payload
    )
    assert response.status_code == 200
    again = response.json()
    assert len(again) == 1
    assert again[0]["id"] == lei_id  # same row, updated in place
    assert again[0]["description"] == "更新后的描述"


@pytest.mark.asyncio
async def test_list_character_careers_returns_stage_index(client):
    async with get_db_session() as session:
        character = Character(novel_id=NOVEL_ID, name="沐青", role="配角")
        career = CareerSystem(
            novel_id=NOVEL_ID,
            name="剑修",
            category="武道",
            description="以剑入道",
            stages=[
                {"level": 1, "name": "执剑", "description": "初执"},
                {"level": 2, "name": "剑意", "description": "凝意"},
                {"level": 3, "name": "剑心", "description": "明心"},
            ],
            max_stage=3,
        )
        session.add(character)
        session.add(career)
        await session.flush()
        char_id = character.id
        career_id = career.id
        session.add(
            CharacterCareer(
                character_id=char_id, career_id=career_id, current_stage=3
            )
        )
        await session.flush()

    response = await client.get(
        f"/api/v1/projects/{NOVEL_ID}/characters/careers"
    )
    assert response.status_code == 200
    data = response.json()
    match = next(a for a in data if a["character_id"] == char_id)
    assert match["career_id"] == career_id
    # current_stage=3 (level) -> stage_index=2 (0-based array index).
    assert match["stage_index"] == 2


@pytest.mark.asyncio
async def test_save_character_career_translates_stage_index(client):
    async with get_db_session() as session:
        character = Character(novel_id=NOVEL_ID, name="苏砚", role="主角")
        career = CareerSystem(
            novel_id=NOVEL_ID,
            name="丹师",
            category="修仙",
            description="炼丹",
            stages=[
                {"level": 1, "name": "识药", "description": "辨药"},
                {"level": 2, "name": "合丹", "description": "成丹"},
            ],
            max_stage=2,
        )
        session.add(character)
        session.add(career)
        await session.flush()
        char_id = character.id
        career_id = career.id

    # stage_index=1 (0-based) -> current_stage=2 (level).
    response = await client.post(
        f"/api/v1/projects/{NOVEL_ID}/characters/careers",
        json={
            "character_id": char_id,
            "career_id": career_id,
            "stage_index": 1,
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "created"
    assert data["current_stage"] == 2

    async with get_db_session() as session:
        row = (
            await session.execute(
                select(CharacterCareer).where(
                    CharacterCareer.character_id == char_id
                )
            )
        ).scalar_one()
        assert row.current_stage == 2

    # Empty career_id clears the assignment (frontend "暂无职业").
    response = await client.post(
        f"/api/v1/projects/{NOVEL_ID}/characters/careers",
        json={
            "character_id": char_id,
            "career_id": "",
            "stage_index": 0,
        },
    )
    assert response.status_code == 201
    assert response.json()["status"] == "cleared"

    async with get_db_session() as session:
        rows = (
            await session.execute(
                select(CharacterCareer).where(
                    CharacterCareer.character_id == char_id
                )
            )
        ).scalars().all()
        assert rows == []


@pytest.mark.asyncio
async def test_delete_career_idempotent_for_pseudo_id(client):
    async with get_db_session() as session:
        career = CareerSystem(
            novel_id=NOVEL_ID,
            name="阵法师",
            category="魔法",
            description="布阵",
            stages=[{"level": 1, "name": "识阵", "description": "辨阵"}],
        )
        session.add(career)
        await session.flush()
        career_id = career.id

    # Numeric id deletes the real row.
    response = await client.delete(
        f"/api/v1/projects/{NOVEL_ID}/careers/{career_id}"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "deleted"

    # String pseudo-id (no DB row) is an idempotent no-op.
    response = await client.delete(
        f"/api/v1/projects/{NOVEL_ID}/careers/def-xiuxian"
    )
    assert response.status_code == 200
    assert response.json()["status"] == "noop"
