# tests/unit/test_change060_volume_quality_report.py
import pytest

from src.api.services.long_form_generation_helpers import generate_volume_quality_report


@pytest.mark.asyncio
async def test_failed_chapter_produces_warning_not_fake_score():
    """传入 generation_failed=True 的章节，报告不应给 0.7 假分，而应标记 unverified 并告警。"""
    chapters = [
        {
            "chapter": 1,
            "title": "第一章",
            "content": "正常内容，足够长，足够长，足够长，足够长，足够长，足够长，足够长。",
            "word_count": 30,
        },
        {
            "chapter": 2,
            "title": "第二章",
            "content": "[章节生成失败: timeout]",
            "word_count": 0,
            "generation_failed": True,
        },
    ]
    report = await generate_volume_quality_report(
        novel_id="novel-1", volume_number=1, chapters=chapters
    )

    # 不能再是固定 0.7
    assert report["avg_quality_score"] != 0.7 or report.get("has_unverified")
    # 失败章节必须出现在告警或 unverified 列表
    assert report["warnings"], "失败章节应产生告警"
    unverified = [c for c in report.get("unverified_chapters", [])]
    assert any(c.get("chapter") == 2 for c in unverified + report["warnings"])


@pytest.mark.asyncio
async def test_normal_chapters_no_false_alarm():
    """正常章节不应被误报为灌水或停滞。"""
    chapters = [
        {"chapter": i, "title": f"第{i}章", "content": "内容" * 500, "word_count": 1000}
        for i in range(1, 4)
    ]
    report = await generate_volume_quality_report(
        novel_id="novel-1", volume_number=1, chapters=chapters
    )
    assert report["chapter_count"] == 3
    assert not report.get("unverified_chapters")
    # 短章节不应被无脑标为灌水（1000 字不算灌水）
    assert not report["filler_chapters"] or all(
        c.get("chapter") not in [1, 2, 3] for c in report["filler_chapters"]
    )
