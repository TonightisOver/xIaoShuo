"""add task_checkpoints table with legacy backfill

Revision ID: 20260721d
Revises: 20260721c
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721d_task_checkpoints"
down_revision: str | Sequence[str] | None = "20260721c_chapter_side_effect"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "task_checkpoints",
        sa.Column(
            "task_id",
            sa.String(100),
            sa.ForeignKey("tasks.task_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("novel_id", sa.String(100), nullable=False, index=True),
        sa.Column("operation_id", sa.String(200), nullable=False, index=True),
        sa.Column("current_stage", sa.String(40), nullable=False),
        sa.Column("volume_number", sa.Integer, nullable=True),
        sa.Column("chapter_number", sa.Integer, nullable=True),
        sa.Column(
            "last_completed_volume",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "last_completed_chapter",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column("active_version_number", sa.Integer, nullable=True),
        sa.Column(
            "checkpoint_version",
            sa.Integer,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "attempt_number", sa.Integer, nullable=False, server_default="0"
        ),
        sa.Column(
            "last_event_sequence",
            sa.BigInteger,
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "status", sa.String(20), nullable=False, server_default="pending"
        ),
        sa.Column(
            "pause_requested",
            sa.Boolean,
            nullable=False,
            server_default=sa.false(),
        ),
        sa.Column("failure_category", sa.String(30), nullable=True),
        sa.Column(
            "recoverable", sa.Boolean, nullable=False, server_default=sa.true()
        ),
        sa.Column("failure_detail", sa.JSON, nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    # 历史任务回填（B24 修正）：不尝试把自由格式的 progress.current_stage 映射到
    # 新状态机（会写入 'chapter_generation' 等非法值导致恢复时状态机不认识）。
    # 策略：历史任务一律回填 current_stage='task_end' + recoverable=false
    # + failure_category='unrecoverable'（completed 除外），表示"legacy 任务
    # 不自动从 checkpoint 恢复"，只保留诊断。真正需要续作的历史任务由用户显式
    # /retry（会重建 checkpoint）。checkpoint.status 只写合法枚举，非法的
    # Task.status（cancelled/partially_completed/...）统一归一化为 'failed'。
    op.execute(
        """
        INSERT INTO task_checkpoints (
            task_id, novel_id, operation_id, current_stage,
            status, recoverable, failure_category, updated_at
        )
        SELECT
            t.task_id,
            COALESCE(t.novel_id, ''),
            COALESCE(t.operation_id, t.task_id),
            'task_end',
            CASE
                WHEN t.status = 'completed' THEN 'succeeded'
                WHEN t.status = 'running' THEN 'pending'
                WHEN t.status IN ('pending', 'paused', 'failed') THEN t.status
                ELSE 'failed'
            END,
            false,
            CASE WHEN t.status = 'completed' THEN NULL ELSE 'unrecoverable' END,
            NOW()
        FROM tasks t
        WHERE t.task_type IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM task_checkpoints c WHERE c.task_id = t.task_id
          )
        """
    )


def downgrade() -> None:
    op.drop_table("task_checkpoints")
