"""add persistent task queue fields

Revision ID: d7e4f9a2c1b0
Revises: c3d8e1f7a2b4
Create Date: 2026-07-19
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "d7e4f9a2c1b0"
down_revision: str | None = "c3d8e1f7a2b4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tasks", sa.Column("task_type", sa.String(length=50), nullable=True)
    )
    op.add_column("tasks", sa.Column("task_payload", sa.JSON(), nullable=True))
    op.add_column(
        "tasks", sa.Column("queue_state", sa.String(length=20), nullable=True)
    )
    op.add_column(
        "tasks",
        sa.Column(
            "attempt_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )
    op.add_column(
        "tasks",
        sa.Column(
            "max_attempts",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "tasks",
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks", sa.Column("lease_owner", sa.String(length=120), nullable=True)
    )
    op.add_column(
        "tasks",
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("heartbeat_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_tasks_queue_ready",
        "tasks",
        ["queue_state", "available_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_queue_ready", table_name="tasks")
    op.drop_column("tasks", "heartbeat_at")
    op.drop_column("tasks", "lease_expires_at")
    op.drop_column("tasks", "lease_owner")
    op.drop_column("tasks", "available_at")
    op.drop_column("tasks", "max_attempts")
    op.drop_column("tasks", "attempt_count")
    op.drop_column("tasks", "queue_state")
    op.drop_column("tasks", "task_payload")
    op.drop_column("tasks", "task_type")

