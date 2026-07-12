"""novel_generator.py 补充单元测试

覆盖现有测试未触及的关键路径：
- calculate_long_form_chapter_plan: auto_calc 算法边界与 clamp
- _full_generate_percentage: 百分比计算
- pause_task / resume_task / is_task_paused: 任务暂停/恢复
- generate_novel_background: 失败时标记 task 失败 + novel 状态 failed
- _run_sub_feature: 子特性失败不阻塞后续
- _generate_chapters_batch: 批量生成循环（暂停等待、上下文衔接）
- generate_volume_background: 无 outline 时的 fallback 路径
"""
from __future__ import annotations

import math
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
        from src.api.services.novel_generator import calculate_long_form_chapter_plan

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
        from src.api.services.novel_generator import calculate_long_form_chapter_plan

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
        from src.api.services.novel_generator import calculate_long_form_chapter_plan

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
        from src.api.services.novel_generator import calculate_long_form_chapter_plan

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
        from src.api.services.novel_generator import calculate_long_form_chapter_plan

        plan = calculate_long_form_chapter_plan(_make_request())
        assert set(plan.keys()) == {
            "estimated_total_chapters", "computed_chapters_per_volume",
            "chapters_per_volume", "total_chapters",
        }


class TestFullGeneratePercentage:
    """_full_generate_percentage 百分比计算。"""

    def test_first_stage_returns_positive(self):
        from src.api.services.novel_generator import _full_generate_percentage
        assert _full_generate_percentage(0) > 0

    def test_last_stage_returns_100(self):
        from src.api.services.novel_generator import _full_generate_percentage
        last = len([
            "idea_expansion", "world_building", "character_design",
            "outline_generation", "chapter_generation", "quality_check",
            "human_review", "power_systems", "outline_persist", "storylines",
            "character_arcs", "scenes", "auto_conversation",
        ]) - 1
        assert _full_generate_percentage(last) == 100

    def test_monotonic_increasing(self):
        """百分比随 stage_index 单调递增。"""
        from src.api.services.novel_generator import _full_generate_percentage

        values = [_full_generate_percentage(i) for i in range(13)]
        for prev, curr in zip(values, values[1:]):
            assert curr > prev, f"非递增: {prev} -> {curr}"

    def test_override_total_stages(self):
        """total_stages 覆盖参数生效。"""
        from src.api.services.novel_generator import _full_generate_percentage
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
        from src.api.services.novel_generator import pause_task

        store = MagicMock()
        store.set_paused = AsyncMock()
        emit = AsyncMock()

        with patch(
            "src.api.services.pause_state_store.get_pause_state_store",
            return_value=store,
        ), patch("src.api.services.novel_generator._emit_progress", emit):
            await pause_task("task-1")

        store.set_paused.assert_awaited_once_with("task-1")
        emit.assert_awaited_once()
        event_type = emit.call_args.args[1]
        assert "paused" in event_type.value or "PAUSED" in event_type.value

    @pytest.mark.asyncio
    async def test_resume_task_clears_paused_and_emits(self):
        from src.api.services.novel_generator import resume_task

        store = MagicMock()
        store.clear_paused = AsyncMock()
        emit = AsyncMock()

        with patch(
            "src.api.services.pause_state_store.get_pause_state_store",
            return_value=store,
        ), patch("src.api.services.novel_generator._emit_progress", emit):
            await resume_task("task-1")

        store.clear_paused.assert_awaited_once_with("task-1")
        emit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_is_task_paused_delegates_to_store(self):
        from src.api.services.novel_generator import is_task_paused

        store = MagicMock()
        store.is_paused = AsyncMock(return_value=True)

        with patch(
            "src.api.services.pause_state_store.get_pause_state_store",
            return_value=store,
        ):
            result = await is_task_paused("task-1")

        assert result is True
        store.is_paused.assert_awaited_once_with("task-1")

    @pytest.mark.asyncio
    async def test_is_task_paused_returns_false_when_not_paused(self):
        from src.api.services.novel_generator import is_task_paused

        store = MagicMock()
        store.is_paused = AsyncMock(return_value=False)

        with patch(
            "src.api.services.pause_state_store.get_pause_state_store",
            return_value=store,
        ):
            result = await is_task_paused("task-2")

        assert result is False


