"""Creative Control 生成路径插桩测试。

验证生成路径落库后写入 control 元数据（best-effort，不破坏生成），
锁定章在自动模式被跳过，force 可覆盖锁定。
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.creative_control.control_service import CreativeControlService


def _locked_chapter_row():
    return SimpleNamespace(
        id=1, novel_id="novel-1", artifact_type="chapter", artifact_id="5",
        control_status="locked", locked=True, version=1, stage=7,
        generation_meta=None, stale_reason=None, awaiting_review=False,
    )


def _fake_session(returning_row):
    """假 session：_select_for_update 返回 returning_row；add/flush 可调用。"""
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = returning_row
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    @asynccontextmanager
    async def ctx():
        yield session

    return ctx, session


@pytest.mark.asyncio
async def test_record_generated_creates_new_row_when_absent():
    """生成路径：无 control 行则建 generated。"""
    service = CreativeControlService()
    ctx, session = _fake_session(None)  # _select_for_update 返回 None
    with patch("src.core.creative_control.control_service.get_db_session", new=ctx):
        result = await service.record_generated(
            "novel-1", "world", "novel-1",
            generation_meta={"source": "generation", "model": "deepseek"},
        )
    assert result is not None
    assert result["control_status"] == "generated"
    assert result["artifact_type"] == "world"
    # 新建了 control 行
    assert session.add.call_count >= 1


@pytest.mark.asyncio
async def test_record_generated_never_raises():
    """插桩失败不破坏生成：任何异常被吞，返回 None。"""
    service = CreativeControlService()
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=Exception("db down"))

    @asynccontextmanager
    async def ctx():
        yield session

    with patch("src.core.creative_control.control_service.get_db_session", new=ctx):
        result = await service.record_generated(
            "novel-1", "world", "novel-1", generation_meta={}
        )
    assert result is None


@pytest.mark.asyncio
async def test_record_generated_respects_locked_for_chapter():
    """对 chapter 产物：若已 locked，生成路径应跳过（返回 skipped_locked=True，不覆盖）。"""
    service = CreativeControlService()
    locked_row = _locked_chapter_row()
    ctx, _ = _fake_session(locked_row)
    with patch("src.core.creative_control.control_service.get_db_session", new=ctx):
        result = await service.record_generated(
            "novel-1", "chapter", "5", generation_meta={}, respect_locked=True
        )
    assert result is not None
    assert result.get("skipped_locked") is True
    assert locked_row.control_status == "locked"  # 未被改写


@pytest.mark.asyncio
async def test_record_generated_force_overrides_locked():
    """force=True 时即使锁定也记录生成（用于显式重生成锁定内容）。"""
    service = CreativeControlService()
    locked_row = _locked_chapter_row()
    ctx, _ = _fake_session(locked_row)
    with patch("src.core.creative_control.control_service.get_db_session", new=ctx):
        result = await service.record_generated(
            "novel-1", "chapter", "5", generation_meta={},
            respect_locked=False, force=True,
        )
    assert result is not None
    assert result.get("skipped_locked") is not True
    assert locked_row.control_status == "generated"
    assert locked_row.version == 2


@pytest.mark.asyncio
async def test_record_generated_marks_awaiting_review_when_requested():
    """辅助/手动模式：awaiting_review=True 时落库后置标记。"""
    service = CreativeControlService()
    ctx, _ = _fake_session(None)
    with patch("src.core.creative_control.control_service.get_db_session", new=ctx):
        result = await service.record_generated(
            "novel-1", "world", "novel-1",
            generation_meta={}, awaiting_review=True,
        )
    assert result is not None
    assert result["awaiting_review"] is True
