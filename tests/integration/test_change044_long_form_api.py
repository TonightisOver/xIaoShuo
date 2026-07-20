"""Integration tests for CHANGE-044: long-form novel API endpoints.

Tests the following endpoints:
- POST /api/v1/novels/long-form
- GET  /api/v1/novels/{novel_id}/quality-report
- GET  /api/v1/novels/{novel_id}/filler-detection
- GET  /api/v1/novels/{novel_id}/foreshadow-tracker
- GET  /api/v1/novels/{novel_id}/long-form/progress
- POST /api/v1/novels/{novel_id}/volumes/{volume_number}/generate
- POST /api/v1/novels/{novel_id}/volumes/{volume_number}/pause
- POST /api/v1/novels/{novel_id}/volumes/{volume_number}/resume

Uses a real test database. The ASGI transport does not start the persistent
queue worker, so queued generation handlers and LLM calls do not run.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text

from src.api.main import app
from src.core.database import Base, get_db_session, get_engine

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
async def _db_setup():
    """Create all tables before module tests, drop after."""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def client(_db_setup):
    """Async HTTP client for API testing."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _create_novel_via_api(client: AsyncClient, **overrides) -> str:
    """Helper: create a long-form novel via the API and return novel_id."""
    payload = {
        "idea": "一个程序员穿越到修仙世界，用编程思维改造修炼体系的冒险故事",
        "novel_type": "玄幻",
        "target_words": 1_000_000,
        "volumes": 3,
        "chapters_per_volume": 20,
        "words_per_chapter": 3000,
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/novels/long-form", json=payload)
    assert resp.status_code == 202, resp.text
    return resp.json()["novel_id"]


async def _insert_novel_direct(novel_id: str, **kwargs):
    """Insert a Novel record directly into the DB for testing."""
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO novels (novel_id, title, idea, novel_type, target_words,
                    status, writing_style, words_per_chapter, is_long_form, total_volumes,
                    chapters_per_volume, owner_id, created_at, updated_at)
                VALUES (:novel_id, :title, :idea, :novel_type, :target_words,
                    :status, :writing_style, :words_per_chapter, :is_long_form,
                    :total_volumes, :chapters_per_volume, :owner_id, NOW(), NOW())
                """
            ),
            {
                "novel_id": novel_id,
                "title": kwargs.get("title", "Test Novel"),
                "idea": kwargs.get("idea", "测试创意内容描述足够长度"),
                "novel_type": kwargs.get("novel_type", "玄幻"),
                "target_words": kwargs.get("target_words", 1_000_000),
                "status": kwargs.get("status", "generating"),
                "writing_style": kwargs.get("writing_style", "现代白话"),
                "words_per_chapter": kwargs.get("words_per_chapter", 3000),
                "is_long_form": kwargs.get("is_long_form", True),
                "total_volumes": kwargs.get("total_volumes", 3),
                "chapters_per_volume": kwargs.get("chapters_per_volume", 10),
                # Phase 3 Task 3 给端点加了 verify_novel_owner，直接插入的 novel
                # 必须带 owner_id 才能通过鉴权；conftest 的 mock user id=1。
                "owner_id": kwargs.get("owner_id", 1),
            },
        )


async def _insert_chapter(novel_id: str, chapter_number: int, volume_number: int,
                           word_count: int = 3000, chapter_type: str = None, title: str = None):
    """Insert a Chapter record directly."""
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO chapters (novel_id, chapter_number, volume_number, title,
                    word_count, chapter_type, status, updated_at)
                VALUES (:novel_id, :chapter_number, :volume_number, :title,
                    :word_count, :chapter_type, 'completed', NOW())
                ON CONFLICT (novel_id, chapter_number) DO UPDATE SET
                    word_count = :word_count, chapter_type = :chapter_type
                """
            ),
            {
                "novel_id": novel_id,
                "chapter_number": chapter_number,
                "volume_number": volume_number,
                "title": title or f"Chapter {chapter_number}",
                "word_count": word_count,
                "chapter_type": chapter_type,
            },
        )


