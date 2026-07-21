"""持久化任务 worker 的轮询、心跳和停机语义测试。"""

import asyncio
import os
import socket
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _manager(**overrides):
    defaults = {
        "claim_next_task": AsyncMock(return_value=None),
        "renew_lease": AsyncMock(return_value=True),
        "release_claim": AsyncMock(return_value=True),
        "retry_or_fail_claim": AsyncMock(return_value=False),
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _claim() -> dict[str, object]:
    return {
        "task_id": "task-1",
        "task_type": "novel.generate",
        "task_payload": {"request": {}},
        "attempt_count": 1,
        "max_attempts": 1,
    }


def test_default_worker_id_contains_host_pid_and_unique_suffix():
    from src.api.services.tasks.task_worker import PersistentTaskWorker

    worker = PersistentTaskWorker(_manager(), AsyncMock())

    prefix = f"{socket.gethostname()}:{os.getpid()}:"
    assert worker.worker_id.startswith(prefix)
    assert len(worker.worker_id.removeprefix(prefix)) == 8


def test_task_queue_settings_have_safe_defaults():
    from src.core.config import Settings

    settings = Settings(DEEPSEEK_API_KEY="test-key", _env_file=None)

    assert settings.TASK_QUEUE_ENABLED is True
    assert settings.TASK_QUEUE_POLL_SECONDS == 1.0
    assert settings.TASK_QUEUE_LEASE_SECONDS == 120
    assert settings.TASK_QUEUE_RETRY_DELAY_SECONDS == 5
    assert settings.LONG_FORM_MAX_ATTEMPTS == 3


def test_get_task_worker_builds_singleton_from_settings(monkeypatch):
    import src.api.services.tasks.task_worker as task_worker_module

    manager = _manager()
    settings = SimpleNamespace(
        TASK_QUEUE_POLL_SECONDS=2.5,
        TASK_QUEUE_LEASE_SECONDS=90,
        TASK_QUEUE_RETRY_DELAY_SECONDS=11,
    )
    monkeypatch.setattr(task_worker_module, "get_settings", lambda: settings)
    monkeypatch.setattr(task_worker_module, "get_task_manager", lambda: manager)
    monkeypatch.setattr(task_worker_module, "_task_worker", None)

    worker = task_worker_module.get_task_worker()

    assert worker is task_worker_module.get_task_worker()
    assert worker.manager is manager
    assert worker.poll_seconds == 2.5
    assert worker.lease_seconds == 90
    assert worker.retry_delay_seconds == 11


@pytest.mark.asyncio
async def test_no_claim_waits_then_polls_again():
    from src.api.services.tasks.task_worker import PersistentTaskWorker

    polled_twice = asyncio.Event()
    poll_count = 0

    async def claim_next(*_args):
        nonlocal poll_count
        poll_count += 1
        if poll_count >= 2:
            polled_twice.set()
        return None

    manager = _manager(claim_next_task=AsyncMock(side_effect=claim_next))
    worker = PersistentTaskWorker(
        manager,
        AsyncMock(),
        poll_seconds=0.001,
        worker_id="worker-test",
    )

    await worker.start()
    await asyncio.wait_for(polled_twice.wait(), timeout=0.2)
    await worker.stop()

    assert manager.claim_next_task.await_count >= 2


@pytest.mark.asyncio
async def test_claim_error_waits_then_continues_polling():
    from src.api.services.tasks.task_worker import PersistentTaskWorker

    recovered_poll = asyncio.Event()
    poll_count = 0

    async def claim_next(*_args):
        nonlocal poll_count
        poll_count += 1
        if poll_count == 1:
            raise RuntimeError("database unavailable")
        recovered_poll.set()
        return None

    manager = _manager(claim_next_task=AsyncMock(side_effect=claim_next))
    worker = PersistentTaskWorker(
        manager,
        AsyncMock(),
        poll_seconds=0.001,
        worker_id="worker-test",
    )

    await worker.start()
    try:
        await asyncio.wait_for(recovered_poll.wait(), timeout=0.2)
    finally:
        await worker.stop()

    assert manager.claim_next_task.await_count >= 2


@pytest.mark.asyncio
async def test_claimed_task_dispatches_once_and_releases_claim():
    from src.api.services.tasks.task_worker import PersistentTaskWorker

    manager = _manager()
    dispatcher = AsyncMock()
    worker = PersistentTaskWorker(
        manager,
        dispatcher,
        poll_seconds=0.001,
        worker_id="worker-test",
    )
    claim = _claim()

    await worker._run_claim(claim)

    dispatcher.assert_awaited_once_with(claim)
    manager.release_claim.assert_awaited_once_with("task-1", "worker-test")
    manager.retry_or_fail_claim.assert_not_awaited()


@pytest.mark.asyncio
async def test_long_task_renews_lease_while_dispatcher_is_running():
    from src.api.services.tasks.task_worker import PersistentTaskWorker

    dispatcher_started = asyncio.Event()
    finish_dispatch = asyncio.Event()
    lease_renewed = asyncio.Event()

    async def dispatch(_claim):
        dispatcher_started.set()
        await finish_dispatch.wait()

    async def renew_lease(*_args):
        lease_renewed.set()
        return True

    manager = _manager(renew_lease=AsyncMock(side_effect=renew_lease))
    worker = PersistentTaskWorker(
        manager,
        dispatch,
        poll_seconds=0.001,
        lease_seconds=1,
        worker_id="worker-test",
    )

    execution = asyncio.create_task(worker._run_claim(_claim()))
    await asyncio.wait_for(dispatcher_started.wait(), timeout=0.2)
    await asyncio.wait_for(lease_renewed.wait(), timeout=0.2)
    finish_dispatch.set()
    await execution

    manager.renew_lease.assert_awaited_with("task-1", "worker-test", 1)


@pytest.mark.asyncio
@pytest.mark.parametrize("renew_result", [False, RuntimeError("renew failed")])
async def test_lease_loss_cancels_dispatcher_without_releasing_claim(renew_result):
    from src.api.services.tasks.task_worker import PersistentTaskWorker

    dispatcher_started = asyncio.Event()
    dispatcher_cancelled = asyncio.Event()

    async def dispatch(_claim):
        dispatcher_started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            dispatcher_cancelled.set()
            raise

    async def renew_lease(*_args):
        if isinstance(renew_result, Exception):
            raise renew_result
        return renew_result

    manager = _manager(renew_lease=AsyncMock(side_effect=renew_lease))
    worker = PersistentTaskWorker(
        manager,
        dispatch,
        poll_seconds=0.001,
        lease_seconds=1,
        worker_id="worker-test",
    )

    execution = asyncio.create_task(worker._run_claim(_claim()))
    try:
        await asyncio.wait_for(dispatcher_started.wait(), timeout=0.2)
        await asyncio.wait_for(dispatcher_cancelled.wait(), timeout=0.2)
        await asyncio.wait_for(execution, timeout=0.2)
    finally:
        if not execution.done():
            execution.cancel()
            try:
                await execution
            except (asyncio.CancelledError, RuntimeError):
                pass

    manager.release_claim.assert_not_awaited()
    manager.retry_or_fail_claim.assert_not_awaited()


@pytest.mark.asyncio
async def test_dispatcher_exception_retries_or_fails_claim():
    from src.api.services.tasks.task_worker import PersistentTaskWorker

    manager = _manager()
    dispatcher = AsyncMock(side_effect=RuntimeError("boom"))
    worker = PersistentTaskWorker(
        manager,
        dispatcher,
        retry_delay_seconds=7,
        worker_id="worker-test",
    )

    await worker._run_claim(_claim())

    manager.retry_or_fail_claim.assert_awaited_once_with(
        "task-1",
        "worker-test",
        "RuntimeError: boom",
        7,
    )
    manager.release_claim.assert_not_awaited()


@pytest.mark.asyncio
async def test_shutdown_cancellation_does_not_release_or_fail_claim():
    from src.api.services.tasks.task_worker import PersistentTaskWorker

    dispatcher_started = asyncio.Event()

    async def dispatch(_claim):
        dispatcher_started.set()
        await asyncio.Event().wait()

    manager = _manager(
        claim_next_task=AsyncMock(side_effect=[_claim(), None]),
    )
    worker = PersistentTaskWorker(
        manager,
        dispatch,
        poll_seconds=0.001,
        worker_id="worker-test",
    )

    await worker.start()
    await asyncio.wait_for(dispatcher_started.wait(), timeout=0.2)
    await worker.stop()

    manager.release_claim.assert_not_awaited()
    manager.retry_or_fail_claim.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_and_stop_are_idempotent():
    from src.api.services.tasks.task_worker import PersistentTaskWorker

    claim_started = asyncio.Event()

    async def blocked_claim(*_args):
        claim_started.set()
        await asyncio.Event().wait()

    manager = _manager(claim_next_task=AsyncMock(side_effect=blocked_claim))
    worker = PersistentTaskWorker(
        manager,
        AsyncMock(),
        worker_id="worker-test",
    )

    await worker.start()
    await worker.start()
    await asyncio.wait_for(claim_started.wait(), timeout=0.2)
    assert manager.claim_next_task.await_count == 1

    await worker.stop()
    await worker.stop()


@pytest.mark.asyncio
async def test_stop_prevents_later_claims():
    from src.api.services.tasks.task_worker import PersistentTaskWorker

    first_poll = asyncio.Event()

    async def claim_next(*_args):
        first_poll.set()
        return None

    manager = _manager(claim_next_task=AsyncMock(side_effect=claim_next))
    worker = PersistentTaskWorker(
        manager,
        AsyncMock(),
        poll_seconds=0.001,
        worker_id="worker-test",
    )

    await worker.start()
    await asyncio.wait_for(first_poll.wait(), timeout=0.2)
    await worker.stop()
    calls_after_stop = manager.claim_next_task.await_count
    await asyncio.sleep(0.01)

    assert manager.claim_next_task.await_count == calls_after_stop


@pytest.mark.asyncio
async def test_start_task_queue_recovers_before_starting_worker(monkeypatch):
    import src.api.main as main_module
    from src.api.services.tasks.task_manager import RecoverySummary

    events: list[str] = []

    async def recover():
        events.append("recover")
        return RecoverySummary(queued_preserved=2, stale_failed=1)

    async def start():
        events.append("start")

    manager = SimpleNamespace(recover_interrupted_tasks=AsyncMock(side_effect=recover))
    worker = SimpleNamespace(
        worker_id="worker-test",
        start=AsyncMock(side_effect=start),
    )
    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(TASK_QUEUE_ENABLED=True),
    )
    monkeypatch.setattr(main_module, "get_task_manager", lambda: manager)
    monkeypatch.setattr(main_module, "get_task_worker", lambda: worker)

    started = await main_module.start_task_queue()

    assert started is worker
    assert events == ["recover", "start"]


