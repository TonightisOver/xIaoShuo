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
    # 早期 users 迁移未包含 ORM 已长期使用的管理员标记；create_all 测试曾掩盖
    # 该漂移。IF NOT EXISTS 兼容已由应用启动流程补齐此列的现有部署。
    op.execute(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS "
        "is_admin BOOLEAN NOT NULL DEFAULT false"
    )
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
    # is_admin 可能在旧部署中已由 create_all 创建；降级时保留，避免误删既有数据。
