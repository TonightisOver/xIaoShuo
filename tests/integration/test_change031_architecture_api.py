"""Integration tests for CHANGE-031: architecture cleanup.

Tests cover:
1. API endpoint behavior unchanged (power systems, characters CRUD)
2. Ownership validation via API (cross-novel access returns 404)
3. UniqueConstraint enforcement (duplicate insert raises IntegrityError)
"""

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from src.api.main import app
from src.api.models.db_models import Chapter, Novel, Volume
from src.core.auth_models import User
from src.core.database import Base, get_db_session, get_engine

NOVEL_A = "integ-031-novel-a"
NOVEL_B = "integ-031-novel-b"


@pytest.fixture(scope="module")
async def _db_setup():
    """Create tables and seed two novels for isolation tests."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with get_db_session() as session:
        # owner_id=1 需真实用户行；conftest 的 mock user id=1
        if not await session.get(User, 1):
            session.add(User(id=1, username="test_user", hashed_password="mocked", is_admin=True))
        for nid in (NOVEL_A, NOVEL_B):
            existing = await session.execute(
                select(Novel).where(Novel.novel_id == nid)
            )
            if not existing.scalar_one_or_none():
                session.add(Novel(
                    novel_id=nid,
                    title=f"集成测试小说 {nid}",
                    idea="集成测试用的小说创意描述内容",
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


# ============================================================
#  Power System ownership isolation
# ============================================================


class TestPowerSystemOwnership:
    """Verify power system CRUD respects novel_id ownership."""

    @pytest.mark.asyncio
    async def test_create_and_update_power_system(self, client):
        """Create under novel_a, update succeeds with correct novel_id."""
        resp = await client.post(
            f"/api/v1/projects/{NOVEL_A}/power-systems",
            json={"name": "修仙境界", "description": "从凡人到仙尊", "levels": []},
        )
        assert resp.status_code == 201
        ps_id = resp.json()["id"]

        # Update with correct novel_id
        resp = await client.put(
            f"/api/v1/projects/{NOVEL_A}/power-systems/{ps_id}",
            json={"name": "修仙境界v2", "description": "更新", "levels": []},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_cross_novel_update_power_system_returns_404(self, client):
        """Update power system via wrong novel_id returns 404."""
        # Create under novel_a
        resp = await client.post(
            f"/api/v1/projects/{NOVEL_A}/power-systems",
            json={"name": "隔离测试体系", "description": "test", "levels": []},
        )
        assert resp.status_code == 201
        ps_id = resp.json()["id"]

        # Attempt update via novel_b
        resp = await client.put(
            f"/api/v1/projects/{NOVEL_B}/power-systems/{ps_id}",
            json={"name": "篡改", "description": "should fail", "levels": []},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_novel_delete_power_system_returns_404(self, client):
        """Delete power system via wrong novel_id returns 404."""
        resp = await client.post(
            f"/api/v1/projects/{NOVEL_A}/power-systems",
            json={"name": "删除隔离测试", "description": "test", "levels": []},
        )
        assert resp.status_code == 201
        ps_id = resp.json()["id"]

        # Attempt delete via novel_b
        resp = await client.delete(
            f"/api/v1/projects/{NOVEL_B}/power-systems/{ps_id}",
        )
        assert resp.status_code == 404

        # Verify still exists under novel_a
        resp = await client.get(f"/api/v1/projects/{NOVEL_A}/power-systems")
        assert resp.status_code == 200
        names = [ps["name"] for ps in resp.json()]
        assert "删除隔离测试" in names


# ============================================================
#  Character ownership isolation
# ============================================================


class TestCharacterOwnership:
    """Verify character CRUD respects novel_id ownership."""

    @pytest.mark.asyncio
    async def test_create_and_update_character(self, client):
        """Create under novel_a, update succeeds with correct novel_id."""
        resp = await client.post(
            f"/api/v1/projects/{NOVEL_A}/characters",
            json={"name": "张三", "role": "主角", "description": "年轻修仙者"},
        )
        assert resp.status_code == 201
        char_id = resp.json()["id"]

        resp = await client.put(
            f"/api/v1/projects/{NOVEL_A}/characters/{char_id}",
            json={"name": "张三", "role": "主角", "description": "更新描述"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_cross_novel_update_character_returns_404(self, client):
        """Update character via wrong novel_id returns 404."""
        resp = await client.post(
            f"/api/v1/projects/{NOVEL_A}/characters",
            json={"name": "隔离角色", "role": "配角"},
        )
        assert resp.status_code == 201
        char_id = resp.json()["id"]

        resp = await client.put(
            f"/api/v1/projects/{NOVEL_B}/characters/{char_id}",
            json={"name": "篡改角色", "role": "主角"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_cross_novel_delete_character_returns_404(self, client):
        """Delete character via wrong novel_id returns 404."""
        resp = await client.post(
            f"/api/v1/projects/{NOVEL_A}/characters",
            json={"name": "删除隔离角色", "role": "配角"},
        )
        assert resp.status_code == 201
        char_id = resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/projects/{NOVEL_B}/characters/{char_id}",
        )
        assert resp.status_code == 404

        # Verify still exists
        resp = await client.get(f"/api/v1/projects/{NOVEL_A}/characters")
        assert resp.status_code == 200
        names = [c["name"] for c in resp.json()]
        assert "删除隔离角色" in names


# ============================================================
#  UniqueConstraint enforcement
# ============================================================


class TestUniqueConstraintEnforcement:
    """Verify DB-level unique constraints on Chapter and Volume."""

    @pytest.mark.asyncio
    async def test_duplicate_chapter_raises_integrity_error(self, _db_setup):
        """Inserting two chapters with same (novel_id, chapter_number) raises."""
        from sqlalchemy.exc import IntegrityError

        async with get_db_session() as session:
            ch1 = Chapter(
                novel_id=NOVEL_A,
                chapter_number=999,
                title="唯一约束测试章节",
                content="内容",
                word_count=2,
                status="generated",
            )
            session.add(ch1)

        with pytest.raises(IntegrityError):
            async with get_db_session() as session:
                ch2 = Chapter(
                    novel_id=NOVEL_A,
                    chapter_number=999,
                    title="重复章节",
                    content="重复内容",
                    word_count=4,
                    status="generated",
                )
                session.add(ch2)

    @pytest.mark.asyncio
    async def test_duplicate_volume_raises_integrity_error(self, _db_setup):
        """Inserting two volumes with same (novel_id, volume_number) raises."""
        from sqlalchemy.exc import IntegrityError

        async with get_db_session() as session:
            vol1 = Volume(
                novel_id=NOVEL_A,
                volume_number=999,
                title="唯一约束测试卷",
                status="draft",
            )
            session.add(vol1)

        with pytest.raises(IntegrityError):
            async with get_db_session() as session:
                vol2 = Volume(
                    novel_id=NOVEL_A,
                    volume_number=999,
                    title="重复卷",
                    status="draft",
                )
                session.add(vol2)

    @pytest.mark.asyncio
    async def test_same_chapter_number_different_novel_ok(self, _db_setup):
        """Same chapter_number under different novel_id is allowed."""
        async with get_db_session() as session:
            ch_a = Chapter(
                novel_id=NOVEL_A,
                chapter_number=998,
                title="A的章节",
                content="A",
                word_count=1,
                status="generated",
            )
            ch_b = Chapter(
                novel_id=NOVEL_B,
                chapter_number=998,
                title="B的章节",
                content="B",
                word_count=1,
                status="generated",
            )
            session.add(ch_a)
            session.add(ch_b)
        # No exception means success

    @pytest.mark.asyncio
    async def test_same_volume_number_different_novel_ok(self, _db_setup):
        """Same volume_number under different novel_id is allowed."""
        async with get_db_session() as session:
            vol_a = Volume(
                novel_id=NOVEL_A,
                volume_number=998,
                title="A的卷",
                status="draft",
            )
            vol_b = Volume(
                novel_id=NOVEL_B,
                volume_number=998,
                title="B的卷",
                status="draft",
            )
            session.add(vol_a)
            session.add(vol_b)
        # No exception means success
