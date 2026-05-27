"""质量评估公共模块"""

from src.core.quality.evaluator import (
    EVALUATION_PROMPT,
    QUALITY_DIMENSIONS,
    QualityResult,
    evaluate_chapter_quality,
)

__all__ = [
    "EVALUATION_PROMPT",
    "QUALITY_DIMENSIONS",
    "QualityResult",
    "evaluate_chapter_quality",
]
