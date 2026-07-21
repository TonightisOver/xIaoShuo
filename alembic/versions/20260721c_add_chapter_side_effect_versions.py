"""add chapters.bible_applied_version / kg_applied_version with sentinel backfill

Revision ID: 20260721c
Revises: 20260721b
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721c_chapter_side_effect"
down_revision: str | Sequence[str] | None = "20260721b_chapter_version_idem"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chapters",
        sa.Column("bible_applied_version", sa.Integer, nullable=True),
    )
    op.add_column(
        "chapters",
        sa.Column("kg_applied_version", sa.Integer, nullable=True),
    )
    # 历史章节回填哨兵 -1，语义"已应用，版本未知，跳过重跑"，避免 retry 时
    # 对历史稳定章重复调用 update_bible_after_generation / extract_from_chapter
    # 产生重复 append（B25 修正）。
    op.execute(
        "UPDATE chapters SET bible_applied_version = -1, kg_applied_version = -1"
    )


def downgrade() -> None:
    op.drop_column("chapters", "kg_applied_version")
    op.drop_column("chapters", "bible_applied_version")
