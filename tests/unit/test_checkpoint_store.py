"""CheckpointStore 单元测试 — 幂等创建、乐观锁推进、lease 守卫。

覆盖：
- ensure_checkpoint 幂等创建
- advance_checkpoint 正常推进 + 返回新版本号
- expected_checkpoint_version 不匹配 → CheckpointConflict
- lease_owner 不匹配 / lease 过期 → LeaseLost
- advance_checkpoint 不校验 queue_state（B2：暂停时可推进 status='paused'）
- STAGE_ORDER 常量完整
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import CheckpointConflict, LeaseLost


def _make_session():
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    return session


def _patch_db(session):
    mock_db = MagicMock()
    mock_db.return_value = session
    return patch(
        "src.api.services.tasks.checkpoint_store.get_db_session", mock_db
    )


def _make_task_row(
    *,
    task_id: str = "task-1",
    lease_owner: str | None = "worker-a",
    lease_expires_at: datetime | None = None,
    queue_state: str = "leased",
):
    if lease_expires_at is None:
        lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)
    row = MagicMock()
    row.task_id = task_id
    row.lease_owner = lease_owner
    row.lease_expires_at = lease_expires_at
    row.queue_state = queue_state
    return row


def _make_checkpoint_row(
    *,
    task_id: str = "task-1",
    checkpoint_version: int = 0,
    current_stage: str = "chapter_planned",
    status: str = "pending",
):
    row = MagicMock()
    row.task_id = task_id
    row.novel_id = "novel-1"
    row.operation_id = "novel-1:long_form"
    row.current_stage = current_stage
    row.volume_number = None
    row.chapter_number = None
    row.last_completed_volume = 0
    row.last_completed_chapter = 0
    row.active_version_number = None
    row.checkpoint_version = checkpoint_version
    row.attempt_number = 0
    row.last_event_sequence = 0
    row.status = status
    row.pause_requested = False
    row.failure_category = None
    row.recoverable = True
    row.failure_detail = None
    row.updated_at = datetime.now(UTC)
    return row


class TestStageOrder:
    def test_stage_order_contains_chapter_and_volume_stages(self):
        from src.api.services.tasks.checkpoint_store import STAGE_ORDER

        for stage in (
            "chapter_planned",
            "generation_started",
            "baseline_persisted",
            "quality_finalized",
            "side_effects_recorded",
            "chapter_completed",
            "volume_start",
            "volume_end",
            "task_end",
        ):
            assert stage in STAGE_ORDER


class TestEnsureCheckpoint:
    @pytest.mark.asyncio
    async def test_creates_initial_checkpoint(self):
        from src.api.services.tasks.checkpoint_store import CheckpointStore

        session = _make_session()
        # first select: no existing checkpoint
        empty_result = MagicMock()
        empty_result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=empty_result)

        store = CheckpointStore()
        with _patch_db(session):
            cp = await store.ensure_checkpoint(
                task_id="task-1",
                novel_id="novel-1",
                operation_id="novel-1:long_form",
            )

        session.add.assert_called_once()
        added = session.add.call_args.args[0]
        assert added.task_id == "task-1"
        assert added.novel_id == "novel-1"
        assert added.operation_id == "novel-1:long_form"
        assert added.current_stage == "chapter_planned"
        assert added.checkpoint_version == 0
        assert added.status == "pending"
        assert cp["task_id"] == "task-1"
        assert cp["checkpoint_version"] == 0
        assert cp["current_stage"] == "chapter_planned"

    @pytest.mark.asyncio
    async def test_ensure_is_idempotent_when_exists(self):
        from src.api.services.tasks.checkpoint_store import CheckpointStore

        session = _make_session()
        existing = _make_checkpoint_row(checkpoint_version=3, current_stage="baseline_persisted")
        hit = MagicMock()
        hit.scalar_one_or_none.return_value = existing
        session.execute = AsyncMock(return_value=hit)

        store = CheckpointStore()
        with _patch_db(session):
            cp = await store.ensure_checkpoint(
                task_id="task-1",
                novel_id="novel-1",
                operation_id="novel-1:long_form",
            )

        session.add.assert_not_called()
        assert cp["checkpoint_version"] == 3
        assert cp["current_stage"] == "baseline_persisted"


class TestAdvanceCheckpoint:
    def _setup_advance(self, *, task_row, update_rowcount: int = 1):
        session = _make_session()

        task_result = MagicMock()
        task_result.scalar_one_or_none.return_value = task_row

        update_result = MagicMock()
        update_result.rowcount = update_rowcount

        # first execute = select Task, second = update TaskCheckpoint
        session.execute = AsyncMock(side_effect=[task_result, update_result])
        return session

    @pytest.mark.asyncio
    async def test_advance_returns_new_version(self):
        from src.api.services.tasks.checkpoint_store import CheckpointStore

        task_row = _make_task_row(lease_owner="worker-a")
        session = self._setup_advance(task_row=task_row, update_rowcount=1)

        store = CheckpointStore()
        with _patch_db(session):
            new_ver = await store.advance_checkpoint(
                task_id="task-1",
                worker_id="worker-a",
                expected_checkpoint_version=0,
                stage="generation_started",
                chapter_number=1,
            )

        assert new_ver == 1
        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_advance_conflict_raises(self):
        from src.api.services.tasks.checkpoint_store import CheckpointStore

        task_row = _make_task_row(lease_owner="worker-a")
        session = self._setup_advance(task_row=task_row, update_rowcount=0)

        store = CheckpointStore()
        with _patch_db(session):
            with pytest.raises(CheckpointConflict) as exc_info:
                await store.advance_checkpoint(
                    task_id="task-1",
                    worker_id="worker-a",
                    expected_checkpoint_version=0,
                    stage="generation_started",
                )
        assert exc_info.value.task_id == "task-1"
        assert exc_info.value.expected_version == 0

    @pytest.mark.asyncio
    async def test_advance_lease_owner_mismatch_raises_lease_lost(self):
        from src.api.services.tasks.checkpoint_store import CheckpointStore

        task_row = _make_task_row(lease_owner="other-worker")
        session = self._setup_advance(task_row=task_row)

        store = CheckpointStore()
        with _patch_db(session):
            with pytest.raises(LeaseLost) as exc_info:
                await store.advance_checkpoint(
                    task_id="task-1",
                    worker_id="worker-a",
                    expected_checkpoint_version=0,
                    stage="generation_started",
                )
        assert exc_info.value.task_id == "task-1"
        # only the Task select should have run; no update
        assert session.execute.await_count == 1

    @pytest.mark.asyncio
    async def test_advance_expired_lease_raises_lease_lost(self):
        from src.api.services.tasks.checkpoint_store import CheckpointStore

        expired = datetime.now(UTC) - timedelta(seconds=1)
        task_row = _make_task_row(
            lease_owner="worker-a", lease_expires_at=expired
        )
        session = self._setup_advance(task_row=task_row)

        store = CheckpointStore()
        with _patch_db(session):
            with pytest.raises(LeaseLost):
                await store.advance_checkpoint(
                    task_id="task-1",
                    worker_id="worker-a",
                    expected_checkpoint_version=0,
                    stage="generation_started",
                )

    @pytest.mark.asyncio
    async def test_advance_ignores_queue_state(self):
        """B2: even when queue_state is idle (pause path), advance still works
        as long as lease_owner + lease_expires_at are valid."""
        from src.api.services.tasks.checkpoint_store import CheckpointStore

        task_row = _make_task_row(
            lease_owner="worker-a", queue_state="idle"
        )
        session = self._setup_advance(task_row=task_row, update_rowcount=1)

        store = CheckpointStore()
        with _patch_db(session):
            new_ver = await store.advance_checkpoint(
                task_id="task-1",
                worker_id="worker-a",
                expected_checkpoint_version=2,
                stage="chapter_completed",
                status="paused",
            )
        assert new_ver == 3

    @pytest.mark.asyncio
    async def test_advance_missing_task_raises_lease_lost(self):
        from src.api.services.tasks.checkpoint_store import CheckpointStore

        session = self._setup_advance(task_row=None)

        store = CheckpointStore()
        with _patch_db(session):
            with pytest.raises(LeaseLost):
                await store.advance_checkpoint(
                    task_id="missing",
                    worker_id="worker-a",
                    expected_checkpoint_version=0,
                    stage="generation_started",
                )


class TestRead:
    @pytest.mark.asyncio
    async def test_read_returns_dict(self):
        from src.api.services.tasks.checkpoint_store import CheckpointStore

        session = _make_session()
        existing = _make_checkpoint_row(
            checkpoint_version=5, current_stage="quality_finalized"
        )
        hit = MagicMock()
        hit.scalar_one_or_none.return_value = existing
        session.execute = AsyncMock(return_value=hit)

        store = CheckpointStore()
        with _patch_db(session):
            cp = await store.read("task-1")

        assert cp is not None
        assert cp["checkpoint_version"] == 5
        assert cp["current_stage"] == "quality_finalized"

    @pytest.mark.asyncio
    async def test_read_missing_returns_none(self):
        from src.api.services.tasks.checkpoint_store import CheckpointStore

        session = _make_session()
        empty = MagicMock()
        empty.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=empty)

        store = CheckpointStore()
        with _patch_db(session):
            cp = await store.read("missing")
        assert cp is None
