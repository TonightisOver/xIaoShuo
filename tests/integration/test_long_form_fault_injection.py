"""Task 12：故障注入测试套件。

设计依据：docs/superpowers/specs/2026-07-20-long-form-stability-design.md §故障注入场景覆盖。
DB 状态断言为主，不真实 kill 进程。覆盖端到端关键场景：
1. 检查点恢复（lease 丢失后重 claim 从断点续）
2. 幂等重试不产生重复版本
3. lease 丢失停写
4. resume 幂等
5. 已完成章跳过
6. 重复投递去重（operation_id）
7. 单活跃版本不变量
8. 错误分类（consistency_blocked → needs_human via mark_failed）
9. abort 后 retry 从断点续
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from src.core.database import Base, get_db_session, get_engine
from src.core.exceptions import LeaseLost


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
                VALUES (1, 'fault_test_user', 'mocked', true)
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
                VALUES (:novel_id, 'Fault Test', '故障注入端到端测试的足够长创意',
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
    status: str = "running",
    queue_state: str = "leased",
    lease_owner: str | None = "worker-a",
    operation_id: str | None = None,
    attempt_count: int = 1,
    lease_offset_minutes: int = 5,
) -> None:
    lease_expires = (
        datetime.now(UTC) + timedelta(minutes=lease_offset_minutes)
        if lease_owner
        else None
    )
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO tasks (task_id, operation_id, novel_id, status, idea,
                    novel_type, target_words, created_at, queue_state, attempt_count,
                    max_attempts, lease_owner, lease_expires_at, owner_id)
                VALUES (:task_id, :operation_id, :novel_id, :status, '故障测试',
                    '玄幻', 1000000, NOW(), :queue_state, :attempt_count, 3,
                    :lease_owner, :lease_expires_at, 1)
                """
            ),
            {
                "task_id": task_id,
                "operation_id": operation_id or f"{novel_id}:long_form",
                "novel_id": novel_id,
                "status": status,
                "queue_state": queue_state,
                "attempt_count": attempt_count,
                "lease_owner": lease_owner,
                "lease_expires_at": lease_expires,
            },
        )


async def _insert_checkpoint(
    task_id: str,
    novel_id: str,
    *,
    status: str = "running",
    last_completed_chapter: int = 0,
    current_stage: str = "chapter_planned",
    checkpoint_version: int = 0,
    pause_requested: bool = False,
    failure_category: str | None = None,
) -> None:
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO task_checkpoints (task_id, novel_id, operation_id,
                    current_stage, checkpoint_version, status, last_completed_volume,
                    last_completed_chapter, attempt_number, last_event_sequence,
                    pause_requested, recoverable, failure_category, updated_at)
                VALUES (:task_id, :novel_id, :operation_id, :current_stage,
                    :checkpoint_version, :status, 0, :last_completed_chapter, 0, 0,
                    :pause_requested, true, :failure_category, NOW())
                """
            ),
            {
                "task_id": task_id,
                "novel_id": novel_id,
                "operation_id": f"{novel_id}:long_form",
                "current_stage": current_stage,
                "checkpoint_version": checkpoint_version,
                "status": status,
                "last_completed_chapter": last_completed_chapter,
                "pause_requested": pause_requested,
                "failure_category": failure_category,
            },
        )


async def _insert_chapter(novel_id: str, chapter_number: int) -> None:
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO chapters (novel_id, chapter_number, volume_number, title,
                    content, word_count, chapter_type, status, updated_at)
                VALUES (:novel_id, :chapter_number, 1, :title, :content, :word_count,
                    'normal', 'generated', NOW())
                ON CONFLICT (novel_id, chapter_number) DO NOTHING
                """
            ),
            {
                "novel_id": novel_id,
                "chapter_number": chapter_number,
                "title": f"Chapter {chapter_number}",
                "content": f"第{chapter_number}章正文",
                "word_count": 10,
            },
        )


async def _read_checkpoint(task_id: str) -> dict:
    async with get_db_session() as session:
        res = await session.execute(
            text(
                "SELECT status, current_stage, last_completed_chapter, "
                "checkpoint_version FROM task_checkpoints WHERE task_id = :tid"
            ),
            {"tid": task_id},
        )
        row = res.one()
        return {
            "status": row[0],
            "current_stage": row[1],
            "last_completed_chapter": row[2],
            "checkpoint_version": row[3],
        }


