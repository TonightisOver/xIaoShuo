"""Creative Control 数据模型与迁移单元测试。

验证 ORM 模型列与索引存在性（不连真实 DB，只检 __table__ 元数据）。
"""

from src.api.models.db_models import (
    ArtifactControl,
    ArtifactVersion,
    ChapterBlueprint,
    Novel,
    OperationLog,
)


def _columns(model) -> set[str]:
    return set(model.__table__.columns.keys())


def _index_names(model) -> list[str]:
    return [idx.name for idx in model.__table__.indexes]


def test_artifact_controls_table_columns():
    cols = _columns(ArtifactControl)
    for name in (
        "id", "novel_id", "artifact_type", "artifact_id",
        "control_status", "locked", "version", "stage",
        "generation_meta", "stale_reason", "awaiting_review",
        "created_at", "updated_at",
    ):
        assert name in cols, name


def test_artifact_controls_unique_constraint():
    constrs = [c.name for c in ArtifactControl.__table__.constraints]
    assert any("novel_id" in (c.name or "") and "artifact" in (c.name or "")
               for c in ArtifactControl.__table__.constraints) or \
        any("uq" in (n or "").lower() for n in constrs)


def test_artifact_versions_table_columns():
    cols = _columns(ArtifactVersion)
    for name in (
        "id", "novel_id", "artifact_type", "artifact_id",
        "version_number", "content_snapshot", "source", "model",
        "operator_id", "task_id", "operation_id", "is_active", "created_at",
    ):
        assert name in cols, name


def test_artifact_versions_active_partial_unique_index():
    names = _index_names(ArtifactVersion)
    assert any("active" in (n or "") for n in names), names


def test_operation_log_columns():
    cols = _columns(OperationLog)
    for name in (
        "id", "novel_id", "artifact_type", "artifact_id", "action",
        "from_version", "to_version", "operator_id", "reason",
        "task_id", "operation_id", "meta", "created_at",
    ):
        assert name in cols, name


def test_novel_has_creation_mode_and_creative_stage():
    cols = _columns(Novel)
    assert "creation_mode" in cols
    assert "creative_stage" in cols


def test_blueprint_has_version_number():
    cols = _columns(ChapterBlueprint)
    assert "version_number" in cols
