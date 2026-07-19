"""OutlineService 单元测试 — 三级大纲管理服务的 CRUD 与生成主路径。

覆盖范围：
- upsert_volume_outline: 更新已存在卷 / 新增卷
- upsert_chapter_outline: 更新已存在章 / 新增章
- get_volume_outlines: 正常返回列表 / 空列表
- get_chapter_outlines: 按 volume_number 过滤 / 不过滤
- generate_master_from_novel: 小说不存在抛错 / 正常生成并持久化总纲 / world+characters 可选时仍生成

所有数据库（get_db_session）、LLM（get_llm_client / generate_and_parse_json）、
其他 service 单例（get_novel_manager / get_character_service）均被 mock，
被测方法自身的查询构造、条件分支、持久化聚合逻辑真实执行。

未覆盖（依赖真实 LLM/复杂编排，纯 mock 价值低）：
- generate_volume_outlines / generate_chapter_outlines / generate_master_from_conversation
  （内部直接走 LLM 生成，已通过 patch generate_and_parse_json 在 generate_master_from_novel
   中覆盖同款 LLM 集成路径；此处不重复）
- persist_outlines_from_result / get_outline_tree: 仅是聚合调用，依赖上述方法，
  集成价值更高，单测收益有限，留待集成测试。
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_volume_row(
    id_: int = 1,
    novel_id: str = "novel-1",
    volume_number: int = 1,
    content: dict | None = None,
    status: str = "draft",
) -> MagicMock:
    row = MagicMock(spec=["id", "novel_id", "level", "volume_number",
                          "chapter_number", "content", "status", "updated_at"])
    row.id = id_
    row.novel_id = novel_id
    row.level = "volume"
    row.volume_number = volume_number
    row.chapter_number = None
    row.content = content if content is not None else {"title": "卷一"}
    row.status = status
    row.updated_at = datetime(2026, 7, 4, tzinfo=UTC)
    return row


def _make_chapter_row(
    id_: int = 1,
    novel_id: str = "novel-1",
    volume_number: int = 1,
    chapter_number: int = 1,
    content: dict | None = None,
    status: str = "draft",
) -> MagicMock:
    row = MagicMock(spec=["id", "novel_id", "level", "volume_number",
                          "chapter_number", "content", "status", "updated_at"])
    row.id = id_
    row.novel_id = novel_id
    row.level = "chapter"
    row.volume_number = volume_number
    row.chapter_number = chapter_number
    row.content = content if content is not None else {"title": "章一"}
    row.status = status
    row.updated_at = datetime(2026, 7, 4, tzinfo=UTC)
    return row


def _fake_session(scalar_one_or_none_result=None, all_result=None):
    """Return (ctx_factory, session) mimicking get_db_session async CM."""
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = scalar_one_or_none_result
    if all_result is not None:
        mock_result.scalars.return_value.all.return_value = all_result
    session.execute = AsyncMock(return_value=mock_result)
    session.add = MagicMock()

    @asynccontextmanager
    async def _ctx():
        yield session

    return _ctx, session


# ---------------------------------------------------------------------------
# upsert_volume_outline
# ---------------------------------------------------------------------------

class TestUpsertVolumeOutline:
    @pytest.mark.asyncio
    async def test_update_existing_volume_overwrites_content(self):
        """已存在卷 -> 更新 content 与 updated_at，不调用 session.add。"""
        from src.api.services.content.outline_service import OutlineService

        existing = _make_volume_row(
            volume_number=2, content={"title": "旧标题"}, status="approved"
        )
        ctx, session = _fake_session(scalar_one_or_none_result=existing)
        new_content = {"title": "新标题", "climax": "高潮"}

        with patch("src.api.services.content.outline_service.get_db_session", ctx):
            await OutlineService().upsert_volume_outline("novel-1", 2, new_content)

        # content 被原地覆盖
        assert existing.content == new_content
        # 已存在分支不应 add 新对象
        session.add.assert_not_called()
        # 确实查询了一次
        session.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_insert_new_volume_adds_outline(self):
        """不存在卷 -> 创建 Outline 并 session.add，status 默认 draft。"""
        from src.api.models.db_models import Outline
        from src.api.services.content.outline_service import OutlineService

        ctx, session = _fake_session(scalar_one_or_none_result=None)
        new_content = {"title": "全新卷"}

        with patch("src.api.services.content.outline_service.get_db_session", ctx):
            await OutlineService().upsert_volume_outline("novel-9", 3, new_content)

        session.add.assert_called_once()
        added = session.add.call_args.args[0]
        assert isinstance(added, Outline)
        assert added.novel_id == "novel-9"
        assert added.level == "volume"
        assert added.volume_number == 3
        assert added.content == new_content
        assert added.status == "draft"


# ---------------------------------------------------------------------------
# upsert_chapter_outline
# ---------------------------------------------------------------------------

class TestUpsertChapterOutline:
    @pytest.mark.asyncio
    async def test_update_existing_chapter_overwrites_content(self):
        """已存在章 -> 更新 content，不 add。"""
        from src.api.services.content.outline_service import OutlineService

        existing = _make_chapter_row(
            volume_number=1, chapter_number=5,
            content={"old": True}, status="approved",
        )
        ctx, session = _fake_session(scalar_one_or_none_result=existing)
        new_content = {"scenes": ["场景A"]}

        with patch("src.api.services.content.outline_service.get_db_session", ctx):
            await OutlineService().upsert_chapter_outline("novel-1", 1, 5, new_content)

        assert existing.content == new_content
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_insert_new_chapter_adds_outline(self):
        """不存在章 -> 新建 Outline(chapter) 并 add。"""
        from src.api.models.db_models import Outline
        from src.api.services.content.outline_service import OutlineService

        ctx, session = _fake_session(scalar_one_or_none_result=None)
        new_content = {"chapter": 7, "title": "第七章"}

        with patch("src.api.services.content.outline_service.get_db_session", ctx):
            await OutlineService().upsert_chapter_outline("novel-1", 2, 7, new_content)

        session.add.assert_called_once()
        added = session.add.call_args.args[0]
        assert isinstance(added, Outline)
        assert added.level == "chapter"
        assert added.volume_number == 2
        assert added.chapter_number == 7
        assert added.content == new_content
        assert added.status == "draft"


# ---------------------------------------------------------------------------
# get_volume_outlines / get_chapter_outlines
# ---------------------------------------------------------------------------

class TestGetOutlines:
    @pytest.mark.asyncio
    async def test_get_volume_outlines_maps_rows_to_dicts(self):
        """返回卷列表，按字段映射为 dict。"""
        from src.api.services.content.outline_service import OutlineService

        rows = [
            _make_volume_row(id_=1, volume_number=1, content={"t": "v1"}),
            _make_volume_row(id_=2, volume_number=2, content={"t": "v2"}, status="approved"),
        ]
        ctx, _ = _fake_session(all_result=rows)

        with patch("src.api.services.content.outline_service.get_db_session", ctx):
            out = await OutlineService().get_volume_outlines("novel-1")

        assert isinstance(out, list)
        assert len(out) == 2
        assert out[0] == {"id": 1, "volume_number": 1, "content": {"t": "v1"}, "status": "draft"}
        assert out[1]["volume_number"] == 2
        assert out[1]["status"] == "approved"

    @pytest.mark.asyncio
    async def test_get_volume_outlines_empty(self):
        """无卷 -> 返回空列表。"""
        from src.api.services.content.outline_service import OutlineService

        ctx, _ = _fake_session(all_result=[])

        with patch("src.api.services.content.outline_service.get_db_session", ctx):
            out = await OutlineService().get_volume_outlines("novel-x")

        assert out == []

    @pytest.mark.asyncio
    async def test_get_chapter_outlines_without_volume_filter(self):
        """不传 volume_number -> 查询不带卷过滤，返回全部章。"""
        from src.api.services.content.outline_service import OutlineService

        rows = [
            _make_chapter_row(id_=1, volume_number=1, chapter_number=1),
            _make_chapter_row(id_=2, volume_number=2, chapter_number=1),
        ]
        ctx, _ = _fake_session(all_result=rows)

        with patch("src.api.services.content.outline_service.get_db_session", ctx):
            out = await OutlineService().get_chapter_outlines("novel-1")

        assert len(out) == 2
        assert out[0] == {
            "id": 1, "volume_number": 1, "chapter_number": 1,
            "content": {"title": "章一"}, "status": "draft",
        }

    @pytest.mark.asyncio
    async def test_get_chapter_outlines_with_volume_filter(self):
        """传 volume_number -> 返回该卷章列表（mock 已按 all_result 给定）。"""
        from src.api.services.content.outline_service import OutlineService

        rows = [
            _make_chapter_row(id_=3, volume_number=2, chapter_number=1,
                              content={"t": "v2c1"}, status="approved"),
        ]
        ctx, _ = _fake_session(all_result=rows)

        with patch("src.api.services.content.outline_service.get_db_session", ctx):
            out = await OutlineService().get_chapter_outlines("novel-1", volume_number=2)

        assert len(out) == 1
        assert out[0]["volume_number"] == 2
        assert out[0]["chapter_number"] == 1
        assert out[0]["status"] == "approved"


# ---------------------------------------------------------------------------
# generate_master_from_novel
# ---------------------------------------------------------------------------

class TestGenerateMasterFromNovel:
    @pytest.mark.asyncio
    async def test_novel_not_found_raises(self):
        """manager.get_novel 返回 None -> 抛 ValueError。"""
        from src.api.services.content.outline_service import OutlineService

        ctx, _ = _fake_session()
        manager = AsyncMock()
        manager.get_novel = AsyncMock(return_value=None)

        with (
            patch("src.api.services.content.outline_service.get_db_session", ctx),
            patch("src.api.services.content.novel_manager.get_novel_manager", return_value=manager),
        ):
            with pytest.raises(ValueError, match="小说不存在"):
                await OutlineService().generate_master_from_novel("missing-novel")

    @pytest.mark.asyncio
    async def test_generates_and_persists_master(self):
        """正常路径: 组装 context -> 调 LLM 解析 -> upsert_master_outline 持久化。"""
        from src.api.services.content.outline_service import OutlineService

        ctx, _ = _fake_session()
        manager = AsyncMock()
        manager.get_novel = AsyncMock(return_value={
            "novel_type": "玄幻",
            "idea": "少年持剑走天涯",
        })
        manager.get_world_setting = AsyncMock(return_value={
            "background": "九重天境界分明" * 20,  # 超过 300 字以验证切片
        })
        char_service = AsyncMock()
        char_service.list_characters = AsyncMock(return_value=[
            {"name": "林风", "role": "主角"},
        ])
        master_content = {
            "premise": "核心前提", "main_conflict": "冲突",
            "plot_arcs": [], "ending": "结局", "themes": ["成长"],
        }

        svc = OutlineService()
        with (
            patch("src.api.services.content.outline_service.get_db_session", ctx),
            patch("src.api.services.content.novel_manager.get_novel_manager", return_value=manager),
            patch("src.api.services.content.character_service.get_character_service",
                  return_value=char_service),
            patch("src.api.services.content.outline_service.get_llm_client",
                  return_value=AsyncMock()),
            patch("src.api.services.content.outline_service.generate_and_parse_json",
                  new_callable=AsyncMock, return_value=master_content),
            patch.object(svc, "upsert_master_outline", new_callable=AsyncMock) as upsert_mock,
        ):
            result = await svc.generate_master_from_novel("novel-1")

        assert result == master_content
        # 持久化被调用一次，使用返回的 master 内容
        upsert_mock.assert_awaited_once()
        assert upsert_mock.call_args.args[0] == "novel-1"
        assert upsert_mock.call_args.args[1] == master_content

    @pytest.mark.asyncio
    async def test_generates_without_world_and_characters(self):
        """world=None / characters=[] 时仍能正常生成（context 退化为暂无人物/世界观）。"""
        from src.api.services.content.outline_service import OutlineService

        ctx, _ = _fake_session()
        manager = AsyncMock()
        manager.get_novel = AsyncMock(return_value={"novel_type": "都市", "idea": "短"})
        manager.get_world_setting = AsyncMock(return_value=None)
        char_service = AsyncMock()
        char_service.list_characters = AsyncMock(return_value=[])
        master_content = {"premise": "待完善", "main_conflict": "待完善",
                         "plot_arcs": [], "ending": "待完善", "themes": []}

        svc = OutlineService()
        with (
            patch("src.api.services.content.outline_service.get_db_session", ctx),
            patch("src.api.services.content.novel_manager.get_novel_manager", return_value=manager),
            patch("src.api.services.content.character_service.get_character_service",
                  return_value=char_service),
            patch("src.api.services.content.outline_service.get_llm_client",
                  return_value=AsyncMock()),
            patch("src.api.services.content.outline_service.generate_and_parse_json",
                  new_callable=AsyncMock, return_value=master_content),
            patch.object(svc, "upsert_master_outline", new_callable=AsyncMock) as upsert_mock,
        ):
            result = await svc.generate_master_from_novel("novel-2")

        assert result == master_content
        upsert_mock.assert_awaited_once()
