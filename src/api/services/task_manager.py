"""任务管理器 - PostgreSQL 版本

负责任务的创建、状态管理和持久化
"""

from datetime import datetime, timedelta
from typing import Any
from uuid import uuid4

import structlog
from sqlalchemy import func, select

from src.api.models.db_models import Task
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)


class TaskManager:
    """任务管理器 - 使用 PostgreSQL 存储"""

    async def create_task(
        self, idea: str, novel_type: str, target_words: int,
        novel_id: str | None = None,
    ) -> str:
        """创建新任务"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        task_id = f"novel-{timestamp}-{uuid4().hex[:8]}"

        async with get_db_session() as session:
            task = Task(
                task_id=task_id,
                novel_id=novel_id,
                status="pending",
                idea=idea,
                novel_type=novel_type,
                target_words=target_words,
                created_at=datetime.now(),
                started_at=None,
                completed_at=None,
                estimated_completion=None,
                progress=None,
                result=None,
                errors=[],
            )
            session.add(task)
            await session.commit()

            logger.info(f"Created task {task_id}")
            return task_id

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

    async def complete_task(self, task_id: str, result: dict[str, Any]) -> None:
        """完成任务

        Args:
            task_id: 任务 ID
            result: 任务结果
        """
        async with get_db_session() as session:
            db_result = await session.execute(
                select(Task).where(Task.task_id == task_id)
            )
            task = db_result.scalar_one_or_none()

            if not task:
                logger.warning(f"Task {task_id} not found")
                return

            task.status = "completed"
            task.completed_at = datetime.now()
            task.result = result
            task.progress = {
                "current_stage": result.get("current_stage", "completed"),
                "completed_chapters": len(result.get("chapters", [])),
                "total_chapters": len(result.get("chapters", [])),
                "percentage": 100,
            }

            await session.commit()
            logger.info(f"Completed task {task_id}")

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

    async def recover_interrupted_tasks(self) -> int:
        """服务启动时恢复被中断的任务。

        服务重启时，内存中正在跑的 BackgroundTask 会丢失，但 Task 表里这些任务的
        status 仍是 ``running``（无人实际在跑）。本方法将这些「孤儿 running 任务」
        标记为 failed，避免它们永远卡在 running 状态误导用户。

        设计决策：标记为 failed 而非自动重跑——自动重跑有重复生成的风险（用户可能
        已经手动重试），且不同生成类型（分步/全功能/长篇）的入队参数各异，自动重放
        复杂且易错。标记 failed 让用户知情并自行决定是否重试，更安全。

        Returns:
            被标记为 failed 的孤儿任务数。
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(Task).where(Task.status == "running")
            )
            orphan_tasks = result.scalars().all()
            now = datetime.now()
            for task in orphan_tasks:
                task.status = "failed"
                task.completed_at = now
                current_errors = task.errors or []
                current_errors.append("系统重启中断：服务重启时任务仍在运行，已标记为失败，请重新发起")
                task.errors = current_errors
            await session.commit()
            if orphan_tasks:
                logger.warning(
                    "recovered_interrupted_tasks",
                    count=len(orphan_tasks),
                    task_ids=[t.task_id for t in orphan_tasks],
                )
            return len(orphan_tasks)


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
