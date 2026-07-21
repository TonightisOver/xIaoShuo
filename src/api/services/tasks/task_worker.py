"""PostgreSQL 租约队列的进程内 worker。"""

import asyncio
import os
import socket
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any
from uuid import uuid4

import structlog

from src.api.services.tasks.task_dispatcher import dispatch_task
from src.api.services.tasks.task_manager import TaskManager, get_task_manager
from src.core.config import get_settings
from src.core.exceptions import LeaseLost, PausedExit

logger = structlog.get_logger(__name__)


class PersistentTaskWorker:
    """逐个领取持久化任务，并在执行期间维护数据库租约。"""

    def __init__(
        self,
        manager: TaskManager,
        dispatcher: Callable[[dict[str, Any]], Awaitable[None]] = dispatch_task,
        *,
        poll_seconds: float = 1.0,
        lease_seconds: int = 120,
        retry_delay_seconds: int = 5,
        worker_id: str | None = None,
    ) -> None:
        self.manager = manager
        self.dispatcher = dispatcher
        self.poll_seconds = poll_seconds
        self.lease_seconds = lease_seconds
        self.retry_delay_seconds = retry_delay_seconds
        self.worker_id = worker_id or (
            f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:8]}"
        )
        self._stop_event = asyncio.Event()
        self._runner: asyncio.Task[None] | None = None

    async def start(self) -> None:
        """启动轮询；重复调用不会创建第二个 runner。"""
        if self._runner is not None and not self._runner.done():
            return
        self._stop_event.clear()
        self._runner = asyncio.create_task(
            self._run_loop(),
            name=f"persistent-task-worker:{self.worker_id}",
        )

    async def stop(self) -> None:
        """停止领取并取消当前执行；取消不转换为业务失败。"""
        runner = self._runner
        if runner is None:
            return

        self._stop_event.set()
        if not runner.done():
            runner.cancel()
        with suppress(asyncio.CancelledError):
            await runner
        if self._runner is runner:
            self._runner = None

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                claim = await self.manager.claim_next_task(
                    self.worker_id,
                    self.lease_seconds,
                )
                if self._stop_event.is_set():
                    return
                if claim is None:
                    await self._wait_for_poll()
                    continue
                await self._run_claim(claim)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "persistent_task_worker_iteration_failed",
                    worker_id=self.worker_id,
                )
                await self._wait_for_poll()

    async def _wait_for_poll(self) -> None:
        try:
            await asyncio.wait_for(
                self._stop_event.wait(),
                timeout=self.poll_seconds,
            )
        except TimeoutError:
            pass

    async def _run_claim(self, claim: dict[str, Any]) -> None:
        task_id = str(claim["task_id"])
        # B1: worker_id 注入 claim dict，供 dispatcher → generate_* → advance_checkpoint
        # 全链路 lease 守卫使用。业务层据此在安全边界复查 lease 所有权。
        claim["worker_id"] = self.worker_id
        dispatch = asyncio.create_task(
            self.dispatcher(claim),
            name=f"task-dispatch:{task_id}",
        )
        heartbeat = asyncio.create_task(
            self._heartbeat(task_id),
            name=f"task-heartbeat:{task_id}",
        )
        try:
            done, _ = await asyncio.wait(
                {dispatch, heartbeat},
                return_when=asyncio.FIRST_COMPLETED,
            )
            if heartbeat in done and not dispatch.done():
                try:
                    heartbeat.result()
                except Exception:
                    logger.exception(
                        "persistent_task_heartbeat_failed",
                        task_id=task_id,
                        worker_id=self.worker_id,
                    )
                dispatch.cancel()
                with suppress(asyncio.CancelledError):
                    await dispatch
                return

            try:
                await dispatch
            except asyncio.CancelledError:
                raise
            except (LeaseLost, PausedExit) as clean_exit:
                # B7/B12: lease 丢失或协作式暂停——worker 干净退出，
                # 不调 release_claim / retry_or_fail_claim。
                # lease 已归属新 worker（LeaseLost）或任务已置 paused（PausedExit），
                # 由新 worker / resume 接管。
                logger.info(
                    "task_dispatch_clean_exit",
                    task_id=task_id,
                    worker_id=self.worker_id,
                    reason=type(clean_exit).__name__,
                )
                return
            except Exception as exc:
                error = f"{type(exc).__name__}: {exc}"
                logger.exception(
                    "persistent_task_dispatch_failed",
                    task_id=task_id,
                    task_type=claim.get("task_type"),
                    error=error,
                )
                await self.manager.retry_or_fail_claim(
                    task_id,
                    self.worker_id,
                    error,
                    self.retry_delay_seconds,
                )
            else:
                await self.manager.release_claim(task_id, self.worker_id)
        finally:
            dispatch.cancel()
            heartbeat.cancel()
            for child in (dispatch, heartbeat):
                with suppress(asyncio.CancelledError, Exception):
                    await child

    async def _heartbeat(self, task_id: str) -> None:
        interval = max(0.001, min(self.poll_seconds, self.lease_seconds / 4))
        while True:
            await asyncio.sleep(interval)
            renewed = await self.manager.renew_lease(
                task_id,
                self.worker_id,
                self.lease_seconds,
            )
            if not renewed:
                logger.warning(
                    "persistent_task_lease_lost",
                    task_id=task_id,
                    worker_id=self.worker_id,
                )
                return


_task_worker: PersistentTaskWorker | None = None


def get_task_worker() -> PersistentTaskWorker:
    """按应用配置创建并复用当前进程的 worker。"""
    global _task_worker
    if _task_worker is None:
        settings = get_settings()
        _task_worker = PersistentTaskWorker(
            get_task_manager(),
            poll_seconds=settings.TASK_QUEUE_POLL_SECONDS,
            lease_seconds=settings.TASK_QUEUE_LEASE_SECONDS,
            retry_delay_seconds=settings.TASK_QUEUE_RETRY_DELAY_SECONDS,
        )
    return _task_worker
