"""Task 8：_emit_progress 失败不阻断 + complete_task 真实 percentage。

设计依据：docs/superpowers/specs/2026-07-20-long-form-stability-design.md §八
- R7：进度事件失败不判失败——_emit_progress 包 try/except，失败仅 log，不抛。
- B8：调用方传入由 CheckpointStore 原子分配的 sequence。
- R9：complete_task 非 completed 状态写真实 percentage，不强制 100。
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# _emit_progress 失败不阻断
# ---------------------------------------------------------------------------


class TestEmitProgressResilience:
    @pytest.mark.asyncio
    async def test_publish_exception_is_swallowed(self):
        """event_bus.publish 抛异常时 _emit_progress 不向上抛，章节流程可继续。"""
        from src.api.services.generation.chapter_generation_utils import _emit_progress
        from src.api.services.generation.progress_event_bus import EventType

        bus = MagicMock()
        bus.publish = AsyncMock(side_effect=RuntimeError("redis down"))

        with patch(
            "src.api.services.generation.chapter_generation_utils.get_event_bus",
            return_value=bus,
        ):
            # 不抛即通过
            await _emit_progress(
                "task-1", EventType.CHAPTER_PROGRESS, {"percentage": 10}
            )

        bus.publish.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_status_exception_is_swallowed(self):
        """update_status 抛异常时也不向上抛。"""
        from src.api.services.generation.chapter_generation_utils import _emit_progress
        from src.api.services.generation.progress_event_bus import EventType

        bus = MagicMock()
        bus.publish = AsyncMock()
        tm = MagicMock()
        tm.update_status = AsyncMock(side_effect=RuntimeError("db down"))

        with (
            patch(
                "src.api.services.generation.chapter_generation_utils.get_event_bus",
                return_value=bus,
            ),
            patch(
                "src.api.services.generation.chapter_generation_utils.get_task_manager",
                return_value=tm,
            ),
        ):
            await _emit_progress(
                "task-1",
                EventType.CHAPTER_PROGRESS,
                {"percentage": 10},
                update_status=True,
            )

    @pytest.mark.asyncio
    async def test_caller_allocated_sequence_is_published(self):
        """发布调用方已原子分配的 sequence，不在发布层重复读取检查点。"""
        from src.api.services.generation.chapter_generation_utils import _emit_progress
        from src.api.services.generation.progress_event_bus import EventType

        bus = MagicMock()
        bus.publish = AsyncMock()
        with patch(
            "src.api.services.generation.chapter_generation_utils.get_event_bus",
            return_value=bus,
        ):
            await _emit_progress(
                "task-1",
                EventType.CHAPTER_PROGRESS,
                {"percentage": 50},
                sequence=8,
            )

        published = bus.publish.await_args.args[0]
        assert published.data["sequence"] == 8
        assert published.data["percentage"] == 50

    @pytest.mark.asyncio
    async def test_no_checkpoint_still_publishes_without_sequence(self):
        """无 checkpoint（短篇）时正常 publish，不强制 sequence。"""
        from src.api.services.generation.chapter_generation_utils import _emit_progress
        from src.api.services.generation.progress_event_bus import EventType

        bus = MagicMock()
        bus.publish = AsyncMock()
        with patch(
            "src.api.services.generation.chapter_generation_utils.get_event_bus",
            return_value=bus,
        ):
            await _emit_progress(
                "task-1", EventType.CHAPTER_PROGRESS, {"percentage": 20}
            )

        published = bus.publish.await_args.args[0]
        assert "sequence" not in published.data
        assert published.data["percentage"] == 20


# ---------------------------------------------------------------------------
# complete_task 真实 percentage
# ---------------------------------------------------------------------------


class TestCompleteTaskRealPercentage:
    def _manager_with_task(self, task_mock):
        from src.api.services.tasks.task_manager import TaskManager

        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)
        session.commit = AsyncMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = task_mock
        session.execute = AsyncMock(return_value=result)
        return TaskManager(), session

    @pytest.mark.asyncio
    async def test_partially_completed_writes_real_percentage(self):
        """status='partially_completed' 时 percentage 取 result.completion_percentage，不强制 100。"""
        task_mock = MagicMock()
        task_mock.lease_owner = None
        task_mock.lease_expires_at = None
        task_mock.queue_state = None
        task_mock.status = "running"

        manager, session = self._manager_with_task(task_mock)
        with patch(
            "src.api.services.tasks.task_manager.get_db_session",
            return_value=session,
        ):
            await manager.complete_task(
                "task-1",
                {
                    "chapters": [{"id": 1}, {"id": 2}],
                    "completion_percentage": 67,
                    "current_stage": "partially_completed",
                },
                status="partially_completed",
            )

        assert task_mock.progress["percentage"] == 67
        assert task_mock.status == "partially_completed"

    @pytest.mark.asyncio
    async def test_completed_still_writes_100(self):
        """status='completed' 时 percentage 仍为 100。"""
        task_mock = MagicMock()
        task_mock.lease_owner = None
        task_mock.lease_expires_at = None
        task_mock.queue_state = None
        task_mock.status = "running"

        manager, session = self._manager_with_task(task_mock)
        with patch(
            "src.api.services.tasks.task_manager.get_db_session",
            return_value=session,
        ):
            await manager.complete_task(
                "task-1",
                {"chapters": [{"id": 1}], "completion_percentage": 80},
                status="completed",
            )

        assert task_mock.progress["percentage"] == 100

    @pytest.mark.asyncio
    async def test_partially_completed_defaults_to_0_without_percentage(self):
        """partially_completed 且未传 completion_percentage 时默认 0（不伪造 100）。"""
        task_mock = MagicMock()
        task_mock.lease_owner = None
        task_mock.lease_expires_at = None
        task_mock.queue_state = None
        task_mock.status = "running"

        manager, session = self._manager_with_task(task_mock)
        with patch(
            "src.api.services.tasks.task_manager.get_db_session",
            return_value=session,
        ):
            await manager.complete_task(
                "task-1",
                {"chapters": [{"id": 1}]},
                status="partially_completed",
            )

        assert task_mock.progress["percentage"] == 0
