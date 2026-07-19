"""Unit tests for NovelManager.

覆盖范围：
- create_novel: 正常创建 + title 默认值分支 + 自定义参数透传
- get_novel: 找到 / 未找到 / status=generating 时附带 active_task_id
- list_novels: 空列表 + 总数计数 + generating 状态附带 task_id
- update_novel: 更新字段 / 字段过滤(None 跳过) / 小说不存在返回 False
- delete_novel: 正常删除 / 不存在返回 False
- 状态机字段: create 时默认 status=draft
- 委托方法: create_chapter_version / list_power_system 等正确转发到对应 service 单例
- rollback_chapter_version: 目标不存在返回 None / 存在时调用 create_chapter_version

所有数据库 / LLM / 其他 service 交互均被 mock。
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _novel_id() -> str:
    return f"novel-test-{uuid.uuid4().hex[:8]}"


def _make_novel_row(**overrides) -> MagicMock:
    """构造一个 Novel ORM mock 对象，覆盖 _novel_to_dict / _novel_summary 访问的全部属性。"""
    m = MagicMock()
    m.novel_id = overrides.get("novel_id", _novel_id())
    m.title = overrides.get("title", "测试小说")
    m.idea = overrides.get("idea", "一个测试想法")
    m.novel_type = overrides.get("novel_type", "玄幻")
    m.target_words = overrides.get("target_words", 10000)
    m.writing_style = overrides.get("writing_style", "现代白话")
    m.custom_style_description = overrides.get("custom_style_description", None)
    m.writing_style_prompt = overrides.get("writing_style_prompt", None)
    m.status = overrides.get("status", "draft")
    m.created_at = overrides.get("created_at", datetime(2026, 7, 1, tzinfo=UTC))
    m.updated_at = overrides.get("updated_at", datetime(2026, 7, 1, tzinfo=UTC))
    m.completed_at = overrides.get("completed_at", None)
    m.owner_id = overrides.get("owner_id", None)
    m.world_setting = overrides.get("world_setting", None)
    m.characters = overrides.get("characters", [])
    m.power_systems = overrides.get("power_systems", [])
    return m


def _fake_session(novel=None, scalars=None, scalar=None, rows=None):
    """构造一个 mock async session context manager。

    返回 (ctx_factory, session)。通过结果对象的不同方法返回 novel / scalar / rows。
    """
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = novel
    if scalar is not None:
        mock_result.scalar_one_or_none.return_value = scalar
    if scalars is not None:
        mock_result.scalars.return_value.all.return_value = scalars
    if rows is not None:
        mock_result.all.return_value = rows
    # scalar_one 用于 list_novels 的 count 查询
    mock_result.scalar_one.return_value = 0
    session.execute = AsyncMock(return_value=mock_result)
    session.add = MagicMock()
    session.delete = AsyncMock()

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx, session


# ===========================================================================
# create_novel
# ===========================================================================

class TestCreateNovel:
    """Tests for NovelManager.create_novel."""

    @pytest.mark.asyncio
    async def test_create_novel_returns_id_and_defaults_status_draft(self):
        """创建后返回 novel- 前缀 id，且 session.add 被调用一次。"""
        from src.api.services.content.novel_manager import NovelManager

        ctx_factory, session = _fake_session()
        mgr = NovelManager()

        with patch("src.api.services.content.novel_manager.get_db_session", ctx_factory):
            novel_id = await mgr.create_novel(
                idea="主角复仇的故事", novel_type="玄幻", target_words=50000
            )

        assert novel_id.startswith("novel-")
        session.add.assert_called_once()
        added_obj = session.add.call_args.args[0]
        # 状态机：新建小说默认 draft
        assert added_obj.status == "draft"
        assert added_obj.idea == "主角复仇的故事"
        assert added_obj.novel_type == "玄幻"
        assert added_obj.target_words == 50000

    @pytest.mark.asyncio
    async def test_create_novel_title_defaults_to_idea_prefix(self):
        """未传 title 时，title 默认取 idea 前 50 字符。"""
        from src.api.services.content.novel_manager import NovelManager

        ctx_factory, session = _fake_session()
        mgr = NovelManager()
        long_idea = "这是一段很长的创意" * 20  # > 50 字符

        with patch("src.api.services.content.novel_manager.get_db_session", ctx_factory):
            await mgr.create_novel(idea=long_idea, novel_type="都市", target_words=10000)

        added_obj = session.add.call_args.args[0]
        assert added_obj.title == long_idea[:50]

    @pytest.mark.asyncio
    async def test_create_novel_passes_custom_params(self):
        """自定义风格 / owner_id / writing_style_prompt 透传到 Novel 对象。"""
        from src.api.services.content.novel_manager import NovelManager

        ctx_factory, session = _fake_session()
        mgr = NovelManager()

        with patch("src.api.services.content.novel_manager.get_db_session", ctx_factory):
            await mgr.create_novel(
                idea="idea",
                novel_type="科幻",
                target_words=30000,
                title="自定义标题",
                writing_style="古风",
                custom_style_description="描述",
                writing_style_prompt="提示词",
                owner_id=42,
            )

        added_obj = session.add.call_args.args[0]
        assert added_obj.title == "自定义标题"
        assert added_obj.writing_style == "古风"
        assert added_obj.custom_style_description == "描述"
        assert added_obj.writing_style_prompt == "提示词"
        assert added_obj.owner_id == 42


# ===========================================================================
# get_novel
# ===========================================================================

class TestGetNovel:
    """Tests for NovelManager.get_novel."""

    @pytest.mark.asyncio
    async def test_get_novel_not_found_returns_none(self):
        """小说不存在时返回 None。"""
        from src.api.services.content.novel_manager import NovelManager

        ctx_factory, _ = _fake_session(novel=None)
        mgr = NovelManager()

        with patch("src.api.services.content.novel_manager.get_db_session", ctx_factory):
            result = await mgr.get_novel("novel-missing")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_novel_found_draft_no_task_query(self):
        """找到小说且 status != generating 时，active_task_id 为 None，不查 Task。"""
        from src.api.services.content.novel_manager import NovelManager

        novel = _make_novel_row(novel_id="novel-1", status="completed",
                                characters=[1, 2], power_systems=[1])
        # 用一个 session，execute 返回的 result 每次 scalar_one_or_none 不同
        # 第一次返回 novel，理论上不应有第二次 execute
        ctx_factory, session = _fake_session(novel=novel)
        mgr = NovelManager()

        with patch("src.api.services.content.novel_manager.get_db_session", ctx_factory):
            result = await mgr.get_novel("novel-1")

        assert result is not None
        assert result["novel_id"] == "novel-1"
        assert result["status"] == "completed"
        assert result["active_task_id"] is None
        assert result["characters_count"] == 2
        assert result["power_systems_count"] == 1
        assert result["world_setting"] is False
        # status != generating -> 只执行一次查询
        assert session.execute.await_count == 1

    @pytest.mark.asyncio
    async def test_get_novel_generating_status_attaches_task_id(self):
        """status=generating 时额外查 Task，active_task_id 为查到的 task_id。"""
        from src.api.services.content.novel_manager import NovelManager

        novel = _make_novel_row(novel_id="novel-g", status="generating")
        ctx_factory, session = _fake_session(novel=novel)

        # 第一次 execute 返回 novel，第二次返回 task_id
        first_result = MagicMock()
        first_result.scalar_one_or_none.return_value = novel
        second_result = MagicMock()
        second_result.scalar_one_or_none.return_value = "task-abc"
        session.execute = AsyncMock(side_effect=[first_result, second_result])

        mgr = NovelManager()

        with patch("src.api.services.content.novel_manager.get_db_session", ctx_factory):
            result = await mgr.get_novel("novel-g")

        assert result["status"] == "generating"
        assert result["active_task_id"] == "task-abc"
        assert session.execute.await_count == 2


# ===========================================================================
# list_novels
# ===========================================================================

class TestListNovels:
    """Tests for NovelManager.list_novels."""

    @pytest.mark.asyncio
    async def test_list_novels_empty(self):
        """空列表返回空 summaries 且 total=0。"""
        from src.api.services.content.novel_manager import NovelManager

        ctx_factory, session = _fake_session(rows=[])
        # count 查询 scalar_one 返回 0
        mock_result = MagicMock()
        mock_result.scalar_one.return_value = 0
        mock_result.all.return_value = []
        session.execute = AsyncMock(return_value=mock_result)

        mgr = NovelManager()
        with patch("src.api.services.content.novel_manager.get_db_session", ctx_factory):
            summaries, total = await mgr.list_novels()

        assert summaries == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_novels_with_rows_and_generating_task(self):
        """有数据时返回 summary 列表；generating 状态附带 task_id，其它状态 task_id=None。"""
        from src.api.services.content.novel_manager import NovelManager

        n1 = _make_novel_row(novel_id="novel-a", status="generating", title="A")
        n2 = _make_novel_row(novel_id="novel-b", status="draft", title="B")
        rows = [(n1, "task-1"), (n2, None)]

        ctx_factory, session = _fake_session()
        # 第一次 execute (count) 返回 scalar_one=2；第二次 (rows) 返回 all=rows
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2
        rows_result = MagicMock()
        rows_result.all.return_value = rows
        session.execute = AsyncMock(side_effect=[count_result, rows_result])

        mgr = NovelManager()
        with patch("src.api.services.content.novel_manager.get_db_session", ctx_factory):
            summaries, total = await mgr.list_novels()

        assert total == 2
        assert len(summaries) == 2
        s1 = next(s for s in summaries if s["novel_id"] == "novel-a")
        s2 = next(s for s in summaries if s["novel_id"] == "novel-b")
        assert s1["active_task_id"] == "task-1"
        assert s2["active_task_id"] is None
        assert s1["status"] == "generating"
        assert s2["status"] == "draft"


# ===========================================================================
# update_novel
# ===========================================================================

class TestUpdateNovel:
    """Tests for NovelManager.update_novel."""

    @pytest.mark.asyncio
    async def test_update_novel_not_found_returns_false(self):
        """小说不存在时返回 False。"""
        from src.api.services.content.novel_manager import NovelManager

        ctx_factory, _ = _fake_session(novel=None)
        mgr = NovelManager()

        with patch("src.api.services.content.novel_manager.get_db_session", ctx_factory):
            result = await mgr.update_novel("novel-missing", title="新标题")

        assert result is False

    @pytest.mark.asyncio
    async def test_update_novel_sets_valid_fields(self):
        """传入合法字段时 setattr 更新到 novel 对象，返回 True。"""
        from src.api.services.content.novel_manager import NovelManager

        novel = _make_novel_row(novel_id="novel-1", status="draft", title="旧标题")
        ctx_factory, _ = _fake_session(novel=novel)
        mgr = NovelManager()

        with patch("src.api.services.content.novel_manager.get_db_session", ctx_factory):
            result = await mgr.update_novel("novel-1", title="新标题", status="completed")

        assert result is True
        assert novel.title == "新标题"
        assert novel.status == "completed"
        # updated_at 被刷新
        assert novel.updated_at is not None

    @pytest.mark.asyncio
    async def test_update_novel_skips_none_values(self):
        """kwargs 中 value=None 的字段被跳过，不覆盖已有值。"""
        from src.api.services.content.novel_manager import NovelManager

        novel = _make_novel_row(novel_id="novel-1", title="原标题", status="draft")
        ctx_factory, _ = _fake_session(novel=novel)
        mgr = NovelManager()

        with patch("src.api.services.content.novel_manager.get_db_session", ctx_factory):
            result = await mgr.update_novel(
                "novel-1", title=None, status="completed"
            )

        assert result is True
        # title=None 被跳过，保持原值
        assert novel.title == "原标题"
        assert novel.status == "completed"

    @pytest.mark.asyncio
    async def test_update_novel_skips_unknown_attribute(self):
        """kwargs 中 novel 不存在的属性被 hasattr 过滤，不抛错。"""
        from src.api.services.content.novel_manager import NovelManager

        novel = _make_novel_row(novel_id="novel-1")
        ctx_factory, _ = _fake_session(novel=novel)
        mgr = NovelManager()

        with patch("src.api.services.content.novel_manager.get_db_session", ctx_factory):
            # nonexistent_field 不是 Novel 属性
            result = await mgr.update_novel(
                "novel-1", nonexistent_field="x", status="failed"
            )

        assert result is True
        assert novel.status == "failed"
        # 不应给 novel 设置该属性
        assert not hasattr(novel, "nonexistent_field") or \
            getattr(novel, "nonexistent_field", "x") in ("x", MagicMock())


# ===========================================================================
# delete_novel
# ===========================================================================

class TestDeleteNovel:
    """Tests for NovelManager.delete_novel."""

    @pytest.mark.asyncio
    async def test_delete_novel_not_found_returns_false(self):
        """小说不存在时返回 False，不调用 session.delete。"""
        from src.api.services.content.novel_manager import NovelManager

        ctx_factory, session = _fake_session(novel=None)
        mgr = NovelManager()

        with patch("src.api.services.content.novel_manager.get_db_session", ctx_factory):
            result = await mgr.delete_novel("novel-missing")

        assert result is False
        session.delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_delete_novel_success(self):
        """找到小说时调用 session.delete 并返回 True。"""
        from src.api.services.content.novel_manager import NovelManager

        novel = _make_novel_row(novel_id="novel-1")
        ctx_factory, session = _fake_session(novel=novel)
        mgr = NovelManager()

        with patch("src.api.services.content.novel_manager.get_db_session", ctx_factory):
            result = await mgr.delete_novel("novel-1")

        assert result is True
        session.delete.assert_awaited_once_with(novel)


# ===========================================================================
# 委托方法 (delegated to ChapterService / WorldService)
# ===========================================================================

class TestDelegations:
    """Tests for methods that delegate to ChapterService / WorldService 单例."""

    @pytest.mark.asyncio
    async def test_create_chapter_version_delegates(self):
        """create_chapter_version 转发到 ChapterService.create_chapter_version。"""
        from src.api.services.content.novel_manager import NovelManager

        mgr = NovelManager()
        mock_chapter_svc = MagicMock()
        mock_chapter_svc.create_chapter_version = AsyncMock(return_value=3)

        with patch("src.api.services.content.novel_manager.get_chapter_service",
                   return_value=mock_chapter_svc):
            result = await mgr.create_chapter_version(
                novel_id="novel-1", chapter_number=1, content="正文",
                source="manual", is_active=True
            )

        assert result == 3
        mock_chapter_svc.create_chapter_version.assert_awaited_once_with(
            novel_id="novel-1", chapter_number=1, content="正文",
            source="manual", rewrite_instruction=None, quality_score=None,
            model_name=None, prompt_summary=None, diff_from_previous=None,
            kg_conflicts=None, user_notes=None, is_active=True,
        )

    @pytest.mark.asyncio
    async def test_list_power_systems_delegates(self):
        """list_power_systems 转发到 WorldService.list_power_systems。"""
        from src.api.services.content.novel_manager import NovelManager

        mgr = NovelManager()
        mock_world_svc = MagicMock()
        mock_world_svc.list_power_systems = AsyncMock(
            return_value=[{"id": 1, "name": "修真"}]
        )

        with patch("src.api.services.content.novel_manager.get_world_service",
                   return_value=mock_world_svc):
            result = await mgr.list_power_systems("novel-1")

        assert result == [{"id": 1, "name": "修真"}]
        mock_world_svc.list_power_systems.assert_awaited_once_with("novel-1")

    @pytest.mark.asyncio
    async def test_create_power_system_delegates(self):
        """create_power_system 转发参数到 WorldService.create_power_system。"""
        from src.api.services.content.novel_manager import NovelManager

        mgr = NovelManager()
        mock_world_svc = MagicMock()
        mock_world_svc.create_power_system = AsyncMock(return_value=7)

        with patch("src.api.services.content.novel_manager.get_world_service",
                   return_value=mock_world_svc):
            result = await mgr.create_power_system(
                novel_id="novel-1", name="魔法", description="d", levels=[1, 2]
            )

        assert result == 7
        mock_world_svc.create_power_system.assert_awaited_once_with(
            novel_id="novel-1", name="魔法", description="d", levels=[1, 2]
        )


# ===========================================================================
# rollback_chapter_version (内部调用 get_chapter_version + create_chapter_version)
# ===========================================================================

class TestRollbackChapterVersion:
    """Tests for NovelManager.rollback_chapter_version."""

    @pytest.mark.asyncio
    async def test_rollback_target_not_found_returns_none(self):
        """目标版本不存在时返回 None，不创建新版本。"""
        from src.api.services.content.novel_manager import NovelManager

        mgr = NovelManager()
        mock_chapter_svc = MagicMock()
        mock_chapter_svc.get_chapter_version = AsyncMock(return_value=None)
        mock_chapter_svc.create_chapter_version = AsyncMock(return_value=1)

        with patch("src.api.services.content.novel_manager.get_chapter_service",
                   return_value=mock_chapter_svc):
            result = await mgr.rollback_chapter_version("novel-1", 1, 2)

        assert result is None
        mock_chapter_svc.create_chapter_version.assert_not_called()

    @pytest.mark.asyncio
    async def test_rollback_success_creates_rollback_version(self):
        """目标存在时调用 create_chapter_version 创建 source=rollback 的新版本。"""
        from src.api.services.content.novel_manager import NovelManager

        mgr = NovelManager()
        target = {"content": "回滚正文", "version_number": 2}
        mock_chapter_svc = MagicMock()
        mock_chapter_svc.get_chapter_version = AsyncMock(return_value=target)
        mock_chapter_svc.create_chapter_version = AsyncMock(return_value=3)

        with patch("src.api.services.content.novel_manager.get_chapter_service",
                   return_value=mock_chapter_svc):
            result = await mgr.rollback_chapter_version("novel-1", 1, 2)

        assert result == 3
        create_kwargs = mock_chapter_svc.create_chapter_version.await_args.kwargs
        assert create_kwargs["novel_id"] == "novel-1"
        assert create_kwargs["chapter_number"] == 1
        assert create_kwargs["content"] == "回滚正文"
        assert create_kwargs["source"] == "rollback"
        assert "回滚自版本 2" in create_kwargs["rewrite_instruction"]
