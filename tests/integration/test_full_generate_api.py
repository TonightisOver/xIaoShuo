"""Integration tests for CHANGE-026 full generate API endpoints.

Tests:
- POST /api/v1/projects/full-generate (create + full generate)
- POST /api/v1/projects/{novel_id}/generate-full (full generate existing)
- Edge cases: validation, missing novel, etc.

These tests use a real database connection (configured in tests/conftest.py).
Background task execution (LLM) is mocked to avoid real API calls during tests.
"""

import pytest
from httpx import ASGITransport, AsyncClient
from unittest.mock import AsyncMock, patch

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
    """Globally mock background generation tasks to prevent real LLM calls.

    The HTTP layer tests focus on request/response validation and DB
    persistence.  Background task execution hits the real LLM API which
    is out of scope for these API integration tests.
    """
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


# ============================================================
#  POST /api/v1/projects/full-generate
# ============================================================

class TestFullGenerateProject:
    """Tests for the combined create+generate endpoint."""

    @pytest.mark.asyncio
    async def test_full_generate_creates_project_and_starts_task(self, client):
        """Happy path: creates a novel project and starts a full generate task."""
        response = await client.post(
            "/api/v1/projects/full-generate",
            json={
                "idea": "一个现代程序员穿越到修仙世界，用编程思维改造修炼体系",
                "novel_type": "玄幻",
                "target_words": 100000,
                "title": "码仙",
                "writing_style": "现代白话",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert "task_id" in data
        assert "novel_id" in data
        assert data["status"] == "full_generating"
        assert data["pipeline"] == "full_13_stage"
        assert data["novel_id"].startswith("novel-")
        assert data["task_id"].startswith("novel-")

        # Verify the novel was created in DB
        novel_id = data["novel_id"]
        get_resp = await client.get(f"/api/v1/projects/{novel_id}")
        assert get_resp.status_code == 200
        novel_data = get_resp.json()
        assert novel_data["novel_id"] == novel_id
        assert novel_data["status"] in ("draft", "generating")

    @pytest.mark.asyncio
    async def test_full_generate_validates_idea_length(self, client):
        """Rejects idea shorter than 10 chars."""
        response = await client.post(
            "/api/v1/projects/full-generate",
            json={
                "idea": "短",
                "novel_type": "玄幻",
                "target_words": 100000,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_full_generate_validates_idea_too_long(self, client):
        """Rejects idea longer than 1000 chars."""
        response = await client.post(
            "/api/v1/projects/full-generate",
            json={
                "idea": "A" * 1001,
                "novel_type": "玄幻",
                "target_words": 100000,
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_full_generate_validates_novel_type(self, client):
        """Rejects invalid novel_type (triggers validate_novel_type)."""
        response = await client.post(
            "/api/v1/projects/full-generate",
            json={
                "idea": "一个现代程序员穿越到修仙世界的故事内容描述",
                "novel_type": "无效类型测试",
                "target_words": 100000,
            },
        )
        assert response.status_code in (400, 422)

    @pytest.mark.asyncio
    async def test_full_generate_validates_target_words(self, client):
        """Rejects target_words outside 10000-10000000 range."""
        response = await client.post(
            "/api/v1/projects/full-generate",
            json={
                "idea": "一个现代程序员穿越到修仙世界的故事内容描述",
                "novel_type": "玄幻",
                "target_words": 500,  # below minimum 10000
            },
        )
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_full_generate_defaults_writing_style(self, client):
        """writing_style defaults to 现代白话 when not provided."""
        response = await client.post(
            "/api/v1/projects/full-generate",
            json={
                "idea": "一个现代程序员穿越到修仙世界的故事内容描述",
                "novel_type": "玄幻",
            },
        )
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "full_generating"


# ============================================================
#  POST /api/v1/projects/{novel_id}/generate-full
# ============================================================

class TestFullGenerateExisting:
    """Tests for full generation on an existing novel project."""

    @pytest.mark.asyncio
    async def test_full_generate_existing_novel(self, client):
        """Happy path: triggers full generate on an existing novel."""
        create_resp = await client.post(
            "/api/v1/projects",
            json={
                "idea": "一个剑客在江湖中追寻失传的剑法，发现世界背后的真相",
                "novel_type": "武侠",
                "target_words": 150000,
                "title": "剑踪",
                "writing_style": "古白话",
                "writing_style_prompt": "",
            },
        )
        assert create_resp.status_code == 201
        novel_id = create_resp.json()["novel_id"]

        # Now trigger full generate on it
        response = await client.post(
            f"/api/v1/projects/{novel_id}/generate-full"
        )
        assert response.status_code == 202
        data = response.json()
        assert data["novel_id"] == novel_id
        assert "task_id" in data
        assert data["status"] == "full_generating"
        assert data["pipeline"] == "full_13_stage"

    @pytest.mark.asyncio
    async def test_full_generate_nonexistent_novel(self, client):
        """Returns 404 when novel_id does not exist."""
        response = await client.post(
            "/api/v1/projects/nonexistent-novel-id-fake/generate-full"
        )
        assert response.status_code == 404
        assert "Novel not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_generate_full_creates_task_with_correct_data(self, client):
        """Verify the generated task has correct idea, novel_type, etc."""
        create_resp = await client.post(
            "/api/v1/projects",
            json={
                "idea": "一个星际探险家在银河边缘发现了一个失落的文明",
                "novel_type": "科幻",
                "target_words": 80000,
                "title": "银河边缘",
                "writing_style": "现代白话",
                "writing_style_prompt": "",
            },
        )
        assert create_resp.status_code == 201
        novel_id = create_resp.json()["novel_id"]

        # Trigger full generate
        gen_resp = await client.post(
            f"/api/v1/projects/{novel_id}/generate-full"
        )
        assert gen_resp.status_code == 202
        task_id = gen_resp.json()["task_id"]

        # Check the task via API
        task_resp = await client.get(f"/api/v1/novels/{task_id}")
        assert task_resp.status_code == 200
        task_data = task_resp.json()
        assert task_data["task_id"] == task_id
        # novel_id may be None if not linked to a project; in this test it is linked
        assert task_data["status"] == "pending"
        # TaskDetailResponse doesn't expose novel_type directly;
        # verify task exists with correct metadata from the projects endpoint
        proj_resp = await client.get(f"/api/v1/projects/{novel_id}")
        assert proj_resp.status_code == 200
        proj_data = proj_resp.json()
        assert proj_data["novel_type"] == "科幻"


# ============================================================
#  Response format validation
# ============================================================

class TestFullGenerateResponseFormat:
    """Validate response JSON structure for new endpoints."""

    @pytest.mark.asyncio
    async def test_full_generate_response_has_required_fields(self, client):
        """full-generate response contains task_id, novel_id, status, pipeline."""
        response = await client.post(
            "/api/v1/projects/full-generate",
            json={
                "idea": "一个魔法师在现代都市中隐藏身份生活的故事",
                "novel_type": "玄幻",
                "target_words": 70000,
            },
        )
        assert response.status_code == 202
        data = response.json()
        # Verify all required fields present and typed correctly
        assert isinstance(data["task_id"], str) and len(data["task_id"]) > 0
        assert isinstance(data["novel_id"], str) and len(data["novel_id"]) > 0
        assert data["status"] == "full_generating"
        assert data["pipeline"] == "full_13_stage"

    @pytest.mark.asyncio
    async def test_generate_full_response_has_required_fields(self, client):
        """generate-full response contains task_id, novel_id, status, pipeline."""
        create_resp = await client.post(
            "/api/v1/projects",
            json={
                "idea": "一个普通高中生获得超能力后的校园生活故事",
                "novel_type": "都市",
                "target_words": 60000,
                "title": "超能校园",
                "writing_style": "轻小说",
                "writing_style_prompt": "",
            },
        )
        novel_id = create_resp.json()["novel_id"]

        response = await client.post(
            f"/api/v1/projects/{novel_id}/generate-full"
        )
        assert response.status_code == 202
        data = response.json()
        assert isinstance(data["task_id"], str)
        assert data["novel_id"] == novel_id
        assert data["status"] == "full_generating"
        assert data["pipeline"] == "full_13_stage"


# ============================================================
#  Verify project CRUD still works
# ============================================================

class TestProjectCRUDCompatibility:
    """Ensure existing project endpoints are not broken by new routes."""

    @pytest.mark.asyncio
    async def test_list_projects_includes_new_novels(self, client):
        """List projects returns novels created via both paths."""
        # Create one via old endpoint
        await client.post(
            "/api/v1/projects",
            json={
                "idea": "一个魔法学徒在魔法学院中成长的故事",
                "novel_type": "玄幻",
                "target_words": 120000,
                "title": "魔法学徒",
                "writing_style": "现代白话",
                "writing_style_prompt": "",
            },
        )

        # Create one via full-generate
        await client.post(
            "/api/v1/projects/full-generate",
            json={
                "idea": "一个退役特工回到都市过上平凡生活的故事",
                "novel_type": "都市",
                "target_words": 60000,
                "title": "平凡生活",
                "writing_style": "现代白话",
            },
        )

        # List should include both
        response = await client.get("/api/v1/projects?limit=100")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 2

    @pytest.mark.asyncio
    async def test_delete_project_cleanup(self, client):
        """Delete a project and verify all sub-resource endpoints return 404."""
        create_resp = await client.post(
            "/api/v1/projects/full-generate",
            json={
                "idea": "一个被删除的测试项目的创意内容描述",
                "novel_type": "玄幻",
                "target_words": 50000,
                "title": "待删除",
                "writing_style": "现代白话",
            },
        )
        novel_id = create_resp.json()["novel_id"]

        # Add sub-resources to ensure they exist before deletion
        await client.put(
            f"/api/v1/projects/{novel_id}/world",
            json={"background": "测试世界观"},
        )
        await client.post(
            f"/api/v1/projects/{novel_id}/characters",
            json={"name": "测试角色"},
        )
        await client.post(
            f"/api/v1/projects/{novel_id}/power-systems",
            json={"name": "测试力量体系"},
        )

        # Delete
        del_resp = await client.delete(f"/api/v1/projects/{novel_id}")
        assert del_resp.status_code == 200

        # Verify project gone
        get_resp = await client.get(f"/api/v1/projects/{novel_id}")
        assert get_resp.status_code == 404

        # Verify sub-resource GET endpoints also return 404
        sub_resources = [
            f"/api/v1/projects/{novel_id}/volumes",
            f"/api/v1/projects/{novel_id}/volumes/1",
            f"/api/v1/projects/{novel_id}/world",
            f"/api/v1/projects/{novel_id}/power-systems",
            f"/api/v1/projects/{novel_id}/characters",
            f"/api/v1/projects/{novel_id}/chapters",
            f"/api/v1/projects/{novel_id}/chapters/1",
        ]
        for url in sub_resources:
            resp = await client.get(url)
            assert resp.status_code == 404, (
                f"Expected 404 for {url} after project deletion, "
                f"got {resp.status_code}: {resp.text[:200]}"
            )

    @pytest.mark.asyncio
    async def test_sub_resources_empty_when_novel_exists(self, client):
        """Sub-resources return empty data when novel exists but has no data."""
        create_resp = await client.post(
            "/api/v1/projects/full-generate",
            json={
                "idea": "一个空项目用于测试子资源空数据返回的创意内容",
                "novel_type": "玄幻",
                "target_words": 50000,
                "title": "空项目",
                "writing_style": "现代白话",
            },
        )
        novel_id = create_resp.json()["novel_id"]

        # These should return empty lists (project exists, no data)
        lists_ok = [
            f"/api/v1/projects/{novel_id}/volumes",
            f"/api/v1/projects/{novel_id}/power-systems",
            f"/api/v1/projects/{novel_id}/characters",
            f"/api/v1/projects/{novel_id}/chapters",
        ]
        for url in lists_ok:
            resp = await client.get(url)
            assert resp.status_code == 200, (
                f"Expected 200 for {url} on empty project, "
                f"got {resp.status_code}"
            )
            data = resp.json()
            assert data == [], (
                f"Expected empty list for {url}, got {data}"
            )

        # World setting returns empty object (project exists, no world data)
        world_resp = await client.get(f"/api/v1/projects/{novel_id}/world")
        assert world_resp.status_code == 200
        world_data = world_resp.json()
        assert world_data["background"] is None

        # Cleanup
        await client.delete(f"/api/v1/projects/{novel_id}")

    @pytest.mark.asyncio
    async def test_sub_resource_mutations_404_on_deleted_novel(self, client):
        """Mutation endpoints return 404 when novel doesn't exist."""
        novel_id = "novel-deadbeef0000000000000000"

        mutations = [
            ("put", f"/api/v1/projects/{novel_id}/volumes/1",
             {"title": "test"}),
            ("put", f"/api/v1/projects/{novel_id}/world",
             {"background": "test"}),
            ("post", f"/api/v1/projects/{novel_id}/power-systems",
             {"name": "test"}),
            ("put", f"/api/v1/projects/{novel_id}/power-systems/1",
             {"name": "test"}),
            ("delete", f"/api/v1/projects/{novel_id}/power-systems/1", None),
            ("post", f"/api/v1/projects/{novel_id}/characters",
             {"name": "test"}),
            ("put", f"/api/v1/projects/{novel_id}/characters/1",
             {"name": "test"}),
            ("delete", f"/api/v1/projects/{novel_id}/characters/1", None),
            ("put", f"/api/v1/projects/{novel_id}/chapters/1",
             {"title": "test"}),
            ("delete", f"/api/v1/projects/{novel_id}/chapters/1", None),
        ]

        for method, url, body in mutations:
            if method == "put":
                resp = await client.put(url, json=body or {})
            elif method == "post":
                resp = await client.post(url, json=body or {})
            else:
                resp = await client.delete(url)
            assert resp.status_code == 404, (
                f"Expected 404 for {method.upper()} {url} on non-existent novel, "
                f"got {resp.status_code}: {resp.text[:200]}"
            )
