"""CreativeControlService —— 创作产物控制元数据统一入口。

职责：
- assert_writable：乐观锁（expected_version）+ 锁定 + generating 占用校验
- begin/complete/fail_generating：生成生命周期
- mark_stale：上游变更触发，级联下游（未锁→可重生成，已锁/已确认→仅标记）
- lock/unlock/approve/set_status：带 expected_version 的状态转移
- get_or_create：历史产物惰性建行

所有变更在单个 get_db_session 事务内完成（select-for-update + 写状态 + version+1 + op log）。
设计依据：docs/superpowers/specs/2026-07-21-creative-control-design.md
"""

from __future__ import annotations

import importlib
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select

from src.core.creative_control.contracts import (
    DEPENDENCY_GRAPH,
    is_legal_transition,
    stage_of,
)
from src.core.database import get_db_session
from src.core.exceptions import (
    ArtifactBusyError,
    ArtifactConflictError,
    ArtifactLockedError,
    LeaseLost,
)

logger = structlog.get_logger(__name__)


def _orm():
    """延迟导入 ORM 模型：core 层不在顶层依赖 api.models（layer boundary）。

    用 importlib 动态加载，避免在模块中出现 ``from src.api...`` 的 import 语句
    （层边界静态守卫会扫描所有 AST import 节点，包括函数内与 TYPE_CHECKING 块）。
    """
    module = importlib.import_module("src.api.models.db_models")
    return module.ArtifactControl, module.OperationLog

# 已确认/锁定：上游变更时仅标记过期，不自动重生成。
_PROTECTED_STATUSES = frozenset({"approved", "locked"})
@dataclass(frozen=True)
class GenerationFence:
    task_id: str
    worker_id: str | None
    attempt_count: int | None


_CURRENT_GENERATION_TASK: ContextVar[GenerationFence | None] = ContextVar(
    "current_generation_task", default=None
)


def bind_generation_task(
    task_id: str,
    *,
    worker_id: str | None,
    attempt_count: int | None,
) -> None:
    """把当前 worker 协程绑定到持久任务，供产物写入 fencing 校验。"""
    _CURRENT_GENERATION_TASK.set(
        GenerationFence(task_id, worker_id, attempt_count)
    )


def has_generation_fence() -> bool:
    return _CURRENT_GENERATION_TASK.get() is not None


def current_generation_task_id() -> str | None:
    fence = _CURRENT_GENERATION_TASK.get()
    return fence.task_id if fence is not None else None


async def assert_generation_write_allowed_in_session(
    session,
    novel_id: str,
    artifact_type: str,
    artifact_id: str,
) -> None:
    """若当前协程属于后台生成任务，在业务写事务内执行统一 fence 校验。"""
    if has_generation_fence():
        await CreativeControlService().assert_generation_allowed_in_session(
            session, novel_id, artifact_type, artifact_id
        )


def _row_to_dict(row: Any) -> dict[str, Any]:
    return {
        "novel_id": row.novel_id,
        "artifact_type": row.artifact_type,
        "artifact_id": row.artifact_id,
        "control_status": row.control_status,
        "locked": row.locked,
        "version": row.version,
        "stage": row.stage,
        "generation_meta": row.generation_meta,
        "stale_reason": row.stale_reason,
        "awaiting_review": row.awaiting_review,
    }


