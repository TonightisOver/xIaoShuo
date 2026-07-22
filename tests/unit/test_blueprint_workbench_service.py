"""BlueprintWorkbenchService 单元测试。

聚合查询：章节摘要列表（含未生成）+ workspace 详情 + options。
所有 DB 交互通过 mock session 注入，禁止真实 LLM/DB。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.content.blueprint_workbench_service import (
    BlueprintWorkbenchService,
)


def _row(**kw):
    """构造一个 mock ORM 行，按属性名访问。"""
    m = MagicMock()
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def _session_ctx(rows_by_stmt=None):
    """构造 async session context manager；rows_by_stmt: list[返回 result]。"""
    session = AsyncMock()

    results = list(rows_by_stmt or [])

    async def execute(stmt, *a, **kw):
        return results.pop(0) if results else MagicMock()

    session.execute = AsyncMock(side_effect=execute)

    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *a):
            return False

    return _Ctx, session


@pytest.mark.asyncio
async def test_list_summaries_includes_chapters_without_blueprint():
    """Outline 有章号但无 ChapterBlueprint → 仍出现且 has_blueprint=false。"""
    svc = BlueprintWorkbenchService()
    # mock _load_* 方法返回原始 ORM 行集合
    with (
        patch.object(svc, "_load_chapter_outlines", new=AsyncMock(return_value=[
            _row(chapter_number=1, volume_number=1, content={"title": "首章"}),
            _row(chapter_number=2, volume_number=1, content={"title": "次章"}),
        ])),
        patch.object(svc, "_load_active_blueprints", new=AsyncMock(return_value={
            1: _row(chapter_number=1, version_number=3, updated_at="t1"),
        })),
        patch.object(svc, "_load_chapters", new=AsyncMock(return_value={
            2: _row(chapter_number=2, title="次章正文", quality_status="verified"),
        })),
        patch.object(svc, "_load_volumes", new=AsyncMock(return_value=[])),
        patch.object(svc, "_load_blueprint_controls", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_generating_chapters", new=AsyncMock(return_value=set())),
    ):
        result = await svc.list_chapter_summaries("novel-1")

    items = result["items"]
    assert len(items) == 2
    ch1 = next(i for i in items if i["chapter_number"] == 1)
    ch2 = next(i for i in items if i["chapter_number"] == 2)
    assert ch1["has_blueprint"] is True
    assert ch1["blueprint_version"] == 3
    assert ch2["has_blueprint"] is False
    assert ch2["blueprint_version"] is None
    assert ch2["has_chapter"] is True
    assert ch2["quality_status"] == "verified"
    # 章号排序
    assert [i["chapter_number"] for i in items] == [1, 2]
    assert result["total"] == 2


@pytest.mark.asyncio
async def test_list_summaries_dedup_by_chapter_number():
    """多源同章号合并为一行。"""
    svc = BlueprintWorkbenchService()
    with (
        patch.object(svc, "_load_chapter_outlines", new=AsyncMock(return_value=[
            _row(chapter_number=5, volume_number=1, content={"title": "大纲"}),
        ])),
        patch.object(svc, "_load_active_blueprints", new=AsyncMock(return_value={
            5: _row(chapter_number=5, version_number=1, updated_at="t"),
        })),
        patch.object(svc, "_load_chapters", new=AsyncMock(return_value={
            5: _row(chapter_number=5, title="正文", quality_status=None),
        })),
        patch.object(svc, "_load_volumes", new=AsyncMock(return_value=[])),
        patch.object(svc, "_load_blueprint_controls", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_generating_chapters", new=AsyncMock(return_value=set())),
    ):
        result = await svc.list_chapter_summaries("novel-1")
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["has_outline"] is True
    assert item["has_blueprint"] is True
    assert item["has_chapter"] is True


@pytest.mark.asyncio
async def test_list_summaries_filter_by_volume():
    svc = BlueprintWorkbenchService()
    with (
        patch.object(svc, "_load_chapter_outlines", new=AsyncMock(return_value=[
            _row(chapter_number=1, volume_number=1, content={}),
            _row(chapter_number=2, volume_number=2, content={}),
        ])),
        patch.object(svc, "_load_active_blueprints", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_chapters", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_volumes", new=AsyncMock(return_value=[])),
        patch.object(svc, "_load_blueprint_controls", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_generating_chapters", new=AsyncMock(return_value=set())),
    ):
        result = await svc.list_chapter_summaries("novel-1", volume_number=2)
    assert [i["chapter_number"] for i in result["items"]] == [2]


@pytest.mark.asyncio
async def test_list_summaries_page_size_capped_at_100():
    svc = BlueprintWorkbenchService()
    outlines = [_row(chapter_number=i, volume_number=1, content={}) for i in range(1, 151)]
    with (
        patch.object(svc, "_load_chapter_outlines", new=AsyncMock(return_value=outlines)),
        patch.object(svc, "_load_active_blueprints", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_chapters", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_volumes", new=AsyncMock(return_value=[])),
        patch.object(svc, "_load_blueprint_controls", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_generating_chapters", new=AsyncMock(return_value=set())),
    ):
        result = await svc.list_chapter_summaries("novel-1", page=1, page_size=200)
    assert result["page_size"] == 100
    assert len(result["items"]) == 100
    assert result["total"] == 150


@pytest.mark.asyncio
async def test_list_summaries_status_counts():
    svc = BlueprintWorkbenchService()
    # ch1 有蓝图无 control → draft；ch2 无蓝图 → not_generated
    with (
        patch.object(svc, "_load_chapter_outlines", new=AsyncMock(return_value=[
            _row(chapter_number=1, volume_number=1, content={}),
            _row(chapter_number=2, volume_number=1, content={}),
        ])),
        patch.object(svc, "_load_active_blueprints", new=AsyncMock(return_value={
            1: _row(chapter_number=1, version_number=1, updated_at="t"),
        })),
        patch.object(svc, "_load_chapters", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_volumes", new=AsyncMock(return_value=[])),
        patch.object(svc, "_load_blueprint_controls", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_generating_chapters", new=AsyncMock(return_value=set())),
    ):
        result = await svc.list_chapter_summaries("novel-1")
    assert result["status_counts"]["draft"] == 1
    assert result["status_counts"]["not_generated"] == 1


@pytest.mark.asyncio
async def test_get_workspace_aggregates_all_fields():
    svc = BlueprintWorkbenchService()
    with (
        patch.object(svc, "_get_blueprint_dict", new=AsyncMock(return_value={"chapter_type": "climax"})),
        patch.object(svc, "_get_control_dict", new=AsyncMock(return_value={"control_status": "draft", "version": 1, "locked": False})),
        patch.object(svc, "_get_versions_list", new=AsyncMock(return_value=[{"version_number": 1}])),
        patch.object(svc, "_get_chapter_outline_dict", new=AsyncMock(return_value={"content": {"plot": "x"}})),
        patch.object(svc, "_get_previous_state_delta", new=AsyncMock(return_value={"events": []})),
        patch.object(svc, "_get_chapter_summary", new=AsyncMock(return_value={"status": "draft", "word_count": 0, "quality_status": None})),
        patch.object(svc, "_get_available_characters", new=AsyncMock(return_value=[{"id": 1, "name": "主角", "role": "protagonist"}])),
    ):
        ws = await svc.get_workspace("novel-1", 5)
    assert ws["blueprint"]["chapter_type"] == "climax"
    assert ws["control"]["version"] == 1
    assert ws["versions"] == [{"version_number": 1}]
    assert ws["outline"]["content"]["plot"] == "x"
    assert ws["available_characters"][0]["name"] == "主角"
    assert ws["quality_status"] is None


@pytest.mark.asyncio
async def test_get_workspace_blueprint_null_when_missing():
    svc = BlueprintWorkbenchService()
    with (
        patch.object(svc, "_get_blueprint_dict", new=AsyncMock(return_value=None)),
        patch.object(svc, "_get_control_dict", new=AsyncMock(return_value={"control_status": "draft", "version": 1, "locked": False})),
        patch.object(svc, "_get_versions_list", new=AsyncMock(return_value=[])),
        patch.object(svc, "_get_chapter_outline_dict", new=AsyncMock(return_value=None)),
        patch.object(svc, "_get_previous_state_delta", new=AsyncMock(return_value=None)),
        patch.object(svc, "_get_chapter_summary", new=AsyncMock(return_value=None)),
        patch.object(svc, "_get_available_characters", new=AsyncMock(return_value=[])),
    ):
        ws = await svc.get_workspace("novel-1", 9)
    assert ws["blueprint"] is None
    assert ws["versions"] == []
    assert ws["outline"] is None


def test_get_options_returns_enum_values():
    svc = BlueprintWorkbenchService()
    opts = svc.get_options()
    assert "main_advance" in opts["chapter_type"]
    assert "fast" in opts["pacing_target"]
    assert "plant" in opts["foreshadow_action"]
