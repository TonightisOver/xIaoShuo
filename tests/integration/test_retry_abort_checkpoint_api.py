"""Task 10：/checkpoint /retry /abort 接口 + 错误分类。

设计依据：docs/superpowers/specs/2026-07-20-long-form-stability-design.md §九、§API。
覆盖：
- mark_failed：写入 failure_category/failure_detail/recoverable/status='failed'。
- public_view：返回公开字段，不含 failure_detail。
- retry_task：recoverable/needs_human 重入队（attempt 归零）；unrecoverable 409。
- abort_task：置 failed + 保留 checkpoint。
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from src.core.database import Base, get_db_session, get_engine


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
                VALUES (1, 'retry_test_user', 'mocked', true)
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
                VALUES (:novel_id, 'Retry Test', '重试中止接口测试的足够长创意',
                    '玄幻', 1000000, 'generating', '现代白话', 3000, true, 2, 5, 1,
                    NOW(), NOW())
                """
            ),
            {"novel_id": novel_id},
        )


async def _insert_task(
    task_id: str,
    novel_id: str,
    *,
    status: str = "failed",
    queue_state: str = "idle",
    lease_owner: str | None = None,
) -> None:
    lease_expires = (
        datetime.now(UTC) + timedelta(minutes=5) if lease_owner else None
    )
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO tasks (task_id, operation_id, novel_id, status, idea,
                    novel_type, target_words, created_at, queue_state, attempt_count,
                    max_attempts, lease_owner, lease_expires_at, owner_id)
                VALUES (:task_id, :operation_id, :novel_id, :status, '重试测试',
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
                "lease_expires_at": lease_expires,
            },
        )


