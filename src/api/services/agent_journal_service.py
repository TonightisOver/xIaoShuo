"""AgentJournal 工作日志服务

记录 Sub-Agent 每次执行的输入、输出、状态变更等关键信息，
提供可观测性和审计能力。
"""
from datetime import datetime

import structlog
from sqlalchemy import select

from src.api.models.db_models import AgentJournal
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)


class AgentJournalService:
    """Agent 工作日志服务"""

    async def create_entry(
        self,
        task_id: str,
        agent_name: str,
        novel_id: int | None = None,
        chapter_id: str | None = None,
        input_summary: dict | None = None,
        stage_snapshot: str | None = None,
    ) -> AgentJournal:
        """创建一条 Agent 执行日志

        Args:
            task_id: 所属 Task ID
            agent_name: Agent 名称 (continuity_editor / memory_curator / graph_reconciler)
            novel_id: 小说 ID（可选）
            chapter_id: 章节 ID（可选）
            input_summary: 输入摘要（可选）
            stage_snapshot: 父 task 当前阶段（可选）

        Returns:
            创建的 AgentJournal 实例
        """
        async with get_db_session() as session:
            entry = AgentJournal(
                task_id=task_id,
                agent_name=agent_name,
                novel_id=novel_id,
                chapter_id=chapter_id,
                status="running",
                input_summary=input_summary,
                stage_snapshot=stage_snapshot,
            )
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
            return entry

    async def complete_entry(
        self,
        entry_id: int,
        status: str = "success",
        output_summary: dict | None = None,
        state_changes: list[dict] | None = None,
        duration_ms: int | None = None,
        error_message: str | None = None,
        **extra_fields,
    ) -> AgentJournal | None:
        """标记一条 Agent 执行日志为完成状态

        Args:
            entry_id: 日志 ID
            status: 完成状态 (success/failed/timeout)
            output_summary: 输出摘要
            state_changes: 状态变更记录
            duration_ms: 执行耗时（毫秒，若未提供则自动计算）
            error_message: 错误信息
            **extra_fields: 各 Agent 专用字段

        Returns:
            更新后的 AgentJournal 实例
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(AgentJournal).where(AgentJournal.id == entry_id)
            )
            entry = result.scalar_one_or_none()
            if not entry:
                logger.warning("agent_journal_entry_not_found", entry_id=entry_id)
                return None

            entry.status = status
            if output_summary is not None:
                entry.output_summary = output_summary
            if state_changes is not None:
                entry.state_changes = state_changes
            if duration_ms is not None:
                entry.duration_ms = duration_ms
            elif entry.duration_ms is None and status in ("success", "failed"):
                # 自动计算耗时（从 created_at 到 now）
                delta = datetime.utcnow() - entry.created_at.replace(tzinfo=None)
                entry.duration_ms = int(delta.total_seconds() * 1000)
            if error_message is not None:
                entry.error_message = error_message

            # 写入各 Agent 专用字段
            for key in ("conflict_count", "blocked_entity_count", "memo_update_count", "continuity_score"):
                val = extra_fields.pop(key, None)
                if val is not None:
                    setattr(entry, key, val)

            await session.commit()
            await session.refresh(entry)
            return entry

    async def get_task_journal(
        self,
        task_id: str,
        agent_name: str | None = None,
        limit: int = 50,
    ) -> list[AgentJournal]:
        """获取某个 Task 的所有 Agent 日志

        Args:
            task_id: 任务 ID
            agent_name: Agent 名称过滤（可选）
            limit: 最大返回数

        Returns:
            AgentJournal 实例列表
        """
        async with get_db_session() as session:
            query = (
                select(AgentJournal)
                .where(AgentJournal.task_id == task_id)
                .order_by(AgentJournal.id.desc())
                .limit(limit)
            )
            if agent_name:
                query = query.where(AgentJournal.agent_name == agent_name)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def get_recent_journals(
        self,
        agent_name: str,
        novel_id: int,
        limit: int = 10,
    ) -> list[AgentJournal]:
        """获取某个 Agent 在某个小说上的最近执行日志

        Args:
            agent_name: Agent 名称
            novel_id: 小说 ID
            limit: 最大返回数

        Returns:
            AgentJournal 实例列表
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(AgentJournal)
                .where(AgentJournal.agent_name == agent_name)
                .where(AgentJournal.novel_id == novel_id)
                .order_by(AgentJournal.id.desc())
                .limit(limit)
            )
            return list(result.scalars().all())


# 单例
_journal_service: AgentJournalService | None = None


def get_journal_service() -> AgentJournalService:
    """获取 AgentJournal 服务单例，并注入到 core 层记录器端口。

    core/agents 下的 Sub-Agent 通过依赖反转的 ``get_journal_recorder``
    访问日志记录器；首次创建单例时将其注入 core 层，使 Sub-Agent
    无需直接依赖 api 层即可记录工作日志。
    """
    global _journal_service  # noqa: PLW0603
    if _journal_service is None:
        _journal_service = AgentJournalService()
        # 将实现注入 core 层端口（依赖反转）
        from src.core.agents.journal_recorder import set_journal_recorder
        set_journal_recorder(_journal_service)
    return _journal_service