async def _count_versions(novel_id: str, chapter_number: int) -> int:
    async with get_db_session() as session:
        res = await session.execute(
            text(
                "SELECT COUNT(*) FROM chapter_versions "
                "WHERE novel_id = :nid AND chapter_number = :cn"
            ),
            {"nid": novel_id, "cn": chapter_number},
        )
        return res.scalar_one()


@pytest.fixture
async def novel_task(_db_setup):
    novel_id = f"novel-ft-{uuid.uuid4().hex[:8]}"
    task_id = f"task-ft-{uuid.uuid4().hex[:8]}"
    await _insert_novel(novel_id)
    return novel_id, task_id


# ---------------------------------------------------------------------------
# 场景 1+3：lease 丢失停写 + checkpoint 未推进
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_lease_lost_aborts_checkpoint_advance(novel_task):
    """lease 过期时 advance_checkpoint 抛 LeaseLost，checkpoint 未推进。"""
    from src.api.services.tasks.checkpoint_store import CheckpointStore

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id, lease_offset_minutes=-5)  # 已过期
    await _insert_checkpoint(task_id, novel_id, checkpoint_version=0)

    with pytest.raises(LeaseLost):
        await CheckpointStore().advance_checkpoint(
            task_id, "worker-a",
            expected_checkpoint_version=0,
            stage="baseline_persisted",
        )

    cp = await _read_checkpoint(task_id)
    assert cp["checkpoint_version"] == 0  # 未推进
    assert cp["current_stage"] == "chapter_planned"


# ---------------------------------------------------------------------------
# 场景 2：幂等重试不产生重复版本
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_idempotent_retry_no_duplicate_version(novel_task):
    """同一幂等键第二次调用返回同版本号，不新建。"""
    from src.api.services.content.chapter_service import (
        ChapterService,
        chapter_idem_key,
    )

    novel_id, task_id = novel_task
    await _insert_chapter(novel_id, 1)
    op = f"{novel_id}:long_form"
    key = chapter_idem_key(op, "baseline", 1)

    svc = ChapterService()
    v1 = await svc.create_chapter_version(
        novel_id, 1, "正文A", source="generation", is_active=True,
        idempotency_key=key,
    )
    v2 = await svc.create_chapter_version(
        novel_id, 1, "正文B", source="generation", is_active=True,
        idempotency_key=key,
    )
    assert v1 == v2
    assert await _count_versions(novel_id, 1) == 1


# ---------------------------------------------------------------------------
# 场景 4：resume 幂等
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_resume_idempotent_second_call_noop(novel_task):
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
    second = await tm.requeue_paused_task(task_id)
    assert first.requeued is True
    assert second.requeued is False
    assert second.reason == "not_paused"


# ---------------------------------------------------------------------------
# 场景 5：已完成章跳过
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_completed_chapter_skipped_on_resume(novel_task):
    """checkpoint last_completed_chapter=5 → 恢复从第 6 章起，前 5 章不重生成。"""
    from src.api.services.generation import long_form_generation_helpers as h

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id)
    await _insert_checkpoint(
        task_id, novel_id,
        checkpoint_version=7, last_completed_chapter=5,
        current_stage="chapter_completed",
    )

    generated: list[int] = []

    async def _fake_stream(ctx):
        generated.append(ctx.chapter_outline["chapter"])
        return {"chapter": ctx.chapter_outline["chapter"], "title": "t",
                "content": "c", "word_count": 1, "volume_number": 1}

    async def _fake_stages(**kwargs):
        return kwargs["expected_checkpoint_version"] + 4

    with (
        patch(
            "src.core.llm.chapter_generator.generate_chapter_stream",
            new=AsyncMock(side_effect=_fake_stream),
        ),
        patch.object(h, "_run_chapter_stages", new=AsyncMock(side_effect=_fake_stages)),
        patch.object(h, "_get_story_bible_context", new=AsyncMock(return_value=None)),
        patch.object(h, "_get_blueprint", new=AsyncMock(return_value=None)),
        patch.object(h, "_emit_progress", new=AsyncMock()),
    ):
        await h.generate_volume_chapters(
            task_id=task_id, novel_id=novel_id, volume_number=1,
            chapter_start=1, chapter_end=6,
            vol_outline={"chapters": [{"chapter": n, "title": f"第{n}章"} for n in range(1, 7)]},
            words_per_chapter=3000, request=None, worker_id="worker-a",
        )

    assert generated == [6]