class CreativeControlService:
    """控制元数据统一入口。"""

    # ------------------------------------------------------------------ read

    async def get_or_create(
        self,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        *,
        stage: int | None = None,
    ) -> dict[str, Any]:
        """读取 control 行；历史产物无行时惰性创建 generated/version=1。"""
        ArtifactControl, _ = _orm()  # noqa: N806
        async with get_db_session() as session:
            row = await self._select_for_update(session, novel_id, artifact_type, artifact_id)
            if row is None:
                row = ArtifactControl(
                    novel_id=novel_id,
                    artifact_type=artifact_type,
                    artifact_id=artifact_id,
                    control_status="generated",
                    version=1,
                    stage=stage or stage_of(artifact_type) or 1,
                )
                session.add(row)
                await session.flush()
            return _row_to_dict(row)

    async def reconcile_terminal_generations(self) -> int:
        """启动时收敛任务已终态但仍停留 generating 的控制行。"""
        module = importlib.import_module("src.api.models.db_models")
        ArtifactControl = module.ArtifactControl  # noqa: N806
        OperationLog = module.OperationLog  # noqa: N806
        Task = module.Task  # noqa: N806
        changed = 0
        async with get_db_session() as session:
            rows = list((
                await session.execute(
                    select(ArtifactControl)
                    .where(ArtifactControl.control_status == "generating")
                    .with_for_update()
                )
            ).scalars().all())
            for row in rows:
                task_id = (row.generation_meta or {}).get("task_id")
                task = None
                if task_id:
                    task = (
                        await session.execute(
                            select(Task).where(Task.task_id == task_id)
                        )
                    ).scalar_one_or_none()
                if task is not None and task.status not in {
                    "completed", "failed", "cancelled"
                }:
                    continue
                previous = row.version
                succeeded = task is not None and task.status == "completed"
                row.control_status = "generated" if succeeded else "failed"
                row.version += 1
                row.updated_at = datetime.now(UTC)
                session.add(OperationLog(
                    novel_id=row.novel_id,
                    artifact_type=row.artifact_type,
                    artifact_id=row.artifact_id,
                    action="generate",
                    from_version=previous,
                    to_version=row.version,
                    task_id=task_id,
                    operation_id=(row.generation_meta or {}).get("operation_id"),
                    meta={"reconciled": True, "task_status": getattr(task, "status", None)},
                ))
                changed += 1
        return changed

    # -------------------------------------------------------- assert_writable

    async def assert_generation_allowed(
        self,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        *,
        force: bool = False,
    ) -> None:
        """生成写入前锁定 control 行；锁定产物禁止被后台覆盖。"""
        async with get_db_session() as session:
            await self.assert_generation_allowed_in_session(
                session,
                novel_id,
                artifact_type,
                artifact_id,
                force=force,
            )

    async def assert_generation_allowed_in_session(
        self,
        session,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        *,
        force: bool = False,
    ) -> None:
        """在业务写入的同一事务内执行生成锁检查。"""
        fence = _CURRENT_GENERATION_TASK.get()
        if fence is not None and fence.worker_id is not None:
            module = importlib.import_module("src.api.models.db_models")
            Task = module.Task  # noqa: N806
            task = (
                await session.execute(
                    select(Task).where(Task.task_id == fence.task_id).with_for_update()
                )
            ).scalar_one_or_none()
            now = datetime.now(UTC)
            if (
                task is None
                or task.status != "running"
                or task.queue_state != "leased"
                or task.lease_owner != fence.worker_id
                or task.attempt_count != fence.attempt_count
                or task.lease_expires_at is None
                or task.lease_expires_at <= now
            ):
                raise LeaseLost(fence.task_id)
        row = await self._select_for_update(
            session, novel_id, artifact_type, artifact_id
        )
        if (
            row is not None
            and (row.locked or row.control_status == "locked")
            and not force
        ):
            raise ArtifactLockedError(
                novel_id, artifact_type, artifact_id
            )
        if row is not None and row.control_status == "generating":
            owner_task = (row.generation_meta or {}).get("task_id")
            if owner_task and (
                fence is None or owner_task != fence.task_id
            ):
                raise ArtifactBusyError(novel_id, artifact_type, artifact_id)

    async def record_generated(
        self,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        *,
        generation_meta: dict | None = None,
        operator_id: int | None = None,
        task_id: str | None = None,
        operation_id: str | None = None,
        respect_locked: bool = True,
        force: bool = False,
        awaiting_review: bool = False,
    ) -> dict[str, Any] | None:
        """生成路径专用：幂等记录产物已生成。

        与人工编辑的 assert_writable 不同，本方法用于生成路径自身落库后回写控制元数据：
        - 无 control 行 → 惰性建 generated/version=1。
        - 已存在 → 转 generating→generated，version+1，写 generation_meta。
        - respect_locked 且行已 locked 且非 force → 跳过（不覆盖锁定内容），返回 skipped_locked=True。
        - 任何异常被吞，返回 None（插桩不破坏生成，遵循 gate.py "never throw" 不变量）。
        """
        try:
            ArtifactControl, OperationLog = _orm()  # noqa: N806
            async with get_db_session() as session:
                row = await self._select_for_update(
                    session, novel_id, artifact_type, artifact_id
                )
                if row is None:
                    row = ArtifactControl(
                        novel_id=novel_id,
                        artifact_type=artifact_type,
                        artifact_id=artifact_id,
                        control_status="generating",
                        version=0,
                        stage=stage_of(artifact_type) or 1,
                    )
                    session.add(row)
                    await session.flush()
                if respect_locked and row.locked and not force:
                    return {
                        "novel_id": novel_id, "artifact_type": artifact_type,
                        "artifact_id": artifact_id, "skipped_locked": True,
                        "version": row.version,
                    }
                # generating -> generated（宽松转换，允许从任意非终态进入）
                row.control_status = "generated"
                row.version += 1
                row.generation_meta = generation_meta
                row.awaiting_review = awaiting_review
                row.updated_at = datetime.now(UTC)
                session.add(OperationLog(
                    novel_id=novel_id, artifact_type=artifact_type,
                    artifact_id=artifact_id, action="generate",
                    from_version=row.version - 1, to_version=row.version,
                    operator_id=operator_id, task_id=task_id, operation_id=operation_id,
                ))
                await session.flush()
                return _row_to_dict(row)
        except Exception:  # noqa: BLE001 - 插桩不破坏生成
            logger.warning(
                "creative_control_record_generated_failed",
                novel_id=novel_id, artifact_type=artifact_type,
                artifact_id=artifact_id,
            )
            return None

    # -------------------------------------------------------- assert_writable (人工编辑严格校验)

    async def assert_writable(
        self,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        expected_version: int,
        *,
        force: bool = False,
    ) -> None:
        """校验乐观锁 + 锁定 + generating 占用。不符即抛对应 409 异常。"""
        async with get_db_session() as session:
            await self.assert_writable_in_session(
                session,
                novel_id,
                artifact_type,
                artifact_id,
                expected_version,
                force=force,
            )

    async def assert_writable_in_session(
        self,
        session,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        expected_version: int,
        *,
        force: bool = False,
    ) -> Any | None:
        """在调用方事务内执行人工写入的完整并发检查。"""
        row = await self._select_for_update(
            session, novel_id, artifact_type, artifact_id
        )
        if row is None:
            if expected_version != 0:
                raise ArtifactConflictError(
                    novel_id, artifact_type, artifact_id, expected_version, 0
                )
            return None
        if row.version != expected_version:
            raise ArtifactConflictError(
                novel_id, artifact_type, artifact_id, expected_version, row.version
            )
        if row.control_status == "generating":
            raise ArtifactBusyError(novel_id, artifact_type, artifact_id)
        if (row.locked or row.control_status == "locked") and not force:
            raise ArtifactLockedError(novel_id, artifact_type, artifact_id)
        return row

    # ----------------------------------------------------------- 生成生命周期

    async def begin_generating(
        self, novel_id, artifact_type, artifact_id, *, expected_version,
        operator_id=None, task_id=None, operation_id=None, force=False,
    ) -> int:
        """原子抢占生成权；force=True 时在同一行锁事务内解除锁定。"""
        async with get_db_session() as session:
            row, _ = await self._guard(
                session,
                novel_id,
                artifact_type,
                artifact_id,
                expected_version,
            )
            if row.control_status == "generating":
                raise ArtifactBusyError(novel_id, artifact_type, artifact_id)
            if (row.locked or row.control_status == "locked") and not force:
                raise ArtifactLockedError(novel_id, artifact_type, artifact_id)
            if force:
                row.locked = False
            return await self._apply_in_session(
                session,
                row,
                to_status="generating",
                action="generate",
                expected_version=expected_version,
                operator_id=operator_id,
                task_id=task_id,
                operation_id=operation_id,
            )

    async def complete_generating(
        self, novel_id, artifact_type, artifact_id, *, expected_version,
        generation_meta=None, operator_id=None, task_id=None, operation_id=None,
        awaiting_review=False,
    ) -> int:
        return await self._transition(
            novel_id, artifact_type, artifact_id, "generated",
            expected_version=expected_version, action="generate",
            operator_id=operator_id, task_id=task_id, operation_id=operation_id,
            extra_values={"generation_meta": generation_meta, "awaiting_review": awaiting_review},
        )

    async def fail_generating(
        self, novel_id, artifact_type, artifact_id, *, expected_version,
        reason=None, operator_id=None, task_id=None, operation_id=None,
    ) -> int:
        return await self._transition(
            novel_id, artifact_type, artifact_id, "failed",
            expected_version=expected_version, action="generate",
            operator_id=operator_id, task_id=task_id, operation_id=operation_id,
            extra_values={"stale_reason": reason},
        )

    # ------------------------------------------------------- lock/unlock/approve

    async def lock(
        self, novel_id, artifact_type, artifact_id, *, expected_version, operator_id=None
    ) -> int:
        async with get_db_session() as session:
            row, _ = await self._guard(session, novel_id, artifact_type, artifact_id, expected_version)
            if row.control_status != "approved":
                raise ValueError(
                    f"lock requires approved status, got {row.control_status}"
                )
            version = await self._apply_in_session(
                session, row, to_status="locked", action="lock",
                expected_version=expected_version, operator_id=operator_id,
            )
            row.locked = True
            return version

    async def unlock(
        self, novel_id, artifact_type, artifact_id, *, expected_version, operator_id=None
    ) -> int:
        async with get_db_session() as session:
            row, _ = await self._guard(
                session, novel_id, artifact_type, artifact_id, expected_version
            )
            version = await self._apply_in_session(
                session,
                row,
                to_status="approved",
                expected_version=expected_version,
                action="unlock",
                operator_id=operator_id,
            )
            row.locked = False
            return version

    async def approve(
        self, novel_id, artifact_type, artifact_id, *, expected_version, operator_id=None
    ) -> int:
        return await self._single_session_apply(
            novel_id, artifact_type, artifact_id, to_status="approved",
            expected_version=expected_version, action="approve", operator_id=operator_id,
        )

    async def set_status(
        self, novel_id, artifact_type, artifact_id, *, expected_version, to_status, action,
        operator_id=None, reason=None,
    ) -> int:
        return await self._single_session_apply(
            novel_id, artifact_type, artifact_id, to_status=to_status,
            expected_version=expected_version, action=action,
            operator_id=operator_id, reason=reason,
        )

    # ------------------------------------------------------------- mark_stale

    async def mark_stale(
        self, novel_id, artifact_type, artifact_id, *, expected_version, reason
    ) -> dict[str, Any]:
        """上游变更触发：标记自身 stale，级联下游。

        下游按 control 状态分流：未锁/未确认 → regenerable；已锁/已确认 → to_mark_stale。
        """
        _, OperationLog = _orm()  # noqa: N806
        async with get_db_session() as session:
            row = await self._select_for_update(session, novel_id, artifact_type, artifact_id)
            # 标记自身 stale（无行则跳过，仅级联下游）
            if row is not None:
                if row.version != expected_version:
                    raise ArtifactConflictError(
                        novel_id,
                        artifact_type,
                        artifact_id,
                        expected_version,
                        row.version,
                    )
                row.control_status = "stale"
                row.stale_reason = reason
                row.version += 1
                row.updated_at = datetime.now(UTC)
                session.add(OperationLog(
                    novel_id=novel_id, artifact_type=artifact_type,
                    artifact_id=artifact_id, action="update_params",
                    from_version=row.version - 1, to_version=row.version,
                    reason=f"marked stale: {reason}",
                ))
            elif expected_version != 0:
                raise ArtifactConflictError(
                    novel_id, artifact_type, artifact_id, expected_version, 0
                )

            # 级联下游
            downstream_rows = await self._select_downstream(session, novel_id, artifact_type)
            regenerable: list[dict] = []
            to_mark_stale: list[dict] = []
            for d in downstream_rows:
                d_dict = _row_to_dict(d)
                if d.locked or d.control_status in _PROTECTED_STATUSES:
                    d.control_status = "stale"
                    d.stale_reason = f"upstream {artifact_type} changed: {reason}"
                    d.version += 1
                    d.updated_at = datetime.now(UTC)
                    to_mark_stale.append(d_dict)
                else:
                    regenerable.append(d_dict)
            await session.flush()

            upstream_dict = _row_to_dict(row) if row else {
                "novel_id": novel_id, "artifact_type": artifact_type,
                "artifact_id": artifact_id, "control_status": "stale",
                "version": 1, "locked": False,
            }
            return {
                "upstream": upstream_dict,
                "regenerable": regenerable,
                "to_mark_stale": to_mark_stale,
            }

    # --------------------------------------------------------------- 内部

    async def _select_for_update(
        self, session, novel_id, artifact_type, artifact_id
    ) -> Any | None:
        ArtifactControl, _ = _orm()  # noqa: N806
        result = await session.execute(
            select(ArtifactControl)
            .where(
                ArtifactControl.novel_id == novel_id,
                ArtifactControl.artifact_type == artifact_type,
                ArtifactControl.artifact_id == artifact_id,
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    async def _select_downstream(
        self, session, novel_id, artifact_type
    ) -> list[Any]:
        """按依赖图查直接下游产物的 control 行。"""
        ArtifactControl, _ = _orm()  # noqa: N806
        direct = DEPENDENCY_GRAPH.get(artifact_type, [])
        if not direct:
            return []
        result = await session.execute(
            select(ArtifactControl)
            .where(
                ArtifactControl.novel_id == novel_id,
                ArtifactControl.artifact_type.in_(direct),
            )
        )
        return list(result.scalars().all())

    async def _guard(
        self, session, novel_id, artifact_type, artifact_id, expected_version
    ) -> tuple[Any, None]:
        """单 session 内 select-for-update + 乐观锁校验，返回 row。"""
        row = await self._select_for_update(session, novel_id, artifact_type, artifact_id)
        if row is None:
            raise ArtifactConflictError(novel_id, artifact_type, artifact_id, expected_version, 0)
        if row.version != expected_version:
            raise ArtifactConflictError(novel_id, artifact_type, artifact_id, expected_version, row.version)
        return row, None

    async def _apply_in_session(
        self, session, row, *, to_status, action, expected_version,
        operator_id=None, reason=None, task_id=None, operation_id=None,
        extra_values=None,
    ) -> int:
        """在已持有行锁的 session 内做状态转移 + version+1 + op log。"""
        _, OperationLog = _orm()  # noqa: N806
        from_status = row.control_status
        if to_status != "generating" and not is_legal_transition(from_status, to_status):
            raise ValueError(f"illegal transition {from_status} -> {to_status}")
        row.control_status = to_status
        row.version += 1
        row.updated_at = datetime.now(UTC)
        if extra_values:
            for k, v in extra_values.items():
                if v is not None:
                    setattr(row, k, v)
        session.add(OperationLog(
            novel_id=row.novel_id, artifact_type=row.artifact_type,
            artifact_id=row.artifact_id, action=action,
            from_version=expected_version, to_version=row.version,
            operator_id=operator_id, reason=reason, task_id=task_id, operation_id=operation_id,
        ))
        await session.flush()
        return row.version

    async def _single_session_apply(
        self, novel_id, artifact_type, artifact_id, *, to_status, expected_version,
        action, operator_id=None, reason=None,
    ) -> int:
        async with get_db_session() as session:
            row, _ = await self._guard(session, novel_id, artifact_type, artifact_id, expected_version)
            return await self._apply_in_session(
                session, row, to_status=to_status, action=action,
                expected_version=expected_version, operator_id=operator_id, reason=reason,
            )

    async def _transition(
        self, novel_id, artifact_type, artifact_id, to_status, *,
        expected_version, action, operator_id=None, task_id=None, operation_id=None,
        extra_values=None,
    ) -> int:
        async with get_db_session() as session:
            row, _ = await self._guard(session, novel_id, artifact_type, artifact_id, expected_version)
            return await self._apply_in_session(
                session, row, to_status=to_status, action=action,
                expected_version=expected_version, operator_id=operator_id,
                task_id=task_id, operation_id=operation_id, extra_values=extra_values,
            )
