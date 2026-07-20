"""ImpactAnalyzer 单元测试。

覆盖依赖图驱动的下游影响分析：
- 递归收集 full_downstream 类型
- 按 ArtifactControl 行分流 regenerable / to_mark_stale
- character / volume_outline / blueprint 的细化查询走可 mock 的私有方法
- chapter 改正文不级联

通过 patch get_db_session 注入 mock session。mock session 按 artifact_type.in_(...)
绑定的值过滤 ArtifactControl 行，避免脆弱的调用顺序依赖。
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.creative_control.impact_analyzer import ImpactAnalyzer


def _ctrl(
    *,
    artifact_type: str,
    artifact_id: str,
    control_status: str | None = "generated",
    locked: bool = False,
    novel_id: str = "novel-1",
):
    """构造一个 ArtifactControl-like SimpleNamespace。"""
    return SimpleNamespace(
        novel_id=novel_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        control_status=control_status,
        locked=locked,
    )


def _in_types(clause):
    """从 select 语句的 whereclause 中解析 artifact_type.in_() 的绑定值集合。"""
    types: set[str] = set()
    stack: list = [clause]
    seen: set[int] = set()
    while stack:
        el = stack.pop()
        if id(el) in seen:
            continue
        seen.add(id(el))
        left = getattr(el, "left", None)
        right = getattr(el, "right", None)
        if left is not None and right is not None:
            val = getattr(right, "value", None)
            if isinstance(val, list | tuple | set | frozenset):
                if getattr(left, "key", None) == "artifact_type":
                    types.update(val)
            for child in getattr(right, "get_children", lambda: ())():
                v = getattr(child, "value", None)
                if isinstance(v, str) and getattr(left, "key", None) == "artifact_type":
                    types.add(v)
        for child in getattr(el, "get_children", lambda: ())():
            stack.append(child)
    return types


def _mock_session_with_controls(control_rows: list):
    """mock session：execute 按 artifact_type.in_() 过滤 control_rows 返回。

    返回的 fake_session 是 asynccontextmanager；yield 的 session.execute(stmt) 返回
    result，其 scalars().all() == [r for r in control_rows if r.artifact_type in in_types(stmt)]。
    """

    @asynccontextmanager
    async def fake_session():
        session = AsyncMock()

        async def _execute(stmt, *a, **kw):
            types = _in_types(stmt.whereclause)
            matched = [r for r in control_rows if not types or r.artifact_type in types]
            res = MagicMock()
            res.scalars.return_value.all.return_value = matched
            # _load_volume_chapter_range / _load_* 在测试里已被 patch，不走此路径。
            return res

        session.execute = AsyncMock(side_effect=_execute)
        session.flush = AsyncMock()
        yield session

    return fake_session


# ---------------------------------------------------------------------------
# 场景 1: edit world
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_world_downstream_split_regenerable_and_stale():
    rows = [
        # approved+locked -> to_mark_stale
        _ctrl(artifact_type="character", artifact_id="c1", control_status="approved", locked=True),
        # locked only -> to_mark_stale
        _ctrl(artifact_type="master_outline", artifact_id="mo1", control_status="draft", locked=True),
        # approved only -> to_mark_stale
        _ctrl(artifact_type="volume_outline", artifact_id="1", control_status="approved", locked=False),
        # generated -> regenerable
        _ctrl(artifact_type="blueprint", artifact_id="5", control_status="generated", locked=False),
        # draft -> regenerable
        _ctrl(artifact_type="chapter", artifact_id="5", control_status="draft", locked=False),
    ]
    fake_session = _mock_session_with_controls(rows)
    analyzer = ImpactAnalyzer()
    with patch(
        "src.core.creative_control.impact_analyzer.get_db_session",
        new=fake_session,
    ):
        result = await analyzer.analyze("novel-1", "world", "w1")

    assert result["upstream"] == {"artifact_type": "world", "artifact_id": "w1"}

    full_types = {d["artifact_type"] for d in result["full_downstream"]}
    assert full_types == {"character", "master_outline", "volume_outline", "blueprint", "chapter"}

    regen_types = {d["artifact_type"] for d in result["regenerable"]}
    stale_types = {d["artifact_type"] for d in result["to_mark_stale"]}
    assert regen_types == {"blueprint", "chapter"}
    assert stale_types == {"character", "master_outline", "volume_outline"}

    # direct_downstream 只含直接下游：character, master_outline
    direct_types = {d["artifact_type"] for d in result["direct_downstream"]}
    assert direct_types == {"character", "master_outline"}


# ---------------------------------------------------------------------------
# 场景 2: edit character
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_character_uses_character_chapters_loader():
    rows = [
        _ctrl(artifact_type="master_outline", artifact_id="mo1", control_status="draft", locked=False),
    ]
    fake_session = _mock_session_with_controls(rows)
    analyzer = ImpactAnalyzer()
    with patch(
        "src.core.creative_control.impact_analyzer.get_db_session",
        new=fake_session,
    ), patch.object(
        analyzer,
        "_load_character_chapters",
        new=AsyncMock(return_value=[("chapter", "7"), ("chapter", "8")]),
    ):
        result = await analyzer.analyze("novel-1", "character", "c1")

    full_types = {d["artifact_type"] for d in result["full_downstream"]}
    # character 的图下游只有 master_outline；细化补充出场章 chapter(7/8)
    assert "master_outline" in full_types
    chapter_ids = {d["artifact_id"] for d in result["full_downstream"] if d["artifact_type"] == "chapter"}
    assert chapter_ids == {"7", "8"}

    # master_outline 草稿未锁 -> regenerable；出场章无 control 行(默认 regenerable)
    regen_types = {d["artifact_type"] for d in result["regenerable"]}
    assert "master_outline" in regen_types
    assert "chapter" in regen_types


# ---------------------------------------------------------------------------
# 场景 3: edit volume_outline(volume=2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_volume_outline_scoped_to_volume_chapter_range():
    rows = [
        # 范围内 chapter(10~20) 的 blueprint/chapter；范围外的不应出现
        _ctrl(artifact_type="blueprint", artifact_id="10", control_status="draft", locked=False),
        _ctrl(artifact_type="blueprint", artifact_id="20", control_status="approved", locked=False),
        # 范围外：不应被纳入
        _ctrl(artifact_type="blueprint", artifact_id="5", control_status="draft", locked=False),
        _ctrl(artifact_type="chapter", artifact_id="15", control_status="draft", locked=False),
        _ctrl(artifact_type="chapter", artifact_id="25", control_status="draft", locked=False),
    ]
    fake_session = _mock_session_with_controls(rows)
    analyzer = ImpactAnalyzer()
    with patch(
        "src.core.creative_control.impact_analyzer.get_db_session",
        new=fake_session,
    ), patch.object(
        analyzer,
        "_load_volume_chapter_range",
        new=AsyncMock(return_value=(10, 20)),
    ):
        result = await analyzer.analyze("novel-1", "volume_outline", "2")

    bp_ids = {d["artifact_id"] for d in result["full_downstream"] if d["artifact_type"] == "blueprint"}
    ch_ids = {d["artifact_id"] for d in result["full_downstream"] if d["artifact_type"] == "chapter"}
    assert bp_ids == {"10", "20"}
    assert ch_ids == {"15"}

    # blueprint(20) approved -> to_mark_stale；其余 regenerable
    stale_bp = {d["artifact_id"] for d in result["to_mark_stale"] if d["artifact_type"] == "blueprint"}
    assert stale_bp == {"20"}
    regen_bp = {d["artifact_id"] for d in result["regenerable"] if d["artifact_type"] == "blueprint"}
    assert regen_bp == {"10"}


# ---------------------------------------------------------------------------
# 场景 4: edit blueprint(chapter=5)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_blueprint_subsequent_chapters_marked_stale_only():
    rows = [
        # 该章正文 control 行
        _ctrl(artifact_type="chapter", artifact_id="5", control_status="draft", locked=False),
    ]
    fake_session = _mock_session_with_controls(rows)
    analyzer = ImpactAnalyzer()
    with patch(
        "src.core.creative_control.impact_analyzer.get_db_session",
        new=fake_session,
    ), patch.object(
        analyzer,
        "_load_subsequent_chapters",
        new=AsyncMock(return_value=[6, 7]),
    ):
        result = await analyzer.analyze("novel-1", "blueprint", "5")

    # 下游：该章 chapter(5) + 后续章 6/7（连续性，仅 stale-only，不 regenerable）
    ch_in_full = {d["artifact_id"] for d in result["full_downstream"] if d["artifact_type"] == "chapter"}
    assert ch_in_full == {"5", "6", "7"}

    # 该章 chapter(5) 未锁 draft -> regenerable
    regen_ids = {d["artifact_id"] for d in result["regenerable"] if d["artifact_type"] == "chapter"}
    assert regen_ids == {"5"}
    # 后续章 6/7 标 stale-only：归 to_mark_stale（无论其 control 状态）
    stale_ids = {d["artifact_id"] for d in result["to_mark_stale"] if d["artifact_type"] == "chapter"}
    assert stale_ids == {"6", "7"}


# ---------------------------------------------------------------------------
# 场景 5: edit chapter -> downstream empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_edit_chapter_has_empty_downstream():
    rows = [
        _ctrl(artifact_type="blueprint", artifact_id="9", control_status="draft", locked=False),
    ]
    fake_session = _mock_session_with_controls(rows)
    analyzer = ImpactAnalyzer()
    with patch(
        "src.core.creative_control.impact_analyzer.get_db_session",
        new=fake_session,
    ):
        result = await analyzer.analyze("novel-1", "chapter", "5")

    assert result["direct_downstream"] == []
    assert result["full_downstream"] == []
    assert result["regenerable"] == []
    assert result["to_mark_stale"] == []
    assert result["upstream"] == {"artifact_type": "chapter", "artifact_id": "5"}
