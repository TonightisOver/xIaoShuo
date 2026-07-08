"""add_embedding_to_knowledge_entities (fixed down_revision)

Revision ID: 0dbde18317da
Revises: 20c40220fe09
Create Date: 2026-07-08 14:30:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0dbde18317da"
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
