"""extend_story_bibles_fields

Revision ID: 20260522a
Revises: 20260521_extend_chapter_versions
Create Date: 2026-05-22 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260522a"
down_revision: str | None = "20260521_extend_chapter_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("story_bibles", sa.Column("timeline_events", sa.JSON(), nullable=True))
    op.add_column("story_bibles", sa.Column("unresolved_hooks", sa.JSON(), nullable=True))
    op.add_column("story_bibles", sa.Column("main_goals", sa.JSON(), nullable=True))
    op.add_column("story_bibles", sa.Column("banned_elements", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("story_bibles", "banned_elements")
    op.drop_column("story_bibles", "main_goals")
    op.drop_column("story_bibles", "unresolved_hooks")
    op.drop_column("story_bibles", "timeline_events")
