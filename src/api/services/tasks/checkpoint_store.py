"""长篇生成任务的持久化检查点服务。

职责：
- ensure_checkpoint：幂等创建初始检查点
- advance_checkpoint：单事务内 lease 守卫 + checkpoint_version 乐观锁推进
- read：读取当前检查点

设计依据：docs/superpowers/specs/2026-07-20-long-form-stability-design.md
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, update

from src.api.models.db_models import Task, TaskCheckpoint
from src.core.database import get_db_session
from src.core.exceptions import CheckpointConflict, LeaseLost

# 章节 6 阶段 + 卷/任务级阶段。调用方负责合法转换；store 不强制顺序。
STAGE_ORDER: tuple[str, ...] = (
    "chapter_planned",
    "generation_started",
    "baseline_persisted",
    "quality_finalized",
    "side_effects_recorded",
    "chapter_completed",
    "volume_start",
    "volume_end",
    "task_end",
)

LEGAL_STAGE_PREDECESSORS: dict[str, frozenset[str]] = {
    "chapter_planned": frozenset(
        {"chapter_planned", "chapter_completed", "volume_start"}
    ),
    "generation_started": frozenset({"chapter_planned", "generation_started"}),
    "baseline_persisted": frozenset({"generation_started", "baseline_persisted"}),
    "quality_finalized": frozenset({"baseline_persisted", "quality_finalized"}),
    "side_effects_recorded": frozenset(
        {"quality_finalized", "side_effects_recorded"}
    ),
    "chapter_completed": frozenset(
        {"side_effects_recorded", "chapter_completed"}
    ),
    "volume_start": frozenset({"chapter_planned", "volume_end", "volume_start"}),
    "volume_end": frozenset({"chapter_completed", "volume_start", "volume_end"}),
    "task_end": frozenset({"volume_end", "task_end"}),
}


def is_legal_stage_transition(current_stage: str, target_stage: str) -> bool:
    """返回持久化检查点是否允许从当前阶段推进到目标阶段。"""
    return current_stage in LEGAL_STAGE_PREDECESSORS.get(
        target_stage, frozenset()
    )


def _checkpoint_to_dict(row: TaskCheckpoint) -> dict[str, Any]:
    return {
        "task_id": row.task_id,
        "novel_id": row.novel_id,
        "operation_id": row.operation_id,
        "current_stage": row.current_stage,
        "volume_number": row.volume_number,
        "chapter_number": row.chapter_number,
        "last_completed_volume": row.last_completed_volume,
        "last_completed_chapter": row.last_completed_chapter,
        "active_version_number": row.active_version_number,
        "checkpoint_version": row.checkpoint_version,
        "attempt_number": row.attempt_number,
        "last_event_sequence": row.last_event_sequence,
        "status": row.status,
        "pause_requested": row.pause_requested,
        "failure_category": row.failure_category,
        "recoverable": row.recoverable,
        "failure_detail": row.failure_detail,
        "updated_at": row.updated_at,
    }


def _assert_lease_in_session(
    task_row: Task | None,
    worker_id: str,
    now: datetime,
    task_id: str,
) -> None:
    """在已持有行锁的 session 内校验 lease 所有权。

    只校验 lease_owner + lease_expires_at，**不校验 queue_state**（B2 决议：
    暂停路径下 queue_state 可能已变 idle，但 lease 仍有效，允许推进 status='paused'）。
    """
    if (
        task_row is None
        or task_row.lease_owner != worker_id
        or task_row.lease_expires_at is None
        or task_row.lease_expires_at <= now
    ):
        raise LeaseLost(task_id)


class CheckpointStore:
    """长篇任务检查点的读写入口。"""

    async def ensure_checkpoint(
        self,
        task_id: str,
        novel_id: str,
        operation_id: str,
    ) -> dict[str, Any]:
        """幂等创建初始检查点。已存在则直接返回。"""
        async with get_db_session() as session:
            result = await session.execute(
                select(TaskCheckpoint).where(TaskCheckpoint.task_id == task_id)
            )
            existing = result.scalar_one_or_none()
            if existing is not None:
                return _checkpoint_to_dict(existing)

            row = TaskCheckpoint(
                task_id=task_id,
                novel_id=novel_id,
                operation_id=operation_id,
                current_stage="chapter_planned",
                checkpoint_version=0,
                status="pending",
                last_completed_volume=0,
                last_completed_chapter=0,
                attempt_number=0,
                last_event_sequence=0,
                pause_requested=False,
                recoverable=True,
            )
            session.add(row)
            await session.flush()
            return _checkpoint_to_dict(row)

    async def assert_lease_held(self, task_id: str, worker_id: str) -> None:
        """在每个阶段的昂贵操作前做早期 lease 校验。

        advance_checkpoint 内部已在同事务复查 lease（消除 TOCTOU），本方法用于
        在 LLM 生成 / persist 等昂贵写前先确认仍持有 lease，避免白干。
        失败抛 LeaseLost，由调用方（generate_volume_chapters）向上传播、干净退出。
        """
        async with get_db_session() as session:
            task_result = await session.execute(
                select(Task).where(Task.task_id == task_id)
            )
            task_row = task_result.scalar_one_or_none()
            _assert_lease_in_session(task_row, worker_id, datetime.now(UTC), task_id)

    async def read(self, task_id: str) -> dict[str, Any] | None:
        """读取当前检查点；不存在返回 None。"""
        async with get_db_session() as session:
            result = await session.execute(
                select(TaskCheckpoint).where(TaskCheckpoint.task_id == task_id)
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return _checkpoint_to_dict(row)

    async def allocate_event_sequence(
        self,
        task_id: str,
        worker_id: str,
    ) -> int:
        """在 lease 守卫下原子分配单调递增的事件序号。"""
        async with get_db_session() as session:
            task_row = (
                await session.execute(
                    select(Task).where(Task.task_id == task_id).with_for_update()
                )
            ).scalar_one_or_none()
            _assert_lease_in_session(
                task_row, worker_id, datetime.now(UTC), task_id
            )
            checkpoint = (
                await session.execute(
                    select(TaskCheckpoint)
                    .where(TaskCheckpoint.task_id == task_id)
                    .with_for_update()
                )
            ).scalar_one_or_none()
            if checkpoint is None:
                raise ValueError(f"checkpoint not found: {task_id}")
            checkpoint.last_event_sequence += 1
            await session.flush()
            return checkpoint.last_event_sequence

    async def mark_failed(
        self,
        task_id: str,
        worker_id: str | None,
        *,
        category: str,
        detail: dict | None = None,
        recoverable: bool = False,
    ) -> bool:
        """Task 10：写入失败分类（不走 lease 守卫，供路由/abort 调用）。

        worker_id 为 None 时（路由层无 lease）跳过 owner 校验；非 None 时仍要求
        持有 lease（worker 自报失败场景）。只写 failure_category/failure_detail/
        recoverable/status='failed'，不动 stage/checkpoint_version。
        """
        async with get_db_session() as session:
            if worker_id is not None:
                task_row = (
                    await session.execute(
                        select(Task).where(Task.task_id == task_id).with_for_update()
                    )
                ).scalar_one_or_none()
                _assert_lease_in_session(
                    task_row, worker_id, datetime.now(UTC), task_id
                )
            result = await session.execute(
                update(TaskCheckpoint)
                .where(TaskCheckpoint.task_id == task_id)
                .values(
                    failure_category=category,
                    failure_detail=detail,
                    recoverable=recoverable,
                    status="failed",
                    attempt_number=TaskCheckpoint.attempt_number + 1,
                    updated_at=datetime.now(UTC),
                )
            )
            return result.rowcount > 0

    async def public_view(self, task_id: str) -> dict[str, Any] | None:
        """Task 10：对外公开的 checkpoint 摘要（不含 failure_detail 等敏感字段）。"""
        cp = await self.read(task_id)
        if cp is None:
            return None
        return {
            "task_id": cp["task_id"],
            "current_stage": cp["current_stage"],
            "volume_number": cp["volume_number"],
            "chapter_number": cp["chapter_number"],
            "last_completed_volume": cp["last_completed_volume"],
            "last_completed_chapter": cp["last_completed_chapter"],
            "active_version_number": cp["active_version_number"],
            "status": cp["status"],
            "pause_requested": cp["pause_requested"],
            "failure_category": cp["failure_category"],
            "recoverable": cp["recoverable"],
            "attempt_number": cp["attempt_number"],
            "updated_at": cp["updated_at"],
        }

    async def advance_checkpoint(
        self,
        task_id: str,
        worker_id: str,
        *,
        expected_checkpoint_version: int,
        stage: str,
        volume_number: int | None = None,
        chapter_number: int | None = None,
        active_version_number: int | None = None,
        last_completed_volume: int | None = None,
        last_completed_chapter: int | None = None,
        last_event_sequence: int | None = None,
        status: str | None = None,
        failure_category: str | None = None,
        failure_detail: dict | None = None,
        recoverable: bool | None = None,
    ) -> int:
        """在单事务内校验 lease + 乐观锁，推进检查点。

        Returns:
            新的 checkpoint_version。

        Raises:
            LeaseLost: worker 不再持有 lease。
            CheckpointConflict: expected_checkpoint_version 不匹配。
        """
        async with get_db_session() as session:
            task_result = await session.execute(
                select(Task)
                .where(Task.task_id == task_id)
                .with_for_update()
            )
            task_row = task_result.scalar_one_or_none()
            now = datetime.now(UTC)
            _assert_lease_in_session(task_row, worker_id, now, task_id)

            values: dict[str, Any] = {
                "current_stage": stage,
                "checkpoint_version": expected_checkpoint_version + 1,
                "updated_at": now,
            }
            optional = {
                "volume_number": volume_number,
                "chapter_number": chapter_number,
                "active_version_number": active_version_number,
                "last_completed_volume": last_completed_volume,
                "last_completed_chapter": last_completed_chapter,
                "last_event_sequence": last_event_sequence,
                "status": status,
                "failure_category": failure_category,
                "failure_detail": failure_detail,
                "recoverable": recoverable,
            }
            for key, val in optional.items():
                if val is not None:
                    values[key] = val

            result = await session.execute(
                update(TaskCheckpoint)
                .where(
                    TaskCheckpoint.task_id == task_id,
                    TaskCheckpoint.checkpoint_version
                    == expected_checkpoint_version,
                    TaskCheckpoint.current_stage.in_(
                        LEGAL_STAGE_PREDECESSORS.get(stage, frozenset())
                    ),
                )
                .values(**values)
            )
            if result.rowcount == 0:
                raise CheckpointConflict(task_id, expected_checkpoint_version)
            return expected_checkpoint_version + 1


_checkpoint_store: CheckpointStore | None = None


def get_checkpoint_store() -> CheckpointStore:
    """获取 CheckpointStore 单例。"""
    global _checkpoint_store
    if _checkpoint_store is None:
        _checkpoint_store = CheckpointStore()
    return _checkpoint_store
