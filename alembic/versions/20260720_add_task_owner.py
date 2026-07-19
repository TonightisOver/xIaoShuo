"""add task owner

Revision ID: 20260720_task_owner
Revises: d7e4f9a2c1b0
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260720_task_owner"
down_revision: str | Sequence[str] | None = "d7e4f9a2c1b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_owner_id", "tasks", "users", ["owner_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tasks_owner_id", "tasks", ["owner_id"])
    op.execute(
        """
        UPDATE tasks AS t
        SET owner_id = n.owner_id
        FROM novels AS n
        WHERE t.novel_id = n.novel_id
          AND t.owner_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_owner_id", table_name="tasks")
    op.drop_constraint("fk_tasks_owner_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "owner_id")
