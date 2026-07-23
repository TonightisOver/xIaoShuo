"""backfill controls and baseline snapshots for existing blueprints

Revision ID: 20260723a
Revises: 20260722b_artifact_locks
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260723a_blueprint_backfill"
down_revision: str | Sequence[str] | None = "20260722b_artifact_locks"
branch_labels = None
depends_on = None

_MARKER = "20260723a_blueprint_backfill"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO artifact_controls (
            novel_id, artifact_type, artifact_id, control_status,
            locked, version, stage, generation_meta, awaiting_review
        )
        SELECT
            bp.novel_id,
            'blueprint',
            CAST(bp.chapter_number AS VARCHAR),
            'generated',
            false,
            1,
            6,
            '{{"backfilled_by":"{_MARKER}"}}',
            false
        FROM chapter_blueprints AS bp
        WHERE bp.is_active = true
          AND NOT EXISTS (
              SELECT 1
              FROM artifact_controls AS ac
              WHERE ac.novel_id = bp.novel_id
                AND ac.artifact_type = 'blueprint'
                AND ac.artifact_id = CAST(bp.chapter_number AS VARCHAR)
          )
        """
    )
    op.execute(
        f"""
        INSERT INTO artifact_versions (
            novel_id, artifact_type, artifact_id, version_number,
            content_snapshot, source, operation_id, is_active, created_at
        )
        SELECT
            bp.novel_id,
            'blueprint',
            CAST(bp.chapter_number AS VARCHAR),
            COALESCE(bp.version_number, 1),
            json_build_object(
                'chapter_type', bp.chapter_type,
                'plot_goal', bp.plot_goal,
                'hook_design', bp.hook_design,
                'foreshadow_actions', COALESCE(bp.foreshadow_actions, '[]'::json),
                'cliffhanger', bp.cliffhanger,
                'pacing_target', bp.pacing_target,
                'key_characters', COALESCE(bp.key_characters, '[]'::json),
                'word_target', bp.word_target
            ),
            'baseline',
            '{_MARKER}',
            true,
            bp.created_at
        FROM chapter_blueprints AS bp
        WHERE bp.is_active = true
          AND NOT EXISTS (
              SELECT 1
              FROM artifact_versions AS av
              WHERE av.novel_id = bp.novel_id
                AND av.artifact_type = 'blueprint'
                AND av.artifact_id = CAST(bp.chapter_number AS VARCHAR)
          )
        """
    )


def downgrade() -> None:
    op.execute(
        f"""
        DELETE FROM artifact_versions
        WHERE artifact_type = 'blueprint'
          AND operation_id = '{_MARKER}'
        """
    )
    op.execute(
        f"""
        DELETE FROM artifact_controls
        WHERE artifact_type = 'blueprint'
          AND version = 1
          AND generation_meta->>'backfilled_by' = '{_MARKER}'
        """
    )
