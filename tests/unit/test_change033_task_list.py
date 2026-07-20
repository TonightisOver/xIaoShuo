"""Unit tests for CHANGE-033: task list route and model enhancements."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.api.models.responses import TaskSummary
from src.api.routes.novels import list_novel_tasks


class TestTaskSummaryModel:
    """Tests for the TaskSummary model serialization and field additions."""

    def test_task_summary_fields(self):
        """TaskSummary should correctly deserialize with the new optional fields."""
        now = datetime.now()
        summary = TaskSummary(
            task_id="task-123",
            novel_id="novel-456",
            status="running",
            created_at=now,
            completed_at=None,
            novel_type="科幻",
            target_words=150000,
            idea="星际探险与遗迹发现的故事",
        )

        assert summary.task_id == "task-123"
        assert summary.novel_id == "novel-456"
        assert summary.status == "running"
        assert summary.created_at == now
        assert summary.completed_at is None
        assert summary.novel_type == "科幻"
        assert summary.target_words == 150000
        assert summary.idea == "星际探险与遗迹发现的故事"

    def test_task_summary_optional_fields_default_to_none(self):
        """TaskSummary new fields should default to None for backward compatibility."""
        now = datetime.now()
        summary = TaskSummary(
            task_id="task-123",
            status="pending",
            created_at=now,
        )

        assert summary.task_id == "task-123"
        assert summary.novel_id is None
        assert summary.status == "pending"
        assert summary.created_at == now
        assert summary.completed_at is None
        assert summary.novel_type is None
        assert summary.target_words is None
        assert summary.idea is None


class TestListNovelTasksRoute:
    """Tests for the list_novel_tasks router endpoint."""

    @pytest.mark.asyncio
    async def test_list_novel_tasks_returns_summaries_with_new_fields(self):
        """list_novel_tasks should fetch tasks from task manager and map all fields."""
        now = datetime.now()
        mock_tasks = [
            {
                "task_id": "task-001",
                "novel_id": "novel-101",
                "status": "completed",
                "created_at": now,
                "completed_at": now,
                "novel_type": "玄幻",
                "target_words": 200000,
                "idea": "一个武帝重生的故事",
            },
            {
                "task_id": "task-002",
                "novel_id": None,
                "status": "pending",
                "created_at": now,
                # completed_at, novel_type, target_words, idea are missing
            }
        ]

        with patch("src.api.routes.novels.get_task_manager") as mock_gtm:
            mock_task_mgr = AsyncMock()
            mock_task_mgr.list_tasks_for_owner = AsyncMock(
                return_value=(mock_tasks, 2)
            )
            mock_gtm.return_value = mock_task_mgr

            response = await list_novel_tasks(
                status=None,
                limit=20,
                offset=0,
                current_user=SimpleNamespace(id="user-1"),
            )

        # Assert task manager was called correctly
        mock_task_mgr.list_tasks_for_owner.assert_awaited_once_with(
            owner_id="user-1", status=None, limit=20, offset=0
        )

        # Assert response structure and mapped data
        assert response.total == 2
        assert len(response.tasks) == 2

        # First task with complete data
        t1 = response.tasks[0]
        assert t1.task_id == "task-001"
        assert t1.novel_id == "novel-101"
        assert t1.status == "completed"
        assert t1.created_at == now
        assert t1.completed_at == now
        assert t1.novel_type == "玄幻"
        assert t1.target_words == 200000
        assert t1.idea == "一个武帝重生的故事"

        # Second task with minimal data
        t2 = response.tasks[1]
        assert t2.task_id == "task-002"
        assert t2.novel_id is None
        assert t2.status == "pending"
        assert t2.created_at == now
        assert t2.completed_at is None
        assert t2.novel_type is None
        assert t2.target_words is None
        assert t2.idea is None