# ---------------------------------------------------------------------------
# 场景 6：重复投递去重（operation_id）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_duplicate_submit_dedup(novel_task):
    """同 operation_id 重复投递返回同 task_id（B4）。"""
    from src.api.services.tasks.task_manager import TaskManager

    novel_id, task_id = novel_task
    op = f"{novel_id}:long_form"
    await _insert_task(task_id, novel_id, operation_id=op, status="running")

    tm = TaskManager()
    second_id = await tm.create_task(
        idea="测试", novel_type="玄幻", target_words=1000000,
        operation_id=op, novel_id=novel_id, owner_id=1,
    )
    assert second_id == task_id


# ---------------------------------------------------------------------------
# 场景 7：单活跃版本不变量
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_single_active_version_invariant(novel_task):
    """服务切换活跃版本时始终维持数据库单活跃不变量。"""
    from src.api.services.content.chapter_service import ChapterService

    novel_id, task_id = novel_task
    await _insert_chapter(novel_id, 1)

    svc = ChapterService()
    await svc.create_chapter_version(
        novel_id, 1, "正文A", source="generation", is_active=True,
    )
    second = await svc.create_chapter_version(
        novel_id, 1, "正文B", source="manual", is_active=True,
    )
    async with get_db_session() as session:
        result = await session.execute(
            text(
                "SELECT version_number FROM chapter_versions "
                "WHERE novel_id = :novel_id AND chapter_number = 1 "
                "AND is_active = true"
            ),
            {"novel_id": novel_id},
        )
        active_versions = list(result.scalars().all())

    assert active_versions == [second]
    assert await _count_versions(novel_id, 1) == 2


# ---------------------------------------------------------------------------
# 场景 8：错误分类（mark_failed 写 needs_human）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_error_classification_needs_human(novel_task):
    """consistency_blocked → mark_failed(category='needs_human', recoverable=True)。"""
    from src.api.services.tasks.checkpoint_store import CheckpointStore

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id)
    await _insert_checkpoint(task_id, novel_id, status="running")

    ok = await CheckpointStore().mark_failed(
        task_id, None,
        category="needs_human",
        detail={"reason": "consistency_blocked", "chapter": 3},
        recoverable=True,
    )
    assert ok is True

    cp = await _read_checkpoint(task_id)
    assert cp["status"] == "failed"

    async with get_db_session() as session:
        res = await session.execute(
            text(
                "SELECT failure_category, recoverable FROM task_checkpoints "
                "WHERE task_id = :tid"
            ),
            {"tid": task_id},
        )
        row = res.one()
        assert row[0] == "needs_human"
        assert row[1] is True


# ---------------------------------------------------------------------------
# 场景 9：abort 后 retry 从断点续
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_abort_then_retry_resumes_from_checkpoint(novel_task):
    """abort 置 failed 保留 checkpoint；retry 从断点重入队（不新建 task）。"""
    from src.api.services.tasks.task_manager import TaskManager

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id, status="running", queue_state="leased")
    await _insert_checkpoint(
        task_id, novel_id,
        status="running", last_completed_chapter=5,
        current_stage="chapter_completed",
    )

    tm = TaskManager()
    abort_result = await tm.abort_task(task_id)
    assert abort_result.requeued is True

    # abort 后 checkpoint 保留诊断
    cp = await _read_checkpoint(task_id)
    assert cp["last_completed_chapter"] == 5

    # mark_failed 为 recoverable 后 retry
    from src.api.services.tasks.checkpoint_store import CheckpointStore
    await CheckpointStore().mark_failed(
        task_id, None, category="recoverable", recoverable=True
    )
    retry_result = await tm.retry_task(task_id)
    assert retry_result.requeued is True

    # retry 后进度保留
    cp2 = await _read_checkpoint(task_id)
    assert cp2["last_completed_chapter"] == 5
    assert cp2["status"] == "running"
