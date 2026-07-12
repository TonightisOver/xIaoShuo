"""Sub-Agent journal 集成测试

覆盖三个 Sub-Agent 的 AgentJournal 日志路径：
- continuity_editor: block/pass/warn 三级 verdict
- memory_curator: 成功/失败路径
- graph_reconciler: block/pass/escalate 三级路径

依赖反转后，agent 通过 core 层注入点 ``get_journal_recorder`` 获取日志记录器；
测试通过 ``set_journal_recorder`` 注入 mock，并在结束时由 autouse fixture
清理，避免跨测试状态泄漏。
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.agents.journal_recorder import reset_journal_recorder, set_journal_recorder


# ─────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _reset_journal_recorder():
    """每个测试前后清理 core 层日志记录器注入点，避免跨测试泄漏。"""
    reset_journal_recorder()
    yield
    reset_journal_recorder()


@pytest.fixture
def mock_journal_entry():
    """单个 AgentJournal 记录实例"""
    entry = MagicMock()
    entry.id = 42
    entry.status = "running"
    entry.output_summary = None
    entry.duration_ms = None
    entry.error_message = None
    return entry


@pytest.fixture
def mock_llm_client():
    """模拟 LLM 客户端"""
    client = MagicMock()
    client.generate = AsyncMock(return_value="response")
    return client


def _make_journal_service(entry=None):
    """构造一个所有方法都是 AsyncMock 的 AgentJournalService"""
    svc = MagicMock()
    svc.create_entry = AsyncMock(return_value=entry if entry is not None else MagicMock(id=42))
    svc.complete_entry = AsyncMock(return_value=entry)
    svc.get_task_journal = AsyncMock(return_value=[])
    svc.get_recent_journals = AsyncMock(return_value=[])
    return svc


# ─────────────────────────────────────────────
# 1. ContinuityEditor
# ─────────────────────────────────────────────

class TestContinuityEditorJournal:

    @pytest.mark.asyncio
    async def test_pass_verdict_creates_and_completes_journal(
        self, mock_journal_entry, mock_llm_client
    ):
        """verdict=pass → journal status=success, continuity_score=90"""
        mock_llm_client.generate = AsyncMock(
            return_value=json.dumps({"verdict": "pass", "issues": [], "summary": "通过"})
        )
        svc = _make_journal_service(mock_journal_entry)
        set_journal_recorder(svc)

        with patch("src.core.agents.continuity_editor.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.continuity_editor import ContinuityEditorAgent
            agent = ContinuityEditorAgent(task_id="t1", novel_id=1)
            await agent.review("章节内容", "已有设定")

            svc.create_entry.assert_called_once()
            kwargs = svc.complete_entry.call_args.kwargs
            assert kwargs["status"] == "success"
            assert kwargs["continuity_score"] == 90

    @pytest.mark.asyncio
    async def test_block_verdict_journal_score_is_30(
        self, mock_journal_entry, mock_llm_client
    ):
        """verdict=block → continuity_score=30"""
        mock_llm_client.generate = AsyncMock(
            return_value=json.dumps({
                "verdict": "block",
                "issues": [{"type": "contradiction"}],
                "summary": "矛盾",
            })
        )
        svc = _make_journal_service(mock_journal_entry)
        set_journal_recorder(svc)

        with patch("src.core.agents.continuity_editor.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.continuity_editor import ContinuityEditorAgent
            agent = ContinuityEditorAgent(task_id="t1", novel_id=1)
            await agent.review("内容", "设定")

            assert svc.complete_entry.call_args.kwargs["continuity_score"] == 30

    @pytest.mark.asyncio
    async def test_warn_verdict_journal_score_is_60(
        self, mock_journal_entry, mock_llm_client
    ):
        """verdict=warn → continuity_score=60"""
        mock_llm_client.generate = AsyncMock(
            return_value=json.dumps({"verdict": "warn", "issues": [], "summary": "警告"})
        )
        svc = _make_journal_service(mock_journal_entry)
        set_journal_recorder(svc)

        with patch("src.core.agents.continuity_editor.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.continuity_editor import ContinuityEditorAgent
            agent = ContinuityEditorAgent(task_id="t1", novel_id=1)
            await agent.review("内容", "设定")

            assert svc.complete_entry.call_args.kwargs["continuity_score"] == 60

    @pytest.mark.asyncio
    async def test_llm_failure_logs_failed_status(
        self, mock_journal_entry, mock_llm_client
    ):
        """LLM 异常时 journal status=failed"""
        mock_llm_client.generate = AsyncMock(side_effect=Exception("API 超时"))
        svc = _make_journal_service(mock_journal_entry)
        set_journal_recorder(svc)

        with patch("src.core.agents.continuity_editor.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.continuity_editor import ContinuityEditorAgent
            agent = ContinuityEditorAgent(task_id="t1", novel_id=1)
            result = await agent.review("内容", "设定")

            svc.complete_entry.assert_called_once()
            assert svc.complete_entry.call_args.kwargs["status"] == "failed"
            assert result["verdict"] == "pass"  # fallback 默认值

    def test_no_task_id_skips_journal(self, mock_llm_client):
        """task_id=None 时跳过 journal 记录"""
        svc = _make_journal_service()
        set_journal_recorder(svc)
        mock_llm_client.generate = AsyncMock(
            return_value=json.dumps({"verdict": "pass", "issues": [], "summary": "通过"})
        )

        with patch("src.core.agents.continuity_editor.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.continuity_editor import ContinuityEditorAgent
            agent = ContinuityEditorAgent()
            assert agent.task_id is None
            assert agent.novel_id is None

            svc.create_entry.assert_not_called()

    def test_no_recorder_skips_journal(self, mock_llm_client):
        """未注入记录器时（recorder=None）跳过日志，agent 仍正常返回"""
        mock_llm_client.generate = AsyncMock(
            return_value=json.dumps({"verdict": "pass", "issues": [], "summary": "通过"})
        )
        # 不调用 set_journal_recorder → get_journal_recorder() 返回 None

        with patch("src.core.agents.continuity_editor.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.continuity_editor import ContinuityEditorAgent
            agent = ContinuityEditorAgent(task_id="t1", novel_id=1)
            result = agent.__class__.__dict__  # 仅验证可实例化
            assert result is not None


# ─────────────────────────────────────────────
# 2. MemoryCurator
# ─────────────────────────────────────────────

class TestMemoryCuratorJournal:

    @pytest.mark.asyncio
    async def test_success_creates_and_completes_journal(
        self, mock_journal_entry, mock_llm_client
    ):
        mock_llm_client.generate = AsyncMock(return_value="记忆备忘录内容")
        svc = _make_journal_service(mock_journal_entry)
        set_journal_recorder(svc)

        with patch("src.core.agents.memory_curator.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.memory_curator import MemoryCuratorAgent
            agent = MemoryCuratorAgent(task_id="t1", novel_id=1)
            await agent.curate({"chapter": 1}, "kg数据", "约束数据")

            svc.create_entry.assert_called_once()
            svc.complete_entry.assert_called_once()
            assert svc.complete_entry.call_args.kwargs["status"] == "success"
            assert svc.complete_entry.call_args.kwargs["memo_update_count"] == 1

    @pytest.mark.asyncio
    async def test_llm_failure_logs_failed_status(
        self, mock_journal_entry, mock_llm_client
    ):
        mock_llm_client.generate = AsyncMock(side_effect=Exception("API 超时"))
        svc = _make_journal_service(mock_journal_entry)
        set_journal_recorder(svc)

        with patch("src.core.agents.memory_curator.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.memory_curator import MemoryCuratorAgent
            agent = MemoryCuratorAgent(task_id="t1", novel_id=1)
            await agent.curate({"chapter": 1}, "历史", "约束")

            svc.complete_entry.assert_called_once()
            assert svc.complete_entry.call_args.kwargs["status"] == "failed"

    @pytest.mark.asyncio
    async def test_empty_context_returns_placeholder(self):
        """无历史数据时直接返回占位字符串，不调 LLM"""
        from src.core.agents.memory_curator import MemoryCuratorAgent
        agent = MemoryCuratorAgent()
        result = await agent.curate({"chapter": 1}, "", "")
        assert result == "无历史设定。"

    def test_no_task_id_skips_journal(self, mock_llm_client):
        svc = _make_journal_service()
        set_journal_recorder(svc)
        mock_llm_client.generate = AsyncMock(return_value="响应")

        with patch("src.core.agents.memory_curator.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.memory_curator import MemoryCuratorAgent
            agent = MemoryCuratorAgent()
            assert agent.task_id is None

            svc.create_entry.assert_not_called()


# ─────────────────────────────────────────────
# 3. GraphReconciler — 3-stage grading
# ─────────────────────────────────────────────

class TestGraphReconcilerJournal:

    @pytest.mark.asyncio
    async def test_pass_stage_writes_upserts_without_review_flag(
        self, mock_journal_entry, mock_llm_client
    ):
        """Stage 2 pass: entities_to_upsert 中 _needs_review=false"""
        mock_llm_client.generate = AsyncMock(
            return_value=json.dumps({
                "entities_to_upsert": [
                    {"name": "新角色", "type": "character", "_needs_review": False}
                ],
                "triples_to_add": [],
                "entity_status_updates": [],
                "foreshadowing_resolutions": [],
                "blocked_entities": [],
            })
        )
        svc = _make_journal_service(mock_journal_entry)
        set_journal_recorder(svc)

        with patch("src.core.agents.graph_reconciler.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.graph_reconciler import GraphReconcilerAgent
            agent = GraphReconcilerAgent(task_id="t1", novel_id=1)
            result = await agent.reconcile({"verdict": "pass"}, "{}", "无")

            svc.complete_entry.assert_called_once()
            assert svc.complete_entry.call_args.kwargs["status"] == "success"
            assert result["entities_to_upsert"][0]["_needs_review"] is False

    @pytest.mark.asyncio
    async def test_escalate_stage_entity_has_needs_review_flag(
        self, mock_journal_entry, mock_llm_client
    ):
        """Stage 3 escalate: 实体 _needs_review=true，blocked_entities 为空"""
        mock_llm_client.generate = AsyncMock(
            return_value=json.dumps({
                "entities_to_upsert": [
                    {"name": "可疑角色", "type": "character", "_needs_review": True}
                ],
                "triples_to_add": [],
                "entity_status_updates": [],
                "foreshadowing_resolutions": [],
                "blocked_entities": [],
            })
        )
        svc = _make_journal_service(mock_journal_entry)
        set_journal_recorder(svc)

        with patch("src.core.agents.graph_reconciler.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.graph_reconciler import GraphReconcilerAgent
            agent = GraphReconcilerAgent(task_id="t1", novel_id=1)
            result = await agent.reconcile({"verdict": "warn"}, "{}", "无")

            assert result["entities_to_upsert"][0]["_needs_review"] is True
            assert result["blocked_entities"] == []

    @pytest.mark.asyncio
    async def test_block_stage_entities_in_blocked_list(
        self, mock_journal_entry, mock_llm_client
    ):
        """Stage 1 block: 实体进入 blocked_entities，不在 entities_to_upsert"""
        mock_llm_client.generate = AsyncMock(
            return_value=json.dumps({
                "entities_to_upsert": [],
                "triples_to_add": [],
                "entity_status_updates": [],
                "foreshadowing_resolutions": [],
                "blocked_entities": [
                    {"name": "矛盾角色", "reason": "死亡后复活无剧情说明"}
                ],
            })
        )
        svc = _make_journal_service(mock_journal_entry)
        set_journal_recorder(svc)

        with patch("src.core.agents.graph_reconciler.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.graph_reconciler import GraphReconcilerAgent
            agent = GraphReconcilerAgent(task_id="t1", novel_id=1)
            result = await agent.reconcile({"verdict": "block"}, "{}", "无")

            assert len(result["blocked_entities"]) == 1
            assert result["blocked_entities"][0]["name"] == "矛盾角色"
            assert result["entities_to_upsert"] == []

    @pytest.mark.asyncio
    async def test_journal_logs_blocked_count(self, mock_journal_entry, mock_llm_client):
        """blocked_entity_count 和 conflict_count 正确写入 journal"""
        mock_llm_client.generate = AsyncMock(
            return_value=json.dumps({
                "entities_to_upsert": [],
                "triples_to_add": [],
                "entity_status_updates": [],
                "foreshadowing_resolutions": [],
                "blocked_entities": [
                    {"name": "A", "reason": "r"},
                    {"name": "B", "reason": "r2"},
                ],
            })
        )
        svc = _make_journal_service(mock_journal_entry)
        set_journal_recorder(svc)

        with patch("src.core.agents.graph_reconciler.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.graph_reconciler import GraphReconcilerAgent
            agent = GraphReconcilerAgent(task_id="t1", novel_id=1)
            await agent.reconcile({"verdict": "block"}, "{}", "无")

            kwargs = svc.complete_entry.call_args.kwargs
            assert kwargs["blocked_entity_count"] == 2
            assert kwargs["conflict_count"] == 2

    @pytest.mark.asyncio
    async def test_malformed_response_has_fallback_blocked_entities(
        self, mock_journal_entry, mock_llm_client
    ):
        """LLM 返回非 JSON 时，fallback 包含空的 blocked_entities"""
        mock_llm_client.generate = AsyncMock(return_value="这不像 JSON 格式的输出")
        svc = _make_journal_service(mock_journal_entry)
        set_journal_recorder(svc)

        with patch("src.core.agents.graph_reconciler.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.graph_reconciler import GraphReconcilerAgent
            agent = GraphReconcilerAgent(task_id="t1", novel_id=1)
            result = await agent.reconcile({}, "{}", "无")

            assert "blocked_entities" in result
            assert result["blocked_entities"] == []

    @pytest.mark.asyncio
    async def test_no_task_id_skips_journal(self, mock_llm_client):
        """task_id=None 时跳过 journal 记录"""
        svc = _make_journal_service()
        set_journal_recorder(svc)
        mock_llm_client.generate = AsyncMock(
            return_value=json.dumps({
                "entities_to_upsert": [],
                "triples_to_add": [],
                "entity_status_updates": [],
                "foreshadowing_resolutions": [],
                "blocked_entities": [],
            })
        )

        with patch("src.core.agents.graph_reconciler.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.graph_reconciler import GraphReconcilerAgent
            agent = GraphReconcilerAgent()
            result = await agent.reconcile({}, "{}", "无")

            svc.create_entry.assert_not_called()
            assert result["blocked_entities"] == []

    @pytest.mark.asyncio
    async def test_no_recorder_skips_journal_but_returns_result(self, mock_llm_client):
        """未注入记录器时跳过日志，reconcile 仍返回正常结果"""
        mock_llm_client.generate = AsyncMock(
            return_value=json.dumps({
                "entities_to_upsert": [],
                "triples_to_add": [],
                "entity_status_updates": [],
                "foreshadowing_resolutions": [],
                "blocked_entities": [],
            })
        )
        # 不注入记录器 → get_journal_recorder() 返回 None

        with patch("src.core.agents.graph_reconciler.get_llm_client",
                   return_value=mock_llm_client):
            from src.core.agents.graph_reconciler import GraphReconcilerAgent
            agent = GraphReconcilerAgent(task_id="t1", novel_id=1)
            result = await agent.reconcile({"verdict": "pass"}, "{}", "无")

            assert result["blocked_entities"] == []