async def _insert_volume(novel_id: str, volume_number: int, status: str = "completed"):
    """Insert a Volume record directly."""
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO volumes (novel_id, volume_number, title, status,
                    generated_chapters, updated_at)
                VALUES (:novel_id, :volume_number, :title, :status, 0, NOW())
                ON CONFLICT (novel_id, volume_number) DO UPDATE SET status = :status
                """
            ),
            {
                "novel_id": novel_id,
                "volume_number": volume_number,
                "title": f"Volume {volume_number}",
                "status": status,
            },
        )


async def _insert_lfp(novel_id: str, volume_number: int, status: str = "pending",
                       chapter_start: int = 1, chapter_end: int = 10,
                       chapters_completed: int = 0, **extra):
    """Insert a LongFormProgress record directly."""
    qr = extra.get("quality_report")
    async with get_db_session() as session:
        if qr:
            import json as _json
            qr_param = _json.dumps(qr)
            sql = """
                INSERT INTO long_form_progress (novel_id, volume_number, status,
                    chapter_start, chapter_end, chapters_completed, errors,
                    quality_report, created_at, updated_at)
                VALUES (:novel_id, :volume_number, :status,
                    :chapter_start, :chapter_end, :chapters_completed, '[]'::json,
                    :quality_report::json, NOW(), NOW())
                ON CONFLICT DO NOTHING
                """
            params = {
                "novel_id": novel_id,
                "volume_number": volume_number,
                "status": status,
                "chapter_start": chapter_start,
                "chapter_end": chapter_end,
                "chapters_completed": chapters_completed,
                "quality_report": qr_param,
            }
        else:
            sql = """
                INSERT INTO long_form_progress (novel_id, volume_number, status,
                    chapter_start, chapter_end, chapters_completed, errors,
                    quality_report, created_at, updated_at)
                VALUES (:novel_id, :volume_number, :status,
                    :chapter_start, :chapter_end, :chapters_completed, '[]'::json,
                    NULL, NOW(), NOW())
                ON CONFLICT DO NOTHING
                """
            params = {
                "novel_id": novel_id,
                "volume_number": volume_number,
                "status": status,
                "chapter_start": chapter_start,
                "chapter_end": chapter_end,
                "chapters_completed": chapters_completed,
            }
        await session.execute(text(sql), params)


async def _insert_story_bible(novel_id: str, foreshadowing_list=None, unresolved_hooks=None):
    """Insert a StoryBible record directly."""
    import json
    fl = json.dumps(foreshadowing_list or [])
    uh = json.dumps(unresolved_hooks or [])
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO story_bibles (novel_id, worldview_rules, character_cards,
                    foreshadowing_list, unresolved_hooks, updated_at)
                VALUES (:novel_id, '', '[]'::json,
                    CAST(:foreshadowing_list AS jsonb),
                    CAST(:unresolved_hooks AS jsonb), NOW())
                ON CONFLICT (novel_id) DO UPDATE SET
                    foreshadowing_list = CAST(:foreshadowing_list AS jsonb),
                    unresolved_hooks = CAST(:unresolved_hooks AS jsonb)
                """
            ),
            {
                "novel_id": novel_id,
                "foreshadowing_list": fl,
                "unresolved_hooks": uh,
            },
        )


# ============================================================
#  POST /api/v1/novels/long-form
# ============================================================

