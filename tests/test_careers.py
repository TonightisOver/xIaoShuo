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
from src.api.models.db_models import CareerSystem, Character, Novel  # noqa: E402
from src.core.database import Base, get_db_session, get_engine  # noqa: E402

NOVEL_ID = "career-test-novel"


@pytest.fixture(scope="module")
async def _db_setup():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with get_db_session() as session:
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
