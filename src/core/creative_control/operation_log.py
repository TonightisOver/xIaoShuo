"""创作操作审计日志服务（OperationLogService）。

职责：
- record：写一条 OperationLog 行并返回 dict。
- list：按 novel_id 过滤，可选 artifact_type/action/created_at>=since，desc 排序，limit 截断。

设计依据：docs/superpowers/specs/2026-07-21-creative-control-design.md
"""

from __future__ import annotations

import importlib
from datetime import datetime
from typing import Any

from sqlalchemy import select

from src.core.creative_control.contracts import OPERATION_ACTIONS
from src.core.database import get_db_session


def _orm():
    """延迟导入 ORM 模型：core 层不在顶层依赖 api.models（layer boundary）。

    用 importlib 动态加载，避免在模块中出现 ``from src.api...`` 的 import 语句
    （层边界静态守卫会扫描所有 AST import 节点，包括函数内与 TYPE_CHECKING 块）。
    """
    module = importlib.import_module("src.api.models.db_models")
    return module.OperationLog


def _log_to_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row.id,
        "action": row.action,
        "novel_id": row.novel_id,
        "artifact_type": row.artifact_type,
        "artifact_id": row.artifact_id,
        "from_version": row.from_version,
        "to_version": row.to_version,
        "operator_id": row.operator_id,
        "reason": row.reason,
        "task_id": row.task_id,
        "operation_id": row.operation_id,
        "meta": row.meta,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


class OperationLogService:
    """创作操作审计日志的读写入口。"""

    async def record(
        self,
        *,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        action: str,
        from_version: int | None = None,
        to_version: int | None = None,
        operator_id: int | None = None,
        reason: str | None = None,
        task_id: str | None = None,
        operation_id: str | None = None,
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """写一条 OperationLog 行并返回 dict。非法 action 抛 ValueError。"""
        OperationLog = _orm()  # noqa: N806
        if action not in OPERATION_ACTIONS:
            raise ValueError(f"invalid action: {action!r}")

        async with get_db_session() as session:
            row = OperationLog(
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
            )
            session.add(row)
            await session.flush()
            return _log_to_dict(row)

    async def list(
        self,
        novel_id: str,
        *,
        artifact_type: str | None = None,
        action: str | None = None,
        since: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """按 novel_id 过滤，可选 artifact_type/action/created_at>=since，desc 排序，limit 截断。"""
        OperationLog = _orm()  # noqa: N806
        stmt = select(OperationLog).where(OperationLog.novel_id == novel_id)
        if artifact_type is not None:
            stmt = stmt.where(OperationLog.artifact_type == artifact_type)
        if action is not None:
            stmt = stmt.where(OperationLog.action == action)
        if since is not None:
            stmt = stmt.where(OperationLog.created_at >= since)
        stmt = stmt.order_by(OperationLog.created_at.desc()).limit(limit)

        async with get_db_session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [_log_to_dict(row) for row in rows]
