"""extend_chapter_versions_metadata

Revision ID: 20260521_extend_chapter_versions
Revises: 20260521_add_chapter_versions
Create Date: 2026-05-21 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260521_extend_chapter_versions"
down_revision: str | Sequence[str] | None = "20260521_add_chapter_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add metadata columns to chapter_versions and update source constraint."""
    op.add_column("chapter_versions", sa.Column("quality_score", sa.Float(), nullable=True))
    op.add_column("chapter_versions", sa.Column("model_name", sa.String(50), nullable=True))
    op.add_column("chapter_versions", sa.Column("prompt_summary", sa.Text(), nullable=True))
    op.add_column("chapter_versions", sa.Column("diff_from_previous", sa.Text(), nullable=True))
    op.add_column("chapter_versions", sa.Column("kg_conflicts", sa.JSON(), nullable=True))
    op.add_column("chapter_versions", sa.Column("user_notes", sa.Text(), nullable=True))
    op.add_column(
        "chapter_versions",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.drop_constraint("ck_chapter_version_source", "chapter_versions", type_="check")
    op.create_check_constraint(
        "ck_chapter_version_source",
        "chapter_versions",
        "source IN ('manual', 'ai_rewrite', 'rollback', 'generation')",
    )


def downgrade() -> None:
    """Remove metadata columns and revert source constraint."""
    op.drop_constraint("ck_chapter_version_source", "chapter_versions", type_="check")
    op.create_check_constraint(
        "ck_chapter_version_source",
        "chapter_versions",
        "source IN ('manual', 'ai_rewrite', 'rollback')",
    )

    op.drop_column("chapter_versions", "is_active")
    op.drop_column("chapter_versions", "user_notes")
    op.drop_column("chapter_versions", "kg_conflicts")
    op.drop_column("chapter_versions", "diff_from_previous")
    op.drop_column("chapter_versions", "prompt_summary")
    op.drop_column("chapter_versions", "model_name")
    op.drop_column("chapter_versions", "quality_score")
