"""持久化任务队列的 ORM 与 Alembic 迁移契约。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch


def test_task_model_has_internal_queue_fields():
    from src.api.models.db_models import Task

    columns = Task.__table__.c
    assert columns.task_type.nullable is True
    assert columns.task_payload.nullable is True
    assert columns.queue_state.nullable is True
    assert columns.attempt_count.default.arg == 0
    assert columns.max_attempts.default.arg == 1
    assert columns.available_at.nullable is True
    assert columns.lease_owner.nullable is True
    assert columns.lease_expires_at.nullable is True
    assert columns.heartbeat_at.nullable is True


def test_task_queue_ready_index_exists():
    from src.api.models.db_models import Task

    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in Task.__table__.indexes
    }
    assert indexes["ix_tasks_queue_ready"] == ("queue_state", "available_at")


def test_task_queue_migration_upgrade_and_downgrade_are_symmetric():
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "d7e4f9a2c1b0_add_task_queue_fields.py"
    )
    spec = importlib.util.spec_from_file_location(
        "task_queue_migration", migration_path
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "d7e4f9a2c1b0"
    assert migration.down_revision == "c3d8e1f7a2b4"

    fake_op = MagicMock()
    with patch.object(migration, "op", fake_op):
        migration.upgrade()

    added_columns = [
        call.args[1].name for call in fake_op.add_column.call_args_list
    ]
    assert added_columns == [
        "task_type",
        "task_payload",
        "queue_state",
        "attempt_count",
        "max_attempts",
        "available_at",
        "lease_owner",
        "lease_expires_at",
        "heartbeat_at",
    ]
    fake_op.create_index.assert_called_once_with(
        "ix_tasks_queue_ready",
        "tasks",
        ["queue_state", "available_at"],
    )

    fake_op.reset_mock()
    with patch.object(migration, "op", fake_op):
        migration.downgrade()

    fake_op.drop_index.assert_called_once_with(
        "ix_tasks_queue_ready", table_name="tasks"
    )
    dropped_columns = [
        call.args[1] for call in fake_op.drop_column.call_args_list
    ]
    assert dropped_columns == list(reversed(added_columns))
