"""initial_schema

Revision ID: e45b29ed4fe6
Revises: 
Create Date: 2026-05-16 13:55:44.504025

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e45b29ed4fe6'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('idea', sa.Text(), nullable=False),
        sa.Column('novel_type', sa.String(length=50), nullable=False),
        sa.Column('target_words', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('estimated_completion', sa.DateTime(timezone=True), nullable=True),
        sa.Column('progress', sa.JSON(), nullable=True),
        sa.Column('result', sa.JSON(), nullable=True),
        sa.Column('errors', sa.JSON(), server_default='[]', nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('task_id')
    )
    op.create_index('idx_tasks_task_id', 'tasks', ['task_id'])
    op.create_index('idx_tasks_status', 'tasks', ['status'])
    op.create_index('idx_tasks_created_at', 'tasks', ['created_at'], postgresql_ops={'created_at': 'DESC'})


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_tasks_created_at', table_name='tasks')
    op.drop_index('idx_tasks_status', table_name='tasks')
    op.drop_index('idx_tasks_task_id', table_name='tasks')
    op.drop_table('tasks')
