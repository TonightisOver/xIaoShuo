"""make long-form progress initialization idempotent

Revision ID: 20260722a
Revises: 20260721e_creative_control
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260722a_lfp_unique"
down_revision: str | Sequence[str] | None = "20260721e_creative_control"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 历史重复行优先保留 completed / 完成章数较多 / 最近更新的一条。
    op.execute(
        """
        DELETE FROM long_form_progress
        WHERE id IN (
            SELECT id FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY novel_id, volume_number
                           ORDER BY (status = 'completed') DESC,
                                    chapters_completed DESC,
                                    updated_at DESC NULLS LAST,
                                    id DESC
                       ) AS row_number
                FROM long_form_progress
            ) ranked
            WHERE row_number > 1
        )
        """
    )
    op.drop_index("ix_lfp_novel_volume", table_name="long_form_progress")
    op.create_index(
        "ix_lfp_novel_volume",
        "long_form_progress",
        ["novel_id", "volume_number"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_lfp_novel_volume", table_name="long_form_progress")
    op.create_index(
        "ix_lfp_novel_volume",
        "long_form_progress",
        ["novel_id", "volume_number"],
        unique=False,
    )
