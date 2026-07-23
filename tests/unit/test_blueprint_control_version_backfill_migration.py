"""历史蓝图控制记录与版本快照回填迁移测试。"""

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock


def test_upgrade_backfills_missing_blueprint_controls_and_versions():
    path = (
        Path(__file__).parents[2]
        / "alembic/versions/20260723a_backfill_blueprint_control_versions.py"
    )
    spec = importlib.util.spec_from_file_location("blueprint_backfill", path)
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    execute = MagicMock()
    migration.op.execute = execute

    migration.upgrade()

    statements = "\n".join(str(call.args[0]) for call in execute.call_args_list)
    assert "INSERT INTO artifact_controls" in statements
    assert "INSERT INTO artifact_versions" in statements
    assert "NOT EXISTS" in statements
    assert "20260723a_blueprint_backfill" in statements