class TestCreateLongFormNovel:
    """Tests for creating a long-form novel generation task."""

    @pytest.mark.asyncio
    async def test_create_long_form_happy_path(self, client):
        """Happy path: creates a long-form novel task with all fields."""
        resp = await client.post(
            "/api/v1/novels/long-form",
            json={
                "idea": "一个程序员穿越到修仙世界，用编程思维改造修炼体系的冒险故事",
                "novel_type": "玄幻",
                "target_words": 1_000_000,
                "volumes": 10,
                "chapters_per_volume": 40,
                "words_per_chapter": 3000,
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert "task_id" in data
        assert "novel_id" in data
        assert data["status"] == "pending"
        assert data["total_volumes"] == 10
        assert data["total_chapters"] == 400
        assert data["target_words"] == 1_000_000
        assert data["volumes_completed"] == 0
        assert data["chapters_completed"] == 0
        assert data["estimated_duration_hours"] > 0

    @pytest.mark.asyncio
    async def test_create_long_form_validation_short_idea(self, client):
        """Rejects idea shorter than 10 chars (422 from Pydantic)."""
        resp = await client.post(
            "/api/v1/novels/long-form",
            json={
                "idea": "短",
                "novel_type": "玄幻",
            },
        )
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_create_long_form_defaults(self, client):
        """Default values are used for optional fields."""
        resp = await client.post(
            "/api/v1/novels/long-form",
            json={
                "idea": "一个程序员穿越到修仙世界用编程思维改造修炼体系的冒险故事",
                "novel_type": "都市",
            },
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["total_volumes"] == 10  # default
        assert data["total_chapters"] == 400  # 10 * 40
        assert data["target_words"] == 1_000_000  # default


# ============================================================
#  GET /api/v1/novels/{novel_id}/quality-report
# ============================================================

class TestQualityReport:
    """Tests for quality report endpoint."""

    @pytest.mark.asyncio
    async def test_quality_report_empty_novel(self, client):
        """Returns empty report when novel has no chapters."""
        novel_id = await _create_novel_via_api(client)

        resp = await client.get(f"/api/v1/novels/{novel_id}/quality-report")
        assert resp.status_code == 200
        data = resp.json()
        assert data["novel_id"] == novel_id
        assert data["total_volumes"] == 0
        assert data["volume_reports"] == []

    @pytest.mark.asyncio
    async def test_quality_report_with_chapters(self, client):
        """Returns scores when novel has chapters."""
        novel_id = "novel-qr-test-001"
        await _insert_novel_direct(novel_id, total_volumes=1, chapters_per_volume=3)
        await _insert_volume(novel_id, 1, status="completed")
        for i in range(1, 4):
            await _insert_chapter(novel_id, i, 1, word_count=3000)

        resp = await client.get(f"/api/v1/novels/{novel_id}/quality-report")
        assert resp.status_code == 200
        data = resp.json()
        assert data["novel_id"] == novel_id
        assert data["total_volumes"] == 1
        assert data["completed_volumes"] == 1
        assert len(data["volume_reports"]) == 1
        assert data["volume_reports"][0]["chapter_count"] == 3

    @pytest.mark.asyncio
    async def test_quality_report_scores_present(self, client):
        """Quality scores are present in the response."""
        novel_id = "novel-qr-test-002"
        await _insert_novel_direct(novel_id)
        await _insert_volume(novel_id, 1)
        await _insert_chapter(novel_id, 1, 1, word_count=3000)

        resp = await client.get(f"/api/v1/novels/{novel_id}/quality-report")
        data = resp.json()
        # Default scores are 0.7 for each dimension
        for dim, val in data["overall_avg_scores"].items():
            assert val == 0.7


# ============================================================
#  GET /api/v1/novels/{novel_id}/filler-detection
# ============================================================

class TestFillerDetection:
    """Tests for filler detection endpoint."""

    @pytest.mark.asyncio
    async def test_filler_detection_empty_novel(self, client):
        """Returns zero filler when no chapters."""
        novel_id = await _create_novel_via_api(client)
        resp = await client.get(f"/api/v1/novels/{novel_id}/filler-detection")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_chapters"] == 0
        assert data["filler_chapters"] == []
        assert data["filler_ratio"] == 0.0

    @pytest.mark.asyncio
    async def test_filler_detection_normal_chapters(self, client):
        """Normal chapters should not be flagged as filler."""
        novel_id = "novel-fd-test-001"
        await _insert_novel_direct(novel_id)
        for i in range(1, 6):
            await _insert_chapter(novel_id, i, 1, word_count=3000)

        resp = await client.get(f"/api/v1/novels/{novel_id}/filler-detection")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_chapters"] == 5
        assert len(data["filler_chapters"]) == 0

    @pytest.mark.asyncio
    async def test_filler_detection_with_short_chapters(self, client):
        """Very short chapters should be detected as filler."""
        novel_id = "novel-fd-test-002"
        await _insert_novel_direct(novel_id)
        for i in range(1, 6):
            wc = 3000 if i <= 4 else 200  # last chapter is very short
            await _insert_chapter(novel_id, i, 1, word_count=wc)

        resp = await client.get(f"/api/v1/novels/{novel_id}/filler-detection")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_chapters"] == 5
        # Chapter 5 with 200 words should be flagged
        flagged = [f["chapter_number"] for f in data["filler_chapters"]]
        assert 5 in flagged

    @pytest.mark.asyncio
    async def test_filler_detection_recommendations(self, client):
        """Recommendations are generated when filler is found."""
        novel_id = "novel-fd-test-003"
        await _insert_novel_direct(novel_id)
        # Insert mostly short chapters to trigger recommendations
        for i in range(1, 8):
            await _insert_chapter(novel_id, i, 1, word_count=200)

        resp = await client.get(f"/api/v1/novels/{novel_id}/filler-detection")
        data = resp.json()
        assert len(data["recommendations"]) > 0


# ============================================================
#  GET /api/v1/novels/{novel_id}/foreshadow-tracker
# ============================================================

class TestForeshadowTracker:
    """Tests for foreshadow tracker endpoint."""

    @pytest.mark.asyncio
    async def test_foreshadow_tracker_no_bible(self, client):
        """Returns zero foreshadows when no story bible exists."""
        novel_id = await _create_novel_via_api(client)
        resp = await client.get(f"/api/v1/novels/{novel_id}/foreshadow-tracker")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_foreshadows"] == 0
        assert data["resolution_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_foreshadow_tracker_with_data(self, client):
        """Correctly categorizes foreshadows."""
        novel_id = "novel-ft-test-001"
        await _insert_novel_direct(novel_id)
        await _insert_story_bible(
            novel_id,
            foreshadowing_list=[
                {"name": "剑的秘密", "status": "active", "planted_chapter": 1},
                {"name": "身世之谜", "status": "resolved", "planted_chapter": 3,
                 "resolved_chapter": 10},
            ],
            unresolved_hooks=[
                {"name": "神秘人", "description": "跟踪", "chapter": 5},
            ],
        )

        resp = await client.get(f"/api/v1/novels/{novel_id}/foreshadow-tracker")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_foreshadows"] == 3
        assert len(data["planted"]) == 1
        assert len(data["resolved"]) == 1
        assert len(data["dangling"]) == 1
        assert data["resolution_rate"] > 0


# ============================================================
#  GET /api/v1/novels/{novel_id}/long-form/progress
# ============================================================

class TestLongFormProgress:
    """Tests for long-form progress endpoint."""

    @pytest.mark.asyncio
    async def test_progress_novel_not_found(self, client):
        """Returns 404 when novel does not exist."""
        resp = await client.get("/api/v1/novels/nonexistent-novel/long-form/progress")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_progress_empty_novel(self, client):
        """Returns progress data for novel with no progress records."""
        novel_id = await _create_novel_via_api(client)
        resp = await client.get(f"/api/v1/novels/{novel_id}/long-form/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["novel_id"] == novel_id
        # total_volumes comes from novel.total_volumes (may be None → falls back to len(records)=0)
        assert data["completed_volumes"] == 0
        assert data["chapters_completed"] == 0

    @pytest.mark.asyncio
    async def test_progress_with_records(self, client):
        """Returns aggregated progress from DB records."""
        novel_id = "novel-prog-test-001"
        await _insert_novel_direct(novel_id, total_volumes=2, chapters_per_volume=5)
        await _insert_lfp(novel_id, 1, status="completed", chapters_completed=5,
                          chapter_start=1, chapter_end=5)
        await _insert_lfp(novel_id, 2, status="generating", chapters_completed=3,
                          chapter_start=6, chapter_end=10)

        resp = await client.get(f"/api/v1/novels/{novel_id}/long-form/progress")
        assert resp.status_code == 200
        data = resp.json()
        assert data["completed_volumes"] == 1
        assert data["current_volume"] == 2
        assert data["chapters_completed"] == 8
        assert len(data["volume_details"]) == 2


# ============================================================
#  POST /api/v1/novels/{novel_id}/volumes/{volume_number}/generate
# ============================================================

class TestVolumeGenerate:
    """Tests for per-volume generation trigger."""

    @pytest.mark.asyncio
    async def test_volume_generate_not_found(self, client):
        """Returns 404 when volume does not exist."""
        novel_id = "novel-vg-test-fake"
        resp = await client.post(
            f"/api/v1/novels/{novel_id}/volumes/1/generate",
            json={},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_volume_generate_happy_path(self, client):
        """Triggers generation for a pending volume."""
        novel_id = "novel-vg-test-001"
        await _insert_novel_direct(novel_id)
        await _insert_lfp(novel_id, 1, status="pending", chapter_start=1, chapter_end=10)

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/volumes/1/generate",
            json={"start_chapter": 1, "overwrite_existing": False},
        )
        assert resp.status_code == 202
        data = resp.json()
        assert data["novel_id"] == novel_id
        assert data["volume_number"] == 1
        assert data["status"] == "pending"
        assert "task_id" in data

    @pytest.mark.asyncio
    async def test_volume_generate_already_generating(self, client):
        """Returns 400 when volume is already generating."""
        novel_id = "novel-vg-test-002"
        await _insert_novel_direct(novel_id)
        await _insert_lfp(novel_id, 1, status="generating")

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/volumes/1/generate",
            json={},
        )
        assert resp.status_code == 400
        assert "already being generated" in resp.json()["detail"]


# ============================================================
#  POST /api/v1/novels/{novel_id}/volumes/{volume_number}/pause
# ============================================================

class TestVolumePause:
    """Tests for pausing volume generation."""

    @pytest.mark.asyncio
    async def test_pause_happy_path(self, client):
        """Pauses a generating volume."""
        novel_id = "novel-vp-test-001"
        await _insert_novel_direct(novel_id)
        await _insert_lfp(novel_id, 1, status="generating")

        resp = await client.post(f"/api/v1/novels/{novel_id}/volumes/1/pause")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "paused"
        assert data["novel_id"] == novel_id
        assert data["volume_number"] == 1

    @pytest.mark.asyncio
    async def test_pause_returns_success(self, client):
        """Pause endpoint returns correct response format."""
        novel_id = "novel-vp-test-002"
        await _insert_novel_direct(novel_id)
        await _insert_lfp(novel_id, 2, status="generating")

        resp = await client.post(f"/api/v1/novels/{novel_id}/volumes/2/pause")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "novel_id" in data
        assert "volume_number" in data


# ============================================================
#  POST /api/v1/novels/{novel_id}/volumes/{volume_number}/resume
# ============================================================

class TestVolumeResume:
    """Tests for resuming volume generation."""

    @pytest.mark.asyncio
    async def test_resume_not_found(self, client):
        """Returns 404 when volume does not exist."""
        resp = await client.post(
            "/api/v1/novels/novel-fake/volumes/1/resume",
            json={},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_resume_happy_path(self, client):
        """Resumes a paused volume."""
        novel_id = "novel-vr-test-001"
        await _insert_novel_direct(novel_id)
        await _insert_lfp(novel_id, 1, status="paused")

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/volumes/1/resume",
            json={},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["novel_id"] == novel_id
        assert data["volume_number"] == 1
        assert data["status"] == "resuming"
        assert "task_id" in data

    @pytest.mark.asyncio
    async def test_resume_not_paused(self, client):
        """Returns 400 when volume is not paused."""
        novel_id = "novel-vr-test-002"
        await _insert_novel_direct(novel_id)
        await _insert_lfp(novel_id, 1, status="completed")

        resp = await client.post(
            f"/api/v1/novels/{novel_id}/volumes/1/resume",
            json={},
        )
        assert resp.status_code == 400
        assert "not paused" in resp.json()["detail"]


# ============================================================
#  Cross-endpoint integration
# ============================================================

class TestCrossEndpointIntegration:
    """Tests that exercise multiple endpoints together."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self, client):
        """Create novel -> generate -> pause -> resume lifecycle."""
        # 1. Create
        novel_id = await _create_novel_via_api(client)

        # 2. Insert progress
        await _insert_lfp(novel_id, 1, status="pending", chapter_start=1, chapter_end=10)

        # 3. Trigger generation
        gen_resp = await client.post(
            f"/api/v1/novels/{novel_id}/volumes/1/generate",
            json={"start_chapter": 1},
        )
        assert gen_resp.status_code == 202

        # 4. Check progress
        prog_resp = await client.get(f"/api/v1/novels/{novel_id}/long-form/progress")
        assert prog_resp.status_code == 200

        # 5. Check quality report (empty)
        qr_resp = await client.get(f"/api/v1/novels/{novel_id}/quality-report")
        assert qr_resp.status_code == 200

        # 6. Check filler detection (empty)
        fd_resp = await client.get(f"/api/v1/novels/{novel_id}/filler-detection")
        assert fd_resp.status_code == 200

        # 7. Check foreshadow tracker (no bible)
        ft_resp = await client.get(f"/api/v1/novels/{novel_id}/foreshadow-tracker")
        assert ft_resp.status_code == 200

    @pytest.mark.asyncio
    async def test_report_endpoints_with_full_data(self, client):
        """All report endpoints return correct data when novel has full data."""
        novel_id = "novel-cross-test-001"
        await _insert_novel_direct(novel_id, total_volumes=1, chapters_per_volume=3)
        await _insert_volume(novel_id, 1)
        await _insert_lfp(novel_id, 1, status="completed", chapters_completed=3)
        for i in range(1, 4):
            await _insert_chapter(novel_id, i, 1, word_count=3000)
        await _insert_story_bible(
            novel_id,
            foreshadowing_list=[
                {"name": "test hook", "status": "active", "planted_chapter": 1},
            ],
        )

        # Quality report
        qr = await client.get(f"/api/v1/novels/{novel_id}/quality-report")
        assert qr.status_code == 200
        assert qr.json()["total_volumes"] == 1

        # Filler detection
        fd = await client.get(f"/api/v1/novels/{novel_id}/filler-detection")
        assert fd.status_code == 200
        assert fd.json()["total_chapters"] == 3

        # Foreshadow tracker
        ft = await client.get(f"/api/v1/novels/{novel_id}/foreshadow-tracker")
        assert ft.status_code == 200
        assert ft.json()["total_foreshadows"] == 1

        # Progress
        pr = await client.get(f"/api/v1/novels/{novel_id}/long-form/progress")
        assert pr.status_code == 200
        assert pr.json()["chapters_completed"] == 3
