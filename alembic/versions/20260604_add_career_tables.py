"""add_career_tables

Revision ID: 20260604_career_tables
Revises: 20260526_export_sync_reader
Create Date: 2026-06-04 23:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260604_career_tables"
down_revision: str | None = "20260526_export_sync_reader"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "career_systems",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("stages", sa.JSON(), nullable=False),
        sa.Column("max_stage", sa.Integer(), nullable=True),
        sa.Column("requirements", sa.Text(), nullable=True),
        sa.Column("special_abilities", sa.Text(), nullable=True),
        sa.Column("worldview_rules", sa.Text(), nullable=True),
        sa.Column("attribute_bonuses", sa.JSON(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["novel_id"], ["novels.novel_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_career_systems_novel_id", "career_systems", ["novel_id"])

    op.create_table(
        "character_careers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("career_id", sa.Integer(), nullable=False),
        sa.Column(
            "current_stage",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["career_id"], ["career_systems.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["character_id"], ["characters.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("character_id", "career_id", name="uq_character_career"),
    )
    op.create_index(
        "ix_character_careers_career_id",
        "character_careers",
        ["career_id"],
    )
    op.create_index(
        "ix_character_careers_character_id",
        "character_careers",
        ["character_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_character_careers_character_id", table_name="character_careers")
    op.drop_index("ix_character_careers_career_id", table_name="character_careers")
    op.drop_table("character_careers")

    op.drop_index("ix_career_systems_novel_id", table_name="career_systems")
    op.drop_table("career_systems")
