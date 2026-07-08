"""add_embedding_to_knowledge_entities

Revision ID: e1f2a3b4c5d6
Revises: b0018a838516
Create Date: 2026-07-07 10:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: str | Sequence[str] | None = 'b0018a838516'
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
