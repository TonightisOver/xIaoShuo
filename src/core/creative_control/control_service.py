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

from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select

from src.api.models.db_models import ArtifactControl, OperationLog
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
)

logger = structlog.get_logger(__name__)

# 已确认/锁定：上游变更时仅标记过期，不自动重生成。
_PROTECTED_STATUSES = frozenset({"approved", "locked"})


def _row_to_dict(row: ArtifactControl) -> dict[str, Any]:
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

    # -------------------------------------------------------- assert_writable

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
            row = await self._select_for_update(session, novel_id, artifact_type, artifact_id)
            if row is None:
                if expected_version != 0:
                    raise ArtifactConflictError(
                        novel_id, artifact_type, artifact_id, expected_version, 0
                    )
                return
            if row.version != expected_version:
                raise ArtifactConflictError(
                    novel_id, artifact_type, artifact_id, expected_version, row.version
                )
            if row.control_status == "generating":
                raise ArtifactBusyError(novel_id, artifact_type, artifact_id)
            if row.locked and not force:
                raise ArtifactLockedError(novel_id, artifact_type, artifact_id)

    # ----------------------------------------------------------- 生成生命周期

    async def begin_generating(
        self, novel_id, artifact_type, artifact_id, *, expected_version,
        operator_id=None, task_id=None, operation_id=None,
    ) -> int:
        return await self._transition(
            novel_id, artifact_type, artifact_id, "generating",
            expected_version=expected_version, action="generate",
            operator_id=operator_id, task_id=task_id, operation_id=operation_id,
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
            return await self._apply_in_session(
                session, row, to_status="locked", action="lock",
                expected_version=expected_version, operator_id=operator_id,
            )

    async def unlock(
        self, novel_id, artifact_type, artifact_id, *, expected_version, operator_id=None
    ) -> int:
        return await self._single_session_apply(
            novel_id, artifact_type, artifact_id, to_status="approved",
            expected_version=expected_version, action="unlock", operator_id=operator_id,
        )

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
        self, novel_id, artifact_type, artifact_id, *, reason
    ) -> dict[str, Any]:
        """上游变更触发：标记自身 stale，级联下游。

        下游按 control 状态分流：未锁/未确认 → regenerable；已锁/已确认 → to_mark_stale。
        """
        async with get_db_session() as session:
            row = await self._select_for_update(session, novel_id, artifact_type, artifact_id)
            # 标记自身 stale（无行则跳过，仅级联下游）
            if row is not None:
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
    ) -> ArtifactControl | None:
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
    ) -> list[ArtifactControl]:
        """按依赖图查直接下游产物的 control 行。"""
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
    ) -> tuple[ArtifactControl, None]:
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
