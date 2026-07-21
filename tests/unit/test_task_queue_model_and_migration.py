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


def test_task_model_has_owner_field_and_index():
    from src.api.models.db_models import Task

    columns = Task.__table__.c
    assert columns.owner_id.nullable is True
    indexes = {
        index.name: tuple(column.name for column in index.columns)
        for index in Task.__table__.indexes
    }
    assert indexes["ix_tasks_owner_id"] == ("owner_id",)


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


def _index_map(table):
    return {
        index.name: tuple(column.name for column in index.columns)
        for index in table.indexes
    }


def test_task_has_operation_id_and_partial_unique_index():
    from src.api.models.db_models import Task

    columns = Task.__table__.c
    assert "operation_id" in columns
    # 模型层保持 nullable=True，供 T4 落地 create_task 回填前的增量安全过渡；
    # 迁移在回填完成后 alter 为非空（见迁移 1 test）。
    assert columns.operation_id.nullable is True
    indexes = _index_map(Task.__table__)
    assert indexes["uq_tasks_operation_active"] == ("operation_id",)
    idx = next(
        i for i in Task.__table__.indexes if i.name == "uq_tasks_operation_active"
    )
    assert idx.unique is True
    assert idx.dialect_options["postgresql"]["where"] is not None


def test_chapter_version_has_idempotency_key_and_active_indexes():
    from src.api.models.db_models import ChapterVersion

    columns = ChapterVersion.__table__.c
    assert "idempotency_key" in columns
    assert columns.idempotency_key.nullable is True
    indexes = _index_map(ChapterVersion.__table__)
    assert indexes["uq_chapter_version_active"] == ("novel_id", "chapter_number")
    assert indexes["uq_chapter_version_idem"] == (
        "novel_id",
        "chapter_number",
        "idempotency_key",
    )
    active_idx = next(
        i for i in ChapterVersion.__table__.indexes
        if i.name == "uq_chapter_version_active"
    )
    idem_idx = next(
        i for i in ChapterVersion.__table__.indexes
        if i.name == "uq_chapter_version_idem"
    )
    assert active_idx.unique is True
    assert active_idx.dialect_options["postgresql"]["where"] is not None
    assert idem_idx.unique is True
    assert idem_idx.dialect_options["postgresql"]["where"] is not None


def test_chapter_has_side_effect_applied_versions():
    from src.api.models.db_models import Chapter

    columns = Chapter.__table__.c
    assert "bible_applied_version" in columns
    assert columns.bible_applied_version.nullable is True
    assert "kg_applied_version" in columns
    assert columns.kg_applied_version.nullable is True


def test_task_checkpoint_model_schema():
    from src.api.models.db_models import TaskCheckpoint

    columns = TaskCheckpoint.__table__.c
    assert columns.task_id.primary_key is True
    # task_id FK 必须匹配 tasks.task_id 的 String(100)
    assert columns.task_id.type.length == 100
    fk = next(iter(columns.task_id.foreign_keys))
    assert fk.column.table.name == "tasks"
    for name in (
        "novel_id",
        "operation_id",
        "current_stage",
        "volume_number",
        "chapter_number",
        "last_completed_volume",
        "last_completed_chapter",
        "active_version_number",
        "checkpoint_version",
        "attempt_number",
        "last_event_sequence",
        "status",
        "pause_requested",
        "failure_category",
        "recoverable",
        "failure_detail",
        "updated_at",
    ):
        assert name in columns, f"missing column {name}"
    assert columns.operation_id.type.length == 200
    assert columns.last_completed_volume.nullable is False
    assert columns.last_completed_chapter.nullable is False
    assert columns.checkpoint_version.nullable is False
    assert columns.pause_requested.nullable is False
    assert columns.recoverable.nullable is False


