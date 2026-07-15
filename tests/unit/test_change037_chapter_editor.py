"""Unit tests for chapter AI editing and version history."""

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError


@pytest.fixture(autouse=True)
def _mock_owner_guard():
    """Mock verify_novel_owner（测试不校验真实 owner，直接通过）。

    P0-2 加了 owner 鉴权后，端点测试需要 mock 它避免查真实 DB。
    """
    async def _pass(novel_id, current_user):
        return {"novel_id": novel_id, "owner_id": current_user.id}
    with patch("src.api.routes.chapters.verify_novel_owner", side_effect=_pass):
        yield


def _make_mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _make_mock_context(session):
    """Create a mock async context manager that yields the given session."""
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=session)
    mock_ctx.__aexit__ = AsyncMock(return_value=False)
    return mock_ctx


def _patch_db_session(session):
    """Patch get_db_session in all modules that use it.

    NovelManager.create_chapter_version delegates to ChapterService,
    which imports get_db_session at module level from src.core.database.
    We need to patch both:
    - src.core.database.get_db_session (for core modules)
    - src.api.services.chapter_service.get_db_session (for ChapterService)
    - src.api.services.novel_manager.get_db_session (for NovelManager direct use)
    """
    mock_ctx = _make_mock_context(session)
    return _CombinedPatcher([
        patch("src.core.database.get_db_session", return_value=mock_ctx),
        patch("src.api.services.chapter_service.get_db_session", return_value=mock_ctx),
        patch("src.api.services.novel_manager.get_db_session", return_value=mock_ctx),
    ])


class _CombinedPatcher:
    """Apply multiple patches as a context manager."""
    def __init__(self, patchers):
        self._patchers = patchers

    def __enter__(self):
        for p in self._patchers:
            p.start()
        return self

    def __exit__(self, *args):
        for p in reversed(self._patchers):
            p.stop()
        return False


class TestChapterVersionModel:
    def test_model_constraints_are_declared(self):
        from sqlalchemy import CheckConstraint, Index, UniqueConstraint

        from src.api.models.db_models import ChapterVersion

        table_args = ChapterVersion.__table_args__
        assert ChapterVersion.__tablename__ == "chapter_versions"
        assert any(
            isinstance(arg, UniqueConstraint) and arg.name == "uq_chapter_version"
            for arg in table_args
        )
        assert any(
            isinstance(arg, Index) and arg.name == "ix_chapter_versions_novel_chapter"
            for arg in table_args
        )
        assert any(
            isinstance(arg, CheckConstraint)
            and arg.name == "ck_chapter_version_source"
            for arg in table_args
        )

    def test_source_default_is_manual(self):
        from src.api.models.db_models import ChapterVersion

        assert ChapterVersion.__table__.c["source"].default.arg == "manual"


