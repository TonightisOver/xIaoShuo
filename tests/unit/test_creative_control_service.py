"""CreativeControlService 单元测试。

覆盖乐观锁、锁定、generating 占用、状态转移、stale 级联、操作日志写入。
通过 patch get_db_session 注入 mock session，不连真实 DB。
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.creative_control.contracts import ControlStatus
from src.core.creative_control.control_service import CreativeControlService
from src.core.exceptions import (
    ArtifactBusyError,
    ArtifactConflictError,
    ArtifactLockedError,
)


def _control_row(
    *,
    version: int = 1,
    control_status: str = "generated",
    locked: bool = False,
    awaiting_review: bool = False,
    stage: int = 2,
    artifact_type: str = "world",
    artifact_id: str = "w1",
    novel_id: str = "novel-1",
):
    return SimpleNamespace(
        id=1,
        novel_id=novel_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        control_status=control_status,
        locked=locked,
        version=version,
        stage=stage,
        generation_meta=None,
        stale_reason=None,
        awaiting_review=awaiting_review,
    )


def _session_with_control_row(row, *, downstream_rows=None):
    """构造一个 mock session：第一次 execute 返回 control row（带 with_for_update 链）。"""
    session = AsyncMock()
    control_result = MagicMock()
    control_result.scalar_one_or_none.return_value = row
    downstream_result = MagicMock()
    downstream_result.scalars.return_value.all.return_value = downstream_rows or []

    # 后续 execute 调用按顺序：control row -> downstream rows -> update/insert
    session.execute = AsyncMock(side_effect=[control_result, downstream_result])
    session.add = MagicMock()  # 同步 mock，避免 AsyncMock 协程警告
    session.flush = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session

    return fake_session, session


# ---------------------------------------------------------------------------
# assert_writable
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_assert_writable_rejects_stale_version():
    row = _control_row(version=3)
    fake_session, _ = _session_with_control_row(row)
    service = CreativeControlService()
    with patch(
        "src.core.creative_control.control_service.get_db_session",
        new=fake_session,
    ):
        with pytest.raises(ArtifactConflictError) as exc:
            await service.assert_writable(
                "novel-1", "world", "w1", expected_version=1
            )
    assert exc.value.current_version == 3
    assert exc.value.expected_version == 1


@pytest.mark.asyncio
async def test_assert_writable_rejects_locked_without_force():
    row = _control_row(locked=True)
    fake_session, _ = _session_with_control_row(row)
    service = CreativeControlService()
    with patch(
        "src.core.creative_control.control_service.get_db_session",
        new=fake_session,
    ):
        with pytest.raises(ArtifactLockedError):
            await service.assert_writable(
                "novel-1", "world", "w1", expected_version=1
            )


@pytest.mark.asyncio
async def test_assert_writable_force_bypasses_locked():
    row = _control_row(locked=True)
    fake_session, _ = _session_with_control_row(row)
    service = CreativeControlService()
    with patch(
        "src.core.creative_control.control_service.get_db_session",
        new=fake_session,
    ):
        # 不抛异常即通过
        await service.assert_writable(
            "novel-1", "world", "w1", expected_version=1, force=True
        )


@pytest.mark.asyncio
async def test_assert_writable_rejects_generating():
    row = _control_row(control_status="generating")
    fake_session, _ = _session_with_control_row(row)
    service = CreativeControlService()
    with patch(
        "src.core.creative_control.control_service.get_db_session",
        new=fake_session,
    ):
        with pytest.raises(ArtifactBusyError):
            await service.assert_writable(
                "novel-1", "world", "w1", expected_version=1
            )


@pytest.mark.asyncio
async def test_assert_writable_passes_on_fresh_version():
    row = _control_row(version=1, control_status="generated")
    fake_session, _ = _session_with_control_row(row)
    service = CreativeControlService()
    with patch(
        "src.core.creative_control.control_service.get_db_session",
        new=fake_session,
    ):
        await service.assert_writable(
            "novel-1", "world", "w1", expected_version=1
        )


# ---------------------------------------------------------------------------
# mark_stale 级联
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_mark_stale_splits_regenerable_and_to_mark_stale():
    # 上游 world 修改：下游有未锁定的角色（可重生成）+ 已锁定的总纲（仅标记）
    downstream = [
        SimpleNamespace(
            novel_id="novel-1", artifact_type="character", artifact_id="c1",
            control_status="generated", locked=False, version=2, stage=3,
            stale_reason=None, awaiting_review=False, generation_meta=None,
        ),
        SimpleNamespace(
            novel_id="novel-1", artifact_type="master_outline", artifact_id="m1",
            control_status="approved", locked=True, version=1, stage=4,
            stale_reason=None, awaiting_review=False, generation_meta=None,
        ),
    ]
    fake_session, _ = _session_with_control_row(
        _control_row(artifact_type="world"), downstream_rows=downstream
    )
    service = CreativeControlService()
    with patch(
        "src.core.creative_control.control_service.get_db_session",
        new=fake_session,
    ):
        result = await service.mark_stale(
            "novel-1", "world", "w1", reason="world rules changed"
        )
    regenerable_types = {a["artifact_type"] for a in result["regenerable"]}
    stale_types = {a["artifact_type"] for a in result["to_mark_stale"]}
    assert "character" in regenerable_types
    assert "master_outline" in stale_types


@pytest.mark.asyncio
async def test_mark_stale_marks_upstream_itself_stale():
    fake_session, _ = _session_with_control_row(_control_row(artifact_type="world"))
    service = CreativeControlService()
    with patch(
        "src.core.creative_control.control_service.get_db_session",
        new=fake_session,
    ):
        result = await service.mark_stale(
            "novel-1", "world", "w1", reason="world rules changed"
        )
    assert result["upstream"]["control_status"] == ControlStatus.STALE.value


# ---------------------------------------------------------------------------
# lock / approve / state transitions
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lock_rejects_non_approved_state():
    row = _control_row(control_status="generated", version=1)
    fake_session, _ = _session_with_control_row(row)
    service = CreativeControlService()
    with patch(
        "src.core.creative_control.control_service.get_db_session",
        new=fake_session,
    ):
        with pytest.raises(ValueError):
            await service.lock(
                "novel-1", "world", "w1", expected_version=1
            )


@pytest.mark.asyncio
async def test_lock_on_approved_succeeds_and_bumps_version():
    row = _control_row(control_status="approved", version=1)
    fake_session, session = _session_with_control_row(row)
    service = CreativeControlService()
    with patch(
        "src.core.creative_control.control_service.get_db_session",
        new=fake_session,
    ):
        new_version = await service.lock(
            "novel-1", "world", "w1", expected_version=1
        )
    assert new_version == 2
    assert row.locked is True
    # 至少写了一条 operation_log
    assert session.add.call_count >= 1


@pytest.mark.asyncio
async def test_approve_from_generated_bumps_version():
    row = _control_row(control_status="generated", version=1)
    fake_session, session = _session_with_control_row(row)
    service = CreativeControlService()
    with patch(
        "src.core.creative_control.control_service.get_db_session",
        new=fake_session,
    ):
        new_version = await service.approve(
            "novel-1", "world", "w1", expected_version=1
        )
    assert new_version == 2
    assert session.add.call_count >= 1


# ---------------------------------------------------------------------------
# 生成生命周期
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_begin_generating_force_atomically_unlocks():
    row = _control_row(control_status="locked", locked=True, version=1)
    fake_session, _ = _session_with_control_row(row)
    service = CreativeControlService()
    with patch(
        "src.core.creative_control.control_service.get_db_session",
        new=fake_session,
    ):
        new_version = await service.begin_generating(
            "novel-1", "world", "w1", expected_version=1, force=True
        )

    assert new_version == 2
    assert row.control_status == "generating"
    assert row.locked is False


@pytest.mark.asyncio
async def test_begin_generating_rejects_busy_inside_locked_transaction():
    row = _control_row(control_status="generating", version=1)
    fake_session, _ = _session_with_control_row(row)
    service = CreativeControlService()
    with patch(
        "src.core.creative_control.control_service.get_db_session",
        new=fake_session,
    ):
        with pytest.raises(ArtifactBusyError):
            await service.begin_generating(
                "novel-1", "world", "w1", expected_version=1
            )


@pytest.mark.asyncio
async def test_complete_generating_sets_generated_and_logs():
    row = _control_row(control_status="generating", version=1)
    fake_session, session = _session_with_control_row(row)
    service = CreativeControlService()
    with patch(
        "src.core.creative_control.control_service.get_db_session",
        new=fake_session,
    ):
        new_version = await service.complete_generating(
            "novel-1", "world", "w1", expected_version=1,
            generation_meta={"source": "generation", "model": "deepseek"},
        )
    assert new_version == 2
    assert session.add.call_count >= 1


@pytest.mark.asyncio
async def test_lazy_create_on_missing_row():
    # 历史产物无 control 行 -> 读路径惰性创建 generated/version=1
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()
    session.flush = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session

    service = CreativeControlService()
    with patch(
        "src.core.creative_control.control_service.get_db_session",
        new=fake_session,
    ):
        control = await service.get_or_create(
            "novel-1", "world", "w1", stage=2
        )
    assert control["control_status"] == "generated"
    assert control["version"] == 1
    assert session.add.call_count == 1
