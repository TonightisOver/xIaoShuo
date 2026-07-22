from unittest.mock import AsyncMock, patch

import pytest

from src.api.services.creative_control.generation_dispatch import (
    CreativeGenerationDispatcher,
)
from src.api.services.tasks.task_dispatcher import TaskType
from src.core.creative_control.scope_planner import ScopePlan


def _novel():
    return {
        "novel_id": "novel-1",
        "idea": "测试创意",
        "novel_type": "玄幻",
        "target_words": 100000,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("endpoint", "payload", "expected_type"),
    [
        ("blueprint/generate", {"chapter_number": 4}, TaskType.NOVEL_BLUEPRINT.value),
        ("auto-improve", {"chapter_number": 5, "issue_ids": ["q1"]}, TaskType.NOVEL_QUALITY_FIX.value),
        (
            "generate-volume-outline",
            {"volume_number": 2},
            TaskType.NOVEL_VOLUME_OUTLINE.value,
        ),
    ],
)
async def test_dispatches_specialized_scope(endpoint, payload, expected_type):
    manager = AsyncMock()
    manager.create_task.return_value = "task-1"
    plan = ScopePlan(
        endpoint=endpoint,
        payload=payload,
        target_chapters=(
            [payload["chapter_number"]] if "chapter_number" in payload else []
        ),
    )

    with patch(
        "src.api.services.creative_control.generation_dispatch.get_task_manager",
        return_value=manager,
    ):
        result = await CreativeGenerationDispatcher().dispatch_scope(_novel(), 3, plan)

    assert result.task_type == expected_type
    assert manager.create_task.await_args.kwargs["task_type"] == expected_type
    assert manager.create_task.await_args.kwargs["task_payload"] == {
        "novel_id": "novel-1", **payload,
    }


@pytest.mark.asyncio
async def test_non_contiguous_targets_are_dispatched_as_separate_ranges():
    manager = AsyncMock()
    manager.create_task.side_effect = ["task-1", "task-2"]
    plan = ScopePlan(
        endpoint="generate-chapters",
        payload={"chapter_start": 1, "chapter_end": 4},
        target_chapters=[1, 2, 4],
        skipped_locked=[3],
    )

    with patch(
        "src.api.services.creative_control.generation_dispatch.get_task_manager",
        return_value=manager,
    ):
        result = await CreativeGenerationDispatcher().dispatch_scope(_novel(), 3, plan)

    assert result.task_ids == ["task-1", "task-2"]
    payloads = [call.kwargs["task_payload"] for call in manager.create_task.await_args_list]
    assert payloads == [
        {"novel_id": "novel-1", "chapter_start": 1, "chapter_end": 2},
        {"novel_id": "novel-1", "chapter_start": 4, "chapter_end": 4},
    ]


@pytest.mark.asyncio
async def test_repeated_user_operations_get_distinct_operation_ids():
    manager = AsyncMock()
    manager.create_task.side_effect = ["task-1", "task-2"]
    plan = ScopePlan(
        endpoint="generate-chapters",
        payload={"chapter_start": 3, "chapter_end": 3},
        target_chapters=[3],
    )

    with patch(
        "src.api.services.creative_control.generation_dispatch.get_task_manager",
        return_value=manager,
    ):
        dispatcher = CreativeGenerationDispatcher()
        await dispatcher.dispatch_scope(_novel(), 3, plan)
        await dispatcher.dispatch_scope(_novel(), 3, plan)

    operation_ids = [
        call.kwargs["operation_id"] for call in manager.create_task.await_args_list
    ]
    assert operation_ids[0] != operation_ids[1]


@pytest.mark.asyncio
async def test_blueprint_multi_chapter_dispatches_contiguous_ranges_with_per_chapter_detail():
    """blueprint_only 多章按连续区间合并投递 + 逐章 accepted/skipped 明细。"""
    manager = AsyncMock()
    manager.create_task.side_effect = ["task-a", "task-b"]
    plan = ScopePlan(
        endpoint="blueprint/generate",
        payload={"chapter_numbers": [1, 2, 4]},
        target_chapters=[1, 2, 4],
        skipped_locked=[3],
        skipped_confirmed=[],
    )
    with patch(
        "src.api.services.creative_control.generation_dispatch.get_task_manager",
        return_value=manager,
    ):
        result = await CreativeGenerationDispatcher().dispatch_scope(_novel(), 3, plan)

    # 两个连续区间 [1,2] 和 [4,4] → 两个任务
    assert result.task_ids == ["task-a", "task-b"]
    payloads = [call.kwargs["task_payload"] for call in manager.create_task.await_args_list]
    assert payloads == [
        {"novel_id": "novel-1", "chapter_start": 1, "chapter_end": 2},
        {"novel_id": "novel-1", "chapter_start": 4, "chapter_end": 4},
    ]
    # 逐章明细
    accepted_chapters = {a["chapter_number"] for a in result.accepted}
    assert accepted_chapters == {1, 2, 4}
    assert result.skipped_locked == [3]
    assert result.skipped_confirmed == []


@pytest.mark.asyncio
async def test_blueprint_dispatch_already_generating_skipped():
    """control_status=generating 的章被标 already_generating（由 planner 预计算经 plan 传入）。"""
    manager = AsyncMock()
    manager.create_task.return_value = "task-x"
    plan = ScopePlan(
        endpoint="blueprint/generate",
        payload={"chapter_numbers": [5]},
        target_chapters=[5],
    )
    with patch(
        "src.api.services.creative_control.generation_dispatch.get_task_manager",
        return_value=manager,
    ):
        result = await CreativeGenerationDispatcher().dispatch_scope(_novel(), 3, plan)
    assert {a["chapter_number"] for a in result.accepted} == {5}


@pytest.mark.asyncio
async def test_blueprint_dispatch_failed_to_enqueue_records_error():
    """入队异常的章进 failed_to_enqueue，不中断其他章。"""
    manager = AsyncMock()

    async def _boom(**kwargs):
        if kwargs.get("task_payload", {}).get("chapter_start") == 4:
            raise RuntimeError("queue down")
        return "task-ok"

    manager.create_task.side_effect = _boom
    plan = ScopePlan(
        endpoint="blueprint/generate",
        payload={"chapter_numbers": [1, 2, 4]},
        target_chapters=[1, 2, 4],
    )
    with patch(
        "src.api.services.creative_control.generation_dispatch.get_task_manager",
        return_value=manager,
    ):
        result = await CreativeGenerationDispatcher().dispatch_scope(_novel(), 3, plan)
    failed = {f["chapter_number"]: f["error"] for f in result.failed_to_enqueue}
    assert 4 in failed
    accepted = {a["chapter_number"] for a in result.accepted}
    assert accepted == {1, 2}
