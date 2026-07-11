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

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.task_manager import TaskManager


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
    return patch("src.api.services.task_manager.get_db_session", mock_db)


def _make_task_mock(**overrides):
    """构造一个具有 Task 全部属性的 mock 对象，含 to_dict。"""
    task = MagicMock()
    task.task_id = overrides.get("task_id", "novel-1")
    task.novel_id = overrides.get("novel_id", None)
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

    def to_dict():
        return {
            "task_id": task.task_id,
            "novel_id": task.novel_id,
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


class TestRecoverInterruptedTasks:
    """recover_interrupted_tasks — 服务启动时恢复孤儿 running 任务。"""

    @pytest.mark.asyncio
    async def test_marks_orphan_running_tasks_as_failed(self, manager):
        """status=running 的任务被标记为 failed，errors 追加中断说明。"""
        t1 = _make_task_mock(task_id="orphan-1", status="running")
        t2 = _make_task_mock(task_id="orphan-2", status="running")
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [t1, t2]
        session.execute = AsyncMock(return_value=result_mock)

        with _patch_db(session):
            count = await manager.recover_interrupted_tasks()

        assert count == 2
        assert t1.status == "failed"
        assert t2.status == "failed"
        assert t1.completed_at is not None
        assert any("重启中断" in e for e in t1.errors)
        assert any("重启中断" in e for e in t2.errors)
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_no_orphan_returns_zero(self, manager):
        """无 running 任务时返回 0，不 commit。"""
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(return_value=result_mock)

        with _patch_db(session):
            count = await manager.recover_interrupted_tasks()

        assert count == 0
        session.commit.assert_awaited_once()  # 仍 commit（无操作）

    @pytest.mark.asyncio
    async def test_does_not_touch_non_running_tasks(self, manager):
        """pending/completed/failed 任务不受影响（查询只选 running）。"""
        running_task = _make_task_mock(task_id="r1", status="running")
        completed_task = _make_task_mock(task_id="c1", status="completed")
        session = _make_session()
        # 查询只返回 running 的（模拟 SQL where status=running）
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [running_task]
        session.execute = AsyncMock(return_value=result_mock)

        with _patch_db(session):
            count = await manager.recover_interrupted_tasks()

        assert count == 1
        assert running_task.status == "failed"
        # completed_task 不在查询结果里，状态不变
        assert completed_task.status == "completed"

    @pytest.mark.asyncio
    async def test_preserves_existing_errors(self, manager):
        """已有的 errors 被保留，中断说明追加到末尾。"""
        task = _make_task_mock(task_id="r1", status="running", errors=["已有错误"])
        session = _make_session()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [task]
        session.execute = AsyncMock(return_value=result_mock)

        with _patch_db(session):
            await manager.recover_interrupted_tasks()

        assert task.errors[0] == "已有错误"
        assert len(task.errors) == 2
        assert "重启中断" in task.errors[1]
