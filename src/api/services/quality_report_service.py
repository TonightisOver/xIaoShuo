"""质量趋势报告生成服务

负责生成卷级和全书级的质量趋势报告，包括8维度评分分析、
连续低分检测、主线推进效率等。
"""

from typing import Any

import structlog
from sqlalchemy import select

from src.api.models.db_models import Chapter, Volume
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)

# Quality dimensions
QUALITY_DIMENSIONS = [
    "advancement",
    "character_consistency",
    "world_consistency",
    "pacing",
    "conflict",
    "foreshadowing",
    "dialogue_quality",
    "emotional_impact",
]

# Warning thresholds
LOW_SCORE_THRESHOLD = 0.5
CONSECUTIVE_LOW_THRESHOLD = 3
FILLER_CHAPTER_THRESHOLD = 0.3  # quality_score below this = likely filler


class QualityReportService:
    """质量趋势报告生成服务"""

    async def generate_novel_quality_report(
        self, novel_id: str
    ) -> dict[str, Any]:
        """Generate complete quality report for a novel.

        Args:
            novel_id: Novel ID

        Returns:
            Quality report dict
        """
        async with get_db_session() as session:
            # Get volumes
            vol_stmt = select(Volume).where(
                Volume.novel_id == novel_id
            ).order_by(Volume.volume_number)
            vol_result = await session.execute(vol_stmt)
            volumes = vol_result.scalars().all()

            total_volumes = len(volumes)
            completed_volumes = sum(1 for v in volumes if v.status == "completed")

            # Get all chapters with quality scores
            ch_stmt = select(Chapter).where(
                Chapter.novel_id == novel_id
            ).order_by(Chapter.chapter_number)
            ch_result = await session.execute(ch_stmt)
            chapters = ch_result.scalars().all()

            # Build volume reports
            volume_reports = []
            all_scores: dict[str, list[float]] = {dim: [] for dim in QUALITY_DIMENSIONS}

            for vol in volumes:
                vol_chapters = [c for c in chapters if c.volume_number == vol.volume_number]
                vol_report = self._build_volume_report(vol.volume_number, vol_chapters)
                volume_reports.append(vol_report)

                # Accumulate global scores
                for dim in QUALITY_DIMENSIONS:
                    scores = vol_report["avg_scores"].get(dim, 0)
                    if scores > 0:
                        all_scores[dim].append(scores)

            # Calculate overall averages
            overall_avg = {}
            for dim in QUALITY_DIMENSIONS:
                dim_scores = all_scores[dim]
                overall_avg[dim] = round(sum(dim_scores) / len(dim_scores), 3) if dim_scores else 0.0

            # Get foreshadow summary
            foreshadow_summary = self._get_foreshadow_summary(chapters)

            # Get character appearance
            character_appearance = self._get_character_appearance(chapters)

            return {
                "novel_id": novel_id,
                "total_volumes": total_volumes,
                "completed_volumes": completed_volumes,
                "overall_avg_scores": overall_avg,
                "volume_reports": volume_reports,
                "foreshadow_summary": foreshadow_summary,
                "character_appearance": character_appearance,
            }

    def _build_volume_report(
        self, volume_number: int, chapters: list[Chapter]
    ) -> dict[str, Any]:
        """Build quality report for a single volume.

        Args:
            volume_number: Volume number
            chapters: List of Chapter objects

        Returns:
            Volume quality report dict
        """
        if not chapters:
            return {
                "volume_number": volume_number,
                "chapter_count": 0,
                "total_word_count": 0,
                "avg_scores": {},
                "score_trends": {},
                "warnings": [],
                "filler_chapters": [],
                "stalled_chapters": [],
            }

        total_word_count = sum(c.word_count for c in chapters)

        # Collect scores from chapter versions
        score_trends: dict[str, list[float]] = {dim: [] for dim in QUALITY_DIMENSIONS}
        chapter_scores: list[dict[str, float]] = []

        for ch in chapters:
            # Try to get quality score from chapter version
            ch_score = self._extract_chapter_scores(ch)
            chapter_scores.append(ch_score)
            for dim in QUALITY_DIMENSIONS:
                score_trends[dim].append(ch_score.get(dim, 0.0))

        # Calculate averages
        avg_scores = {}
        for dim in QUALITY_DIMENSIONS:
            dim_scores = [cs.get(dim, 0.0) for cs in chapter_scores]
            avg_scores[dim] = round(
                sum(dim_scores) / len(dim_scores) if dim_scores else 0.0, 3
            )

        # Detect warnings
        warnings = self._detect_warnings(chapters, chapter_scores, avg_scores)

        # Detect filler chapters
        filler_chapters = self._detect_filler_chapters(chapters, chapter_scores)

        # Detect stalled chapters
        stalled_chapters = self._detect_stalled_chapters(chapter_scores)

        return {
            "volume_number": volume_number,
            "chapter_count": len(chapters),
            "total_word_count": total_word_count,
            "avg_scores": avg_scores,
            "score_trends": score_trends,
            "warnings": warnings,
            "filler_chapters": filler_chapters,
            "stalled_chapters": stalled_chapters,
        }

    def _extract_chapter_scores(self, chapter: Chapter) -> dict[str, float]:
        """Extract quality scores from a chapter.

        For now, returns default scores. In production, would query ChapterVersion
        for quality_score and kg_conflicts.
        """
        # Default scores - in production would parse from ChapterVersion
        return {dim: 0.7 for dim in QUALITY_DIMENSIONS}

    def _detect_warnings(
        self,
        chapters: list[Chapter],
        chapter_scores: list[dict[str, float]],
        avg_scores: dict[str, float],
    ) -> list[str]:
        """Detect quality warnings."""
        warnings = []

        # Check for overall low scores
        for dim in QUALITY_DIMENSIONS:
            avg = avg_scores.get(dim, 0)
            if 0 < avg < LOW_SCORE_THRESHOLD:
                warnings.append(
                    f"维度 '{dim}' 均分偏低: {avg:.2f} < {LOW_SCORE_THRESHOLD}"
                )

        # Check for consecutive low advancement scores
        advancement_scores = [cs.get("advancement", 0) for cs in chapter_scores]
        consecutive_low = 0
        for score in advancement_scores:
            if score < LOW_SCORE_THRESHOLD:
                consecutive_low += 1
                if consecutive_low >= CONSECUTIVE_LOW_THRESHOLD:
                    warnings.append(
                        f"连续 {consecutive_low} 章主线推进分数低于 {LOW_SCORE_THRESHOLD}"
                    )
                    consecutive_low = 0
            else:
                consecutive_low = 0

        # Check word count consistency
        word_counts = [c.word_count for c in chapters]
        if word_counts:
            avg_words = sum(word_counts) / len(word_counts)
            for i, wc in enumerate(word_counts):
                if wc < avg_words * 0.5:
                    warnings.append(
                        f"第 {i + 1} 章字数异常偏少: {wc} 字 (平均 {int(avg_words)} 字)"
                    )

        return warnings

    def _detect_filler_chapters(
        self,
        chapters: list[Chapter],
        chapter_scores: list[dict[str, float]],
    ) -> list[int]:
        """Detect potential filler chapters based on low quality scores."""
        filler_chapters = []
        for i, (ch, scores) in enumerate(zip(chapters, chapter_scores)):
            overall = sum(scores.values()) / len(scores) if scores else 0
            if overall < FILLER_CHAPTER_THRESHOLD:
                filler_chapters.append(ch.chapter_number)
        return filler_chapters

    def _detect_stalled_chapters(
        self, chapter_scores: list[dict[str, float]]
    ) -> list[int]:
        """Detect chapters where main plot is stalled."""
        stalled = []
        for i, scores in enumerate(chapter_scores):
            advancement = scores.get("advancement", 0)
            if advancement < LOW_SCORE_THRESHOLD:
                stalled.append(i + 1)
        return stalled

    def _get_foreshadow_summary(self, chapters: list[Chapter]) -> dict[str, Any]:
        """Get foreshadow tracking summary from chapters."""
        # Simplified implementation - in production would parse StoryBible
        return {
            "total_planted": 0,
            "total_resolved": 0,
            "dangling_count": 0,
        }

    def _get_character_appearance(self, chapters: list[Chapter]) -> dict[str, Any]:
        """Get character appearance statistics."""
        # Simplified implementation - in production would parse chapter content
        return {
            "total_characters": 0,
            "appearance_frequency": {},
        }


_quality_report_service: QualityReportService | None = None


def get_quality_report_service() -> QualityReportService:
    """Get or create QualityReportService singleton."""
    global _quality_report_service
    if _quality_report_service is None:
        _quality_report_service = QualityReportService()
    return _quality_report_service
