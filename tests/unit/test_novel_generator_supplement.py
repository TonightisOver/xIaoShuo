"""novel_generator / long_form_generation_helpers 补充单元测试

覆盖现有测试未触及的关键路径：
- calculate_long_form_chapter_plan: auto_calc 算法边界与 clamp
- _full_generate_percentage: 百分比计算
- pause_task / resume_task / is_task_paused: 任务暂停/恢复
- generate_novel_background: 失败时标记 task 失败 + novel 状态 failed
- _run_sub_feature: 子特性失败不阻塞后续
- generate_volume_background: 无 outline 时的 fallback 路径
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 纯函数测试
# ---------------------------------------------------------------------------


def _make_request(**kwargs):
    """构造一个长篇 request mock，默认 auto_calc_chapters=False。"""
    req = MagicMock()
    req.auto_calc_chapters = kwargs.get("auto_calc_chapters", False)
    req.target_words = kwargs.get("target_words", 1_500_000)
    req.words_per_chapter = kwargs.get("words_per_chapter", 3_000)
    req.volumes = kwargs.get("volumes", 10)
    req.chapters_per_volume = kwargs.get("chapters_per_volume", 10)
    req.idea = kwargs.get("idea", "测试小说")
    req.novel_type = kwargs.get("novel_type", "玄幻")
    req.writing_style = kwargs.get("writing_style", "")
    req.writing_style_prompt = kwargs.get("writing_style_prompt", "")
    return req


class TestCalculateLongFormChapterPlan:
    """calculate_long_form_chapter_plan 算法正确性。"""

    def test_auto_calc_true_clamps_to_min_20(self):
        """目标章节数过少时，chapters_per_volume 被 clamp 到下限 20。"""
        from src.api.services.generation.novel_generator import (
            calculate_long_form_chapter_plan,
        )

        # 100000 字 / 5000 字每章 = 20 章; /10 卷 = 2 章/卷 → clamp 到 20
        req = _make_request(
            auto_calc_chapters=True, target_words=100_000,
            words_per_chapter=5_000, volumes=10, chapters_per_volume=10,
        )
        plan = calculate_long_form_chapter_plan(req)
        assert plan["chapters_per_volume"] == 20
        assert plan["total_chapters"] == 10 * 20
        assert plan["estimated_total_chapters"] == 20

    def test_auto_calc_true_clamps_to_max_60(self):
        """目标章节数过多时，chapters_per_volume 被 clamp 到上限 60。"""
        from src.api.services.generation.novel_generator import (
            calculate_long_form_chapter_plan,
        )

        # 10000000 字 / 1000 字每章 = 10000 章; /1 卷 = 10000 章/卷 → clamp 到 60
        req = _make_request(
            auto_calc_chapters=True, target_words=10_000_000,
            words_per_chapter=1_000, volumes=1, chapters_per_volume=10,
        )
        plan = calculate_long_form_chapter_plan(req)
        assert plan["chapters_per_volume"] == 60
        assert plan["total_chapters"] == 1 * 60

    def test_auto_calc_true_midrange_no_clamp(self):
        """中等规模时不触发 clamp。"""
        from src.api.services.generation.novel_generator import (
            calculate_long_form_chapter_plan,
        )

        # 1500000 / 3000 = 500 章; /10 卷 = 50 章/卷 → 不 clamp
        req = _make_request(
            auto_calc_chapters=True, target_words=1_500_000,
            words_per_chapter=3_000, volumes=10, chapters_per_volume=10,
        )
        plan = calculate_long_form_chapter_plan(req)
        assert plan["chapters_per_volume"] == 50
        assert plan["computed_chapters_per_volume"] == 50
        assert plan["estimated_total_chapters"] == 500

    def test_auto_calc_false_uses_request_value(self):
        """auto_calc_chapters=False 时直接用 request.chapters_per_volume。"""
        from src.api.services.generation.novel_generator import (
            calculate_long_form_chapter_plan,
        )

        req = _make_request(
            auto_calc_chapters=False, volumes=5, chapters_per_volume=30,
            target_words=999_999, words_per_chapter=1_000,
        )
        plan = calculate_long_form_chapter_plan(req)
        assert plan["chapters_per_volume"] == 30
        assert plan["computed_chapters_per_volume"] == 30
        assert plan["total_chapters"] == 5 * 30
        assert plan["estimated_total_chapters"] == 5 * 30

    def test_auto_calc_returns_all_keys(self):
        """返回的字典必须包含全部 4 个键。"""
        from src.api.services.generation.novel_generator import (
            calculate_long_form_chapter_plan,
        )

        plan = calculate_long_form_chapter_plan(_make_request())
        assert set(plan.keys()) == {
            "estimated_total_chapters", "computed_chapters_per_volume",
            "chapters_per_volume", "total_chapters",
        }


class TestFullGeneratePercentage:
    """_full_generate_percentage 百分比计算。"""

    def test_first_stage_returns_positive(self):
        from src.api.services.generation.novel_generator import (
            _full_generate_percentage,
        )
        assert _full_generate_percentage(0) > 0

    def test_last_stage_returns_100(self):
        from src.api.services.generation.novel_generator import (
            _full_generate_percentage,
        )
        last = len([
            "idea_expansion", "world_building", "character_design",
            "outline_generation", "chapter_generation", "quality_check",
            "human_review", "power_systems", "outline_persist", "storylines",
            "character_arcs", "scenes", "auto_conversation",
        ]) - 1
        assert _full_generate_percentage(last) == 100

    def test_monotonic_increasing(self):
        """百分比随 stage_index 单调递增。"""
        from src.api.services.generation.novel_generator import (
            _full_generate_percentage,
        )

        values = [_full_generate_percentage(i) for i in range(13)]
        for prev, curr in zip(values, values[1:]):
            assert curr > prev, f"非递增: {prev} -> {curr}"

    def test_override_total_stages(self):
        """total_stages 覆盖参数生效。"""
        from src.api.services.generation.novel_generator import (
            _full_generate_percentage,
        )
        # 4 阶段, index=0 → 25%
        assert _full_generate_percentage(0, total_stages=4) == 25
        # 4 阶段, index=3 → 100%
        assert _full_generate_percentage(3, total_stages=4) == 100


# ---------------------------------------------------------------------------
# 任务暂停/恢复
# ---------------------------------------------------------------------------


class TestTaskPauseResume:
    """pause_task / resume_task / is_task_paused 行为。"""

    @pytest.mark.asyncio
    async def test_pause_task_sets_paused_and_emits(self):
        from src.api.services.generation.novel_generator import pause_task

        store = MagicMock()
        store.set_paused = AsyncMock()
        emit = AsyncMock()

        with patch(
            "src.api.services.generation.pause_state_store.get_pause_state_store",
            return_value=store,
        ), patch("src.api.services.generation.novel_generator._emit_progress", emit):
            await pause_task("task-1")

        store.set_paused.assert_awaited_once_with("task-1")
        emit.assert_awaited_once()
        event_type = emit.call_args.args[1]
        assert "paused" in event_type.value or "PAUSED" in event_type.value

    @pytest.mark.asyncio
    async def test_resume_task_clears_paused_and_emits(self):
        from src.api.services.generation.novel_generator import resume_task

        store = MagicMock()
        store.clear_paused = AsyncMock()
        emit = AsyncMock()

        with patch(
            "src.api.services.generation.pause_state_store.get_pause_state_store",
            return_value=store,
        ), patch("src.api.services.generation.novel_generator._emit_progress", emit):
            await resume_task("task-1")

        store.clear_paused.assert_awaited_once_with("task-1")
        emit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_is_task_paused_delegates_to_store(self):
        from src.api.services.generation.novel_generator import is_task_paused

        store = MagicMock()
        store.is_paused = AsyncMock(return_value=True)

        with patch(
            "src.api.services.generation.pause_state_store.get_pause_state_store",
            return_value=store,
        ):
            result = await is_task_paused("task-1")

        assert result is True
        store.is_paused.assert_awaited_once_with("task-1")

    @pytest.mark.asyncio
    async def test_is_task_paused_returns_false_when_not_paused(self):
        from src.api.services.generation.novel_generator import is_task_paused

        store = MagicMock()
        store.is_paused = AsyncMock(return_value=False)

        with patch(
            "src.api.services.generation.pause_state_store.get_pause_state_store",
            return_value=store,
        ):
            result = await is_task_paused("task-2")

        assert result is False


# ---------------------------------------------------------------------------
# LangGraph quality dependency injection
# ---------------------------------------------------------------------------


class TestLangGraphQualityDependencyInjection:
    """API 编排层为 quality_check 注入持久化和 L3 改写依赖。"""

    @pytest.mark.asyncio
    async def test_initial_pipeline_injects_quality_dependencies(self):
        from src.api.services.generation.novel_generator import (
            _persist_quality_to_version,
            _run_langgraph_pipeline,
        )
        from src.api.services.quality.rewrite_loop_service import RewriteLoopService

        captured = {}

        async def fake_astream(state, config):
            captured["config"] = config
            if False:
                yield {}

        graph = MagicMock()
        graph.astream = fake_astream

        with patch(
            "src.api.services.generation.novel_generator.get_task_manager",
            return_value=MagicMock(),
        ), patch(
            "src.api.services.generation.novel_generator.get_event_bus",
            return_value=MagicMock(),
        ), patch(
            "src.api.services.generation.novel_generator.create_novel_graph",
            return_value=graph,
        ), patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value.KNOWLEDGE_GRAPH_ENABLED = False
            await _run_langgraph_pipeline("task-initial", {})

        configurable = captured["config"]["configurable"]
        assert configurable["persist_quality"] is _persist_quality_to_version
        assert isinstance(configurable["rewrite_service"], RewriteLoopService)

    @pytest.mark.asyncio
    async def test_resume_pipeline_injects_quality_dependencies(self):
        from src.api.services.generation.novel_generator import (
            _persist_quality_to_version,
            resume_pipeline,
        )
        from src.api.services.quality.rewrite_loop_service import RewriteLoopService

        captured = {}

        async def fake_astream(command, config):
            captured["config"] = config
            yield {"human_review": {"chapters": []}}

        graph = MagicMock()
        graph.astream = fake_astream
        task_manager = MagicMock()
        task_manager.get_task = AsyncMock(return_value=None)
        task_manager.complete_task = AsyncMock()
        task_manager.fail_task = AsyncMock()

        with patch(
            "src.api.services.generation.novel_generator.get_task_manager",
            return_value=task_manager,
        ), patch(
            "src.api.services.generation.novel_generator.get_event_bus",
            return_value=MagicMock(),
        ), patch(
            "src.api.services.generation.novel_generator.create_novel_graph",
            return_value=graph,
        ), patch(
            "src.api.services.generation.novel_generator._emit_progress",
            new=AsyncMock(),
        ):
            await resume_pipeline(
                "task-resume", {"approval_status": "approved"}
            )

        configurable = captured["config"]["configurable"]
        assert configurable["persist_quality"] is _persist_quality_to_version
        assert isinstance(configurable["rewrite_service"], RewriteLoopService)


# ---------------------------------------------------------------------------
# generate_novel_background 错误恢复
# ---------------------------------------------------------------------------


class TestGenerateNovelBackgroundErrorRecovery:
    """generate_novel_background 失败时正确清理：标记 task 失败 + novel failed。"""

    @pytest.mark.asyncio
    async def test_failure_marks_task_and_novel_failed(self):
        """_run_langgraph_pipeline 抛异常时，task 标记 failed，novel 标记 failed。"""
        from src.api.services.generation.novel_generator import (
            generate_novel_background,
        )

        tm = MagicMock()
        tm.update_status = AsyncMock()
        tm.complete_task = AsyncMock()
        tm.fail_task = AsyncMock()
        tm.get_task = AsyncMock(return_value={"novel_id": "novel-99"})

        nm = MagicMock()
        nm.update_novel = AsyncMock()

        request = _make_request()

        with patch("src.api.services.generation.novel_generator.get_task_manager", return_value=tm), \
             patch("src.api.services.content.novel_manager.get_novel_manager", return_value=nm), \
             patch("src.api.services.generation.novel_generator._emit_progress", AsyncMock()), \
             patch("src.api.services.generation.novel_generator._build_initial_state", AsyncMock(return_value=({}, "novel-99"))), \
             patch("src.api.services.generation.novel_generator._run_langgraph_pipeline", AsyncMock(side_effect=RuntimeError("LLM 超时"))), \
             patch("src.api.services.generation.novel_generator._persist_to_novel", AsyncMock()):
            await generate_novel_background("task-fail", request)

        # task 标记失败
        tm.fail_task.assert_awaited_once()
        args = tm.fail_task.call_args.args
        assert args[0] == "task-fail"
        assert "LLM 超时" in args[1]

        # novel 状态更新为 failed
        nm.update_novel.assert_awaited_once()
        assert nm.update_novel.call_args.kwargs.get("status") == "failed"

    @pytest.mark.asyncio
    async def test_success_completes_task_and_persists(self):
        """正常完成时，complete_task 被调用，结果持久化。"""
        from src.api.services.generation.novel_generator import (
            generate_novel_background,
        )

        tm = MagicMock()
        tm.update_status = AsyncMock()
        tm.complete_task = AsyncMock()
        tm.fail_task = AsyncMock()
        tm.get_task = AsyncMock(return_value={"novel_id": "novel-100"})

        persist = AsyncMock()

        request = _make_request()
        pipeline_result = {"chapters": [{"title": "第1章"}]}

        with patch("src.api.services.generation.novel_generator.get_task_manager", return_value=tm), \
             patch("src.api.services.generation.novel_generator._emit_progress", AsyncMock()), \
             patch("src.api.services.generation.novel_generator._build_initial_state", AsyncMock(return_value=({}, "novel-100"))), \
             patch("src.api.services.generation.novel_generator._run_langgraph_pipeline", AsyncMock(return_value=pipeline_result)), \
             patch("src.api.services.generation.novel_generator._persist_to_novel", persist):
            await generate_novel_background("task-ok", request)

        tm.complete_task.assert_awaited_once()
        args = tm.complete_task.call_args.args
        assert args[0] == "task-ok"
        assert args[1] == pipeline_result
        persist.assert_awaited_once_with("novel-100", pipeline_result)
        tm.fail_task.assert_not_called()


# ---------------------------------------------------------------------------
# _run_sub_feature 隔离性
# ---------------------------------------------------------------------------


class TestRunSubFeatureIsolation:
    """_run_sub_feature 某子特性失败不阻塞后续，也不抛出。"""

    @pytest.mark.asyncio
    async def test_failure_does_not_raise(self):
        """子特性抛异常时，_run_sub_feature 自己吞掉，不向上传播。"""
        from src.api.services.generation.novel_generator import _run_sub_feature

        tm = MagicMock()
        tm.update_status = AsyncMock()

        ai_svc = MagicMock()
        ai_svc.generate_power_systems_ai = AsyncMock(
            side_effect=RuntimeError("AI 服务挂了")
        )

        emit = AsyncMock()

        with patch("src.api.services.generation.novel_generator.get_task_manager", return_value=tm), \
             patch("src.api.services.generation.novel_generator._emit_progress", emit), \
             patch("src.api.services.generation.ai_generation_service.get_ai_generation_service", return_value=ai_svc), \
             patch("src.api.services.content.conversation_service.get_conversation_service"), \
             patch("src.api.services.content.outline_service.get_outline_service"):
            # 不应抛出
            await _run_sub_feature(
                task_id="task-iso", novel_id="novel-iso", result={},
                request=_make_request(),
                feature_index=7, feature_name="power_systems", label="力量体系",
            )

        # 失败时通过 _emit_progress 发出 ERROR 事件
        from src.api.services.generation.progress_event_bus import EventType

        error_emits = [
            c for c in emit.call_args_list
            if len(c.args) >= 2 and c.args[1] == EventType.ERROR
        ]
        assert len(error_emits) >= 1

    @pytest.mark.asyncio
    async def test_skips_when_novel_id_none(self):
        """novel_id=None 时跳过所有子特性逻辑，不调用 AI 服务。"""
        from src.api.services.generation.novel_generator import _run_sub_feature

        tm = MagicMock()
        tm.update_status = AsyncMock()

        ai_svc = MagicMock()
        ai_svc.generate_power_systems_ai = AsyncMock()

        with patch("src.api.services.generation.novel_generator.get_task_manager", return_value=tm), \
             patch("src.api.services.generation.novel_generator._emit_progress", AsyncMock()), \
             patch("src.api.services.generation.ai_generation_service.get_ai_generation_service", return_value=ai_svc), \
             patch("src.api.services.content.conversation_service.get_conversation_service"), \
             patch("src.api.services.content.outline_service.get_outline_service"):
            await _run_sub_feature(
                task_id="task-none", novel_id=None, result={},
                request=_make_request(),
                feature_index=7, feature_name="power_systems", label="力量体系",
            )

        ai_svc.generate_power_systems_ai.assert_not_called()


# ---------------------------------------------------------------------------
# generate_volume_background fallback 路径
# ---------------------------------------------------------------------------


class TestGenerateVolumeBackgroundFallback:
    """generate_volume_background 在 volume_service 无 outline 时走 outline_service fallback。

    Ticket 02 后 generate_volume_background 迁入 long_form_generation_helpers，
    内部不再调 _generate_chapters_batch（已删），改调 generate_volume_chapters。
    fallback 业务逻辑（volume 无 outline → 从 outline_service 取章节数据）仍有效。
    """

    @pytest.mark.asyncio
    async def test_fallback_to_outline_service_when_volume_has_no_outline(self):
        """volume_service.get_volume 返回无 outline 时，从 outline_service 取章节数据。"""
        from src.api.services.generation.long_form_generation_helpers import (
            generate_volume_background,
        )

        tm = MagicMock()
        tm.update_status = AsyncMock()
        tm.complete_task = AsyncMock()
        tm.fail_task = AsyncMock()

        vol_service = MagicMock()
        vol_service.get_volume = AsyncMock(return_value=None)  # 无 volume 数据
        vol_service.update_volume = AsyncMock()

        outline_svc = AsyncMock()
        outline_svc.get_volume_outlines = AsyncMock(return_value=[
            {"volume_number": 1, "content": {"chapters": [{"chapter": 1, "title": "第1章"}]}},
        ])
        outline_svc.get_chapter_outlines = AsyncMock(return_value=[
            {"chapter_number": 1, "content": {"title": "第1章", "turning_point": "转折", "scenes": []}},
        ])

        with patch("src.api.services.generation.long_form_generation_helpers.get_task_manager", return_value=tm), \
             patch("src.api.services.generation.long_form_generation_helpers.get_volume_service", return_value=vol_service), \
             patch("src.api.services.generation.long_form_generation_helpers._emit_progress", AsyncMock()), \
             patch("src.api.services.generation.long_form_generation_helpers.generate_volume_chapters",
                   new=AsyncMock(return_value=[{"chapter": 1}])) as gen_vol_mock, \
             patch("src.api.services.content.outline_service.get_outline_service", return_value=outline_svc):
            await generate_volume_background("task-vol", "novel-1", 1)

        # 走了 fallback：generate_volume_chapters 被调，vol_outline.chapters 从 outline_service 取
        gen_vol_mock.assert_awaited_once()
        vol_outline_passed = gen_vol_mock.call_args.kwargs["vol_outline"]
        assert vol_outline_passed["chapters"][0]["chapter"] == 1
        tm.complete_task.assert_awaited_once()
        vol_service.update_volume.assert_awaited_once()
        assert vol_service.update_volume.call_args.kwargs.get("status") == "completed"

    @pytest.mark.asyncio
    async def test_raises_when_no_outline_anywhere(self):
        """volume 和 outline_service 都无数据时抛 ValueError（被外层捕获标 task 失败）。"""
        from src.api.services.generation.long_form_generation_helpers import (
            generate_volume_background,
        )

        tm = MagicMock()
        tm.update_status = AsyncMock()
        tm.fail_task = AsyncMock()
        tm.complete_task = AsyncMock()

        vol_service = MagicMock()
        vol_service.get_volume = AsyncMock(return_value=None)
        vol_service.update_volume = AsyncMock()

        outline_svc = AsyncMock()
        outline_svc.get_volume_outlines = AsyncMock(return_value=[])  # 无数据
        outline_svc.get_chapter_outlines = AsyncMock(return_value=[])

        with patch("src.api.services.generation.long_form_generation_helpers.get_task_manager", return_value=tm), \
             patch("src.api.services.generation.long_form_generation_helpers.get_volume_service", return_value=vol_service), \
             patch("src.api.services.generation.long_form_generation_helpers._emit_progress", AsyncMock()), \
             patch("src.api.services.generation.long_form_generation_helpers.generate_volume_chapters",
                   new=AsyncMock(return_value=[])), \
             patch("src.api.services.content.outline_service.get_outline_service", return_value=outline_svc):
            await generate_volume_background("task-vol2", "novel-1", 1)

        # 抛 ValueError 被外层 try 捕获 → task 标记失败
        tm.fail_task.assert_awaited_once()
        err_msg = tm.fail_task.call_args.args[1]
        assert "no outline" in err_msg.lower()
        vol_service.update_volume.assert_awaited_once()
        assert vol_service.update_volume.call_args.kwargs.get("status") == "failed"
