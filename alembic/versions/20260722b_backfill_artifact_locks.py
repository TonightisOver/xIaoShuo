"""backfill artifact lock boolean from legacy control status

Revision ID: 20260722b
Revises: 20260722a_lfp_unique
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260722b_artifact_locks"
down_revision: str | Sequence[str] | None = "20260722a_lfp_unique"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "UPDATE artifact_controls SET locked = true "
        "WHERE control_status = 'locked' AND locked = false"
    )


def downgrade() -> None:
    # 无法区分历史不一致行与迁移前已正确锁定的行，降级不反向清锁。
    pass
