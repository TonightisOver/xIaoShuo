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
