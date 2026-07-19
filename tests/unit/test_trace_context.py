"""trace_context 单元测试 — trace_id 绑定与 structlog 日志注入。"""
from __future__ import annotations

from src.core.trace_context import (
    _bind_trace,
    _clear_trace,
    get_current_trace_id,
    trace_context,
)


class TestTraceContext:
    async def test_async_context_binds_and_clears_trace_id(self):
        """async with 内 trace_id 已绑定，退出后清理。"""
        assert get_current_trace_id() is None
        async with trace_context("novel-abc123def456") as trace_id:
            assert trace_id == "novel-abc123"  # 截断到 12 字符
            assert get_current_trace_id() == trace_id
        assert get_current_trace_id() is None

    async def test_trace_id_truncates_long_task_id(self):
        """长 task_id 截断到 12 字符。"""
        async with trace_context("very-long-task-id-1234567890") as trace_id:
            assert len(trace_id) == 12
            assert trace_id == "very-long-ta"  # 12 字符

    async def test_none_task_id_generates_uuid(self):
        """task_id=None 时用 uuid 生成 trace_id。"""
        async with trace_context(None) as trace_id:
            assert len(trace_id) == 12
            assert trace_id is not None

    async def test_manual_bind_and_clear(self):
        """_bind_trace / _clear_trace 手动绑定清理。"""
        assert get_current_trace_id() is None
        token = _bind_trace("manual-task")
        assert get_current_trace_id() == "manual-task"
        _clear_trace(token)
        assert get_current_trace_id() is None

    async def test_nested_contexts_isolate_trace_id(self):
        """嵌套 trace_context 各自有独立 trace_id，内层退出后恢复外层。"""
        async with trace_context("outer-task") as outer_id:
            assert get_current_trace_id() == outer_id
            async with trace_context("inner-task") as inner_id:
                assert get_current_trace_id() == inner_id
                assert inner_id != outer_id
            # 内层退出，恢复外层
            assert get_current_trace_id() == outer_id

    async def test_clear_without_bind_is_safe(self):
        """未绑定时 _clear_trace 不报错。"""
        # 用一个伪 token，确保不抛
        _clear_trace(None)
