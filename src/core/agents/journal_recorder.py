"""Sub-Agent 工作日志记录器端口（core 层抽象）。

core/agents 下的 Sub-Agent 通过本模块获取日志记录器，而不直接依赖
src.api.services.agent_journal_service —— 后者属于 api 层，core 层不应向上
依赖。具体实现（AgentJournalService）由 api 层在应用启动时通过
``set_journal_recorder`` 注入。

当未注入实现时（如单元测试或独立运行 core），``get_journal_recorder`` 返回
``None``，Sub-Agent 应跳过日志写入。这保证了 core 层可脱离 api 层独立运行。
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class JournalRecorder(Protocol):
    """Sub-Agent 工作日志记录器协议。

    由 api 层的 ``AgentJournalService`` 实现，通过依赖注入提供给 core 层。
    """

    async def create_entry(
        self,
        task_id: str,
        agent_name: str,
        novel_id: int | None = None,
        chapter_id: str | None = None,
        input_summary: dict | None = None,
        stage_snapshot: str | None = None,
    ) -> Any:
        """创建一条 Agent 执行日志，返回日志实例（含 .id）。"""
        ...

    async def complete_entry(
        self,
        entry_id: int,
        status: str = "success",
        output_summary: dict | None = None,
        state_changes: list[dict] | None = None,
        duration_ms: int | None = None,
        error_message: str | None = None,
        **extra_fields: Any,
    ) -> Any:
        """标记一条日志为完成状态。"""
        ...


# ─────────────────────────────────────────────────────────────────────────────
# 依赖注入点
# ─────────────────────────────────────────────────────────────────────────────

_recorder: JournalRecorder | None = None


def get_journal_recorder() -> JournalRecorder | None:
    """获取注入的日志记录器；未注入时返回 None（Sub-Agent 应跳过日志）。"""
    return _recorder


def set_journal_recorder(recorder: JournalRecorder | None) -> None:
    """注入日志记录器实现（由 api 层在应用启动时调用）。"""
    global _recorder  # noqa: PLW0603
    _recorder = recorder


def reset_journal_recorder() -> None:
    """清除注入的记录器（主要用于测试隔离）。"""
    global _recorder  # noqa: PLW0603
    _recorder = None
