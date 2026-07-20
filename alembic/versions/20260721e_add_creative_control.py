"""add creative control tables (artifact_controls / artifact_versions / operation_logs)

Revision ID: 20260721e
Revises: 20260721d
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721e_creative_control"
down_revision: str | Sequence[str] | None = "20260721d_task_checkpoints"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- novels: 创作模式 + 当前阶段 ---
    op.add_column(
        "novels",
        sa.Column(
            "creation_mode", sa.String(length=20),
            nullable=False, server_default="auto",
        ),
    )
    op.add_column(
        "novels",
        sa.Column(
            "creative_stage", sa.Integer(),
            nullable=False, server_default="1",
        ),
    )

    # --- chapter_blueprints: version_number（配合 is_active 历史）---
    op.add_column(
        "chapter_blueprints",
        sa.Column(
            "version_number", sa.Integer(),
            nullable=True, server_default="1",
        ),
    )

    # --- artifact_controls ---
    op.create_table(
        "artifact_controls",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "novel_id", sa.String(100),
            sa.ForeignKey("novels.novel_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(30), nullable=False),
        sa.Column("artifact_id", sa.String(100), nullable=False),
        sa.Column(
            "control_status", sa.String(20),
            nullable=False, server_default="draft",
        ),
        sa.Column("locked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("stage", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("generation_meta", sa.JSON(), nullable=True),
        sa.Column("stale_reason", sa.String(300), nullable=True),
        sa.Column(
            "awaiting_review", sa.Boolean(),
            nullable=False, server_default="false",
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "novel_id", "artifact_type", "artifact_id",
            name="uq_artifact_control_target",
        ),
    )
    op.create_index(
        "ix_artifact_controls_control_status",
        "artifact_controls", ["control_status"],
    )
    op.create_index(
        "ix_artifact_controls_awaiting_review",
        "artifact_controls", ["awaiting_review"],
    )
    op.create_index(
        "ix_artifact_control_novel_type",
        "artifact_controls", ["novel_id", "artifact_type"],
    )

    # --- artifact_versions ---
    op.create_table(
        "artifact_versions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "novel_id", sa.String(100),
            sa.ForeignKey("novels.novel_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(30), nullable=False),
        sa.Column("artifact_id", sa.String(100), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content_snapshot", sa.JSON(), nullable=False),
        sa.Column(
            "source", sa.String(20),
            nullable=False, server_default="manual",
        ),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column(
            "operator_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("task_id", sa.String(100), nullable=True),
        sa.Column("operation_id", sa.String(200), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "novel_id", "artifact_type", "artifact_id", "version_number",
            name="uq_artifact_version_number",
        ),
    )
    op.create_index(
        "ix_artifact_version_target",
        "artifact_versions", ["novel_id", "artifact_type", "artifact_id"],
    )
    # 每产物至多一个活跃版本（部分唯一索引）
    op.create_index(
        "uq_artifact_version_active",
        "artifact_versions",
        ["novel_id", "artifact_type", "artifact_id"],
        unique=True,
        postgresql_where=sa.text("is_active IS TRUE"),
    )

    # --- operation_logs ---
    op.create_table(
        "operation_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "novel_id", sa.String(100),
            sa.ForeignKey("novels.novel_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("artifact_type", sa.String(30), nullable=False),
        sa.Column("artifact_id", sa.String(100), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("from_version", sa.Integer(), nullable=True),
        sa.Column("to_version", sa.Integer(), nullable=True),
        sa.Column(
            "operator_id", sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("task_id", sa.String(100), nullable=True),
        sa.Column("operation_id", sa.String(200), nullable=True),
        sa.Column("meta", sa.JSON(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_operation_logs_action",
        "operation_logs", ["action"],
    )
    op.create_index(
        "ix_operation_log_novel_created",
        "operation_logs", ["novel_id", "created_at"],
    )
    op.create_index(
        "ix_operation_log_target",
        "operation_logs", ["novel_id", "artifact_type", "artifact_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_operation_log_target", table_name="operation_logs")
    op.drop_index("ix_operation_log_novel_created", table_name="operation_logs")
    op.drop_index("ix_operation_logs_action", table_name="operation_logs")
    op.drop_table("operation_logs")

    op.drop_index("uq_artifact_version_active", table_name="artifact_versions")
    op.drop_index("ix_artifact_version_target", table_name="artifact_versions")
    op.drop_table("artifact_versions")

    op.drop_index("ix_artifact_control_novel_type", table_name="artifact_controls")
    op.drop_index("ix_artifact_controls_awaiting_review", table_name="artifact_controls")
    op.drop_index("ix_artifact_controls_control_status", table_name="artifact_controls")
    op.drop_table("artifact_controls")

    op.drop_column("chapter_blueprints", "version_number")
    op.drop_column("novels", "creative_stage")
    op.drop_column("novels", "creation_mode")
