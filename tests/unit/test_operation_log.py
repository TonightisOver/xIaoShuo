"""OperationLogService 单元测试。

覆盖 record 写入、10 类 action 合法性校验、list 过滤/排序/截断、空结果。
通过 patch get_db_session 注入 mock session，不连真实 DB。
"""

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.creative_control import OPERATION_ACTIONS
from src.core.creative_control.operation_log import OperationLogService


def _log_row(
    *,
    id_=1,
    novel_id="novel-1",
    artifact_type="world",
    artifact_id="w1",
    action="edit",
    from_version=None,
    to_version=None,
    operator_id=None,
    reason=None,
    task_id=None,
    operation_id=None,
    meta=None,
    created_at=None,
):
    return SimpleNamespace(
        id=id_,
        novel_id=novel_id,
        artifact_type=artifact_type,
        artifact_id=artifact_id,
        action=action,
        from_version=from_version,
        to_version=to_version,
        operator_id=operator_id,
        reason=reason,
        task_id=task_id,
        operation_id=operation_id,
        meta=meta,
        created_at=created_at or datetime(2026, 7, 21, 12, 0, 0, tzinfo=UTC),
    )


def _session_with_rows(rows):
    """构造 mock session：execute 返回包含给定 rows 的 result，并记录传入的 stmt。"""
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    session.execute = AsyncMock(return_value=result)
    session.flush = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session

    return fake_session, session


def _session_for_record():
    """构造 mock session 用于 record（add 同步、flush 异步）。"""
    session = AsyncMock()
    session.add = MagicMock()  # AsyncSession.add 是同步方法
    session.flush = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session

    return fake_session, session


# ---------------------------------------------------------------------------
# OPERATION_ACTIONS 常量
# ---------------------------------------------------------------------------


def test_operation_actions_constant_has_ten_actions():
    assert set(OPERATION_ACTIONS) == {
        "edit", "generate", "regenerate", "lock", "unlock", "approve",
        "rollback", "adopt_candidate", "keep_baseline", "update_params",
    }
    assert len(OPERATION_ACTIONS) == 10


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_writes_row_and_returns_complete_dict():
    fake_session, session = _session_for_record()
    service = OperationLogService()
    with patch("src.core.creative_control.operation_log.get_db_session", new=fake_session):
        result = await service.record(
            novel_id="novel-1",
            artifact_type="world",
            artifact_id="w1",
            action="edit",
            from_version=1,
            to_version=2,
            operator_id=42,
            reason="manual edit",
            task_id="task-1",
            operation_id="op-1",
            meta={"key": "value"},
        )
    # 写入一行
    assert session.add.call_count == 1
    added = session.add.call_args.args[0]
    assert added.novel_id == "novel-1"
    assert added.artifact_type == "world"
    assert added.artifact_id == "w1"
    assert added.action == "edit"
    assert added.from_version == 1
    assert added.to_version == 2
    assert added.operator_id == 42
    assert added.reason == "manual edit"
    assert added.task_id == "task-1"
    assert added.operation_id == "op-1"
    assert added.meta == {"key": "value"}
    # 返回完整 dict
    assert result["action"] == "edit"
    assert result["novel_id"] == "novel-1"
    assert result["artifact_type"] == "world"
    assert result["artifact_id"] == "w1"
    assert result["from_version"] == 1
    assert result["to_version"] == 2
    assert result["operator_id"] == 42
    assert result["reason"] == "manual edit"
    assert result["task_id"] == "task-1"
    assert result["operation_id"] == "op-1"
    assert result["meta"] == {"key": "value"}
    assert "id" in result
    assert "created_at" in result