class TestCreateChapterVersion:
    @pytest.mark.asyncio
    async def test_first_version_is_1_when_no_existing_version(self):
        from src.api.services.novel_manager import NovelManager

        session = _make_mock_session()
        chapter_result = MagicMock()
        chapter_result.scalar_one_or_none.return_value = MagicMock()
        max_result = MagicMock()
        max_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(side_effect=[chapter_result, max_result])

        with _patch_db_session(session):
            version_number = await NovelManager().create_chapter_version(
                novel_id="novel-001",
                chapter_number=1,
                content="chapter content",
                source="manual",
            )

        assert version_number == 1

    @pytest.mark.asyncio
    async def test_version_increments_from_existing_max(self):
        from src.api.services.novel_manager import NovelManager

        session = _make_mock_session()
        chapter_result = MagicMock()
        chapter_result.scalar_one_or_none.return_value = MagicMock()
        max_result = MagicMock()
        max_result.scalar_one_or_none.return_value = 3
        session.execute = AsyncMock(side_effect=[chapter_result, max_result])

        with _patch_db_session(session):
            version_number = await NovelManager().create_chapter_version(
                novel_id="novel-001",
                chapter_number=2,
                content="content",
                source="ai_rewrite",
            )

        assert version_number == 4

    @pytest.mark.asyncio
    async def test_updates_locked_chapter_content_and_word_count(self):
        from src.api.models.db_models import ChapterVersion
        from src.api.services.novel_manager import NovelManager

        session = _make_mock_session()
        chapter = MagicMock()
        chapter_result = MagicMock()
        chapter_result.scalar_one_or_none.return_value = chapter
        max_result = MagicMock()
        max_result.scalar_one_or_none.return_value = 0
        session.execute = AsyncMock(side_effect=[chapter_result, max_result])

        added_objects = []
        session.add = MagicMock(side_effect=added_objects.append)
        content = "new chapter content"

        with _patch_db_session(session):
            await NovelManager().create_chapter_version(
                novel_id="novel-001",
                chapter_number=1,
                content=content,
                source="manual",
            )

        version = next(obj for obj in added_objects if isinstance(obj, ChapterVersion))
        assert version.word_count == len(content)
        assert chapter.content == content
        assert chapter.word_count == len(content)

    @pytest.mark.asyncio
    async def test_locks_chapter_row_not_aggregate_max_query(self):
        from src.api.services.novel_manager import NovelManager

        session = _make_mock_session()
        captured_queries = []

        async def capture_execute(query, *args, **kwargs):
            captured_queries.append(query)
            result = MagicMock()
            result.scalar_one_or_none.return_value = MagicMock()
            return result

        session.execute = capture_execute

        with _patch_db_session(session):
            await NovelManager().create_chapter_version(
                novel_id="novel-001",
                chapter_number=1,
                content="content",
                source="manual",
            )

        assert captured_queries[0]._for_update_arg is not None
        assert captured_queries[1]._for_update_arg is None

    @pytest.mark.asyncio
    async def test_raises_when_chapter_is_missing(self):
        from src.api.services.novel_manager import NovelManager

        session = _make_mock_session()
        chapter_result = MagicMock()
        chapter_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=chapter_result)

        with _patch_db_session(session), pytest.raises(ValueError, match="Chapter"):
            await NovelManager().create_chapter_version(
                novel_id="novel-001",
                chapter_number=404,
                content="content",
            )


class TestVersionQueries:
    @pytest.mark.asyncio
    async def test_list_versions_excludes_content(self):
        from src.api.services.novel_manager import NovelManager

        session = _make_mock_session()
        version = MagicMock()
        version.id = 1
        version.version_number = 2
        version.word_count = 120
        version.source = "ai_rewrite"
        version.rewrite_instruction = "tighten prose"
        version.created_at = datetime.now(UTC)

        result = MagicMock()
        result.scalars.return_value.all.return_value = [version]
        session.execute = AsyncMock(return_value=result)

        with _patch_db_session(session):
            versions = await NovelManager().list_chapter_versions("novel-001", 1)

        assert versions[0]["version_number"] == 2
        assert versions[0]["source"] == "ai_rewrite"
        assert "content" not in versions[0]

    @pytest.mark.asyncio
    async def test_get_version_returns_full_content(self):
        from src.api.services.novel_manager import NovelManager

        session = _make_mock_session()
        version = MagicMock()
        version.id = 1
        version.version_number = 1
        version.content = "full content"
        version.word_count = 12
        version.source = "manual"
        version.rewrite_instruction = None
        version.created_at = datetime.now(UTC)

        result = MagicMock()
        result.scalar_one_or_none.return_value = version
        session.execute = AsyncMock(return_value=result)

        with _patch_db_session(session):
            data = await NovelManager().get_chapter_version("novel-001", 1, 1)

        assert data["content"] == "full content"

    @pytest.mark.asyncio
    async def test_rollback_creates_new_version_from_target(self):
        from src.api.services.novel_manager import NovelManager

        manager = NovelManager()
        target = {"content": "old content", "version_number": 2}

        with patch.object(
            manager, "get_chapter_version", new=AsyncMock(return_value=target)
        ), patch.object(
            manager, "create_chapter_version", new=AsyncMock(return_value=5)
        ) as create_mock:
            new_version = await manager.rollback_chapter_version("novel-001", 1, 2)

        assert new_version == 5
        assert create_mock.call_args.kwargs["source"] == "rollback"
        assert create_mock.call_args.kwargs["content"] == "old content"