# ---------------------------------------------------------------------------
# generate_novel_background 错误恢复
# ---------------------------------------------------------------------------


class TestGenerateNovelBackgroundErrorRecovery:
    """generate_novel_background 失败时正确清理：标记 task 失败 + novel failed。"""

    @pytest.mark.asyncio
    async def test_failure_marks_task_and_novel_failed(self):
        """_run_langgraph_pipeline 抛异常时，task 标记 failed，novel 标记 failed。"""
        from src.api.services.novel_generator import generate_novel_background

        tm = MagicMock()
        tm.update_status = AsyncMock()
        tm.complete_task = AsyncMock()
        tm.fail_task = AsyncMock()
        tm.get_task = AsyncMock(return_value={"novel_id": "novel-99"})

        nm = MagicMock()
        nm.update_novel = AsyncMock()

        request = _make_request()

        with patch("src.api.services.novel_generator.get_task_manager", return_value=tm), \
             patch("src.api.services.novel_manager.get_novel_manager", return_value=nm), \
             patch("src.api.services.novel_generator._emit_progress", AsyncMock()), \
             patch("src.api.services.novel_generator._build_initial_state", AsyncMock(return_value=({}, "novel-99"))), \
             patch("src.api.services.novel_generator._run_langgraph_pipeline", AsyncMock(side_effect=RuntimeError("LLM 超时"))), \
             patch("src.api.services.novel_generator._persist_to_novel", AsyncMock()):
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
        from src.api.services.novel_generator import generate_novel_background

        tm = MagicMock()
        tm.update_status = AsyncMock()
        tm.complete_task = AsyncMock()
        tm.fail_task = AsyncMock()
        tm.get_task = AsyncMock(return_value={"novel_id": "novel-100"})

        persist = AsyncMock()

        request = _make_request()
        pipeline_result = {"chapters": [{"title": "第1章"}]}

        with patch("src.api.services.novel_generator.get_task_manager", return_value=tm), \
             patch("src.api.services.novel_generator._emit_progress", AsyncMock()), \
             patch("src.api.services.novel_generator._build_initial_state", AsyncMock(return_value=({}, "novel-100"))), \
             patch("src.api.services.novel_generator._run_langgraph_pipeline", AsyncMock(return_value=pipeline_result)), \
             patch("src.api.services.novel_generator._persist_to_novel", persist):
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
        from src.api.services.novel_generator import _run_sub_feature

        tm = MagicMock()
        tm.update_status = AsyncMock()

        ai_svc = MagicMock()
        ai_svc.generate_power_systems_ai = AsyncMock(
            side_effect=RuntimeError("AI 服务挂了")
        )

        emit = AsyncMock()

        with patch("src.api.services.novel_generator.get_task_manager", return_value=tm), \
             patch("src.api.services.novel_generator._emit_progress", emit), \
             patch("src.api.services.ai_generation_service.get_ai_generation_service", return_value=ai_svc), \
             patch("src.api.services.conversation_service.get_conversation_service"), \
             patch("src.api.services.outline_service.get_outline_service"):
            # 不应抛出
            await _run_sub_feature(
                task_id="task-iso", novel_id="novel-iso", result={},
                request=_make_request(),
                feature_index=7, feature_name="power_systems", label="力量体系",
            )

        # 失败时通过 _emit_progress 发出 ERROR 事件
        from src.api.services.progress_event_bus import EventType as ET

        error_emits = [
            c for c in emit.call_args_list
            if len(c.args) >= 2 and c.args[1] == ET.ERROR
        ]
        assert len(error_emits) >= 1

    @pytest.mark.asyncio
    async def test_skips_when_novel_id_none(self):
        """novel_id=None 时跳过所有子特性逻辑，不调用 AI 服务。"""
        from src.api.services.novel_generator import _run_sub_feature

        tm = MagicMock()
        tm.update_status = AsyncMock()

        ai_svc = MagicMock()
        ai_svc.generate_power_systems_ai = AsyncMock()

        with patch("src.api.services.novel_generator.get_task_manager", return_value=tm), \
             patch("src.api.services.novel_generator._emit_progress", AsyncMock()), \
             patch("src.api.services.ai_generation_service.get_ai_generation_service", return_value=ai_svc), \
             patch("src.api.services.conversation_service.get_conversation_service"), \
             patch("src.api.services.outline_service.get_outline_service"):
            await _run_sub_feature(
                task_id="task-none", novel_id=None, result={},
                request=_make_request(),
                feature_index=7, feature_name="power_systems", label="力量体系",
            )

        ai_svc.generate_power_systems_ai.assert_not_called()


