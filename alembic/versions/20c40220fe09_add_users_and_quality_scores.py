"""add_users_and_quality_scores

Revision ID: 20c40220fe09
Revises: 20260604_career_tables
Create Date: 2026-07-04 22:16:53.504529

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '20c40220fe09'
down_revision: Union[str, Sequence[str], None] = '20260604_career_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(length=100), nullable=False),
        sa.Column("hashed_password", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # 2. Create user_sessions table
    op.create_table(
        "user_sessions",
        sa.Column("session_token", sa.String(length=100), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_sessions_session_token", "user_sessions", ["session_token"], unique=False)

    # 3. Add owner_id to novels table
    op.add_column("novels", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_novels_owner_id",
        "novels",
        "users",
        ["owner_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # 4. Add quality_scores to chapter_versions table
    op.add_column("chapter_versions", sa.Column("quality_scores", sa.JSON(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Drop quality_scores column
    op.drop_column("chapter_versions", "quality_scores")

    # 2. Drop owner_id FK and column
    op.drop_constraint("fk_novels_owner_id", "novels", type_="foreignkey")
    op.drop_column("novels", "owner_id")

    # 3. Drop user_sessions table
    op.drop_index("ix_user_sessions_session_token", table_name="user_sessions")
    op.drop_table("user_sessions")

    # 4. Drop users table
    op.drop_index("ix_users_username", table_name="users")
    op.drop_table("users")

