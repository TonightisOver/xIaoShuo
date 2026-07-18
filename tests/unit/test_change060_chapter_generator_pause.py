# tests/unit/test_change060_chapter_generator_pause.py
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.llm.chapter_generator import ChapterGenContext, generate_chapter_stream


class _FakeStream:
    """模拟 client.stream_generate 的异步迭代器。"""
    def __init__(self, tokens):
        self._tokens = list(tokens)

    def __aiter__(self):
        async def _gen():
            for t in self._tokens:
                yield t
        return _gen()


@pytest.mark.asyncio
async def test_generate_chapter_stream_accepts_pause_checker():
    """长篇调用传入 pause_checker 时不应抛 unexpected keyword argument。"""
    client = MagicMock()
    # blueprint=None 时函数会先用 client.generate 做规划，再 stream_generate 生成正文
    client.generate = AsyncMock(return_value="规划单内容")
    client.stream_generate = MagicMock(return_value=_FakeStream(["段落一", "段落二"]))
    pause_checker = AsyncMock(return_value=False)

    on_token = AsyncMock()
    on_complete = AsyncMock()

    result = await generate_chapter_stream(
        ChapterGenContext(
            client=client,
            chapter_outline={"chapter": 1, "title": "测试章", "plot": "测试"},
            previous_chapter="",
            characters_json="[]",
            world_setting_json="{}",
            on_token=on_token,
            on_complete=on_complete,
            target_words=100,
            pause_checker=pause_checker,
        )
    )

    assert result.get("generation_failed") is not True
    assert "段落一" in result.get("content", "")
    # pause_checker 至少被调用一次（在生成开始或续写循环中）
    assert pause_checker.call_count >= 1
    # 流式正文生成确实执行了：on_token 被每个 token 调用
    assert on_token.call_count >= 2


@pytest.mark.asyncio
async def test_generate_chapter_stream_pause_true_aborts():
    """当 pause_checker 返回 True 时应中止生成。"""
    client = MagicMock()
    client.generate = AsyncMock(return_value="规划单内容")
    client.stream_generate = MagicMock(return_value=_FakeStream(["段落一"] * 10))
    pause_checker = AsyncMock(return_value=True)

    result = await generate_chapter_stream(
        ChapterGenContext(
            client=client,
            chapter_outline={"chapter": 1, "title": "测试章", "plot": "测试"},
            previous_chapter="",
            characters_json="[]",
            world_setting_json="{}",
            on_token=AsyncMock(),
            on_complete=AsyncMock(),
            target_words=100,
            pause_checker=pause_checker,
        )
    )

    # 暂停时应标记 paused 并中止生成（不能正常完成、不能进入流式生成）
    assert result.get("paused") is True
    # 暂停是用户主动行为，不是生成失败
    assert result.get("generation_failed") is False
    # 流式正文尚未开始（生成前即中止）
    assert client.stream_generate.called is False


@pytest.mark.asyncio
async def test_generate_chapter_stream_pause_mid_stream():
    """流式生成达到节流阈值时 pause_checker 返回 True 应中止，保留已生成内容。"""
    tokens = [f"段{i}" for i in range(60)]
    client = MagicMock()
    client.stream_generate = MagicMock(return_value=_FakeStream(tokens))
    client.generate = AsyncMock(return_value="规划单内容")

    call_count = {"n": 0}
    async def pause_checker():
        call_count["n"] += 1
        # 第 1 次调用在生成前检查点，返回 False 放行进入流式；
        # 第 2 次调用在 token_count==50 节流点，返回 True 触发流式中暂停
        return call_count["n"] >= 2

    on_token = AsyncMock()

    result = await generate_chapter_stream(
        ChapterGenContext(
            client=client,
            chapter_outline={"chapter": 1, "title": "测试章", "plot": "测试"},
            previous_chapter="",
            characters_json="[]",
            world_setting_json="{}",
            on_token=on_token,
            on_complete=AsyncMock(),
            target_words=100,
            pause_checker=pause_checker,
        )
    )

    assert result.get("paused") is True
    assert result.get("generation_failed") is False
    assert client.stream_generate.called
    # 已生成至少 50 个 token 的内容
    assert len(result.get("content", "")) > 0
