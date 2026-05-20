"""add unique constraints to chapters and volumes

Revision ID: chvol_20260520
Revises: kg_20260520
Create Date: 2026-05-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "chvol_20260520"
down_revision: Union[str, Sequence[str], None] = "kg_20260520"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Production already has duplicate generated chapters in some novels.
    # Avoid destructive cleanup during deploy; add lookup indexes instead.
    op.create_index(
        "ix_chapter_novel_number", "chapters", ["novel_id", "chapter_number"]
    )
    op.create_index(
        "ix_volume_novel_number", "volumes", ["novel_id", "volume_number"]
    )


def downgrade() -> None:
    op.drop_index("ix_volume_novel_number", table_name="volumes")
    op.drop_index("ix_chapter_novel_number", table_name="chapters")
