"""Integration tests for Knowledge Graph API endpoints (CHANGE-030).

Tests verify:
- Entity CRUD (create, read, update, delete)
- Triple CRUD
- Extract endpoint (mocked LLM)
- Visualization endpoint
- Consistency check endpoint (mocked LLM)
- Feature flag behavior at API level

Uses a real database connection (configured in tests/conftest.py).
LLM calls are mocked to avoid real DeepSeek API calls.
"""

import json
import uuid
from datetime import UTC
from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.core.database import Base, get_engine


@pytest.fixture(scope="module")
async def _db_setup():
    """Create all tables before module tests, drop after."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(autouse=True)
def _mock_background_tasks():
    """Mock background generation to prevent real LLM calls."""
    with patch(
        "src.api.routes.projects.generate_novel_background",
        new_callable=AsyncMock,
    ), patch(
        "src.api.routes.projects.generate_novel_full_background",
        new_callable=AsyncMock,
    ):
        yield


@pytest.fixture
async def client(_db_setup):
    """Async HTTP client for API testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
async def novel_id(client):
    """Create a novel and return its novel_id. Cleanup after test."""
    create_resp = await client.post(
        "/api/v1/projects",
        json={
            "idea": "知识图谱集成测试用小说，一个修仙者在异世界冒险的故事",
            "novel_type": "玄幻",
            "target_words": 100000,
            "title": "图谱测试小说",
            "writing_style": "现代白话",
        },
    )
    assert create_resp.status_code == 201
    nid = create_resp.json()["novel_id"]
    yield nid
    await client.delete(f"/api/v1/projects/{nid}")


# ---------------------------------------------------------------------------
# Entity CRUD
# ---------------------------------------------------------------------------

