# tests/unit/test_change060_l0_rules.py
from src.core.quality.rules import run_l0_rules


def test_failed_generation_flagged():
    result = run_l0_rules(content="", word_count=0, avg_word_count=2000, chapter_outline="x", chapter_number=1)
    types = [v["type"] for v in result["violations"]]
    assert "too_short" in types


def test_repetitive_paragraphs_detected():
    # 同一段落重复多次
    para = "他走进了房间，环顾四周，什么也没说。"
    content = "\n\n".join([para] * 6)
    result = run_l0_rules(content=content, word_count=len(content), avg_word_count=1000, chapter_outline="x", chapter_number=1)
    types = [v["type"] for v in result["violations"]]
    assert "repetitive_paragraphs" in types


def test_outline_coverage_checked():
    outline = "林炎挑战陈安"
    content = "主角在山上采药，遇到一只白狐，两人相谈甚欢。" * 10
    result = run_l0_rules(content=content, word_count=len(content), avg_word_count=1000, chapter_outline=outline, chapter_number=1)
    types = [v["type"] for v in result["violations"]]
    assert "low_outline_coverage" in types


def test_normal_chapter_clean():
    content = "这是一段全新的原创正文内容，情节推进明显，没有重复。" * 30
    result = run_l0_rules(content=content, word_count=len(content), avg_word_count=len(content), chapter_outline="原创", chapter_number=1)
    assert result["filler_flag"] is False
    assert result["stalled_flag"] is False


def test_filler_flagged_for_very_short():
    result = run_l0_rules(content="短", word_count=1, avg_word_count=2000, chapter_outline="x", chapter_number=1)
    assert result["filler_flag"] is True


def test_generation_failed_flagged():
    result = run_l0_rules(
        content="[章节生成失败: timeout]",
        word_count=0, avg_word_count=2000, chapter_outline="x", chapter_number=1,
    )
    types = [v["type"] for v in result["violations"]]
    assert "generation_failed" in types
    assert result["filler_flag"] is True  # 失败章必须标记为灌水


def test_stalled_flag_when_outline_barely_covered():
    # 大纲关键词丰富，正文几乎不覆盖
    outline = "陈安林炎万剑门残卷古文"
    content = "完全无关的日常描写，没有任何大纲人物或事件。" * 5
    result = run_l0_rules(
        content=content, word_count=len(content),
        avg_word_count=len(content), chapter_outline=outline, chapter_number=1,
    )
    assert result["stalled_flag"] is True


def test_repetitive_sentence_pattern_detected():
    # 同一句式开头重复
    content = "他看着天空，然后叹了口气。他看着天空，然后转身离开。他看着天空，然后低下头。他看着天空，然后闭上了眼。"
    result = run_l0_rules(
        content=content, word_count=len(content),
        avg_word_count=len(content), chapter_outline=None, chapter_number=1,
    )
    types = [v["type"] for v in result["violations"]]
    assert "repetitive_sentence_pattern" in types
