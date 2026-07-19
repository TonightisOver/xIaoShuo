"""任务管理器 - PostgreSQL 版本

负责任务的创建、状态管理、持久化和队列租约。
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy import and_, func, or_, select

from src.api.models.db_models import Task
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class RecoverySummary:
    """服务启动时的队列恢复统计。"""

    queued_preserved: int = 0
    stale_requeued: int = 0
    stale_failed: int = 0
    legacy_failed: int = 0

    @property
    def total_changed(self) -> int:
        return self.stale_requeued + self.stale_failed + self.legacy_failed


def _clear_lease(task: Task) -> None:
    task.lease_owner = None
    task.lease_expires_at = None
    task.heartbeat_at = None


def _is_waiting_review_task(task: Task) -> bool:
    progress = task.progress or {}
    return (
        task.status == "running"
        and task.queue_state == "idle"
        and progress.get("current_stage") == "human_review"
        and progress.get("waiting_for_review") is True
        and progress.get("review_decision", "pending") == "pending"
    )


class TaskManager:
    """任务管理器 - 使用 PostgreSQL 存储"""

    async def create_task(
        self, idea: str, novel_type: str, target_words: int,
        novel_id: str | None = None,
        *,
        task_type: str | None = None,
        task_payload: dict[str, Any] | None = None,
        max_attempts: int = 1,
    ) -> str:
        """创建新任务"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        task_id = f"novel-{timestamp}-{uuid4().hex[:8]}"
        now = datetime.now(UTC)

        async with get_db_session() as session:
            task = Task(
                task_id=task_id,
                novel_id=novel_id,
                status="pending",
                idea=idea,
                novel_type=novel_type,
                target_words=target_words,
                created_at=now,
                started_at=None,
                completed_at=None,
                estimated_completion=None,
                progress=None,
                result=None,
                errors=[],
                task_type=task_type,
                task_payload=task_payload,
                queue_state="queued" if task_type else None,
                attempt_count=0,
                max_attempts=max(1, max_attempts),
                available_at=now if task_type else None,
                lease_owner=None,
                lease_expires_at=None,
                heartbeat_at=None,
            )
            session.add(task)
            await session.commit()

            logger.info(f"Created task {task_id}")
            return task_id

    async def enqueue_existing_task(
        self,
        task_id: str,
        *,
        task_type: str,
        task_payload: dict[str, Any],
        max_attempts: int = 1,
    ) -> bool:
        """把现有 Task 作为新的执行段重新入队（用于 HITL resume）。"""
        now = datetime.now(UTC)
        async with get_db_session() as session:
            result = await session.execute(
                select(Task)
                .where(Task.task_id == task_id)
                .with_for_update()
            )
            task = result.scalar_one_or_none()
            if not task:
                return False

            if task_type == "pipeline.resume":
                progress = task.progress or {}
                decision = task_payload.get("decision")
                if (
                    not _is_waiting_review_task(task)
                    or not isinstance(decision, dict)
                    or decision.get("approval_status")
                    not in {"approved", "revision"}
                ):
                    return False

                updated_progress = dict(progress)
                updated_progress.update(
                    {
                        "review_decision": decision["approval_status"],
                        "review_instructions": decision.get(
                            "revision_instructions", ""
                        ),
                        "reviewed_at": now.isoformat(),
                        "waiting_for_review": False,
                    }
                )
                task.progress = updated_progress

            task.task_type = task_type
            task.task_payload = task_payload
            task.queue_state = "queued"
            task.attempt_count = 0
            task.max_attempts = max(1, max_attempts)
            task.available_at = now
            task.status = "pending"
            task.completed_at = None
            _clear_lease(task)
            await session.commit()
            return True

    async def reject_review_task(
        self,
        task_id: str,
        *,
        instructions: str = "",
    ) -> bool:
        """在行锁内校验并原子驳回等待审核的任务。"""
        now = datetime.now(UTC)
        async with get_db_session() as session:
            result = await session.execute(
                select(Task)
                .where(Task.task_id == task_id)
                .with_for_update()
            )
            task = result.scalar_one_or_none()
            if not task or not _is_waiting_review_task(task):
                return False

            progress = dict(task.progress or {})
            progress.update(
                {
                    "review_decision": "rejected",
                    "review_instructions": instructions,
                    "reviewed_at": now.isoformat(),
                    "waiting_for_review": False,
                }
            )
            task.progress = progress
            task.status = "failed"
            task.completed_at = now
            task.queue_state = "idle"
            task.errors = [*(task.errors or []), "用户驳回审核"]
            _clear_lease(task)
            await session.commit()
            return True

    async def claim_next_task(
        self, worker_id: str, lease_seconds: int
    ) -> dict[str, Any] | None:
        """原子领取一个可执行任务，并写入租约。"""
        now = datetime.now(UTC)
        async with get_db_session() as session:
            query = (
                select(Task)
                .where(
                    Task.task_type.is_not(None),
                    or_(
                        and_(
                            Task.queue_state == "queued",
                            Task.attempt_count < Task.max_attempts,
                            or_(
                                Task.available_at.is_(None),
                                Task.available_at <= now,
                            ),
                        ),
                        and_(
                            Task.queue_state == "leased",
                            or_(
                                Task.lease_expires_at.is_(None),
                                Task.lease_expires_at <= now,
                            ),
                        ),
                    ),
                )
                .order_by(Task.created_at.asc())
                .with_for_update(skip_locked=True)
                .limit(1)
            )
            result = await session.execute(query)
            task = result.scalar_one_or_none()
            if not task:
                return None

            if (
                task.queue_state == "leased"
                and task.attempt_count >= task.max_attempts
            ):
                task.status = "failed"
                task.completed_at = now
                task.queue_state = "idle"
                task.errors = [
                    *(task.errors or []),
                    "任务租约过期：任务已开始执行且不安全自动重放，已标记为失败",
                ]
                _clear_lease(task)
                await session.commit()
                return None

            task.queue_state = "leased"
            task.status = "running"
            task.attempt_count = (task.attempt_count or 0) + 1
            task.lease_owner = worker_id
            task.heartbeat_at = now
            task.lease_expires_at = now + timedelta(seconds=lease_seconds)
            if not task.started_at:
                task.started_at = now
                task.estimated_completion = now + timedelta(minutes=70)
            await session.commit()
            return {
                "task_id": task.task_id,
                "novel_id": task.novel_id,
                "task_type": task.task_type,
                "task_payload": task.task_payload or {},
                "attempt_count": task.attempt_count,
                "max_attempts": task.max_attempts,
            }

    async def renew_lease(
        self, task_id: str, worker_id: str, lease_seconds: int
    ) -> bool:
        """仅允许当前 owner 续租。"""
        now = datetime.now(UTC)
        async with get_db_session() as session:
            result = await session.execute(
                select(Task).where(Task.task_id == task_id).with_for_update()
            )
            task = result.scalar_one_or_none()
            if (
                not task
                or task.queue_state != "leased"
                or task.lease_owner != worker_id
            ):
                return False
            task.heartbeat_at = now
            task.lease_expires_at = now + timedelta(seconds=lease_seconds)
            await session.commit()
            return True

    async def release_claim(self, task_id: str, worker_id: str) -> bool:
        """handler 正常返回后释放租约，识别 HITL/暂停与异常假死。"""
        async with get_db_session() as session:
            result = await session.execute(
                select(Task).where(Task.task_id == task_id).with_for_update()
            )
            task = result.scalar_one_or_none()
            if (
                not task
                or task.queue_state != "leased"
                or task.lease_owner != worker_id
            ):
                return False

            progress = task.progress or {}
            waiting_for_review = bool(
                progress.get("waiting_for_review")
                or progress.get("current_stage") == "human_review"
            )
            if task.status in {"completed", "failed", "paused"} or waiting_for_review:
                task.queue_state = "idle"
            else:
                task.status = "failed"
                task.completed_at = datetime.now(UTC)
                task.queue_state = "idle"
                task.errors = [
                    *(task.errors or []),
                    "队列执行器返回，但任务未进入终态或等待状态",
                ]
            _clear_lease(task)
            await session.commit()
            return True

    async def retry_or_fail_claim(
        self,
        task_id: str,
        worker_id: str,
        error: str,
        retry_delay_seconds: int,
    ) -> bool:
        """未捕获异常后按次数重新排队或进入失败终态。"""
        now = datetime.now(UTC)
        async with get_db_session() as session:
            result = await session.execute(
                select(Task).where(Task.task_id == task_id).with_for_update()
            )
            task = result.scalar_one_or_none()
            if (
                not task
                or task.queue_state != "leased"
                or task.lease_owner != worker_id
            ):
                return False

            task.errors = [*(task.errors or []), error]
            if task.attempt_count < task.max_attempts:
                task.status = "pending"
                task.queue_state = "queued"
                task.available_at = now + timedelta(seconds=retry_delay_seconds)
                _clear_lease(task)
                await session.commit()
                return True

            task.status = "failed"
            task.completed_at = now
            task.queue_state = "idle"
            _clear_lease(task)
            await session.commit()
            return False

    async def get_task(self, task_id: str) -> dict[str, Any] | None:
        """获取任务详情

        Args:
            task_id: 任务 ID

        Returns:
            任务详情字典，如果不存在则返回 None
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(Task).where(Task.task_id == task_id)
            )
            task = result.scalar_one_or_none()
            return task.to_dict() if task else None

    async def list_tasks(
        self,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """列出任务

        Args:
            status: 过滤状态（可选）
            limit: 返回数量
            offset: 偏移量

        Returns:
            (任务列表, 总数)
        """
        async with get_db_session() as session:
            # Build query
            query = select(Task)
            if status:
                query = query.where(Task.status == status)

            # Get total count
            count_query = select(func.count()).select_from(query.subquery())
            total_result = await session.execute(count_query)
            total = total_result.scalar_one()

            # Apply sorting and pagination
            query = query.order_by(Task.created_at.desc()).limit(limit).offset(offset)

            # Execute query
            result = await session.execute(query)
            tasks = result.scalars().all()

            return [task.to_dict() for task in tasks], total

    async def update_status(
        self,
        task_id: str,
        status: str,
        progress: dict[str, Any] | None = None,
    ) -> None:
        """更新任务状态

        Args:
            task_id: 任务 ID
            status: 新状态
            progress: 进度信息（可选）
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(Task).where(Task.task_id == task_id)
            )
            task = result.scalar_one_or_none()

            if not task:
                logger.warning(f"Task {task_id} not found")
                return

            task.status = status

            if status == "running" and not task.started_at:
                task.started_at = datetime.now()
                task.estimated_completion = datetime.now() + timedelta(minutes=70)

            if progress:
                task.progress = progress

            await session.commit()
            logger.info(f"Updated task {task_id} status to {status}")

    async def complete_task(self, task_id: str, result: dict[str, Any], status: str = "completed") -> None:
        """完成任务

        Args:
            task_id: 任务 ID
            result: 任务结果
            status: 任务状态 (completed/partially_completed/completed_with_unverified_quality/failed)
        """
        async with get_db_session() as session:
            db_result = await session.execute(
                select(Task).where(Task.task_id == task_id)
            )
            task = db_result.scalar_one_or_none()

            if not task:
                logger.warning(f"Task {task_id} not found")
                return

            task.status = status
            task.completed_at = datetime.now()
            task.result = result
            if getattr(task, "queue_state", None) is not None:
                task.queue_state = "idle"
                _clear_lease(task)
            task.progress = {
                "current_stage": result.get("current_stage", status),
                "completed_chapters": len(result.get("chapters", [])),
                "total_chapters": len(result.get("chapters", [])),
                "percentage": 100 if status == "completed" else result.get("completion_percentage", 100),
            }

            await session.commit()
            logger.info(f"Completed task {task_id} with status {status}")

    async def fail_task(self, task_id: str, error: str) -> None:
        """任务失败

        Args:
            task_id: 任务 ID
            error: 错误信息
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(Task).where(Task.task_id == task_id)
            )
            task = result.scalar_one_or_none()

            if not task:
                logger.warning(f"Task {task_id} not found")
                return

            task.status = "failed"
            task.completed_at = datetime.now()
            if getattr(task, "queue_state", None) is not None:
                task.queue_state = "idle"
                _clear_lease(task)

            # Append error to errors list
            current_errors = task.errors or []
            current_errors.append(error)
            task.errors = current_errors

            await session.commit()
            logger.error(f"Task {task_id} failed: {error}")

    async def set_review_decision(
        self, task_id: str, status: str, instructions: str = "",
    ) -> None:
        """设置人工审核决策

        将审核决策写入 task progress，供后续流水线读取。

        Args:
            task_id: 任务 ID
            status: 审核结果 (approved/rejected/revision)
            instructions: 修改意见
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(Task).where(Task.task_id == task_id)
            )
            task = result.scalar_one_or_none()

            if not task:
                logger.warning(f"Task {task_id} not found")
                return

            # Merge decision into progress
            current_progress = task.progress or {}
            current_progress.update({
                "review_decision": status,
                "review_instructions": instructions,
                "reviewed_at": datetime.now().isoformat(),
            })
            task.progress = current_progress

            # If rejected, mark task as failed
            if status == "rejected":
                task.status = "failed"

            await session.commit()
            logger.info(f"Review decision set for task {task_id}: {status}")

    async def get_review_data(self, task_id: str) -> dict[str, str | bool | None]:
        """获取待审核数据

        Returns:
            dict with:
                current_stage: 当前阶段
                approval_status: 审核状态
                waiting_for_review: 是否在等待审核
                progress: 进度信息
                result: 任务结果
        """
        task = await self.get_task(task_id)
        if not task:
            return {
                "current_stage": "",
                "approval_status": "none",
                "waiting_for_review": False,
                "progress": None,
                "result": None,
            }

        progress = task.get("progress") or {}
        current_stage = progress.get("current_stage", "")
        approval_status = progress.get("review_decision", "pending")
        waiting_for_review = (
            current_stage == "human_review" and approval_status == "pending"
        )

        return {
            "current_stage": current_stage,
            "approval_status": approval_status,
            "waiting_for_review": waiting_for_review,
            "progress": progress,
            "result": task.get("result"),
        }

    async def expire_stale_tasks(self, hours: int = 2) -> int:
        """将超时未完成的任务标记为失败"""
        cutoff = datetime.now() - timedelta(hours=hours)
        async with get_db_session() as session:
            result = await session.execute(
                select(Task).where(
                    Task.status.in_(["running", "pending"]),
                    Task.queue_state.is_(None),
                    Task.created_at < cutoff,
                )
            )
            stale_tasks = result.scalars().all()
            for task in stale_tasks:
                task.status = "failed"
                task.completed_at = datetime.now()
                current_errors = task.errors or []
                current_errors.append(f"系统自动标记：任务创建超过{hours}小时未完成")
                task.errors = current_errors
            await session.commit()
            if stale_tasks:
                logger.info(f"Expired {len(stale_tasks)} stale tasks")
            return len(stale_tasks)

    async def recover_interrupted_tasks(self) -> RecoverySummary:
        """分类恢复 queued、过期 leased 与历史不可重放任务。"""
        async with get_db_session() as session:
            result = await session.execute(
                select(Task).where(
                    or_(
                        Task.queue_state.in_(["queued", "leased"]),
                        and_(
                            Task.queue_state.is_(None),
                            Task.status.in_(["running", "pending"]),
                        ),
                    )
                ).with_for_update(skip_locked=True)
            )
            tasks = result.scalars().all()
            now = datetime.now(UTC)
            queued_preserved = 0
            stale_requeued = 0
            stale_failed = 0
            legacy_failed = 0

            for task in tasks:
                if task.queue_state == "queued":
                    queued_preserved += 1
                    continue
                if task.queue_state == "idle":
                    continue
                if task.queue_state == "leased":
                    if task.lease_expires_at and task.lease_expires_at > now:
                        continue
                    if task.attempt_count < task.max_attempts:
                        task.status = "pending"
                        task.queue_state = "queued"
                        task.available_at = now
                        _clear_lease(task)
                        stale_requeued += 1
                    else:
                        task.status = "failed"
                        task.completed_at = now
                        task.queue_state = "idle"
                        task.errors = [
                            *(task.errors or []),
                            "系统重启中断：任务已开始执行且不安全自动重放，已标记为失败",
                        ]
                        _clear_lease(task)
                        stale_failed += 1
                    continue

                if task.queue_state is None and task.status in {"running", "pending"}:
                    was_running = task.status == "running"
                    task.status = "failed"
                    task.completed_at = now
                    reason = (
                        "系统重启中断：历史任务执行中断且缺少可重放参数，已标记为失败"
                        if was_running
                        else "系统重启中断：历史排队任务缺少可执行参数，已标记为失败"
                    )
                    task.errors = [*(task.errors or []), reason]
                    legacy_failed += 1

            await session.commit()
            summary = RecoverySummary(
                queued_preserved=queued_preserved,
                stale_requeued=stale_requeued,
                stale_failed=stale_failed,
                legacy_failed=legacy_failed,
            )
            if tasks:
                logger.warning(
                    "recovered_interrupted_tasks",
                    queued_preserved=summary.queued_preserved,
                    stale_requeued=summary.stale_requeued,
                    stale_failed=summary.stale_failed,
                    legacy_failed=summary.legacy_failed,
                )
            return summary


# 全局任务管理器实例
_task_manager: TaskManager | None = None


def get_task_manager() -> TaskManager:
    """获取任务管理器单例

    Returns:
        TaskManager 实例
    """
    global _task_manager
    if _task_manager is None:
        _task_manager = TaskManager()
    return _task_manager