@pytest.mark.asyncio
async def test_start_task_queue_does_nothing_when_disabled(monkeypatch):
    import src.api.main as main_module

    get_manager = AsyncMock()
    get_worker = AsyncMock()
    monkeypatch.setattr(
        main_module,
        "settings",
        SimpleNamespace(TASK_QUEUE_ENABLED=False),
    )
    monkeypatch.setattr(main_module, "get_task_manager", get_manager)
    monkeypatch.setattr(main_module, "get_task_worker", get_worker)

    started = await main_module.start_task_queue()

    assert started is None
    get_manager.assert_not_called()
    get_worker.assert_not_called()


@pytest.mark.asyncio
async def test_shutdown_stops_worker_before_checkpointer_and_database(monkeypatch):
    import src.api.main as main_module

    events: list[str] = []

    async def record(name: str):
        events.append(name)

    async def stop_worker():
        await record("worker")

    async def teardown_checkpointer():
        await record("checkpointer")

    async def close_database():
        await record("database")

    worker = SimpleNamespace(stop=AsyncMock(side_effect=stop_worker))
    monkeypatch.setattr(
        main_module,
        "teardown_persistent_checkpointer",
        AsyncMock(side_effect=teardown_checkpointer),
    )
    monkeypatch.setattr(
        main_module,
        "close_db",
        AsyncMock(side_effect=close_database),
    )

    await main_module.shutdown_application_services(worker)

    assert events == ["worker", "checkpointer", "database"]


