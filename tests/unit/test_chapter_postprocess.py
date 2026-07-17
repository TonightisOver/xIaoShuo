"""章节后处理函数测试"""

from src.core.llm.chapter_generator import post_process_chapter


def test_removes_excessive_dashes():
    """长破折号归一化"""
    result = post_process_chapter("他说——然后——")
    assert "——" in result


def test_removes_ai_buzzwords():
    """删除AI结构词"""
    text = "值得注意的是，这是一个测试。总的来说，结果不错。"
    result = post_process_chapter(text)
    assert "值得注意的是" not in result
    assert "总的来说" not in result


def test_keeps_normal_punctuation():
    """正常标点不受影响"""
    text = "他站了起来，走向门口。"
    result = post_process_chapter(text)
    assert result == "他站了起来，走向门口。"


def test_removes_excessive_blank_lines():
    """合并多余空行"""
    text = "第一段\n\n\n\n\n第二段"
    result = post_process_chapter(text)
    # 最多保留 2 个换行（即一个空行）
    assert result.count("\n") <= 3


def test_strips_trailing_whitespace():
    """去除首尾空格"""
    result = post_process_chapter("  内容  ")
    assert result == "内容"


def test_normalizes_ascii_dashes_to_em_dash():
    """半角连续连字符（句尾常见的 ------）规整为中文全角破折号"""
    # 句尾多个半角连字符 → 单个 ——
    assert post_process_chapter("他说------") == "他说——"
    # 中间多个半角连字符 → 单个 ——
    assert post_process_chapter("他--说") == "他——说"
    # 超长半角连字符串也收敛
    assert post_process_chapter("拖长音---------") == "拖长音——"


def test_single_ascii_dash_preserved():
    """单个半角连字符不处理（避免误伤日期、复合词等合法用法）"""
    assert post_process_chapter("2024-01-01") == "2024-01-01"
    assert post_process_chapter("well-known") == "well-known"


def test_legitimate_em_dash_preserved():
    """中文全角破折号表话语中断是合法用法，单个 —— 保留"""
    # 单个 —— 不被收敛（合理的话语中断）
    assert post_process_chapter("他——") == "他——"
    # 多个连续 —— 收敛为单个 ——（避免 ---- 拖长）
    assert post_process_chapter("他——————") == "他——"


def test_mixed_ascii_and_em_dashes():
    """混合半角/全角连续破折号收敛为单个 ——"""
    assert post_process_chapter("他------——") == "他——"
    assert post_process_chapter("他——------") == "他——"

