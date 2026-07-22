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
    ],
)
async def test_dispatches_specialized_scope(endpoint, payload, expected_type):
    manager = AsyncMock()
    manager.create_task.return_value = "task-1"
    plan = ScopePlan(endpoint=endpoint, payload=payload, target_chapters=[payload["chapter_number"]])

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