async def _insert_checkpoint(
    task_id: str,
    novel_id: str,
    *,
    status: str = "failed",
    failure_category: str | None = "recoverable",
    failure_detail: dict | None = None,
    attempt_number: int = 2,
    last_completed_chapter: int = 5,
) -> None:
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO task_checkpoints (task_id, novel_id, operation_id,
                    current_stage, checkpoint_version, status, last_completed_volume,
                    last_completed_chapter, attempt_number, last_event_sequence,
                    pause_requested, recoverable, failure_category, failure_detail,
                    updated_at)
                VALUES (:task_id, :novel_id, :operation_id, 'chapter_completed',
                    10, :status, 0, :last_completed_chapter, :attempt_number, 5,
                    false, true, :failure_category, CAST(:failure_detail AS JSONB),
                    NOW())
                """
            ),
            {
                "task_id": task_id,
                "novel_id": novel_id,
                "operation_id": f"{novel_id}:long_form",
                "status": status,
                "failure_category": failure_category,
                "failure_detail": (
                    __import__("json").dumps(failure_detail) if failure_detail else None
                ),
                "attempt_number": attempt_number,
                "last_completed_chapter": last_completed_chapter,
            },
        )


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


async def _read_checkpoint(task_id: str) -> dict:
    async with get_db_session() as session:
        res = await session.execute(
            text(
                "SELECT status, failure_category, attempt_number, "
                "last_completed_chapter FROM task_checkpoints WHERE task_id = :tid"
            ),
            {"tid": task_id},
        )
        row = res.one()
        return {
            "status": row[0],
            "failure_category": row[1],
            "attempt_number": row[2],
            "last_completed_chapter": row[3],
        }


@pytest.fixture
async def novel_task(_db_setup):
    novel_id = f"novel-rt-{uuid.uuid4().hex[:8]}"
    task_id = f"task-rt-{uuid.uuid4().hex[:8]}"
    await _insert_novel(novel_id)
    return novel_id, task_id


# ---------------------------------------------------------------------------
# mark_failed + public_view
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_mark_failed_writes_category(novel_task):
    from src.api.services.tasks.checkpoint_store import CheckpointStore

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id)
    await _insert_checkpoint(
        task_id, novel_id, status="running", failure_category=None
    )

    ok = await CheckpointStore().mark_failed(
        task_id, None,
        category="needs_human",
        detail={"reason": "consistency_blocked", "chapter": 7},
        recoverable=True,
    )
    assert ok is True

    cp = await _read_checkpoint(task_id)
    assert cp["status"] == "failed"
    assert cp["failure_category"] == "needs_human"


@pytest.mark.asyncio
async def test_public_view_excludes_failure_detail(novel_task):
    """public_view 不含 failure_detail（敏感字段）。"""
    from src.api.services.tasks.checkpoint_store import CheckpointStore

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id)
    await _insert_checkpoint(
        task_id, novel_id,
        failure_detail={"secret": "internal-diagnostic"},
    )

    view = await CheckpointStore().public_view(task_id)
    assert view is not None
    assert "failure_detail" not in view
    assert view["failure_category"] == "recoverable"
    assert view["last_completed_chapter"] == 5


@pytest.mark.asyncio
async def test_public_view_returns_none_without_checkpoint(novel_task):
    from src.api.services.tasks.checkpoint_store import CheckpointStore

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id)
    view = await CheckpointStore().public_view(task_id)
    assert view is None


# ---------------------------------------------------------------------------
# retry_task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retry_recoverable_requeues_and_resets_attempt(novel_task):
    """recoverable → 重入队，attempt_number 归零，进度保留。"""
    from src.api.services.tasks.task_manager import TaskManager

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id, status="failed", queue_state="idle")
    await _insert_checkpoint(
        task_id, novel_id,
        status="failed", failure_category="recoverable", attempt_number=2,
    )

    result = await TaskManager().retry_task(task_id)
    assert result.requeued is True

    t = await _read_task(task_id)
    assert t["queue_state"] == "queued"
    assert t["status"] == "pending"
    cp = await _read_checkpoint(task_id)
    assert cp["status"] == "running"
    assert cp["attempt_number"] == 0
    assert cp["last_completed_chapter"] == 5  # 进度保留


@pytest.mark.asyncio
async def test_retry_unrecoverable_returns_409(novel_task):
    """unrecoverable → 不重试，返回 reason='unrecoverable'。"""
    from src.api.services.tasks.task_manager import TaskManager

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id, status="failed", queue_state="idle")
    await _insert_checkpoint(
        task_id, novel_id,
        status="failed", failure_category="unrecoverable",
    )

    result = await TaskManager().retry_task(task_id)
    assert result.requeued is False
    assert result.reason == "unrecoverable"

    # 状态未变
    t = await _read_task(task_id)
    assert t["queue_state"] == "idle"


@pytest.mark.asyncio
async def test_retry_no_checkpoint_returns_404(novel_task):
    """无 checkpoint（短篇）→ reason='no_checkpoint'。"""
    from src.api.services.tasks.task_manager import TaskManager

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id, status="failed", queue_state="idle")

    result = await TaskManager().retry_task(task_id)
    assert result.requeued is False
    assert result.reason == "no_checkpoint"


@pytest.mark.asyncio
async def test_retry_rejects_task_that_is_still_running(novel_task):
    """运行中的 worker 仍持有任务时，人工 retry 不得清租约或重复入队。"""
    from src.api.services.tasks.task_manager import TaskManager

    novel_id, task_id = novel_task
    await _insert_task(
        task_id,
        novel_id,
        status="running",
        queue_state="leased",
        lease_owner="worker-active",
    )
    await _insert_checkpoint(
        task_id,
        novel_id,
        status="running",
        failure_category=None,
    )

    result = await TaskManager().retry_task(task_id)
    assert result.requeued is False
    assert result.reason == "not_retryable"

    task = await _read_task(task_id)
    assert task["status"] == "running"
    assert task["queue_state"] == "leased"
    assert task["lease_owner"] == "worker-active"


# ---------------------------------------------------------------------------
# abort_task
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_abort_marks_failed_preserves_checkpoint(novel_task):
    """abort：Task.status='failed'，checkpoint 保留诊断字段。"""
    from src.api.services.tasks.task_manager import TaskManager

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id, status="running", queue_state="leased")
    await _insert_checkpoint(
        task_id, novel_id,
        status="running", failure_category=None, last_completed_chapter=8,
    )

    result = await TaskManager().abort_task(task_id)
    assert result.requeued is True
    assert result.reason == "aborted"

    t = await _read_task(task_id)
    assert t["status"] == "failed"
    assert t["queue_state"] == "idle"
    cp = await _read_checkpoint(task_id)
    assert cp["status"] == "failed"
    assert cp["last_completed_chapter"] == 8  # 诊断保留
