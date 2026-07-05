"""add_export_sync_reader_tables

Revision ID: 20260526_export_sync_reader
Revises: 20260525_blueprint
Create Date: 2026-05-26 10:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260526_export_sync_reader"
down_revision: str | None = "20260525_blueprint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "outlines",
        sa.Column("deviation_summary", sa.Text(), nullable=True),
    )

    op.create_table(
        "outline_sync_suggestions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.String(100), nullable=False),
        sa.Column("source_level", sa.String(20), nullable=False),
        sa.Column("source_volume", sa.Integer(), nullable=True),
        sa.Column("source_chapter", sa.Integer(), nullable=True),
        sa.Column("affected_chapter", sa.Integer(), nullable=False),
        sa.Column("impact_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.novel_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_outline_sync_suggestions_novel_id",
        "outline_sync_suggestions",
        ["novel_id"],
    )
    op.create_index(
        "ix_outline_sync_suggestions_affected_chapter",
        "outline_sync_suggestions",
        ["affected_chapter"],
    )
    op.create_index(
        "ix_outline_sync_suggestions_status",
        "outline_sync_suggestions",
        ["status"],
    )
    op.create_index(
        "ix_sync_novel_status",
        "outline_sync_suggestions",
        ["novel_id", "status"],
    )

    op.create_table(
        "reader_simulations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.String(100), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("personas_used", sa.JSON(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.novel_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reader_simulations_novel_id",
        "reader_simulations",
        ["novel_id"],
    )
    op.create_index(
        "ix_reader_simulations_status",
        "reader_simulations",
        ["status"],
    )
    op.create_index(
        "ix_reader_sim_novel_chapter",
        "reader_simulations",
        ["novel_id", "chapter_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_reader_sim_novel_chapter", table_name="reader_simulations")
    op.drop_index("ix_reader_simulations_status", table_name="reader_simulations")
    op.drop_index("ix_reader_simulations_novel_id", table_name="reader_simulations")
    op.drop_table("reader_simulations")

    op.drop_index("ix_sync_novel_status", table_name="outline_sync_suggestions")
    op.drop_index(
        "ix_outline_sync_suggestions_status",
        table_name="outline_sync_suggestions",
    )
    op.drop_index(
        "ix_outline_sync_suggestions_affected_chapter",
        table_name="outline_sync_suggestions",
    )
    op.drop_index(
        "ix_outline_sync_suggestions_novel_id",
        table_name="outline_sync_suggestions",
    )
    op.drop_table("outline_sync_suggestions")

    op.drop_column("outlines", "deviation_summary")
