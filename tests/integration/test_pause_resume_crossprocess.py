"""Task 7：暂停/resume 跨进程化 — pause_requested 与 status 分离、requeue、recover。

设计依据：docs/superpowers/specs/2026-07-20-long-form-stability-design.md §七。

覆盖：
- set_paused 只设 checkpoint.pause_requested=True，不改 checkpoint.status（B14）。
- is_pause_requested / is_paused_confirmed 语义分离。
- mark_paused：owner 校验 + queue_state='idle' + 清 lease。
- requeue_paused_task：paused+pause_requested → 重入队；第二次 no-op（幂等）；
  无 checkpoint → no_checkpoint。
- recover_interrupted_tasks：paused+pause_requested=False → 重入队；
  pause_requested=True → 保持 paused。

跨事务 / 行锁 / checkpoint-task 联动须真实 DB 验证，故走真实 PG 集成路径。
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from src.core.database import Base, get_db_session, get_engine

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
async def _db_setup():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO users (id, username, hashed_password, is_admin)
                VALUES (1, 'pause_test_user', 'mocked', true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
        )
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _insert_novel(novel_id: str) -> None:
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO novels (novel_id, title, idea, novel_type, target_words,
                    status, writing_style, words_per_chapter, is_long_form, total_volumes,
                    chapters_per_volume, owner_id, created_at, updated_at)
                VALUES (:novel_id, 'Pause Test', '暂停恢复跨进程测试的足够长创意描述',
                    '玄幻', 1000000, 'generating', '现代白话', 3000, true, 3, 10, 1,
                    NOW(), NOW())
                """
            ),
            {"novel_id": novel_id},
        )


async def _insert_task(
    task_id: str,
    novel_id: str,
    *,
    status: str = "running",
    queue_state: str = "leased",
    lease_owner: str | None = "worker-a",
    lease_offset_minutes: int = 5,
) -> None:
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO tasks (task_id, operation_id, novel_id, status, idea,
                    novel_type, target_words, created_at, queue_state, attempt_count,
                    max_attempts, lease_owner, lease_expires_at, owner_id)
                VALUES (:task_id, :operation_id, :novel_id, :status, '暂停测试任务',
                    '玄幻', 1000000, NOW(), :queue_state, 1, 3,
                    :lease_owner, :lease_expires_at, 1)
                """
            ),
            {
                "task_id": task_id,
                "operation_id": f"{novel_id}:long_form",
                "novel_id": novel_id,
                "status": status,
                "queue_state": queue_state,
                "lease_owner": lease_owner,
                "lease_expires_at": (
                    datetime.now(UTC) + timedelta(minutes=lease_offset_minutes)
                    if lease_owner
                    else None
                ),
            },
        )


async def _insert_checkpoint(
    task_id: str,
    novel_id: str,
    *,
    status: str = "running",
    pause_requested: bool = False,
    checkpoint_version: int = 0,
) -> None:
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO task_checkpoints (task_id, novel_id, operation_id,
                    current_stage, checkpoint_version, status, last_completed_volume,
                    last_completed_chapter, attempt_number, last_event_sequence,
                    pause_requested, recoverable, updated_at)
                VALUES (:task_id, :novel_id, :operation_id, 'chapter_completed',
                    :checkpoint_version, :status, 0, 3, 0, 0,
                    :pause_requested, true, NOW())
                """
            ),
            {
                "task_id": task_id,
                "novel_id": novel_id,
                "operation_id": f"{novel_id}:long_form",
                "checkpoint_version": checkpoint_version,
                "status": status,
                "pause_requested": pause_requested,
            },
        )


async def _read_checkpoint(task_id: str) -> dict | None:
    async with get_db_session() as session:
        res = await session.execute(
            text(
                "SELECT status, pause_requested FROM task_checkpoints "
                "WHERE task_id = :tid"
            ),
            {"tid": task_id},
        )
        row = res.one_or_none()
        if row is None:
            return None
        return {"status": row[0], "pause_requested": row[1]}


async def _read_task(task_id: str) -> dict:
    async with get_db_session() as session:
        res = await session.execute(
            text(
                "SELECT status, queue_state, lease_owner FROM tasks "
                "WHERE task_id = :tid"
            ),
            {"tid": task_id},
        )
        row = res.one()
        return {"status": row[0], "queue_state": row[1], "lease_owner": row[2]}


@pytest.fixture
async def novel_task(_db_setup):
    novel_id = f"novel-pz-{uuid.uuid4().hex[:8]}"
    task_id = f"task-pz-{uuid.uuid4().hex[:8]}"
    await _insert_novel(novel_id)
    return novel_id, task_id


# ---------------------------------------------------------------------------
# pause_state_store：pause_requested 与 status 分离（B14）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_set_paused_only_sets_pause_requested(novel_task, monkeypatch):
    """有 checkpoint 时 set_paused 只设 pause_requested，不改 checkpoint.status。"""
    monkeypatch.delenv("REDIS_URL", raising=False)
    from src.api.services.generation.pause_state_store import PauseStateStore

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id)
    await _insert_checkpoint(task_id, novel_id, status="running", pause_requested=False)

    store = PauseStateStore()
    await store.set_paused(task_id)

    cp = await _read_checkpoint(task_id)
    assert cp["pause_requested"] is True
    assert cp["status"] == "running"  # 未被改为 paused（worker 才有权确认）


