"""add_knowledge_entity_states

Revision ID: 0dbde18317da
Revises: chvol_20260520
Create Date: 2026-05-20 11:10:21.332418

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0dbde18317da"
down_revision: str | Sequence[str] | None = "chvol_20260520"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "knowledge_entity_states",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("novel_id", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["knowledge_entities.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["novel_id"],
            ["novels.novel_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "entity_id",
            "chapter_number",
            name="uq_kes_entity_chapter",
        ),
    )
    op.create_index(
        op.f("ix_knowledge_entity_states_chapter_number"),
        "knowledge_entity_states",
        ["chapter_number"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_entity_states_entity_id"),
        "knowledge_entity_states",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_knowledge_entity_states_novel_id"),
        "knowledge_entity_states",
        ["novel_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(
        op.f("ix_knowledge_entity_states_novel_id"),
        table_name="knowledge_entity_states",
    )
    op.drop_index(
        op.f("ix_knowledge_entity_states_entity_id"),
        table_name="knowledge_entity_states",
    )
    op.drop_index(
        op.f("ix_knowledge_entity_states_chapter_number"),
        table_name="knowledge_entity_states",
    )
    op.drop_table("knowledge_entity_states")
