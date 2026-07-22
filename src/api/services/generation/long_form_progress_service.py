"""百万字长篇进度追踪服务

负责管理长篇生成任务的进度追踪，包括卷级状态管理和全局进度汇总。
"""

from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.models.db_models import LongFormProgress, Novel
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)

# Singleton instance
_progress_service: "LongFormProgressService | None" = None


class LongFormProgressService:
    """百万字长篇进度追踪服务"""

    def __init__(self, session: AsyncSession | None = None) -> None:
        self._session = session

    async def _get_session(self) -> AsyncSession:
        """Get database session (injected or new)."""
        if self._session:
            return self._session
        # Return a context manager session
        return None  # Will use get_db_session() directly

    async def initialize_progress(
        self,
        novel_id: str,
        total_volumes: int,
        chapters_per_volume: int,
    ) -> list[dict[str, Any]]:
        """Initialize progress tracking for a long-form novel.

        Args:
            novel_id: Novel ID
            total_volumes: Total number of volumes
            chapters_per_volume: Chapters per volume

        Returns:
            List of created progress records as dicts
        """
        async with get_db_session() as session:
            existing_result = await session.execute(
                select(LongFormProgress)
                .where(LongFormProgress.novel_id == novel_id)
                .with_for_update()
            )
            existing_by_volume = {
                row.volume_number: row
                for row in existing_result.scalars().all()
            }
            records = []
            global_chapter_start = 1

            for vol_num in range(1, total_volumes + 1):
                chapter_end = global_chapter_start + chapters_per_volume - 1
                existing = existing_by_volume.get(vol_num)
                if existing is None:
                    existing = LongFormProgress(
                        novel_id=novel_id,
                        volume_number=vol_num,
                        status="pending",
                        chapter_start=global_chapter_start,
                        chapter_end=chapter_end,
                        chapters_completed=0,
                        errors=[],
                    )
                    session.add(existing)
                records.append({
                    "volume_number": vol_num,
                    "status": existing.status,
                    "chapter_start": existing.chapter_start,
                    "chapter_end": existing.chapter_end,
                })
                global_chapter_start = chapter_end + 1

            logger.info(
                "long_form_progress_initialized",
                novel_id=novel_id,
                total_volumes=total_volumes,
            )
            return records

    async def update_volume_status(
        self,
        novel_id: str,
        volume_number: int,
        status: str,
        chapters_completed: int | None = None,
        current_chapter: int | None = None,
        quality_report: dict | None = None,
        filler_report: dict | None = None,
        errors: list[str] | None = None,
    ) -> None:
        """Update progress for a specific volume.

        Args:
            novel_id: Novel ID
            volume_number: Volume number
            status: New status (pending/generating/completed/failed/paused)
            chapters_completed: Number of completed chapters
            current_chapter: Current chapter being generated
            quality_report: Quality report data
            filler_report: Filler detection report
            errors: Error messages to append
        """
        async with get_db_session() as session:
            stmt = select(LongFormProgress).where(
                LongFormProgress.novel_id == novel_id,
                LongFormProgress.volume_number == volume_number,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if not record:
                logger.warning(
                    "progress_record_not_found",
                    novel_id=novel_id,
                    volume_number=volume_number,
                )
                return

            record.status = status
            if chapters_completed is not None:
                record.chapters_completed = chapters_completed
            if current_chapter is not None:
                record.current_chapter = current_chapter
            if quality_report is not None:
                record.quality_report = quality_report
            if filler_report is not None:
                record.filler_report = filler_report
            if errors:
                existing_errors = record.errors or []
                record.errors = existing_errors + errors

            if status == "completed":
                from datetime import UTC, datetime
                record.completed_at = datetime.now(UTC)

            logger.info(
                "volume_status_updated",
                novel_id=novel_id,
                volume_number=volume_number,
                status=status,
            )

    async def get_progress(self, novel_id: str) -> dict[str, Any]:
        """Get overall progress for a long-form novel.

        Args:
            novel_id: Novel ID

        Returns:
            Progress summary dict
        """
        async with get_db_session() as session:
            # Get novel info
            stmt = select(Novel).where(Novel.novel_id == novel_id)
            result = await session.execute(stmt)
            novel = result.scalar_one_or_none()

            if not novel:
                return {"error": "Novel not found"}

            # Get all progress records
            stmt = select(LongFormProgress).where(
                LongFormProgress.novel_id == novel_id
            ).order_by(LongFormProgress.volume_number)
            result = await session.execute(stmt)
            records = result.scalars().all()

            total_volumes = novel.total_volumes or len(records)
            completed_volumes = sum(1 for r in records if r.status == "completed")
            chapters_completed = sum(r.chapters_completed for r in records)
            total_word_count = sum(
                (r.quality_report or {}).get("total_word_count", 0)
                for r in records
                if r.quality_report
            )

            # Estimate total chapters
            chapters_per_vol = novel.chapters_per_volume or 40
            total_chapters = total_volumes * chapters_per_vol

            # Calculate progress percentage
            if novel.target_words > 0:
                progress_percentage = min(100.0, (total_word_count / novel.target_words) * 100)
            else:
                progress_percentage = (chapters_completed / max(total_chapters, 1)) * 100

            # Find current volume
            current_volume = None
            for r in records:
                if r.status == "generating":
                    current_volume = r.volume_number
                    break

            # Collect errors
            all_errors = []
            for r in records:
                if r.errors:
                    all_errors.extend(r.errors)

            # Volume details
            volume_details = []
            for r in records:
                vol_info = {
                    "volume_number": r.volume_number,
                    "status": r.status,
                    "chapter_start": r.chapter_start,
                    "chapter_end": r.chapter_end,
                    "chapters_completed": r.chapters_completed,
                    "current_chapter": r.current_chapter,
                }
                if r.quality_report:
                    vol_info["avg_quality_score"] = r.quality_report.get("avg_quality_score")
                volume_details.append(vol_info)

            return {
                "novel_id": novel_id,
                "total_volumes": total_volumes,
                "completed_volumes": completed_volumes,
                "current_volume": current_volume,
                "total_chapters": total_chapters,
                "chapters_completed": chapters_completed,
                "total_word_count": total_word_count,
                "target_words": novel.target_words,
                "progress_percentage": round(progress_percentage, 2),
                "volume_details": volume_details,
                "errors": all_errors,
            }

    async def get_volume_progress(
        self, novel_id: str, volume_number: int
    ) -> dict[str, Any] | None:
        """Get progress for a specific volume.

        Args:
            novel_id: Novel ID
            volume_number: Volume number

        Returns:
            Volume progress dict or None
        """
        async with get_db_session() as session:
            stmt = select(LongFormProgress).where(
                LongFormProgress.novel_id == novel_id,
                LongFormProgress.volume_number == volume_number,
            )
            result = await session.execute(stmt)
            record = result.scalar_one_or_none()

            if not record:
                return None

            return {
                "novel_id": novel_id,
                "volume_number": record.volume_number,
                "status": record.status,
                "chapter_start": record.chapter_start,
                "chapter_end": record.chapter_end,
                "chapters_completed": record.chapters_completed,
                "current_chapter": record.current_chapter,
                "quality_report": record.quality_report,
                "filler_report": record.filler_report,
                "errors": record.errors or [],
                "created_at": record.created_at.isoformat() if record.created_at else None,
                "completed_at": record.completed_at.isoformat() if record.completed_at else None,
            }


def get_long_form_progress_service(
    session: AsyncSession | None = None,
) -> LongFormProgressService:
    """Get or create LongFormProgressService singleton.

    Args:
        session: Optional database session

    Returns:
        LongFormProgressService instance
    """
    global _progress_service
    if _progress_service is None or session is not None:
        _progress_service = LongFormProgressService(session=session)
    return _progress_service
