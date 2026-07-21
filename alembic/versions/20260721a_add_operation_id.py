"""add tasks.operation_id with dedup partial unique index

Revision ID: 20260721a
Revises: 20260720_task_owner
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721a_operation_id"
down_revision: str | Sequence[str] | None = "20260720_task_owner"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("operation_id", sa.String(200), nullable=True))
    # 历史回填：按业务格式 {novel_id}:{task_type} 推导，而非直接用 task_id（B23）。
    # 无 novel_id 的历史任务用 task_id 兜底（多为短篇早期数据，唯一性由 task_id 保证）。
    op.execute(
        """
        UPDATE tasks SET operation_id = CASE
            WHEN novel_id IS NOT NULL AND task_type IS NOT NULL
                THEN novel_id || ':' || task_type
            WHEN novel_id IS NOT NULL
                THEN novel_id || ':' || 'legacy'
            ELSE task_id
        END
        """
    )
    # 回填后处理历史重复：同一 (novel_id, task_type) 有多个非终态历史行时，
    # 给冲突行追加 task_id 后缀，避免部分唯一索引创建失败。
    op.execute(
        """
        UPDATE tasks t SET operation_id = t.operation_id || ':' || t.task_id
        WHERE t.status NOT IN ('completed','failed','cancelled')
          AND EXISTS (
            SELECT 1 FROM tasks t2
            WHERE t2.operation_id = t.operation_id
              AND t2.status NOT IN ('completed','failed','cancelled')
              AND t2.task_id <> t.task_id
          )
        """
    )
    op.alter_column("tasks", "operation_id", nullable=False)
    op.create_index(
        "uq_tasks_operation_active",
        "tasks",
        ["operation_id"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('completed', 'failed', 'cancelled')"),
    )


def downgrade() -> None:
    op.drop_index("uq_tasks_operation_active", table_name="tasks")
    op.drop_column("tasks", "operation_id")
