"""add_long_form_generation

Revision ID: 20260525_long_form
Revises: 20260522a
Create Date: 2026-05-25 11:20:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_long_form"
down_revision: str | None = "20260522a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "novels",
        sa.Column(
            "is_long_form",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column("novels", sa.Column("total_volumes", sa.Integer(), nullable=True))
    op.add_column("novels", sa.Column("chapters_per_volume", sa.Integer(), nullable=True))
    op.add_column(
        "novels",
        sa.Column(
            "words_per_chapter",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3000"),
        ),
    )
    op.add_column("novels", sa.Column("master_outline", sa.JSON(), nullable=True))

    op.add_column("volumes", sa.Column("target_chapters", sa.Integer(), nullable=True))
    op.add_column(
        "volumes",
        sa.Column(
            "generated_chapters",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column("volumes", sa.Column("avg_quality_score", sa.Float(), nullable=True))
    op.add_column("volumes", sa.Column("quality_report", sa.JSON(), nullable=True))

    op.add_column("chapters", sa.Column("chapter_type", sa.String(30), nullable=True))
    op.create_index("ix_chapters_chapter_type", "chapters", ["chapter_type"])

    op.create_table(
        "long_form_progress",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.String(100), nullable=False),
        sa.Column("volume_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("chapter_start", sa.Integer(), nullable=False),
        sa.Column("chapter_end", sa.Integer(), nullable=False),
        sa.Column("chapters_completed", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("current_chapter", sa.Integer(), nullable=True),
        sa.Column("quality_report", sa.JSON(), nullable=True),
        sa.Column("filler_report", sa.JSON(), nullable=True),
        sa.Column("errors", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.novel_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_long_form_progress_novel_id", "long_form_progress", ["novel_id"])
    op.create_index("ix_long_form_progress_status", "long_form_progress", ["status"])
    op.create_index(
        "ix_lfp_novel_volume",
        "long_form_progress",
        ["novel_id", "volume_number"],
    )


def downgrade() -> None:
    op.drop_index("ix_lfp_novel_volume", table_name="long_form_progress")
    op.drop_index("ix_long_form_progress_status", table_name="long_form_progress")
    op.drop_index("ix_long_form_progress_novel_id", table_name="long_form_progress")
    op.drop_table("long_form_progress")

    op.drop_index("ix_chapters_chapter_type", table_name="chapters")
    op.drop_column("chapters", "chapter_type")

    op.drop_column("volumes", "quality_report")
    op.drop_column("volumes", "avg_quality_score")
    op.drop_column("volumes", "generated_chapters")
    op.drop_column("volumes", "target_chapters")

    op.drop_column("novels", "master_outline")
    op.drop_column("novels", "words_per_chapter")
    op.drop_column("novels", "chapters_per_volume")
    op.drop_column("novels", "total_volumes")
    op.drop_column("novels", "is_long_form")
