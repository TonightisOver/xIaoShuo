"""add_embedding_to_knowledge_entities (renamed to fix duplicate revision id)

Revision ID: a1f3e7c2d9b8
Revises: 20c40220fe09
Create Date: 2026-07-09 01:00:00.000000

NOTE: This file was previously 0dbde18317da which collided with an existing
migration id 0dbde18317da_add_knowledge_entity_states.py. Renamed revision
to a fresh unique id to avoid "Multiple head revisions" error.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1f3e7c2d9b8"
down_revision: str | Sequence[str] | None = "20c40220fe09"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'knowledge_entities',
        sa.Column('embedding', sa.JSON(), nullable=True)
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('knowledge_entities', 'embedding')
