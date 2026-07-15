"""Service 层单元测试 — ChapterService (章节 CRUD + 版本管理)"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_chapter_row(
    id_: int = 1,
    novel_id: str = "novel-1",
    chapter_number: int = 1,
    volume_number: int | None = None,
    title: str = "测试章节",
    content: str = "章节正文内容",
    word_count: int = 100,
    status: str = "generated",
) -> MagicMock:
    row = MagicMock(spec=["id", "novel_id", "chapter_number", "volume_number",
                          "title", "content", "word_count", "status", "chapter_type",
                          "updated_at"])
    row.id = id_
    row.novel_id = novel_id
    row.chapter_number = chapter_number
    row.volume_number = volume_number
    row.title = title
    row.content = content
    row.word_count = word_count
    row.status = status
    row.chapter_type = "normal"
    row.updated_at = datetime(2026, 7, 4, tzinfo=UTC)
    return row


def _make_version_row(
    id_: int = 1,
    novel_id: str = "novel-1",
    chapter_number: int = 1,
    version_number: int = 1,
    content: str = "版本内容",
    source: str = "generation",
    is_active: bool = False,
) -> MagicMock:
    row = MagicMock(spec=["id", "novel_id", "chapter_number", "version_number",
                          "content", "word_count", "source", "rewrite_instruction",
                          "quality_score", "quality_scores", "model_name", "prompt_summary",
                          "diff_from_previous", "kg_conflicts", "user_notes",
                          "is_active", "created_at"])
    row.id = id_
    row.novel_id = novel_id
    row.chapter_number = chapter_number
    row.version_number = version_number
    row.content = content
    row.word_count = len(content)
    row.source = source
    row.rewrite_instruction = None
    row.quality_score = None
    row.quality_scores = None
    row.model_name = None
    row.prompt_summary = None
    row.diff_from_previous = None
    row.kg_conflicts = None
    row.user_notes = None
    row.is_active = is_active
    row.created_at = datetime(2026, 7, 4, tzinfo=UTC)
    return row


def _make_mock_session(scalar_one_or_none_result=None, scalar_result=None, all_result=None):
    """Create a consistent mock session for get_db_session mocking."""
    session = AsyncMock()
    session.execute = AsyncMock()

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_one_or_none_result
    if scalar_result is not None:
        mock_result.scalar.return_value = scalar_result
    if all_result is not None:
        mock_result.all.return_value = all_result

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = all_result or []
    mock_result.scalars = MagicMock(return_value=mock_scalars)

    session.execute.return_value = mock_result
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.delete = AsyncMock()
    return session


# ============================================================
# list_chapters
# ============================================================

class TestListChapters:
    """ChapterService.list_chapters()"""

    @pytest.mark.asyncio
    async def test_list_chapters_returns_all_chapters(self):
        """正常返回所有章节列表"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()
        svc._chapter_service = None  # ensure singleton reset

        rows = [
            _make_chapter_row(1, "novel-1", 1, volume_number=1, title="第一章"),
            _make_chapter_row(2, "novel-1", 2, volume_number=1, title="第二章"),
        ]

        session = _make_mock_session(all_result=rows)
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.list_chapters("novel-1")

        assert len(result) == 2
        assert result[0]["title"] == "第一章"
        assert result[1]["chapter_number"] == 2
        assert result[0]["volume_number"] == 1

    @pytest.mark.asyncio
    async def test_list_chapters_empty(self):
        """无章节时返回空列表"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        session = _make_mock_session(all_result=[])
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.list_chapters("novel-empty")
        assert result == []


# ============================================================
# get_chapter
# ============================================================

class TestGetChapter:
    """ChapterService.get_chapter()"""

    @pytest.mark.asyncio
    async def test_get_chapter_returns_correct_keys(self):
        """返回的 dict 包含所有预期字段"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        row = _make_chapter_row(1, "novel-1", 5, volume_number=2, content="正文内容")
        session = _make_mock_session(scalar_one_or_none_result=row)
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.get_chapter("novel-1", 5)

        assert result is not None
        assert result["chapter_number"] == 5
        assert result["volume_number"] == 2
        assert result["content"] == "正文内容"
        assert "novel_id" in result
        assert "title" in result
        assert "word_count" in result
        assert "status" in result

    @pytest.mark.asyncio
    async def test_get_chapter_not_found_returns_none(self):
        """不存在的章节返回 None"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        session = _make_mock_session(scalar_one_or_none_result=None)
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.get_chapter("novel-none", 999)
        assert result is None


# ============================================================
# update_chapter
# ============================================================

class TestUpdateChapter:
    """ChapterService.update_chapter()"""

    @pytest.mark.asyncio
    async def test_update_chapter_content_updates_word_count(self):
        """更新字数后自动重新计算 word_count"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        row = _make_chapter_row(1, "novel-1", 1, content="旧内容")
        session = _make_mock_session(scalar_one_or_none_result=row)
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.update_chapter("novel-1", 1, content="新内容新内容")

        assert result is True
        assert row.word_count == 6  # "新内容新内容" = 6 chars
        assert row.status == "edited"

    @pytest.mark.asyncio
    async def test_update_chapter_not_found_returns_false(self):
        """不存在的章节返回 False"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        session = _make_mock_session(scalar_one_or_none_result=None)
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.update_chapter("novel-none", 999, title="新标题")
        assert result is False


# ============================================================
# delete_chapter
# ============================================================

class TestDeleteChapter:
    """ChapterService.delete_chapter()"""

    @pytest.mark.asyncio
    async def test_delete_existing_chapter_returns_true(self):
        """删除存在的章节返回 True"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        row = _make_chapter_row(1, "novel-1", 1)
        session = _make_mock_session(scalar_one_or_none_result=row)
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.delete_chapter("novel-1", 1)
        assert result is True

    @pytest.mark.asyncio
    async def test_delete_nonexistent_chapter_returns_false(self):
        """删除不存在的章节返回 False"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        session = _make_mock_session(scalar_one_or_none_result=None)
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.delete_chapter("novel-none", 999)
        assert result is False


# ============================================================
# delete_failed_chapters
# ============================================================

class TestDeleteFailedChapters:
    """ChapterService.delete_failed_chapters()"""

    @pytest.mark.asyncio
    async def test_delete_failed_removes_short_chapters(self):
        """删除 word_count < 100 的失败章节并返回删除数量"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        short_ch = _make_chapter_row(1, "novel-1", 1, word_count=50)
        # Only short chapters returned by the query
        session = _make_mock_session(all_result=[short_ch])
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.delete_failed_chapters("novel-1", min_words=100)
        assert result == 1

    @pytest.mark.asyncio
    async def test_delete_failed_no_short_chapters(self):
        """没有小于 min_words 的章节时返回 0"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        session = _make_mock_session(all_result=[])
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.delete_failed_chapters("novel-1")
        assert result == 0


# ============================================================
# list_chapters_preview
# ============================================================

class TestListChaptersPreview:
    """ChapterService.list_chapters_preview()"""

    @pytest.mark.asyncio
    async def test_preview_excludes_content_and_sorts_by_number(self):
        """预览列表不包含 content，按 chapter_number 排序"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        from sqlalchemy import Row
        row1 = MagicMock(spec=Row)
        row1.id = 2; row1.chapter_number = 2; row1.volume_number = 1
        row1.title = "第二"; row1.word_count = 200; row1.status = "generated"
        row1.chapter_type = "normal"; row1.updated_at = datetime(2026, 7, 4, tzinfo=UTC)

        rows = [row1]
        session = _make_mock_session(all_result=rows)
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.list_chapters_preview("novel-1")

        assert len(result) == 1
        assert result[0]["chapter_number"] == 2
        assert "content" not in result[0]

    @pytest.mark.asyncio
    async def test_preview_empty(self):
        """无章节时返回空"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()
        session = _make_mock_session(all_result=[])
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.list_chapters_preview("novel-empty")
        assert result == []


# ============================================================
# get_chapter_tail
# ============================================================

class TestGetChapterTail:
    """ChapterService.get_chapter_tail()"""

    @pytest.mark.asyncio
    async def test_get_tail_returns_non_empty_content(self):
        """返回章节尾部内容"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        session = _make_mock_session(scalar_one_or_none_result="尾部正文")
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.get_chapter_tail("novel-1", 1, tail_chars=500)
        assert result == "尾部正文"

    @pytest.mark.asyncio
    async def test_get_tail_nonexistent_returns_empty(self):
        """不存在的章节返回空字符串"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        session = _make_mock_session(scalar_result="")
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.get_chapter_tail("novel-1", 999)
        assert result == ""


# ============================================================
# ChapterVersion CRUD
# ============================================================

class TestCreateChapterVersion:
    """ChapterService.create_chapter_version()"""

    @pytest.mark.asyncio
    async def test_create_version_returns_new_version_number(self):
        """创建版本返回递增的 version_number"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        ch_row = _make_chapter_row(1, "novel-1", 1, content="内容")
        # For max version query
        max_ver_result = MagicMock()
        max_ver_result.scalar_one_or_none.return_value = 2  # existing max version

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = ch_row
        mock_scalar = MagicMock()
        mock_scalar.scalar_one_or_none.return_value = 2

        session.execute = AsyncMock()
        # First call returns ch_row, second call returns max_ver
        session.execute.side_effect = [mock_result, mock_scalar]

        session.add = MagicMock()
        session.flush = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.create_chapter_version(
                "novel-1", 1, content="新版本", source="generation"
            )

        assert result == 3  # 2 + 1

    @pytest.mark.asyncio
    async def test_create_version_chapter_not_found_raises(self):
        """不存在的章节抛出 ValueError"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=mock_result)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            with pytest.raises(ValueError, match="Chapter not found"):
                await svc.create_chapter_version("novel-none", 999, content="x")


class TestListChapterVersions:
    """ChapterService.list_chapter_versions()"""

    @pytest.mark.asyncio
    async def test_list_versions_sorted_descending(self):
        """版本列表按 version_number 降序"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        v2 = _make_version_row(2, "novel-1", 1, version_number=2, is_active=True)
        v1 = _make_version_row(1, "novel-1", 1, version_number=1, is_active=False)

        session = _make_mock_session(all_result=[v2, v1])
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.list_chapter_versions("novel-1", 1)

        assert len(result) == 2
        assert result[0]["version_number"] == 2
        assert "content" not in result[0]  # 不含正文

    @pytest.mark.asyncio
    async def test_list_versions_empty(self):
        """无版本时返回空"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()
        session = _make_mock_session(all_result=[])
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.list_chapter_versions("novel-1", 1)
        assert result == []


class TestGetChapterVersion:
    """ChapterService.get_chapter_version()"""

    @pytest.mark.asyncio
    async def test_get_version_returns_full_content(self):
        """返回单个版本的完整内容"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        row = _make_version_row(1, "novel-1", 1, 2, content="版本正文", source="ai_rewrite")
        session = _make_mock_session(scalar_one_or_none_result=row)
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.get_chapter_version("novel-1", 1, 2)

        assert result is not None
        assert result["version_number"] == 2
        assert result["content"] == "版本正文"
        assert "diff_from_previous" in result

    @pytest.mark.asyncio
    async def test_get_version_not_found(self):
        """不存在的版本返回 None"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        session = _make_mock_session(scalar_one_or_none_result=None)
        with patch("src.api.services.chapter_service.get_db_session", return_value=session):
            result = await svc.get_chapter_version("novel-1", 1, 999)
        assert result is None


class TestRollbackChapterVersion:
    """ChapterService.rollback_chapter_version()"""

    @pytest.mark.asyncio
    async def test_rollback_creates_new_version_with_old_content(self):
        """回滚生成新的 version_number"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        # Mock get_chapter_version to return a target
        with patch.object(svc, "get_chapter_version") as mock_get, \
             patch.object(svc, "create_chapter_version") as mock_create:
            mock_get.return_value = {"content": "旧版本正文", "source": "generation"}
            mock_create.return_value = 4  # new version number

            result = await svc.rollback_chapter_version("novel-1", 1, 2)

        assert result == 4
        mock_create.assert_called_once_with(
            novel_id="novel-1", chapter_number=1,
            content="旧版本正文", source="rollback",
            rewrite_instruction="回滚自版本 2",
        )

    @pytest.mark.asyncio
    async def test_rollback_target_not_found(self):
        """不存在的版本回滚返回 None"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        with patch.object(svc, "get_chapter_version", return_value=None):
            result = await svc.rollback_chapter_version("novel-1", 1, 999)
        assert result is None


class TestCompareChapterVersions:
    """ChapterService.compare_chapter_versions()"""

    @pytest.mark.asyncio
    async def test_compare_returns_diff_and_word_count_change(self):
        """对比返回 diff 字符串和字数变化"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        with patch.object(svc, "get_chapter_version") as mock_get:
            def side_effect(nid, cn, vn):
                versions = {
                    1: {"content": "abc", "word_count": 3, "source": "gen", "created_at": datetime(2026, 7, 4, tzinfo=UTC)},
                    2: {"content": "abcdef", "word_count": 6, "source": "edit", "created_at": datetime(2026, 7, 4, tzinfo=UTC)},
                }
                return versions.get(vn)
            mock_get.side_effect = side_effect

            result = await svc.compare_chapter_versions("novel-1", 1, 1, 2)

        assert result is not None
        assert result["word_count_change"] == 3
        assert "diff" in result
        assert result["v1"]["version_number"] == 1
        assert result["v2"]["version_number"] == 2

    @pytest.mark.asyncio
    async def test_compare_one_version_missing(self):
        """某个版本不存在返回 None"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        with patch.object(svc, "get_chapter_version", return_value=None):
            result = await svc.compare_chapter_versions("novel-1", 1, 1, 999)
        assert result is None


class TestFixVolumeNumbers:
    """ChapterService.fix_volume_numbers()"""

    @pytest.mark.asyncio
    async def test_fix_assigns_volume_number_by_volume_range(self):
        """根据卷的范围为 NULL volume_number 的章节赋值"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        # Mock get_volume_service to return volumes with ranges
        with patch("src.api.services.volume_service.get_volume_service") as mock_get_vs:
            mock_vs = MagicMock()
            mock_vs.list_volumes = AsyncMock(return_value=[
                {"volume_number": 1, "chapter_start": 1, "chapter_end": 5},
                {"volume_number": 2, "chapter_start": 6, "chapter_end": 10},
            ])
            mock_get_vs.return_value = mock_vs

            session = AsyncMock()
            mock_exec = AsyncMock()
            mock_exec.rowcount = 3
            session.execute = AsyncMock(return_value=mock_exec)
            session.__aenter__ = AsyncMock(return_value=session)
            session.__aexit__ = AsyncMock(return_value=None)

            with patch("src.api.services.chapter_service.get_db_session", return_value=session):
                result = await svc.fix_volume_numbers("novel-1")

        assert result == 6

    @pytest.mark.asyncio
    async def test_fix_no_volumes_returns_zero(self):
        """没有卷定义时返回 0"""
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()

        with patch("src.api.services.volume_service.get_volume_service") as mock_get_vs:
            mock_vs = MagicMock()
            mock_vs.list_volumes = AsyncMock(return_value=[])
            mock_get_vs.return_value = mock_vs


            session = _make_mock_session(all_result=[])
            with patch("src.api.services.chapter_service.get_db_session", return_value=session):
                result = await svc.fix_volume_numbers("novel-1")
        assert result == 0
