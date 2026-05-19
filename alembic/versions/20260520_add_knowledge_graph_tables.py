"""add_knowledge_graph_tables

Revision ID: kg_20260520
Revises: 20260519_add_status_indexes
Create Date: 2026-05-20 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "kg_20260520"
down_revision: Union[str, Sequence[str], None] = "20260519_add_status_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create knowledge graph tables."""
    # knowledge_entities
    op.create_table(
        "knowledge_entities",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("novel_id", sa.String(100), sa.ForeignKey("novels.novel_id", ondelete="CASCADE"), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("aliases", sa.JSON, server_default="[]"),
        sa.Column("attributes", sa.JSON, server_default="{}"),
        sa.Column("first_chapter", sa.Integer, nullable=False),
        sa.Column("last_chapter", sa.Integer, nullable=True),
        sa.Column("source", sa.String(20), server_default="extracted"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_ke_novel_id", "knowledge_entities", ["novel_id"])
    op.create_index("idx_ke_novel_type", "knowledge_entities", ["novel_id", "entity_type"])
    op.create_index("idx_ke_novel_name", "knowledge_entities", ["novel_id", "name"])

    # knowledge_triples
    op.create_table(
        "knowledge_triples",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("novel_id", sa.String(100), sa.ForeignKey("novels.novel_id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject_id", sa.String(36), sa.ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("predicate", sa.String(100), nullable=False),
        sa.Column("object_id", sa.String(36), sa.ForeignKey("knowledge_entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_number", sa.Integer, nullable=False),
        sa.Column("confidence", sa.Float, server_default="1.0"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("metadata", sa.JSON, server_default="{}"),
        sa.Column("source", sa.String(20), server_default="extracted"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_kt_novel_id", "knowledge_triples", ["novel_id"])
    op.create_index("idx_kt_subject", "knowledge_triples", ["subject_id"])
    op.create_index("idx_kt_object", "knowledge_triples", ["object_id"])
    op.create_index("idx_kt_novel_chapter", "knowledge_triples", ["novel_id", "chapter_number"])
    op.create_index("idx_kt_novel_predicate", "knowledge_triples", ["novel_id", "predicate"])

    # knowledge_extraction_logs
    op.create_table(
        "knowledge_extraction_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("novel_id", sa.String(100), sa.ForeignKey("novels.novel_id", ondelete="CASCADE"), nullable=False),
        sa.Column("chapter_number", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("entities_count", sa.Integer, server_default="0"),
        sa.Column("triples_count", sa.Integer, server_default="0"),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_kel_novel_chapter", "knowledge_extraction_logs", ["novel_id", "chapter_number"], unique=True)


def downgrade() -> None:
    """Drop knowledge graph tables."""
    op.drop_table("knowledge_extraction_logs")
    op.drop_table("knowledge_triples")
    op.drop_table("knowledge_entities")