@pytest.mark.asyncio
async def test_shutdown_closes_resources_when_worker_stop_fails(monkeypatch):
    import src.api.main as main_module

    events: list[str] = []

    async def stop_worker():
        events.append("worker")
        raise RuntimeError("worker crashed")

    async def teardown_checkpointer():
        events.append("checkpointer")

    async def close_database():
        events.append("database")

    worker = SimpleNamespace(stop=AsyncMock(side_effect=stop_worker))
    monkeypatch.setattr(
        main_module,
        "teardown_persistent_checkpointer",
        AsyncMock(side_effect=teardown_checkpointer),
    )
    monkeypatch.setattr(
        main_module,
        "close_db",
        AsyncMock(side_effect=close_database),
    )

    with pytest.raises(RuntimeError, match="worker crashed"):
        await main_module.shutdown_application_services(worker)

    assert events == ["worker", "checkpointer", "database"]


@pytest.mark.asyncio
async def test_lifespan_cleans_initialized_resources_when_late_startup_fails(
    monkeypatch,
):
    import src.api.main as main_module
    import src.api.services.agent_journal_service as journal_module

    events: list[str] = []

    async def init_database():
        events.append("database_init")

    async def setup_checkpointer():
        events.append("checkpointer_setup")

    async def teardown_checkpointer():
        events.append("checkpointer_teardown")

    async def close_database():
        events.append("database_close")

    def fail_journal_init():
        raise RuntimeError("journal init failed")

    monkeypatch.setattr(main_module, "validate_encryption_key", lambda: None)
    monkeypatch.setattr(main_module, "validate_admin_token", lambda: None)
    monkeypatch.setattr(main_module, "init_db", AsyncMock(side_effect=init_database))
    monkeypatch.setattr(
        main_module,
        "setup_persistent_checkpointer",
        AsyncMock(side_effect=setup_checkpointer),
    )
    monkeypatch.setattr(
        main_module,
        "teardown_persistent_checkpointer",
        AsyncMock(side_effect=teardown_checkpointer),
    )
    monkeypatch.setattr(
        main_module,
        "close_db",
        AsyncMock(side_effect=close_database),
    )
    monkeypatch.setattr(
        journal_module,
        "get_journal_service",
        fail_journal_init,
    )

    with pytest.raises(RuntimeError, match="journal init failed"):
        async with main_module.lifespan(SimpleNamespace()):
            pass

    assert events == [
        "database_init",
        "checkpointer_setup",
        "checkpointer_teardown",
        "database_close",
    ]


