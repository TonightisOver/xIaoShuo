"""章节剧情分析路由"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from src.core.llm.client import get_llm_client

router = APIRouter(prefix="/api/v1/projects", tags=["chapter-analysis"])


@router.get("/{novel_id}/chapters/{chapter_number}/analysis")
async def get_chapter_analysis(novel_id: str, chapter_number: int):
    """Analyze chapter content and return structured annotations."""
    from src.api.services.chapter_analysis_service import (
        analyze_chapter_content,
        get_analysis_summary,
    )
    from src.api.services.novel_manager import get_novel_manager

    manager = get_novel_manager()
    chapter = await manager.get_chapter(novel_id, chapter_number)
    if not chapter:
        raise HTTPException(status_code=404, detail="Chapter not found")

    content = chapter.get("content", "")
    if not content:
        raise HTTPException(
            status_code=400,
            detail="Chapter has no content to analyze",
        )

    client = get_llm_client()
    annotations = await analyze_chapter_content(client, content)
    summary = get_analysis_summary(annotations)

    return {
        "novel_id": novel_id,
        "chapter_number": chapter_number,
        "title": chapter.get("title", ""),
        "word_count": chapter.get("word_count", 0),
        "annotations": annotations,
        "summary": summary,
    }