class TestChapterRewriter:
    @pytest.mark.asyncio
    async def test_rewrite_segment_returns_llm_text(self):
        from src.core.llm.chapter_rewriter import rewrite_chapter_segment

        client = MagicMock()
        client.generate = AsyncMock(return_value="rewritten text")

        with patch(
            "src.core.llm.chapter_rewriter.get_llm_client", return_value=client
        ):
            result = await rewrite_chapter_segment(
                novel_id="novel-001",
                chapter_number=1,
                full_content="full text",
                selected_text="old text",
                instruction="make it sharper",
                context={},
            )

        assert result == "rewritten text"
        assert client.generate.await_count == 1

    @pytest.mark.asyncio
    async def test_rewrite_segment_propagates_timeout(self):
        from src.core.llm.chapter_rewriter import rewrite_chapter_segment

        client = MagicMock()
        client.generate = AsyncMock(side_effect=TimeoutError())

        with patch(
            "src.core.llm.chapter_rewriter.get_llm_client", return_value=client
        ), pytest.raises(asyncio.TimeoutError):
            await rewrite_chapter_segment(
                novel_id="novel-001",
                chapter_number=1,
                full_content="full text",
                selected_text="old text",
                instruction="rewrite",
                context={},
            )

    def test_prompt_includes_context_and_task(self):
        from src.core.llm.chapter_rewriter import _build_rewrite_prompt

        prompt = _build_rewrite_prompt(
            context={
                "writing_style": "concise",
                "story_bible": "rules",
                "world_setting": "setting",
                "chapter_outline": "outline",
                "characters": "characters",
                "prev_chapter_summary": "previous",
                "next_chapter_summary": "next",
            },
            full_content="full text",
            selected_text="old text",
            instruction="rewrite instruction",
        )

        assert "old text" in prompt
        assert "rewrite instruction" in prompt
        assert "concise" in prompt
        assert "rules" in prompt


def _make_app():
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from src.api.routes.chapters import router as chapters_router
    from src.api.routes.projects import router as projects_router

    app = FastAPI()
    app.include_router(chapters_router)
    app.include_router(projects_router)

    # 继承 conftest 的 get_current_user override（mock 认证）
    from src.api.main import app as main_app
    app.dependency_overrides = main_app.dependency_overrides

    return TestClient(app)