@pytest.mark.asyncio
async def test_lifespan_closes_database_when_checkpointer_setup_fails(monkeypatch):
    import src.api.main as main_module

    events: list[str] = []

    async def init_database():
        events.append("database_init")

    async def fail_checkpointer_setup():
        events.append("checkpointer_setup")
        raise RuntimeError("checkpointer init failed")

    async def teardown_checkpointer():
        events.append("checkpointer_teardown")

    async def close_database():
        events.append("database_close")

    monkeypatch.setattr(main_module, "validate_encryption_key", lambda: None)
    monkeypatch.setattr(main_module, "validate_admin_token", lambda: None)
    monkeypatch.setattr(main_module, "init_db", AsyncMock(side_effect=init_database))
    monkeypatch.setattr(
        main_module,
        "setup_persistent_checkpointer",
        AsyncMock(side_effect=fail_checkpointer_setup),
    )
    teardown = AsyncMock(side_effect=teardown_checkpointer)
    monkeypatch.setattr(main_module, "teardown_persistent_checkpointer", teardown)
    monkeypatch.setattr(
        main_module,
        "close_db",
        AsyncMock(side_effect=close_database),
    )

    with pytest.raises(RuntimeError, match="checkpointer init failed"):
        async with main_module.lifespan(SimpleNamespace()):
            pass

    assert events == ["database_init", "checkpointer_setup", "database_close"]
    teardown.assert_not_awaited()


@pytest.mark.asyncio
async def test_lease_lost_dispatcher_clean_exit_skips_release_and_retry():
    """B7/B12: dispatch 抛 LeaseLost 时 _run_claim 不调 release/retry，干净退出。"""
    from src.api.services.tasks.task_worker import PersistentTaskWorker
    from src.core.exceptions import LeaseLost

    async def dispatch(_claim):
        raise LeaseLost("task-1")

    manager = _manager()
    worker = PersistentTaskWorker(
        manager, dispatch, worker_id="worker-test", lease_seconds=1
    )

    await worker._run_claim(_claim())

    manager.release_claim.assert_not_awaited()
    manager.retry_or_fail_claim.assert_not_awaited()


@pytest.mark.asyncio
async def test_paused_exit_dispatcher_clean_exit_skips_release_and_retry():
    """PausedExit（worker 协作式暂停）与 LeaseLost 同样跳过 release/retry。"""
    from src.api.services.tasks.task_worker import PersistentTaskWorker
    from src.core.exceptions import PausedExit

    async def dispatch(_claim):
        raise PausedExit("task-1")

    manager = _manager()
    worker = PersistentTaskWorker(
        manager, dispatch, worker_id="worker-test", lease_seconds=1
    )

    await worker._run_claim(_claim())

    manager.release_claim.assert_not_awaited()
    manager.retry_or_fail_claim.assert_not_awaited()
