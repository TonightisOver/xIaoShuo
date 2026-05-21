"""add_chapter_versions_table

Revision ID: 20260521_add_chapter_versions
Revises: 1f4a7c9d2b35
Create Date: 2026-05-21 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260521_add_chapter_versions"
down_revision: str | Sequence[str] | None = "1f4a7c9d2b35"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create chapter_versions table."""
    op.create_table(
        "chapter_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.String(length=100), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("source", sa.String(length=20), nullable=False, server_default="manual"),
        sa.Column("rewrite_instruction", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source IN ('manual', 'ai_rewrite', 'rollback')",
            name="ck_chapter_version_source",
        ),
        sa.ForeignKeyConstraint(
            ["novel_id"],
            ["novels.novel_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id", "chapter_number", "version_number", name="uq_chapter_version"),
    )
    op.create_index(
        "ix_chapter_versions_novel_chapter",
        "chapter_versions",
        ["novel_id", "chapter_number"],
    )


def downgrade() -> None:
    """Drop chapter_versions table."""
    op.drop_index("ix_chapter_versions_novel_chapter", table_name="chapter_versions")
    op.drop_table("chapter_versions")