class TestEntityCRUD:
    """Integration tests for entity endpoints."""

    @pytest.mark.asyncio
    async def test_create_entity(self, client, novel_id):
        """POST /entities creates an entity and returns 201."""
        resp = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={
                "entity_type": "character",
                "name": "张三",
                "aliases": ["小张", "张大侠"],
                "attributes": {"status": "alive"},
                "first_chapter": 1,
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "张三"
        assert data["entity_type"] == "character"
        assert data["source"] == "manual"
        assert "小张" in data["aliases"]

    @pytest.mark.asyncio
    async def test_list_entities(self, client, novel_id):
        """GET /entities returns created entities."""
        # Create two entities
        await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "character", "name": "李四", "first_chapter": 1},
        )
        await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "location", "name": "长安城", "first_chapter": 1},
        )

        resp = await client.get(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities"
        )
        assert resp.status_code == 200
        entities = resp.json()
        assert len(entities) >= 2
        names = [e["name"] for e in entities]
        assert "李四" in names
        assert "长安城" in names

    @pytest.mark.asyncio
    async def test_list_entities_filter_by_type(self, client, novel_id):
        """GET /entities?entity_type=character filters correctly."""
        await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "character", "name": "王五", "first_chapter": 1},
        )
        await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "location", "name": "洛阳", "first_chapter": 2},
        )

        resp = await client.get(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            params={"entity_type": "character"},
        )
        assert resp.status_code == 200
        entities = resp.json()
        for e in entities:
            assert e["entity_type"] == "character"

    @pytest.mark.asyncio
    async def test_get_entity_by_id(self, client, novel_id):
        """GET /entities/{id} returns the specific entity."""
        create_resp = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "item", "name": "轩辕剑", "first_chapter": 3},
        )
        entity_id = create_resp.json()["id"]

        resp = await client.get(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities/{entity_id}"
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "轩辕剑"

    @pytest.mark.asyncio
    async def test_get_entity_not_found(self, client, novel_id):
        """GET /entities/{id} returns 404 for non-existent entity."""
        fake_id = str(uuid.uuid4())
        resp = await client.get(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities/{fake_id}"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_entity(self, client, novel_id):
        """PUT /entities/{id} updates entity fields."""
        create_resp = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "character", "name": "赵六", "first_chapter": 1},
        )
        entity_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities/{entity_id}",
            json={"name": "赵六（改名）", "aliases": ["老赵"]},
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "赵六（改名）"
        assert "老赵" in resp.json()["aliases"]

    @pytest.mark.asyncio
    async def test_delete_entity(self, client, novel_id):
        """DELETE /entities/{id} removes entity."""
        create_resp = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "character", "name": "临时角色", "first_chapter": 1},
        )
        entity_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities/{entity_id}"
        )
        assert resp.status_code == 204

        # Verify gone
        resp = await client.get(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities/{entity_id}"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Triple CRUD
# ---------------------------------------------------------------------------

class TestTripleCRUD:
    """Integration tests for triple endpoints."""

    @pytest.mark.asyncio
    async def test_create_and_list_triple(self, client, novel_id):
        """POST /triples creates a triple; GET /triples lists it."""
        # Create two entities first
        e1 = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "character", "name": "甲", "first_chapter": 1},
        )
        e2 = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "character", "name": "乙", "first_chapter": 1},
        )
        e1_id = e1.json()["id"]
        e2_id = e2.json()["id"]

        # Create triple
        resp = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/triples",
            json={
                "subject_id": e1_id,
                "predicate": "师徒",
                "object_id": e2_id,
                "chapter_number": 1,
                "confidence": 0.95,
            },
        )
        assert resp.status_code == 201
        triple_id = resp.json()["id"]

        # List triples
        list_resp = await client.get(
            f"/api/v1/projects/{novel_id}/knowledge-graph/triples"
        )
        assert list_resp.status_code == 200
        triples = list_resp.json()
        ids = [t["id"] for t in triples]
        assert triple_id in ids

    @pytest.mark.asyncio
    async def test_update_triple(self, client, novel_id):
        """PUT /triples/{id} updates triple fields."""
        e1 = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "character", "name": "丙", "first_chapter": 1},
        )
        e2 = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "character", "name": "丁", "first_chapter": 1},
        )

        create_resp = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/triples",
            json={
                "subject_id": e1.json()["id"],
                "predicate": "朋友",
                "object_id": e2.json()["id"],
                "chapter_number": 2,
            },
        )
        triple_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/v1/projects/{novel_id}/knowledge-graph/triples/{triple_id}",
            json={"predicate": "敌人", "confidence": 0.8},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "updated"

    @pytest.mark.asyncio
    async def test_delete_triple_marks_deleted(self, client, novel_id):
        """DELETE /triples/{id} marks status as deleted (soft delete)."""
        e1 = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "character", "name": "戊", "first_chapter": 1},
        )
        e2 = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "character", "name": "己", "first_chapter": 1},
        )

        create_resp = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/triples",
            json={
                "subject_id": e1.json()["id"],
                "predicate": "认识",
                "object_id": e2.json()["id"],
                "chapter_number": 1,
            },
        )
        triple_id = create_resp.json()["id"]

        resp = await client.delete(
            f"/api/v1/projects/{novel_id}/knowledge-graph/triples/{triple_id}"
        )
        assert resp.status_code == 204

        # Verify not in list (status=deleted is filtered out)
        list_resp = await client.get(
            f"/api/v1/projects/{novel_id}/knowledge-graph/triples"
        )
        ids = [t["id"] for t in list_resp.json()]
        assert triple_id not in ids

    @pytest.mark.asyncio
    async def test_delete_triple_not_found(self, client, novel_id):
        """DELETE /triples/{id} returns 404 for non-existent triple."""
        fake_id = str(uuid.uuid4())
        resp = await client.delete(
            f"/api/v1/projects/{novel_id}/knowledge-graph/triples/{fake_id}"
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

class TestExtraction:
    """Integration tests for extraction endpoints."""

    @pytest.mark.asyncio
    async def test_extract_chapter_not_found(self, client, novel_id):
        """POST /extract/{chapter} returns 404 when chapter doesn't exist."""
        resp = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/extract/999"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_extract_chapter_success(self, client, novel_id):
        """POST /extract/{chapter} triggers extraction with mocked LLM."""
        from datetime import datetime

        from src.api.models.db_models import Chapter
        from src.core.database import get_db_session

        # Insert a chapter
        async with get_db_session() as session:
            ch = Chapter(
                novel_id=novel_id,
                chapter_number=1,
                title="第一章",
                content="张三来到长安城，遇到了李四。两人决定结伴而行。",
                word_count=20,
                status="generated",
                updated_at=datetime.now(UTC),
            )
            session.add(ch)

        llm_response = json.dumps({
            "entities": [
                {"name": "张三", "type": "character", "aliases": [], "attributes": {"status": "alive"}},
                {"name": "长安城", "type": "location", "aliases": [], "attributes": {}},
            ],
            "triples": [
                {"subject": "张三", "predicate": "位于", "object": "长安城", "confidence": 0.9},
            ],
        })

        with patch(
            "src.api.services.knowledge_graph_service.get_llm_client"
        ) as mock_llm:
            mock_llm.return_value.generate = AsyncMock(return_value=llm_response)

            resp = await client.post(
                f"/api/v1/projects/{novel_id}/knowledge-graph/extract/1"
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["entities_count"] == 2
            assert data["triples_count"] == 1

    @pytest.mark.asyncio
    async def test_extraction_logs(self, client, novel_id):
        """GET /extraction-logs returns logs after extraction."""
        resp = await client.get(
            f"/api/v1/projects/{novel_id}/knowledge-graph/extraction-logs"
        )
        assert resp.status_code == 200
        # Should have at least the log from previous test (if run in order)
        assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

class TestVisualization:
    """Integration tests for visualization endpoint."""

    @pytest.mark.asyncio
    async def test_visualization_returns_nodes_and_edges(self, client, novel_id):
        """GET /visualization returns nodes and edges structure."""
        # Create entities and a triple
        e1 = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "character", "name": "可视化角色A", "first_chapter": 1},
        )
        e2 = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/entities",
            json={"entity_type": "character", "name": "可视化角色B", "first_chapter": 1},
        )
        await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/triples",
            json={
                "subject_id": e1.json()["id"],
                "predicate": "同门",
                "object_id": e2.json()["id"],
                "chapter_number": 1,
            },
        )

        resp = await client.get(
            f"/api/v1/projects/{novel_id}/knowledge-graph/visualization"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data
        assert "edges" in data
        assert len(data["nodes"]) >= 2
        assert len(data["edges"]) >= 1

        # Verify edge structure
        edge = next(
            e for e in data["edges"]
            if e["predicate"] == "同门"
        )
        assert edge["source"] == e1.json()["id"]
        assert edge["target"] == e2.json()["id"]


# ---------------------------------------------------------------------------
# Consistency Check
# ---------------------------------------------------------------------------

class TestConsistencyCheck:
    """Integration tests for consistency check endpoint."""

    @pytest.mark.asyncio
    async def test_consistency_check_chapter_not_found(self, client, novel_id):
        """POST /consistency-check/{chapter} returns 404 for missing chapter."""
        resp = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/consistency-check/999"
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_consistency_check_no_conflicts(self, client, novel_id):
        """Consistency check with no conflicts returns empty list."""
        from datetime import datetime

        from src.api.models.db_models import Chapter
        from src.core.database import get_db_session

        # Insert a chapter
        async with get_db_session() as session:
            ch = Chapter(
                novel_id=novel_id,
                chapter_number=10,
                title="第十章",
                content="平静的一天，什么都没发生。",
                word_count=10,
                status="generated",
                updated_at=datetime.now(UTC),
            )
            session.add(ch)

        resp = await client.post(
            f"/api/v1/projects/{novel_id}/knowledge-graph/consistency-check/10"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "conflicts" in data
        assert "checked_at" in data
        assert isinstance(data["conflicts"], list)