@pytest.mark.asyncio
async def test_record_rejects_invalid_action_with_value_error():
    fake_session, _ = _session_for_record()
    service = OperationLogService()
    with patch("src.core.creative_control.operation_log.get_db_session", new=fake_session):
        with pytest.raises(ValueError):
            await service.record(
                novel_id="novel-1",
                artifact_type="world",
                artifact_id="w1",
                action="bogus_action",
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("action", list(OPERATION_ACTIONS))
async def test_record_round_trip_all_ten_actions(action):
    """10 类 action 各自 round-trip：写入对应 action，返回 dict 的 action 一致。"""
    fake_session, session = _session_for_record()
    service = OperationLogService()
    with patch("src.core.creative_control.operation_log.get_db_session", new=fake_session):
        result = await service.record(
            novel_id="novel-1",
            artifact_type="world",
            artifact_id="w1",
            action=action,
            operation_id=f"op-{action}",
        )
    added = session.add.call_args.args[0]
    assert added.action == action
    assert result["action"] == action
    assert result["operation_id"] == f"op-{action}"


# ---------------------------------------------------------------------------
# list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_filters_by_artifact_type_and_action_and_desc_order():
    # mock 返回 DB 已按 created_at desc 排序、过滤后的结果行
    rows = [
        _log_row(id_=3, artifact_type="world", action="edit",
                 created_at=datetime(2026, 7, 21, 12, 3, tzinfo=UTC)),
        _log_row(id_=2, artifact_type="world", action="edit",
                 created_at=datetime(2026, 7, 21, 12, 2, tzinfo=UTC)),
    ]
    fake_session, session = _session_with_rows(rows)
    service = OperationLogService()
    with patch("src.core.creative_control.operation_log.get_db_session", new=fake_session):
        result = await service.list(
            "novel-1",
            artifact_type="world",
            action="edit",
        )
    # 顺序与 mock（DB desc 输出）一致
    assert [r["id"] for r in result] == [3, 2]
    # created_at 序列化为 ISO 字符串
    assert isinstance(result[0]["created_at"], str)
    assert result[0]["created_at"].startswith("2026-07-21T12:03")
    # 断言过滤条件 + desc 排序传入 stmt
    stmt = session.execute.call_args.args[0]
    compiled = str(stmt.compile())
    assert "novel_id" in compiled
    assert "artifact_type" in compiled
    assert "action" in compiled
    assert "ORDER BY" in compiled
    assert "DESC" in compiled


@pytest.mark.asyncio
async def test_list_filters_by_since():
    since = datetime(2026, 7, 21, 12, 2, 30, tzinfo=UTC)
    rows = [
        _log_row(id_=3, created_at=datetime(2026, 7, 21, 12, 3, tzinfo=UTC)),
    ]
    fake_session, session = _session_with_rows(rows)
    service = OperationLogService()
    with patch("src.core.creative_control.operation_log.get_db_session", new=fake_session):
        result = await service.list("novel-1", since=since)
    assert [r["id"] for r in result] == [3]
    # 断言 since 条件传入 stmt
    stmt = session.execute.call_args.args[0]
    assert "created_at" in str(stmt.compile())


@pytest.mark.asyncio
async def test_list_truncates_by_limit():
    rows = [
        _log_row(id_=5, created_at=datetime(2026, 7, 21, 12, 5, tzinfo=UTC)),
        _log_row(id_=4, created_at=datetime(2026, 7, 21, 12, 4, tzinfo=UTC)),
    ]
    fake_session, session = _session_with_rows(rows)
    service = OperationLogService()
    with patch("src.core.creative_control.operation_log.get_db_session", new=fake_session):
        result = await service.list("novel-1", limit=2)
    # limit 由 SQL 执行；断言 stmt 编译含 LIMIT
    stmt = session.execute.call_args.args[0]
    assert "LIMIT" in str(stmt.compile())
    assert len(result) == 2


@pytest.mark.asyncio
async def test_list_empty_returns_empty_list():
    fake_session, _ = _session_with_rows([])
    service = OperationLogService()
    with patch("src.core.creative_control.operation_log.get_db_session", new=fake_session):
        result = await service.list("novel-1")
    assert result == []
