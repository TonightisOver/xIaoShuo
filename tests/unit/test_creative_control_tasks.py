"""创作控制后台任务的操作归属回归测试。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.asyncio
async def test_quality_fix_uses_unique_operation_id_from_task():
    from src.api.services.generation.creative_control_tasks import (
        fix_quality_background,
    )

    task_manager = SimpleNamespace(
        update_status=AsyncMock(),
        get_task=AsyncMock(
            return_value={"operation_id": "novel-1:quality-fix:8:dispatch-unique"}
        ),
        complete_task=AsyncMock(),
        fail_task=AsyncMock(),
    )
    call_order = []

    async def get_active(*args, **kwargs):
        call_order.append("read_active")
        return {"version_number": 3}

    async def improve_chapter(*args, **kwargs):
        call_order.append("improve")
        return {
            "quality_status": "verified",
            "best_version": 4,
            "final_scores": {"overall": 0.82},
        }

    async def finalize(*args, **kwargs):
        call_order.append("finalize")
        return True

    chapter_service = SimpleNamespace(
        get_active_chapter_version=AsyncMock(side_effect=get_active),
        finalize_chapter_version=AsyncMock(side_effect=finalize),
    )
    improve = AsyncMock(side_effect=improve_chapter)

    with (
        patch(
            "src.api.services.generation.creative_control_tasks.get_task_manager",
            return_value=task_manager,
        ),
        patch(
            "src.api.services.generation.creative_control_tasks.CreativeControlService.assert_generation_allowed",
            new=AsyncMock(),
        ),
        patch(
            "src.api.services.generation.creative_control_tasks.RewriteLoopService.auto_improve_chapter",
            new=improve,
        ),
        patch(
            "src.api.services.generation.creative_control_tasks.get_chapter_service",
            return_value=chapter_service,
        ),
    ):
        await fix_quality_background("task-1", "novel-1", 8, worker_id="worker-1")

    improve.assert_awaited_once_with(
        novel_id="novel-1",
        chapter_number=8,
        operation_id="novel-1:quality-fix:8:dispatch-unique",
    )
    chapter_service.finalize_chapter_version.assert_awaited_once_with(
        "novel-1",
        8,
        expected_active_version=3,
        selected_version=4,
        quality_score=0.82,
        quality_scores={"overall": 0.82},
    )
    assert call_order == ["read_active", "improve", "finalize"]
