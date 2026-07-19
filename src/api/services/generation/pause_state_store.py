"""Persistent pause state for generation tasks."""

from __future__ import annotations

import os
from typing import Any

import structlog
from sqlalchemy import select

from src.api.models.db_models import Task
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)

PAUSE_KEY_PREFIX = "generation_pause:"


class PauseStateStore:
    def __init__(self) -> None:
        self._redis: Any | None = None
        self._redis_checked = False

    async def set_paused(self, task_id: str) -> None:
        await self._set_redis(task_id, True)
        await self._set_db_status(task_id, "paused")

    async def clear_paused(self, task_id: str) -> None:
        await self._set_redis(task_id, False)
        await self._set_db_status(task_id, "running")

    async def is_paused(self, task_id: str) -> bool:
        redis = self._get_redis()
        if redis is not None:
            try:
                value = await redis.get(self._key(task_id))
                if value is not None:
                    return value in ("1", b"1", True)
            except Exception as exc:
                logger.warning(
                    "pause_state_redis_read_failed",
                    task_id=task_id,
                    error=str(exc),
                )

        paused = await self._is_db_paused(task_id)
        if paused:
            await self._set_redis(task_id, True)
        return paused

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
