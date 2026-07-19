"""add chapters state_delta and quality_status columns

Revision ID: c3d8e1f7a2b4
Revises: a1f3e7c2d9b8
Create Date: 2026-07-16

补齐 funnel-quality-gate 分支在 Chapter 模型新增但未建迁移的两列：
- state_delta: 结构化状态增量（JSON），替代正文截取做长期记忆
- quality_status: 本章质量门禁状态 verified/unverified/failed

此前模型已定义这两列但无对应迁移，导致线上库缺列、章节相关接口 500。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d8e1f7a2b4"
down_revision: str | Sequence[str] | None = "a1f3e7c2d9b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # state_delta: JSON，可空
    op.add_column(
        "chapters",
        sa.Column("state_delta", sa.JSON(), nullable=True),
    )
    # quality_status: 字符串，可空，带索引（与模型 index=True 一致）
    op.add_column(
        "chapters",
        sa.Column("quality_status", sa.String(length=20), nullable=True),
    )
    op.create_index(
        "ix_chapters_quality_status",
        "chapters",
        ["quality_status"],
    )


def downgrade() -> None:
    op.drop_index("ix_chapters_quality_status", table_name="chapters")
    op.drop_column("chapters", "quality_status")
    op.drop_column("chapters", "state_delta")