class TestChapterEditorEndpoints:
    def test_rewrite_returns_200_on_success(self):
        client = _make_app()
        mock_manager = AsyncMock()
        mock_manager.get_chapter = AsyncMock(return_value={"id": 1})

        # Mock the context builder for the route handler
        mock_rewrite_ctx = MagicMock()
        mock_rewrite_ctx.world_setting = ""
        mock_rewrite_ctx.chapter_outline = ""
        mock_rewrite_ctx.prev_chapter_summary = ""
        mock_rewrite_ctx.next_chapter_summary = ""
        mock_rewrite_ctx.characters = ""
        mock_rewrite_ctx.story_bible = ""
        mock_rewrite_ctx.writing_style = ""

        mock_builder = MagicMock()
        mock_builder.build_rewrite_context = AsyncMock(
            return_value=mock_rewrite_ctx
        )

        @asynccontextmanager
        async def _fake_session():
            yield MagicMock()

        with patch(
            "src.api.routes.chapters.get_chapter_service", return_value=mock_manager
        ), patch(
            "src.core.database.get_db_session",
            _fake_session,
        ) as mock_get_db, patch(
            "src.core.llm.chapter_rewriter.get_llm_client",
        ) as mock_llm, patch(
            "src.api.services.novel_context_service.NovelContextBuilder",
            return_value=mock_builder,
        ):
            mock_llm.return_value.generate = AsyncMock(return_value="rewritten")
            response = client.post(
                "/api/v1/projects/novel-001/chapters/1/rewrite",
                json={
                    "full_content": "full text",
                    "selected_text": "old",
                    "selection_start": 0,
                    "selection_end": 3,
                    "instruction": "rewrite",
                },
            )

        assert response.status_code == 200
        assert response.json() == {
            "rewritten_text": "rewritten",
            "original_text": "old",
        }

    def test_rewrite_returns_504_on_timeout(self):
        client = _make_app()
        mock_manager = AsyncMock()
        mock_manager.get_chapter = AsyncMock(return_value={"id": 1})

        # Mock the context builder for the route handler
        mock_rewrite_ctx = MagicMock()
        mock_rewrite_ctx.world_setting = ""
        mock_rewrite_ctx.chapter_outline = ""
        mock_rewrite_ctx.prev_chapter_summary = ""
        mock_rewrite_ctx.next_chapter_summary = ""
        mock_rewrite_ctx.characters = ""
        mock_rewrite_ctx.story_bible = ""
        mock_rewrite_ctx.writing_style = ""

        mock_builder = MagicMock()
        mock_builder.build_rewrite_context = AsyncMock(
            return_value=mock_rewrite_ctx
        )

        @asynccontextmanager
        async def _fake_session():
            yield MagicMock()

        with patch(
            "src.api.routes.chapters.get_chapter_service", return_value=mock_manager
        ), patch(
            "src.core.database.get_db_session",
            _fake_session,
        ) as mock_get_db, patch(
            "src.core.llm.chapter_rewriter.get_llm_client",
        ) as mock_llm, patch(
            "src.api.services.novel_context_service.NovelContextBuilder",
            return_value=mock_builder,
        ):
            mock_llm.return_value.generate = AsyncMock(
                side_effect=TimeoutError()
            )
            response = client.post(
                "/api/v1/projects/novel-001/chapters/1/rewrite",
                json={
                    "full_content": "full text",
                    "selected_text": "old",
                    "selection_start": 0,
                    "selection_end": 3,
                    "instruction": "rewrite",
                },
            )

        assert response.status_code == 504

    def test_version_endpoints_return_expected_shapes(self):
        client = _make_app()
        now = datetime.now(UTC).isoformat()
        mock_manager = AsyncMock()
        mock_manager.get_chapter = AsyncMock(return_value={"id": 1})
        mock_manager.list_chapter_versions = AsyncMock(
            return_value=[
                {
                    "id": 1,
                    "version_number": 1,
                    "word_count": 10,
                    "source": "manual",
                    "rewrite_instruction": None,
                    "created_at": now,
                }
            ]
        )
        mock_manager.get_chapter_version = AsyncMock(
            return_value={
                "id": 1,
                "version_number": 1,
                "content": "content",
                "word_count": 10,
                "source": "manual",
                "rewrite_instruction": None,
                "created_at": now,
            }
        )
        mock_manager.create_chapter_version = AsyncMock(return_value=2)
        mock_manager.rollback_chapter_version = AsyncMock(return_value=3)

        with patch("src.api.routes.chapters.get_chapter_service", return_value=mock_manager):
            list_response = client.get("/api/v1/projects/novel-001/chapters/1/versions")
            get_response = client.get("/api/v1/projects/novel-001/chapters/1/versions/1")
            create_response = client.post(
                "/api/v1/projects/novel-001/chapters/1/versions",
                json={"content": "new content", "source": "manual"},
            )
            rollback_response = client.post(
                "/api/v1/projects/novel-001/chapters/1/versions/1/rollback"
            )

        assert list_response.status_code == 200
        assert get_response.status_code == 200
        assert get_response.json()["content"] == "content"
        assert create_response.status_code == 201
        assert create_response.json()["version_number"] == 2
        assert rollback_response.status_code == 200
        assert rollback_response.json()["new_version_number"] == 3

    def test_create_version_request_rejects_invalid_source(self):
        from src.api.routes.projects import CreateVersionRequest

        CreateVersionRequest(content="content", source="manual")
        CreateVersionRequest(content="content", source="ai_rewrite")
        CreateVersionRequest(content="content", source="rollback")

        with pytest.raises(ValidationError):
            CreateVersionRequest(content="content", source="invalid")
