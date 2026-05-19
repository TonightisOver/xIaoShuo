"""add_status_indexes

Revision ID: 20260519_add_status_indexes
Revises: b0018a838516
Create Date: 2026-05-19 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260519_add_status_indexes"
down_revision: Union[str, Sequence[str], None] = "b0018a838516"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add status indexes to volumes, chapters, conversations, outlines, storylines."""
    op.create_index("ix_volumes_status", "volumes", ["status"], unique=False)
    op.create_index("ix_chapters_status", "chapters", ["status"], unique=False)
    op.create_index("ix_conversations_status", "conversations", ["status"], unique=False)
    op.create_index("ix_outlines_status", "outlines", ["status"], unique=False)
    op.create_index("ix_storylines_status", "storylines", ["status"], unique=False)


def downgrade() -> None:
    """Remove status indexes."""
    op.drop_index("ix_storylines_status", table_name="storylines")
    op.drop_index("ix_outlines_status", table_name="outlines")
    op.drop_index("ix_conversations_status", table_name="conversations")
    op.drop_index("ix_chapters_status", table_name="chapters")
    op.drop_index("ix_volumes_status", table_name="volumes")
