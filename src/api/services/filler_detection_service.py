"""注水检测服务

负责检测小说中的注水章节（填充内容、主线停滞等），
并提供处理建议。
"""

from typing import Any

import structlog
from sqlalchemy import select

from src.api.models.db_models import Chapter
from src.core.database import get_db_session
from src.core.quality.rules import run_l0_rules

logger = structlog.get_logger(__name__)

# Detection thresholds
LOW_QUALITY_THRESHOLD = 0.4  # Below this = likely filler
SHORT_CHAPTER_RATIO = 0.5  # Chapter < 50% of avg word count
REPEITIVE_CONTENT_THRESHOLD = 0.3  # Content similarity threshold


class FillerDetectionService:
    """注水检测服务"""

    async def detect_filler_chapters(
        self, novel_id: str
    ) -> dict[str, Any]:
        """Detect filler chapters in a novel.

        Args:
            novel_id: Novel ID

        Returns:
            Filler detection result dict
        """
        async with get_db_session() as session:
            # Get all chapters
            stmt = select(Chapter).where(
                Chapter.novel_id == novel_id
            ).order_by(Chapter.chapter_number)
            result = await session.execute(stmt)
            chapters = result.scalars().all()

            total_chapters = len(chapters)
            if total_chapters == 0:
                return {
                    "novel_id": novel_id,
                    "total_chapters": 0,
                    "filler_chapters": [],
                    "filler_ratio": 0.0,
                    "recommendations": [],
                }

            # Analyze each chapter
            filler_chapters = []
            avg_word_count = sum(c.word_count for c in chapters) / total_chapters

            for ch in chapters:
                filler_score = self._calculate_filler_score(ch, avg_word_count)
                if filler_score > 0.5:
                    filler_chapters.append({
                        "chapter_number": ch.chapter_number,
                        "title": ch.title,
                        "word_count": ch.word_count,
                        "filler_score": round(filler_score, 3),
                        "reasons": self._get_filler_reasons(ch, avg_word_count),
                    })

            filler_ratio = len(filler_chapters) / total_chapters if total_chapters > 0 else 0.0

            # Generate recommendations
            recommendations = self._generate_recommendations(
                filler_chapters, filler_ratio, total_chapters
            )

            return {
                "novel_id": novel_id,
                "total_chapters": total_chapters,
                "filler_chapters": filler_chapters,
                "filler_ratio": round(filler_ratio, 3),
                "recommendations": recommendations,
            }

    def _calculate_filler_score(
        self, chapter: Chapter, avg_word_count: float
    ) -> float:
        """Calculate filler score. 复用 L0 规则门禁的重复/句式/字数检测。"""
        content = chapter.content or ""
        l0 = run_l0_rules(
            content=content,
            word_count=chapter.word_count,
            avg_word_count=avg_word_count,
            chapter_outline=None,
            chapter_number=chapter.chapter_number,
        )
        return l0.get("filler_score", 0.0)

    def _get_filler_reasons(
        self, chapter: Chapter, avg_word_count: float
    ) -> list[str]:
        """Get reasons why a chapter is flagged as filler."""
        reasons = []

        if avg_word_count > 0:
            word_ratio = chapter.word_count / avg_word_count
            if word_ratio < SHORT_CHAPTER_RATIO:
                reasons.append(
                    f"字数过少: {chapter.word_count}字 (平均{int(avg_word_count)}字的{word_ratio:.0%})"
                )

        if chapter.chapter_type == "filler":
            reasons.append("章节类型标记为 'filler'")

        if chapter.word_count < 1000:
            reasons.append(f"字数极低: {chapter.word_count}字")

        return reasons

    def _generate_recommendations(
        self,
        filler_chapters: list[dict[str, Any]],
        filler_ratio: float,
        total_chapters: int,
    ) -> list[str]:
        """Generate recommendations for handling filler chapters."""
        recommendations = []

        if filler_ratio > 0.2:
            recommendations.append(
                f"注水比例较高 ({filler_ratio:.0%})，建议对以下章节进行重写或删除"
            )

        if len(filler_chapters) > 5:
            recommendations.append(
                f"发现 {len(filler_chapters)} 个注水章节，建议批量重新生成"
            )

        for ch in filler_chapters[:5]:  # Top 5
            reasons = ch.get("reasons", [])
            if reasons:
                recommendations.append(
                    f"第{ch['chapter_number']}章: {'; '.join(reasons)}"
                )

        if not recommendations:
            recommendations.append("未发现明显注水章节，质量良好")

        return recommendations


_filler_detection_service: FillerDetectionService | None = None


def get_filler_detection_service() -> FillerDetectionService:
    """Get or create FillerDetectionService singleton."""
    global _filler_detection_service
    if _filler_detection_service is None:
        _filler_detection_service = FillerDetectionService()
    return _filler_detection_service