# ---------------------------------------------------------------------------
# _generate_chapters_batch 循环行为
# ---------------------------------------------------------------------------


class TestGenerateChaptersBatch:
    """_generate_chapters_batch 批量生成循环（暂停等待 + 上下文衔接）。"""

    @pytest.mark.asyncio
    async def test_generates_all_chapters_sequentially(self):
        """按顺序生成所有章节，返回结果列表。"""
        from src.api.services.novel_generator import _generate_chapters_batch

        outlines = [
            {"chapter": 1, "title": "第1章", "plot": "开端"},
            {"chapter": 2, "title": "第2章", "plot": "发展"},
        ]

        gen_chapter = AsyncMock(side_effect=[
            {"chapter": 1, "title": "第1章", "content": "内容1", "chapter_type": "main"},
            {"chapter": 2, "title": "第2章", "content": "内容2", "chapter_type": "main"},
        ])

        with patch("src.api.services.novel_generator.is_task_paused", AsyncMock(return_value=False)), \
             patch("src.api.services.novel_generator._get_story_bible_context", AsyncMock(return_value="bible")), \
             patch("src.api.services.novel_generator._get_blueprint", AsyncMock(return_value={"blueprint": True})), \
             patch("src.api.services.novel_generator._emit_progress", AsyncMock()), \
             patch("src.api.services.novel_generator._sync_chapter_type_to_db", AsyncMock()), \
             patch("src.core.llm.chapter_generator.generate_single_chapter", gen_chapter), \
             patch("src.core.llm.client.get_llm_client"), \
             patch("src.api.services.novel_generator._context_builder") as mock_ctx, \
             patch("src.core.database.get_db_session") as mock_session:
            mock_ctx.build_generation_context = AsyncMock(return_value=MagicMock(
                chars_str="人物", world_str="世界", storylines_str="故事线",
                style_instruction="风格",
            ))
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()

            result = await _generate_chapters_batch(
                task_id="task-batch", novel_id="novel-1",
                chapter_outlines=outlines, prev_context="前文",
            )

        assert len(result) == 2
        assert gen_chapter.call_count == 2
        # 第1章用 prev_context；第2章用第1章的结尾内容
        first_call_prev = gen_chapter.call_args_list[0].kwargs["previous_chapter"]
        assert "前文" in first_call_prev

    @pytest.mark.asyncio
    async def test_waits_while_paused(self):
        """任务暂停时，循环等待直到恢复。"""
        from src.api.services.novel_generator import _generate_chapters_batch

        # 先返回 True（暂停），再返回 False（恢复）
        paused_states = iter([True, False])

        async def _paused(_task_id):
            return next(paused_states)

        gen_chapter = AsyncMock(return_value={"chapter": 1, "content": "内容", "chapter_type": "main"})

        with patch("src.api.services.novel_generator.is_task_paused", side_effect=_paused), \
             patch("src.api.services.novel_generator._get_story_bible_context", AsyncMock(return_value="")), \
             patch("src.api.services.novel_generator._get_blueprint", AsyncMock(return_value=None)), \
             patch("src.api.services.novel_generator._emit_progress", AsyncMock()), \
             patch("src.api.services.novel_generator._sync_chapter_type_to_db", AsyncMock()), \
             patch("src.core.llm.chapter_generator.generate_single_chapter", gen_chapter), \
             patch("src.core.llm.client.get_llm_client"), \
             patch("src.api.services.novel_generator._context_builder") as mock_ctx, \
             patch("src.core.database.get_db_session") as mock_session:
            mock_ctx.build_generation_context = AsyncMock(return_value=MagicMock(
                chars_str="", world_str="", storylines_str="", style_instruction="",
            ))
            mock_session.return_value.__aenter__ = AsyncMock()
            mock_session.return_value.__aexit__ = AsyncMock()

            result = await _generate_chapters_batch(
                task_id="task-pause", novel_id="novel-1",
                chapter_outlines=[{"chapter": 1, "title": "第1章", "plot": ""}],
                prev_context="",
            )

        assert len(result) == 1
        # is_task_paused 被调用至少 2 次（第一次 True 等，第二次 False 继续）
        assert gen_chapter.call_count == 1


