"""add chapter_versions.idempotency_key + single-active partial unique index

Revision ID: 20260721b
Revises: 20260721a

停服窗口：多活跃版本清理 + 部分唯一索引创建要求停止 worker
（TASK_WORKER_ENABLED=false 或维护窗口），避免清理与加索引之间
有 worker 按旧逻辑写入新的 is_active 行导致 CREATE UNIQUE INDEX 失败。
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260721b_chapter_version_idem"
down_revision: str | Sequence[str] | None = "20260721a_operation_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chapter_versions",
        sa.Column("idempotency_key", sa.String(200), nullable=True),
    )
    # 清理历史多活跃版本：每章保留"当前应视为活跃"的版本，其余置 inactive。
    # 用 (version_number DESC, id DESC) 而非 MAX(id)——version_number 是业务版本序，
    # 更贴近"最新版本"语义；id 仅作同版本号的 tiebreak（B22 修正）。
    op.execute(
        """
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY novel_id, chapter_number
                       ORDER BY version_number DESC, id DESC
                   ) AS rn
            FROM chapter_versions
            WHERE is_active = true
        )
        UPDATE chapter_versions cv SET is_active = false
        FROM ranked r
        WHERE cv.id = r.id AND r.rn > 1
        """
    )
    # 补激活：若某章 0 个 active（历史 bug），激活其最高 version_number 版本，
    # 避免正文显示空白。
    op.execute(
        """
        WITH need_active AS (
            SELECT novel_id, chapter_number
            FROM chapter_versions
            GROUP BY novel_id, chapter_number
            HAVING SUM(CASE WHEN is_active THEN 1 ELSE 0 END) = 0
        ), pick AS (
            SELECT DISTINCT ON (cv.novel_id, cv.chapter_number) cv.id
            FROM chapter_versions cv
            JOIN need_active na ON na.novel_id = cv.novel_id
                               AND na.chapter_number = cv.chapter_number
            ORDER BY cv.novel_id, cv.chapter_number,
                     cv.version_number DESC, cv.id DESC
        )
        UPDATE chapter_versions cv SET is_active = true
        FROM pick p WHERE cv.id = p.id
        """
    )
    op.create_index(
        "uq_chapter_version_active",
        "chapter_versions",
        ["novel_id", "chapter_number"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "uq_chapter_version_idem",
        "chapter_versions",
        ["novel_id", "chapter_number", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_chapter_version_idem", table_name="chapter_versions")
    op.drop_index("uq_chapter_version_active", table_name="chapter_versions")
    op.drop_column("chapter_versions", "idempotency_key")