@pytest.mark.asyncio
async def test_is_pause_requested_vs_confirmed(novel_task, monkeypatch):
    """is_pause_requested 读 pause_requested；is_paused_confirmed 读 status=='paused'。"""
    monkeypatch.delenv("REDIS_URL", raising=False)
    from src.api.services.generation.pause_state_store import PauseStateStore

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id)
    await _insert_checkpoint(task_id, novel_id, status="running", pause_requested=True)

    store = PauseStateStore()
    assert await store.is_pause_requested(task_id) is True
    assert await store.is_paused_confirmed(task_id) is False  # status 仍 running

    # worker 确认暂停后
    async with get_db_session() as session:
        await session.execute(
            text(
                "UPDATE task_checkpoints SET status='paused' WHERE task_id=:tid"
            ),
            {"tid": task_id},
        )
    assert await store.is_paused_confirmed(task_id) is True


# ---------------------------------------------------------------------------
# mark_paused
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_paused_clears_lease_and_idles(novel_task):
    """mark_paused：owner 匹配 → queue_state='idle' + 清 lease。"""
    from src.api.services.tasks.task_manager import TaskManager

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id, lease_owner="worker-a")
    await _insert_checkpoint(task_id, novel_id)

    ok = await TaskManager().mark_paused(task_id, "worker-a")
    assert ok is True

    t = await _read_task(task_id)
    assert t["queue_state"] == "idle"
    assert t["lease_owner"] is None


@pytest.mark.asyncio
async def test_mark_paused_owner_mismatch_returns_false(novel_task):
    """mark_paused：owner 不匹配 → 返回 False，不动 task。"""
    from src.api.services.tasks.task_manager import TaskManager

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id, lease_owner="worker-a")
    await _insert_checkpoint(task_id, novel_id)

    ok = await TaskManager().mark_paused(task_id, "worker-other")
    assert ok is False

    t = await _read_task(task_id)
    assert t["queue_state"] == "leased"  # 未被改
    assert t["lease_owner"] == "worker-a"


# ---------------------------------------------------------------------------
# requeue_paused_task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_requeue_paused_task_requeues(novel_task):
    """paused + pause_requested=True → 重入队；checkpoint 转 running。"""
    from src.api.services.tasks.task_manager import TaskManager

    novel_id, task_id = novel_task
    # 已暂停态：task idle + 无 lease，checkpoint paused + pause_requested
    await _insert_task(
        task_id, novel_id, status="running", queue_state="idle", lease_owner=None
    )
    await _insert_checkpoint(
        task_id, novel_id, status="paused", pause_requested=True
    )

    result = await TaskManager().requeue_paused_task(task_id)
    assert result.requeued is True

    cp = await _read_checkpoint(task_id)
    assert cp["status"] == "running"
    assert cp["pause_requested"] is False
    t = await _read_task(task_id)
    assert t["queue_state"] == "queued"
    assert t["status"] == "pending"


@pytest.mark.asyncio
async def test_requeue_paused_task_idempotent_second_call(novel_task):
    """第二次调用（已 running）→ no-op：requeued=False, reason='not_paused'。"""
    from src.api.services.tasks.task_manager import TaskManager

    novel_id, task_id = novel_task
    await _insert_task(
        task_id, novel_id, status="running", queue_state="idle", lease_owner=None
    )
    await _insert_checkpoint(
        task_id, novel_id, status="paused", pause_requested=True
    )

    tm = TaskManager()
    first = await tm.requeue_paused_task(task_id)
    assert first.requeued is True
    second = await tm.requeue_paused_task(task_id)
    assert second.requeued is False
    assert second.reason == "not_paused"


@pytest.mark.asyncio
async def test_requeue_no_checkpoint_returns_reason(novel_task):
    """无 checkpoint（短篇）→ requeued=False, reason='no_checkpoint'。"""
    from src.api.services.tasks.task_manager import TaskManager

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id, status="paused", queue_state="idle")
    # 不插 checkpoint

    result = await TaskManager().requeue_paused_task(task_id)
    assert result.requeued is False
    assert result.reason == "no_checkpoint"


# ---------------------------------------------------------------------------
# recover_interrupted_tasks 处理 paused
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_recover_requeues_paused_without_request(novel_task):
    """recover：paused + pause_requested=False → 重入队（被 resume 但 worker 没起）。"""
    from src.api.services.tasks.task_manager import TaskManager

    novel_id, task_id = novel_task
    await _insert_task(
        task_id, novel_id, status="running", queue_state="idle", lease_owner=None
    )
    await _insert_checkpoint(
        task_id, novel_id, status="paused", pause_requested=False
    )

    await TaskManager().recover_interrupted_tasks()

    t = await _read_task(task_id)
    assert t["queue_state"] == "queued"
    cp = await _read_checkpoint(task_id)
    assert cp["status"] == "running"


@pytest.mark.asyncio
async def test_recover_preserves_paused_with_request(novel_task):
    """recover：paused + pause_requested=True → 保持 paused（用户仍要暂停）。"""
    from src.api.services.tasks.task_manager import TaskManager

    novel_id, task_id = novel_task
    await _insert_task(
        task_id, novel_id, status="running", queue_state="idle", lease_owner=None
    )
    await _insert_checkpoint(
        task_id, novel_id, status="paused", pause_requested=True
    )

    await TaskManager().recover_interrupted_tasks()

    t = await _read_task(task_id)
    assert t["queue_state"] == "idle"  # 未重入队
    cp = await _read_checkpoint(task_id)
    assert cp["status"] == "paused"
