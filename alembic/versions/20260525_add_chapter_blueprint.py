"""add_chapter_blueprint

Revision ID: 20260525_blueprint
Revises: 20260525_long_form
Create Date: 2026-05-25 16:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260525_blueprint"
down_revision: str | None = "20260525_long_form"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chapter_blueprints",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("novel_id", sa.String(100), nullable=False),
        sa.Column("chapter_number", sa.Integer(), nullable=False),
        sa.Column(
            "chapter_type",
            sa.String(30),
            nullable=False,
            server_default="main_advance",
        ),
        sa.Column("plot_goal", sa.Text(), nullable=False, server_default=""),
        sa.Column("hook_design", sa.Text(), nullable=False, server_default=""),
        sa.Column("foreshadow_actions", sa.JSON(), nullable=True),
        sa.Column("cliffhanger", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "pacing_target", sa.String(20), nullable=False, server_default="medium"
        ),
        sa.Column("key_characters", sa.JSON(), nullable=True),
        sa.Column(
            "word_target", sa.Integer(), nullable=False, server_default=sa.text("3000")
        ),
        sa.Column("rewrite_actions", sa.JSON(), nullable=True),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["novel_id"], ["novels.novel_id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_chapter_blueprints_novel_id", "chapter_blueprints", ["novel_id"]
    )
    op.create_index(
        "ix_blueprint_novel_chapter",
        "chapter_blueprints",
        ["novel_id", "chapter_number"],
    )
    op.create_unique_constraint(
        "uq_blueprint_novel_chapter_active",
        "chapter_blueprints",
        ["novel_id", "chapter_number", "is_active"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_blueprint_novel_chapter_active", "chapter_blueprints", type_="unique"
    )
    op.drop_index("ix_blueprint_novel_chapter", table_name="chapter_blueprints")
    op.drop_index("ix_chapter_blueprints_novel_id", table_name="chapter_blueprints")
    op.drop_table("chapter_blueprints")
