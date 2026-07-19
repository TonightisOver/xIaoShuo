"""无卷退化重构的纯逻辑测试。

重构目标：删掉 _generate_chapters_batch，让按卷/按范围两调用方接入
generate_volume_chapters。差异点在章号推断——有卷时用 chapter_start+i，
无卷时需从 outline 自身 chapter 字段推断。

提取纯函数 compute_chapter_numbering 承载此逻辑，TDD 锁住。
"""


from src.api.services.generation.long_form_generation_helpers import (
    compute_chapter_numbering,
)


def _outline(ch_num: int) -> dict:
    return {"chapter": ch_num, "title": f"第{ch_num}章", "plot": "推进"}


class TestComputeChapterNumbering:
    def test_with_volume_uses_chapter_start_offset(self):
        """有卷模式：chapter_start=21, 3 章 → 全局章号 21/22/23"""
        outlines = [_outline(1), _outline(2), _outline(3)]
        items, total = compute_chapter_numbering(
            chapter_start=21, chapter_end=23, outlines=outlines, request=None,
        )
        assert [g for g, _ in items] == [21, 22, 23]
        assert total == 23

    def test_no_volume_infers_chapter_start_from_first_outline(self):
        """无卷模式：chapter_start=None 时从首个 outline.chapter 推断起点"""
        outlines = [_outline(5), _outline(6), _outline(7)]
        items, total = compute_chapter_numbering(
            chapter_start=None, chapter_end=None, outlines=outlines, request=None,
        )
        # outline 自带 chapter 字段，直接用它作为全局章号
        assert [g for g, _ in items] == [5, 6, 7]
        assert total == 7

    def test_no_volume_outline_missing_chapter_uses_index_plus_one(self):
        """无卷 + outline 无 chapter 字段：回退 1-based 序号"""
        outlines = [{"title": "a", "plot": ""}, {"title": "b", "plot": ""}]
        items, total = compute_chapter_numbering(
            chapter_start=None, chapter_end=None, outlines=outlines, request=None,
        )
        assert [g for g, _ in items] == [1, 2]
        assert total == 2

    def test_no_volume_request_none_total_uses_max_chapter(self):
        """无卷 + request=None：total 取 outlines 最大章号"""
        outlines = [_outline(10), _outline(11), _outline(12)]
        _, total = compute_chapter_numbering(
            chapter_start=None, chapter_end=None, outlines=outlines, request=None,
        )
        assert total == 12
