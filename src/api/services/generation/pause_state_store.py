"""Persistent pause state for generation tasks.

Task 7（B14）：暂停意图（pause_requested）与暂停确认（status='paused'）分离。
- 长篇非 HITL 任务有 task_checkpoints 行：pause 语义走 checkpoint。
  - set_paused 只设 checkpoint.pause_requested=True（意图），不改 status——避免
    "用户点暂停瞬间 status 就变 paused 但 worker 还在写"的假象；worker 在下一个
    安全边界（chapter_completed）自行 advance_checkpoint(status='paused')。
  - is_pause_requested：读 checkpoint.pause_requested（业务层循环用，判断该不该停）。
  - is_paused_confirmed：读 checkpoint.status=='paused'（路由/前端用，判断真的停了）。
- 短篇 / HITL 任务无 checkpoint 行：降级为旧机制（直接读写 Task.status='paused'）。

Redis 作为 pause_requested 的加速缓存（DB 兜底），跨进程通知 worker。
"""

from __future__ import annotations

import os
from typing import Any

import structlog
from sqlalchemy import select, update

from src.api.models.db_models import Task, TaskCheckpoint
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)

PAUSE_KEY_PREFIX = "generation_pause:"


class PauseStateStore:
    def __init__(self) -> None:
        self._redis: Any | None = None
        self._redis_checked = False

    # ------------------------------------------------------------------
    # 暂停意图（pause_requested）
    # ------------------------------------------------------------------

    async def set_paused(self, task_id: str) -> None:
        """设置暂停意图。

        有 checkpoint（长篇）：设 checkpoint.pause_requested=True，不动 status。
        无 checkpoint（短篇/HITL）：降级设 Task.status='paused'（旧行为）。
        Redis 缓存 pause_requested=1 供 worker 跨进程快速感知。
        """
        await self._set_redis(task_id, True)
        has_cp = await self._set_checkpoint_pause_requested(task_id, True)
        if not has_cp:
            await self._set_db_status(task_id, "paused")

    async def clear_paused(self, task_id: str) -> None:
        """清除暂停意图（保留兼容：resume 主路径改走 requeue_paused_task）。

        有 checkpoint：清 checkpoint.pause_requested=False。
        无 checkpoint：降级把 Task.status 从 paused 改回 running。
        """
        await self._set_redis(task_id, False)
        has_cp = await self._set_checkpoint_pause_requested(task_id, False)
        if not has_cp:
            await self._set_db_status(task_id, "running")

    async def is_pause_requested(self, task_id: str) -> bool:
        """是否已请求暂停（业务层循环在安全边界判断该不该停）。

        Redis 命中优先；否则读 checkpoint.pause_requested；无 checkpoint 回退读
        Task.status=='paused'（短篇兼容）。
        """
        redis = self._get_redis()
        if redis is not None:
            try:
                value = await redis.get(self._key(task_id))
                if value is not None:
                    return value in ("1", b"1", True)
            except Exception as exc:
                logger.warning(
                    "pause_state_redis_read_failed", task_id=task_id, error=str(exc)
                )

        requested, has_cp = await self._read_checkpoint_pause_requested(task_id)
        if has_cp:
            if requested:
                await self._set_redis(task_id, True)
            return requested
        # 短篇降级
        paused = await self._is_db_paused(task_id)
        if paused:
            await self._set_redis(task_id, True)
        return paused

    async def is_paused_confirmed(self, task_id: str) -> bool:
        """worker 是否真的已在安全边界停下（checkpoint.status=='paused'）。

        无 checkpoint 回退读 Task.status=='paused'。路由/前端据此显示"已暂停"。
        """
        async with get_db_session() as session:
            cp_status = (
                await session.execute(
                    select(TaskCheckpoint.status).where(
                        TaskCheckpoint.task_id == task_id
                    )
                )
            ).scalar_one_or_none()
            if cp_status is not None:
                return cp_status == "paused"
            task_status = (
                await session.execute(
                    select(Task.status).where(Task.task_id == task_id)
                )
            ).scalar_one_or_none()
            return task_status == "paused"

    # 兼容别名：老调用点 is_paused 语义等价于"是否请求暂停"（业务层循环）。
    async def is_paused(self, task_id: str) -> bool:
        return await self.is_pause_requested(task_id)

    # ------------------------------------------------------------------
    # 内部：checkpoint / Task / Redis 读写
    # ------------------------------------------------------------------

    async def _set_checkpoint_pause_requested(
        self, task_id: str, value: bool
    ) -> bool:
        """UPDATE checkpoint.pause_requested。返回是否存在 checkpoint 行。

        不走 advance_checkpoint（无 lease 守卫）——pause 意图由路由/用户触发，
        与 worker 是否持 lease 无关；只设意图位，不推进 stage/checkpoint_version。
        """
        async with get_db_session() as session:
            result = await session.execute(
                update(TaskCheckpoint)
                .where(TaskCheckpoint.task_id == task_id)
                .values(pause_requested=value)
            )
            return result.rowcount > 0

    async def _read_checkpoint_pause_requested(
        self, task_id: str
    ) -> tuple[bool, bool]:
        """返回 (pause_requested, has_checkpoint)。"""
        async with get_db_session() as session:
            row = (
                await session.execute(
                    select(TaskCheckpoint.pause_requested).where(
                        TaskCheckpoint.task_id == task_id
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return False, False
            return bool(row), True

    def _get_redis(self) -> Any | None:
        if self._redis_checked:
            return self._redis

        self._redis_checked = True
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            return None

        try:
            from redis.asyncio import Redis
        except Exception as exc:
            logger.warning("pause_state_redis_import_failed", error=str(exc))
            return None

        try:
            self._redis = Redis.from_url(redis_url, decode_responses=True)
        except Exception as exc:
            logger.warning("pause_state_redis_init_failed", error=str(exc))
            self._redis = None
        return self._redis

    async def _set_redis(self, task_id: str, paused: bool) -> None:
        redis = self._get_redis()
        if redis is None:
            return

        try:
            if paused:
                await redis.set(self._key(task_id), "1")
            else:
                await redis.delete(self._key(task_id))
        except Exception as exc:
            logger.warning(
                "pause_state_redis_write_failed",
                task_id=task_id,
                paused=paused,
                error=str(exc),
            )

    async def _set_db_status(self, task_id: str, status: str) -> None:
        async with get_db_session() as session:
            result = await session.execute(select(Task).where(Task.task_id == task_id))
            task = result.scalar_one_or_none()
            if not task:
                logger.warning("pause_state_task_not_found", task_id=task_id)
                return
            task.status = status

    async def _is_db_paused(self, task_id: str) -> bool:
        async with get_db_session() as session:
            stmt = select(Task.status).where(Task.task_id == task_id)
            result = await session.execute(stmt)
            status = result.scalar_one_or_none()
            return status == "paused"

    @staticmethod
    def _key(task_id: str) -> str:
        return f"{PAUSE_KEY_PREFIX}{task_id}"


_pause_state_store: PauseStateStore | None = None


def get_pause_state_store() -> PauseStateStore:
    global _pause_state_store
    if _pause_state_store is None:
        _pause_state_store = PauseStateStore()
    return _pause_state_store
