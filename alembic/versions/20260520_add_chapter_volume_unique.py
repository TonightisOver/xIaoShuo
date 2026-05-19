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
    op.create_unique_constraint(
        "uq_chapter_novel_number", "chapters", ["novel_id", "chapter_number"]
    )
    op.create_unique_constraint(
        "uq_volume_novel_number", "volumes", ["novel_id", "volume_number"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_volume_novel_number", "volumes", type_="unique")
    op.drop_constraint("uq_chapter_novel_number", "chapters", type_="unique")
