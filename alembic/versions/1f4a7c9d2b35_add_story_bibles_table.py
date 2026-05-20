"""add_story_bibles_table

Revision ID: 1f4a7c9d2b35
Revises: 0dbde18317da
Create Date: 2026-05-20 15:45:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "1f4a7c9d2b35"
down_revision: str | Sequence[str] | None = "0dbde18317da"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "story_bibles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.String(length=100), nullable=False),
        sa.Column("worldview_rules", sa.Text(), nullable=True),
        sa.Column("character_cards", sa.JSON(), nullable=True),
        sa.Column("faction_relations", sa.Text(), nullable=True),
        sa.Column("location_settings", sa.Text(), nullable=True),
        sa.Column("prop_settings", sa.Text(), nullable=True),
        sa.Column("foreshadowing_list", sa.JSON(), nullable=True),
        sa.Column("hard_settings", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["novel_id"],
            ["novels.novel_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("novel_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("story_bibles")
