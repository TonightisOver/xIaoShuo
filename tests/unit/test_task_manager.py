"""TaskManager 单元测试 - 覆盖任务生命周期管理

覆盖范围:
- create_task: 创建任务，生成 task_id 格式并提交
- get_task: 获取任务详情，存在/不存在分支
- update_status: 更新状态；running 时设置 started_at/estimated_completion；
  progress 合并；任务不存在时静默返回
- complete_task: 完成任务，设置 status/completed_at/result/progress，
  progress 中根据 chapters 计算章节计数与百分比
- fail_task: 任务失败，追加 error 到 errors 列表
- list_tasks: 列出任务，返回 (列表, 总数)；status 过滤分支

依赖说明:
TaskManager 仅依赖 get_db_session（async context manager），无 LLM、无其他
service 单例依赖，因此全部用 mock 纯单元测试，无需跳过任何方法。
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.tasks.task_manager import TaskManager


def _make_session():
    """构造一个 mock async db session（async context manager）。

    返回 (session, result_factory) 其中 result_factory 可被设置以控制 execute
    的返回值。session.execute 为 AsyncMock，便于配置 side_effect/return_value。
    """
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.add = MagicMock()  # add 是同步方法
    session.commit = AsyncMock()
    return session


def _patch_db(session):
    """返回 patch 上下文，将源模块的 get_db_session 替换为返回 session 的 mock。"""
    mock_db = MagicMock()
    mock_db.return_value = session
    return patch("src.api.services.tasks.task_manager.get_db_session", mock_db)


def _make_task_mock(**overrides):
    """构造一个具有 Task 全部属性的 mock 对象，含 to_dict。"""
    task = MagicMock()
    task.task_id = overrides.get("task_id", "novel-1")
    task.novel_id = overrides.get("novel_id", None)
    task.owner_id = overrides.get("owner_id", None)
    task.status = overrides.get("status", "pending")
    task.idea = overrides.get("idea", "an idea")
    task.novel_type = overrides.get("novel_type", "都市")
    task.target_words = overrides.get("target_words", 5000)
    task.created_at = overrides.get("created_at", datetime(2026, 1, 1))
    task.started_at = overrides.get("started_at", None)
    task.completed_at = overrides.get("completed_at", None)
    task.estimated_completion = overrides.get("estimated_completion", None)
    task.progress = overrides.get("progress", None)
    task.result = overrides.get("result", None)
    task.errors = overrides.get("errors", [])
    task.task_type = overrides.get("task_type", None)
    task.task_payload = overrides.get("task_payload", None)
    task.queue_state = overrides.get("queue_state", None)
    task.attempt_count = overrides.get("attempt_count", 0)
    task.max_attempts = overrides.get("max_attempts", 1)
    task.available_at = overrides.get("available_at", None)
    task.lease_owner = overrides.get("lease_owner", None)
    task.lease_expires_at = overrides.get("lease_expires_at", None)
    task.heartbeat_at = overrides.get("heartbeat_at", None)

    def to_dict():
        return {
            "task_id": task.task_id,
            "novel_id": task.novel_id,
            "owner_id": task.owner_id,
            "status": task.status,
            "idea": task.idea,
            "novel_type": task.novel_type,
            "target_words": task.target_words,
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "estimated_completion": task.estimated_completion,
            "progress": task.progress,
            "result": task.result,
            "errors": task.errors or [],
        }

    task.to_dict.side_effect = to_dict
    return task


@pytest.fixture
def manager():
    return TaskManager()


class TestCreateTask:
    @pytest.mark.asyncio
    async def test_creates_task_and_returns_id_with_prefix(self, manager):
        session = _make_session()
        with _patch_db(session):
            task_id = await manager.create_task(
                idea="一个故事", novel_type="玄幻", target_words=10000
            )
        assert task_id.startswith("novel-")
        # session.add 被调用一次（传入 Task 实例）
        assert session.add.call_count == 1
        added = session.add.call_args[0][0]
        assert added.task_id == task_id
        assert added.status == "pending"
        assert added.idea == "一个故事"
        assert added.novel_type == "玄幻"
        assert added.target_words == 10000
        assert added.errors == []
        assert added.started_at is None
        assert added.completed_at is None
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_task_id_format_is_unique_with_timestamp_and_hex(self, manager):
        session = _make_session()
        with _patch_db(session):
            id1 = await manager.create_task("a", "x", 1)
            id2 = await manager.create_task("a", "x", 1)
        # 两个 id 不同（uuid hex 段随机）
        assert id1 != id2
        # 格式: novel-{14位时间戳}-{8位hex}
        parts1 = id1.split("-")
        assert len(parts1) == 3  # novel / timestamp / hex
        assert parts1[0] == "novel"
        assert len(parts1[1]) == 14  # %Y%m%d%H%M%S
        assert len(parts1[2]) == 8  # uuid4().hex[:8]

    @pytest.mark.asyncio
    async def test_create_task_with_novel_id_propagated(self, manager):
        session = _make_session()
        with _patch_db(session):
            task_id = await manager.create_task(
                idea="idea", novel_type="科幻", target_words=3000,
                novel_id="novel-abc",
            )
        added = session.add.call_args[0][0]
        assert added.novel_id == "novel-abc"

    @pytest.mark.asyncio
    async def test_create_task_persists_owner_id(self, manager):
        session = _make_session()
        with _patch_db(session):
            await manager.create_task(
                idea="idea",
                novel_type="科幻",
                target_words=3000,
                owner_id=7,
            )

        added = session.add.call_args[0][0]
        assert added.owner_id == 7


class TestGetTask:
    @pytest.mark.asyncio
    async def test_returns_dict_when_task_exists(self, manager):
        session = _make_session()
        task_mock = _make_task_mock(
            task_id="novel-1", status="running", target_words=8000,
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = task_mock
        session.execute = AsyncMock(return_value=result)
        with _patch_db(session):
            data = await manager.get_task("novel-1")
        assert data is not None
        assert data["task_id"] == "novel-1"
        assert data["status"] == "running"
        assert data["target_words"] == 8000

    @pytest.mark.asyncio
    async def test_returns_none_when_task_not_found(self, manager):
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)
        with _patch_db(session):
            data = await manager.get_task("does-not-exist")
        assert data is None


class TestUpdateStatus:
    @pytest.mark.asyncio
    async def test_running_status_sets_started_at_and_estimated_completion(
        self, manager
    ):
        session = _make_session()
        task_mock = _make_task_mock(
            task_id="novel-1", status="pending", started_at=None
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = task_mock
        session.execute = AsyncMock(return_value=result)
        before = datetime.now()
        with _patch_db(session):
            await manager.update_status("novel-1", "running")
        assert task_mock.status == "running"
        assert task_mock.started_at is not None
        assert task_mock.started_at >= before
        assert task_mock.estimated_completion is not None
        # estimated_completion 约为 started_at + 70 分钟
        diff = task_mock.estimated_completion - task_mock.started_at
        assert timedelta(minutes=69) <= diff <= timedelta(minutes=71)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_running_does_not_overwrite_existing_started_at(self, manager):
        session = _make_session()
        original_started = datetime(2025, 1, 1, 12, 0, 0)
        task_mock = _make_task_mock(
            task_id="novel-1", status="pending", started_at=original_started
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = task_mock
        session.execute = AsyncMock(return_value=result)
        with _patch_db(session):
            await manager.update_status("novel-1", "running")
        # 已存在 started_at，不应被覆盖
        assert task_mock.started_at == original_started
        assert task_mock.estimated_completion is None

    @pytest.mark.asyncio
    async def test_non_running_status_does_not_set_started_at(self, manager):
        session = _make_session()
        task_mock = _make_task_mock(
            task_id="novel-1", status="running", started_at=None
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = task_mock
        session.execute = AsyncMock(return_value=result)
        with _patch_db(session):
            await manager.update_status("novel-1", "completed")
        assert task_mock.status == "completed"
        assert task_mock.started_at is None
        assert task_mock.estimated_completion is None

    @pytest.mark.asyncio
    async def test_progress_is_merged_when_provided(self, manager):
        session = _make_session()
        task_mock = _make_task_mock(task_id="novel-1", progress=None)
        result = MagicMock()
        result.scalar_one_or_none.return_value = task_mock
        session.execute = AsyncMock(return_value=result)
        progress = {"current_stage": "drafting", "percentage": 42}
        with _patch_db(session):
            await manager.update_status("novel-1", "running", progress=progress)
        assert task_mock.progress == progress

    @pytest.mark.asyncio
    async def test_progress_not_overwritten_when_not_provided(self, manager):
        session = _make_session()
        existing = {"current_stage": "outline"}
        task_mock = _make_task_mock(task_id="novel-1", progress=existing)
        result = MagicMock()
        result.scalar_one_or_none.return_value = task_mock
        session.execute = AsyncMock(return_value=result)
        with _patch_db(session):
            await manager.update_status("novel-1", "running")
        # 未传 progress，progress 保持原值
        assert task_mock.progress == existing

    @pytest.mark.asyncio
    async def test_update_status_silent_when_task_not_found(self, manager):
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)
        with _patch_db(session):
            # 应直接返回，不抛异常
            ret = await manager.update_status("missing", "running")
        assert ret is None
        # 未提交
        session.commit.assert_not_awaited()


class TestCompleteTask:
    @pytest.mark.asyncio
    async def test_sets_completed_fields_and_progress(self, manager):
        session = _make_session()
        task_mock = _make_task_mock(task_id="novel-1", status="running")
        result = MagicMock()
        result.scalar_one_or_none.return_value = task_mock
        session.execute = AsyncMock(return_value=result)
        before = datetime.now()
        payload = {
            "current_stage": "done",
            "chapters": [{"id": 1}, {"id": 2}, {"id": 3}],
        }
        with _patch_db(session):
            await manager.complete_task("novel-1", payload)
        assert task_mock.status == "completed"
        assert task_mock.completed_at is not None
        assert task_mock.completed_at >= before
        assert task_mock.result == payload
        assert task_mock.progress == {
            "current_stage": "done",
            "completed_chapters": 3,
            "total_chapters": 3,
            "percentage": 100,
        }
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_progress_defaults_when_chapters_missing(self, manager):
        session = _make_session()
        task_mock = _make_task_mock(task_id="novel-1")
        result = MagicMock()
        result.scalar_one_or_none.return_value = task_mock
        session.execute = AsyncMock(return_value=result)
        with _patch_db(session):
            # result 中无 current_stage / chapters
            await manager.complete_task("novel-1", {"other": 1})
        assert task_mock.progress == {
            "current_stage": "completed",
            "completed_chapters": 0,
            "total_chapters": 0,
            "percentage": 100,
        }

    @pytest.mark.asyncio
    async def test_complete_silent_when_task_not_found(self, manager):
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)
        with _patch_db(session):
            ret = await manager.complete_task("missing", {"chapters": []})
        assert ret is None
        session.commit.assert_not_awaited()


class TestFailTask:
    @pytest.mark.asyncio
    async def test_appends_error_and_marks_failed(self, manager):
        session = _make_session()
        task_mock = _make_task_mock(
            task_id="novel-1", status="running", errors=["prev error"]
        )
        result = MagicMock()
        result.scalar_one_or_none.return_value = task_mock
        session.execute = AsyncMock(return_value=result)
        before = datetime.now()
        with _patch_db(session):
            await manager.fail_task("novel-1", "LLM 超时")
        assert task_mock.status == "failed"
        assert task_mock.completed_at is not None
        assert task_mock.completed_at >= before
        assert task_mock.errors == ["prev error", "LLM 超时"]
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_fail_initializes_errors_when_none(self, manager):
        session = _make_session()
        task_mock = _make_task_mock(task_id="novel-1", errors=None)
        result = MagicMock()
        result.scalar_one_or_none.return_value = task_mock
        session.execute = AsyncMock(return_value=result)
        with _patch_db(session):
            await manager.fail_task("novel-1", "boom")
        # errors 原为 None，应被初始化为 [error]
        assert task_mock.errors == ["boom"]

    @pytest.mark.asyncio
    async def test_fail_silent_when_task_not_found(self, manager):
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)
        with _patch_db(session):
            ret = await manager.fail_task("missing", "err")
        assert ret is None
        session.commit.assert_not_awaited()


class TestListTasks:
    @pytest.mark.asyncio
    async def test_returns_tasks_and_total(self, manager):
        session = _make_session()
        t1 = _make_task_mock(task_id="novel-1", status="completed")
        t2 = _make_task_mock(task_id="novel-2", status="running")

        # 两次 execute: 第一次 count（scalar_one）, 第二次查询（scalars().all()）
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [t1, t2]
        session.execute = AsyncMock(side_effect=[count_result, list_result])

        with _patch_db(session):
            tasks, total = await manager.list_tasks()

        assert total == 2
        assert len(tasks) == 2
        assert tasks[0]["task_id"] == "novel-1"
        assert tasks[1]["task_id"] == "novel-2"
        assert tasks[1]["status"] == "running"
        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_status_filter_passes_to_query(self, manager):
        session = _make_session()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(side_effect=[count_result, list_result])

        with _patch_db(session):
            tasks, total = await manager.list_tasks(status="failed", limit=5,
                                                    offset=10)
        assert total == 0
        assert tasks == []
        # 两次 execute 调用均发生
        assert session.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_empty_result_when_no_tasks(self, manager):
        session = _make_session()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(side_effect=[count_result, list_result])

        with _patch_db(session):
            tasks, total = await manager.list_tasks()

        assert tasks == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_tasks_for_owner_filters_every_query(self, manager):
        session = _make_session()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        list_result = MagicMock()
        list_result.scalars.return_value.all.return_value = [
            _make_task_mock(task_id="novel-7", owner_id=7)
        ]
        session.execute = AsyncMock(side_effect=[count_result, list_result])

        with _patch_db(session):
            tasks, total = await manager.list_tasks_for_owner(owner_id=7)

        assert total == 1
        assert tasks[0]["owner_id"] == 7
        for call in session.execute.await_args_list:
            assert "tasks.owner_id =" in str(call.args[0])


class TestExpireStaleTasks:
    @pytest.mark.asyncio
    async def test_only_expires_legacy_tasks_without_queue_state(self, manager):
        session = _make_session()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            await manager.expire_stale_tasks(hours=1)

        query = session.execute.await_args.args[0]
        assert "tasks.queue_state IS NULL" in str(query)


class TestPersistentQueueState:
    @pytest.mark.asyncio
    async def test_create_task_can_persist_executable_payload(self, manager):
        session = _make_session()
        with _patch_db(session):
            await manager.create_task(
                "idea",
                "玄幻",
                10000,
                task_type="novel.generate",
                task_payload={"request": {"idea": "idea"}},
            )

        added = session.add.call_args.args[0]
        assert added.task_type == "novel.generate"
        assert added.task_payload == {"request": {"idea": "idea"}}
        assert added.queue_state == "queued"
        assert added.attempt_count == 0
        assert added.max_attempts == 1
        assert added.available_at is not None

    @pytest.mark.asyncio
    async def test_enqueue_existing_task_resets_execution_segment(self, manager):
        task = _make_task_mock(
            task_id="task-1",
            status="running",
            queue_state="idle",
            attempt_count=1,
            lease_owner="old-worker",
            progress={
                "current_stage": "human_review",
                "waiting_for_review": True,
                "review_decision": "pending",
            },
        )
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = task
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            queued = await manager.enqueue_existing_task(
                "task-1",
                task_type="pipeline.resume",
                task_payload={"decision": {"approval_status": "approved"}},
            )

        assert queued is True
        assert task.task_type == "pipeline.resume"
        assert task.queue_state == "queued"
        assert task.attempt_count == 0
        assert task.lease_owner is None
        assert task.status == "pending"
        assert task.progress["review_decision"] == "approved"
        assert task.progress["waiting_for_review"] is False

    @pytest.mark.asyncio
    async def test_pipeline_resume_enqueue_requires_idle_waiting_review(self, manager):
        task = _make_task_mock(
            task_id="task-1",
            status="running",
            queue_state="leased",
            lease_owner="active-worker",
            progress={
                "current_stage": "chapter_generation",
                "waiting_for_review": False,
            },
        )
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = task
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            queued = await manager.enqueue_existing_task(
                "task-1",
                task_type="pipeline.resume",
                task_payload={"decision": {"approval_status": "approved"}},
            )

        assert queued is False
        assert task.queue_state == "leased"
        assert task.lease_owner == "active-worker"
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_reject_review_task_atomically_fails_waiting_task(self, manager):
        task = _make_task_mock(
            task_id="task-review",
            status="running",
            queue_state="idle",
            progress={
                "current_stage": "human_review",
                "waiting_for_review": True,
                "review_decision": "pending",
            },
        )
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = task
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            rejected = await manager.reject_review_task(
                "task-review",
                instructions="主线方向错误",
            )

        assert rejected is True
        assert task.status == "failed"
        assert task.queue_state == "idle"
        assert task.progress["review_decision"] == "rejected"
        assert task.progress["review_instructions"] == "主线方向错误"
        assert task.progress["waiting_for_review"] is False
        assert "用户驳回审核" in task.errors
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_reject_review_task_refuses_non_waiting_state(self, manager):
        task = _make_task_mock(
            task_id="task-review",
            status="pending",
            queue_state="queued",
            progress={
                "current_stage": "human_review",
                "waiting_for_review": False,
                "review_decision": "approved",
            },
        )
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = task
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            rejected = await manager.reject_review_task("task-review")

        assert rejected is False
        assert task.status == "pending"
        assert task.queue_state == "queued"
        session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_claim_next_task_uses_skip_locked_and_sets_lease(self, manager):
        task = _make_task_mock(
            task_id="task-1",
            task_type="novel.generate",
            task_payload={"request": {}},
            queue_state="queued",
        )
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = task
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            claimed = await manager.claim_next_task("worker-1", 120)

        query = session.execute.call_args.args[0]
        assert query._for_update_arg is not None
        assert query._for_update_arg.skip_locked is True
        assert query._limit_clause.value == 1
        assert claimed["task_id"] == "task-1"
        assert claimed["task_type"] == "novel.generate"
        assert task.queue_state == "leased"
        assert task.status == "running"
        assert task.attempt_count == 1
        assert task.lease_owner == "worker-1"
        assert task.lease_expires_at > task.heartbeat_at

    @pytest.mark.asyncio
    async def test_claim_next_task_returns_none_when_queue_empty(self, manager):
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            claimed = await manager.claim_next_task("worker-1", 120)

        assert claimed is None

    @pytest.mark.asyncio
    async def test_claim_finalizes_expired_lease_when_attempts_exhausted(
        self, manager
    ):
        task = _make_task_mock(
            task_id="task-stale",
            task_type="novel.generate",
            status="running",
            queue_state="leased",
            attempt_count=1,
            max_attempts=1,
            lease_owner="dead-worker",
            lease_expires_at=datetime.now(UTC) - timedelta(seconds=1),
        )
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = task
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            claimed = await manager.claim_next_task("worker-2", 120)

        assert claimed is None
        assert task.status == "failed"
        assert task.queue_state == "idle"
        assert task.lease_owner is None
        assert any("不安全自动重放" in error for error in task.errors)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_renew_lease_requires_owner(self, manager):
        task = _make_task_mock(
            task_id="task-1", queue_state="leased", lease_owner="worker-1"
        )
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = task
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            renewed = await manager.renew_lease("task-1", "other", 120)

        assert renewed is False
        assert task.heartbeat_at is None

        with _patch_db(session):
            renewed = await manager.renew_lease("task-1", "worker-1", 120)

        assert renewed is True
        assert task.heartbeat_at is not None

    @pytest.mark.asyncio
    async def test_release_waiting_review_claim_to_idle(self, manager):
        task = _make_task_mock(
            task_id="task-1",
            status="running",
            queue_state="leased",
            lease_owner="worker-1",
            progress={"current_stage": "human_review", "waiting_for_review": True},
        )
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = task
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            released = await manager.release_claim("task-1", "worker-1")

        assert released is True
        assert task.status == "running"
        assert task.queue_state == "idle"
        assert task.lease_owner is None

    @pytest.mark.asyncio
    async def test_release_plain_running_claim_marks_failed(self, manager):
        task = _make_task_mock(
            task_id="task-1",
            status="running",
            queue_state="leased",
            lease_owner="worker-1",
        )
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = task
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            released = await manager.release_claim("task-1", "worker-1")

        assert released is True
        assert task.status == "failed"
        assert task.queue_state == "idle"
        assert any("未进入终态" in error for error in task.errors)

    @pytest.mark.asyncio
    async def test_retry_or_fail_requeues_when_attempts_remain(self, manager):
        task = _make_task_mock(
            task_id="task-1",
            status="running",
            queue_state="leased",
            lease_owner="worker-1",
            attempt_count=1,
            max_attempts=2,
        )
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = task
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            requeued = await manager.retry_or_fail_claim(
                "task-1", "worker-1", "boom", 5
            )

        assert requeued is True
        assert task.status == "pending"
        assert task.queue_state == "queued"
        assert task.available_at is not None
        assert task.errors[-1] == "boom"

    @pytest.mark.asyncio
    async def test_retry_or_fail_marks_failed_when_attempts_exhausted(self, manager):
        task = _make_task_mock(
            task_id="task-1",
            status="running",
            queue_state="leased",
            lease_owner="worker-1",
            attempt_count=1,
            max_attempts=1,
        )
        session = _make_session()
        result = MagicMock()
        result.scalar_one_or_none.return_value = task
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            requeued = await manager.retry_or_fail_claim(
                "task-1", "worker-1", "boom", 5
            )

        assert requeued is False
        assert task.status == "failed"
        assert task.queue_state == "idle"
        assert task.completed_at is not None


class TestRecoverInterruptedTasks:
    @pytest.mark.asyncio
    async def test_classifies_queue_and_legacy_tasks(self, manager):
        now = datetime.now(UTC)
        queued = _make_task_mock(
            task_id="queued", status="pending", queue_state="queued"
        )
        stale_retry = _make_task_mock(
            task_id="retry",
            status="running",
            queue_state="leased",
            attempt_count=1,
            max_attempts=2,
            lease_expires_at=now - timedelta(seconds=1),
        )
        stale_fail = _make_task_mock(
            task_id="fail",
            status="running",
            queue_state="leased",
            attempt_count=1,
            max_attempts=1,
            lease_expires_at=now - timedelta(seconds=1),
        )
        legacy = _make_task_mock(
            task_id="legacy", status="pending", queue_state=None
        )
        future_lease = _make_task_mock(
            task_id="future",
            status="running",
            queue_state="leased",
            lease_expires_at=now + timedelta(minutes=5),
        )
        idle = _make_task_mock(
            task_id="idle", status="running", queue_state="idle"
        )

        session = _make_session()
        result = MagicMock()
        result.scalars.return_value.all.return_value = [
            queued,
            stale_retry,
            stale_fail,
            legacy,
            future_lease,
            idle,
        ]
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            summary = await manager.recover_interrupted_tasks()

        assert summary.queued_preserved == 1
        assert summary.stale_requeued == 1
        assert summary.stale_failed == 1
        assert summary.legacy_failed == 1
        assert summary.total_changed == 3
        assert stale_retry.queue_state == "queued"
        assert stale_retry.status == "pending"
        assert stale_fail.status == "failed"
        assert legacy.status == "failed"
        assert future_lease.queue_state == "leased"
        assert idle.queue_state == "idle"

    @pytest.mark.asyncio
    async def test_empty_recovery_returns_zero_summary(self, manager):
        session = _make_session()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            summary = await manager.recover_interrupted_tasks()

        assert summary.total_changed == 0
        assert summary.queued_preserved == 0

    @pytest.mark.asyncio
    async def test_recovery_locks_only_actionable_queue_rows(self, manager):
        session = _make_session()
        result = MagicMock()
        result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=result)

        with _patch_db(session):
            await manager.recover_interrupted_tasks()

        query = session.execute.await_args.args[0]
        assert query._for_update_arg is not None
        assert query._for_update_arg.skip_locked is True
        list_params = [
            value
            for value in query.compile().params.values()
            if isinstance(value, list)
        ]
        assert ["queued", "leased"] in list_params
        assert ["queued", "leased", "idle"] not in list_params