def _load_migration(filename: str, module_name: str):
    migration_path = (
        Path(__file__).parents[2] / "alembic" / "versions" / filename
    )
    spec = importlib.util.spec_from_file_location(module_name, migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def test_operation_id_migration_symmetric():
    migration = _load_migration(
        "20260721a_add_operation_id.py", "op_id_migration"
    )
    assert migration.revision == "20260721a_operation_id"
    assert migration.down_revision == "20260720_task_owner"

    fake_op = MagicMock()
    with patch.object(migration, "op", fake_op):
        migration.upgrade()
    assert fake_op.add_column.call_args.args[1].name == "operation_id"
    # 回填按 {novel_id}:{task_type} 格式（修正 B23）
    executed = " ".join(str(c.args[0]) for c in fake_op.execute.call_args_list)
    assert "novel_id || ':' || task_type" in executed
    create_idx_names = [c.args[0] for c in fake_op.create_index.call_args_list]
    assert "uq_tasks_operation_active" in create_idx_names

    fake_op.reset_mock()
    with patch.object(migration, "op", fake_op):
        migration.downgrade()
    fake_op.drop_index.assert_called_once_with(
        "uq_tasks_operation_active", table_name="tasks"
    )
    fake_op.drop_column.assert_called_once_with("tasks", "operation_id")


def test_chapter_version_idem_migration_uses_version_number_order():
    migration = _load_migration(
        "20260721b_add_chapter_version_idem.py", "cv_idem_migration"
    )
    assert migration.revision == "20260721b_chapter_version_idem"
    assert migration.down_revision == "20260721a_operation_id"

    fake_op = MagicMock()
    with patch.object(migration, "op", fake_op):
        migration.upgrade()
    executed = " ".join(str(c.args[0]) for c in fake_op.execute.call_args_list)
    # 修正 B22：用 version_number DESC 而非 MAX(id)
    assert "version_number DESC" in executed
    assert "MAX(id)" not in executed
    create_idx_names = [c.args[0] for c in fake_op.create_index.call_args_list]
    assert "uq_chapter_version_active" in create_idx_names
    assert "uq_chapter_version_idem" in create_idx_names


def test_side_effect_migration_backfills_sentinel():
    migration = _load_migration(
        "20260721c_add_chapter_side_effect_versions.py", "side_effect_migration"
    )
    assert migration.revision == "20260721c_chapter_side_effect"
    assert migration.down_revision == "20260721b_chapter_version_idem"

    fake_op = MagicMock()
    with patch.object(migration, "op", fake_op):
        migration.upgrade()
    added = [c.args[1].name for c in fake_op.add_column.call_args_list]
    assert added == ["bible_applied_version", "kg_applied_version"]
    # 修正 B25：回填哨兵 -1
    executed = " ".join(str(c.args[0]) for c in fake_op.execute.call_args_list)
    assert "-1" in executed


def test_task_checkpoints_migration_backfills_legacy_as_unrecoverable():
    migration = _load_migration(
        "20260721d_add_task_checkpoints.py", "checkpoints_migration"
    )
    assert migration.revision == "20260721d_task_checkpoints"
    assert migration.down_revision == "20260721c_chapter_side_effect"

    fake_op = MagicMock()
    with patch.object(migration, "op", fake_op):
        migration.upgrade()
    fake_op.create_table.assert_called_once()
    assert fake_op.create_table.call_args.args[0] == "task_checkpoints"
    # 修正 B24：历史任务回填 task_end + unrecoverable，不映射非法 current_stage
    executed = " ".join(str(c.args[0]) for c in fake_op.execute.call_args_list)
    assert "task_end" in executed
    assert "unrecoverable" in executed

    fake_op.reset_mock()
    with patch.object(migration, "op", fake_op):
        migration.downgrade()
    fake_op.drop_table.assert_called_once_with("task_checkpoints")


def test_task_owner_migration_backfills_and_is_symmetric():
    migration_path = (
        Path(__file__).parents[2]
        / "alembic"
        / "versions"
        / "20260720_add_task_owner.py"
    )
    spec = importlib.util.spec_from_file_location("task_owner_migration", migration_path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    assert migration.revision == "20260720_task_owner"
    assert migration.down_revision == "d7e4f9a2c1b0"

    fake_op = MagicMock()
    with patch.object(migration, "op", fake_op):
        migration.upgrade()

    assert fake_op.add_column.call_args.args[1].name == "owner_id"
    fake_op.create_foreign_key.assert_called_once_with(
        "fk_tasks_owner_id",
        "tasks",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )
    fake_op.create_index.assert_called_once_with(
        "ix_tasks_owner_id", "tasks", ["owner_id"]
    )
    assert "UPDATE tasks AS t" in fake_op.execute.call_args.args[0]

    fake_op.reset_mock()
    with patch.object(migration, "op", fake_op):
        migration.downgrade()

    fake_op.drop_index.assert_called_once_with(
        "ix_tasks_owner_id", table_name="tasks"
    )
    fake_op.drop_constraint.assert_called_once_with(
        "fk_tasks_owner_id", "tasks", type_="foreignkey"
    )
    fake_op.drop_column.assert_called_once_with("tasks", "owner_id")
