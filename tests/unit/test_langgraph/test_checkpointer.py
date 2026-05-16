"""LangGraph checkpointer 模块单元测试"""

from langgraph.checkpoint.memory import MemorySaver

from src.core.langgraph.checkpointer import get_checkpointer


def test_get_checkpointer_returns_memory_saver() -> None:
    """测试 get_checkpointer 返回 MemorySaver"""
    checkpointer = get_checkpointer()
    assert isinstance(checkpointer, MemorySaver)


def test_get_checkpointer_is_callable() -> None:
    """测试 get_checkpointer 可调用"""
    checkpointer = get_checkpointer()
    assert checkpointer is not None
    # MemorySaver 应该有 put 和 get 方法
    assert hasattr(checkpointer, "put")
    assert hasattr(checkpointer, "get")
