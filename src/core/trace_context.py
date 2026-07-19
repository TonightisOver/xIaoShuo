"""生成任务链路追踪：用 structlog contextvars 绑定 trace_id。

为每个生成任务分配唯一 trace_id，自动注入到该任务内所有 structlog 日志中，
形成简易全链路追踪（无需引入 LangSmith/Phoenix 等外部服务）。

用法：
    async with trace_context(task_id) as trace_id:
        # 此作用域内所有 logger.info(...) 自动带 trace_id
        await generate_novel_background(...)

trace_id 格式：``task-{task_id}[:8]`` 截断，避免过长。若 task_id 为空则用 uuid。
"""
from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog

logger = structlog.get_logger(__name__)


def _make_trace_id(task_id: str | None) -> str:
    """根据 task_id 生成 trace_id（截断到 12 字符以内）。"""
    if task_id:
        # 取 task_id 的前 12 字符，保证可读且唯一
        return task_id[:12]
    return uuid.uuid4().hex[:12]


@asynccontextmanager
async def trace_context(task_id: str | None) -> AsyncIterator[str]:
    """绑定 trace_id 到当前异步上下文，作用域内所有日志自动携带。

    Args:
        task_id: 任务 ID（用于派生 trace_id）。

    Yields:
        生成的 trace_id。

    Example:
        async with trace_context("novel-abc123") as tid:
            logger.info("generation_start")  # 日志自动含 trace_id=tid
            await generate(...)
    """
    trace_id = _make_trace_id(task_id)
    # 记录绑定前的上下文快照，退出时恢复（避免跨调用泄漏）
    _prev = structlog.contextvars.get_contextvars()
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    logger.info("trace_context_bound", trace_id=trace_id, task_id=task_id)
    try:
        yield trace_id
    finally:
        structlog.contextvars.clear_contextvars()
        # 恢复绑定前已存在的上下文变量（支持嵌套）
        structlog.contextvars.bind_contextvars(**_prev)
        logger.info("trace_context_unbound", trace_id=trace_id)


def get_current_trace_id() -> str | None:
    """获取当前上下文绑定的 trace_id（未绑定时返回 None）。"""
    try:
        ctx = structlog.contextvars.get_contextvars()
        return ctx.get("trace_id")
    except Exception:
        return None


def _bind_trace(task_id: str | None):
    """绑定 trace_id 到当前上下文（非 contextmanager 版，需手动 _clear_trace）。

    适用于无法用 ``async with trace_context`` 包裹的复杂函数体（如含多层
    try/except 且不想改缩进）。返回绑定前的上下文快照，传给 ``_clear_trace`` 恢复。

    Example:
        snapshot = _bind_trace(task_id)
        try:
            ...
        finally:
            _clear_trace(snapshot)
    """
    trace_id = _make_trace_id(task_id)
    prev = structlog.contextvars.get_contextvars()
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    logger.info("trace_context_bound", trace_id=trace_id, task_id=task_id)
    return prev


def _clear_trace(snapshot: dict | None = None) -> None:
    """清理 _bind_trace 绑定的 trace_id，恢复到 snapshot 状态。"""
    try:
        structlog.contextvars.clear_contextvars()
        if snapshot:
            structlog.contextvars.bind_contextvars(**snapshot)
    except Exception:
        pass