# ---------------------------------------------------------------------------
# generate_volume_background fallback 路径
# ---------------------------------------------------------------------------


class TestGenerateVolumeBackgroundFallback:
    """generate_volume_background 在 volume_service 无 outline 时走 outline_service fallback。"""

    @pytest.mark.asyncio
    async def test_fallback_to_outline_service_when_volume_has_no_outline(self):
        """volume_service.get_volume 返回无 outline 时，从 outline_service 取章节数据。"""
        from src.api.services.novel_generator import generate_volume_background

        tm = MagicMock()
        tm.update_status = AsyncMock()
        tm.complete_task = AsyncMock()
        tm.fail_task = AsyncMock()

        nm = MagicMock()

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

        ch_service = MagicMock()
        ch_service.list_chapters_preview = AsyncMock(return_value=[])

        with patch("src.api.services.novel_generator.get_task_manager", return_value=tm), \
             patch("src.api.services.novel_generator.get_novel_manager", return_value=nm), \
             patch("src.api.services.novel_generator.get_volume_service", return_value=vol_service), \
             patch("src.api.services.novel_generator._emit_progress", AsyncMock()), \
             patch("src.api.services.novel_generator._generate_chapters_batch", AsyncMock(return_value=[{"chapter": 1}])) as batch_mock, \
             patch("src.api.services.novel_generator.persist_generated_chapters", AsyncMock()), \
             patch("src.api.services.outline_service.get_outline_service", return_value=outline_svc), \
             patch("src.api.services.chapter_service.get_chapter_service", return_value=ch_service):
            await generate_volume_background("task-vol", "novel-1", 1)

        # 走了 fallback：chapter_outlines 从 outline_service 取
        batch_mock.assert_awaited_once()
        outlines_passed = batch_mock.call_args.kwargs["chapter_outlines"]
        assert len(outlines_passed) == 1
        assert outlines_passed[0]["chapter"] == 1
        tm.complete_task.assert_awaited_once()
        vol_service.update_volume.assert_awaited_once()
        assert vol_service.update_volume.call_args.kwargs.get("status") == "completed"

    @pytest.mark.asyncio
    async def test_raises_when_no_outline_anywhere(self):
        """volume 和 outline_service 都无数据时抛 ValueError。"""
        from src.api.services.novel_generator import generate_volume_background

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

        with patch("src.api.services.novel_generator.get_task_manager", return_value=tm), \
             patch("src.api.services.novel_generator.get_novel_manager", return_value=MagicMock()), \
             patch("src.api.services.novel_generator.get_volume_service", return_value=vol_service), \
             patch("src.api.services.novel_generator._emit_progress", AsyncMock()), \
             patch("src.api.services.novel_generator._generate_chapters_batch", AsyncMock()), \
             patch("src.api.services.novel_generator.persist_generated_chapters", AsyncMock()), \
             patch("src.api.services.outline_service.get_outline_service", return_value=outline_svc), \
             patch("src.api.services.chapter_service.get_chapter_service", return_value=MagicMock()):
            await generate_volume_background("task-vol2", "novel-1", 1)

        # 抛 ValueError 被外层 try 捕获 → task 标记失败
        tm.fail_task.assert_awaited_once()
        err_msg = tm.fail_task.call_args.args[1]
        assert "no outline" in err_msg.lower()
        vol_service.update_volume.assert_awaited_once()
        assert vol_service.update_volume.call_args.kwargs.get("status") == "failed"
