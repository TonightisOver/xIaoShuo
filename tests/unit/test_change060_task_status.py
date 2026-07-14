import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.api.services.task_manager import TaskManager


def _mock_task():
    return type("T", (), {"status": None, "completed_at": None, "result": None, "progress": None})()


def _mock_session(task):
    session = AsyncMock()
    scalar_result = MagicMock(scalar_one_or_none=MagicMock(return_value=task))
    session.execute = AsyncMock(return_value=scalar_result)
    session.commit = AsyncMock()
    return session


@pytest.mark.asyncio
async def test_complete_task_accepts_status():
    tm = TaskManager()
    with patch("src.api.services.task_manager.get_db_session") as mock_db:
        session = _mock_session(_mock_task())
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        await tm.complete_task("t1", {"chapters": []}, status="partially_completed")
    assert session.execute.call_args[0][0].__class__.__name__ == "Select"
    assert session.commit.called


@pytest.mark.asyncio
async def test_complete_task_defaults_to_completed():
    tm = TaskManager()
    with patch("src.api.services.task_manager.get_db_session") as mock_db:
        session = _mock_session(_mock_task())
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        await tm.complete_task("t1", {"chapters": []})
    assert session.commit.called


@pytest.mark.asyncio
async def test_complete_task_sets_status_on_task():
    tm = TaskManager()
    with patch("src.api.services.task_manager.get_db_session") as mock_db:
        task = _mock_task()
        session = _mock_session(task)
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        await tm.complete_task("t1", {"chapters": []}, status="partially_completed")
    assert task.status == "partially_completed"


@pytest.mark.asyncio
async def test_complete_task_progress_by_status():
    tm = TaskManager()
    with patch("src.api.services.task_manager.get_db_session") as mock_db:
        task = _mock_task()
        session = _mock_session(task)
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        await tm.complete_task("t1", {"chapters": ["c1"], "completion_percentage": 75}, status="partially_completed")
    assert task.status == "partially_completed"
    assert task.progress["percentage"] == 75
    assert task.progress["completed_chapters"] == 1


@pytest.mark.asyncio
async def test_complete_task_completed_has_100_percent():
    tm = TaskManager()
    with patch("src.api.services.task_manager.get_db_session") as mock_db:
        task = _mock_task()
        session = _mock_session(task)
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        await tm.complete_task("t1", {"chapters": []}, status="completed")
    assert task.progress["percentage"] == 100
