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
    improve = AsyncMock(return_value={"quality_status": "verified"})

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
    ):
        await fix_quality_background("task-1", "novel-1", 8, worker_id="worker-1")

    improve.assert_awaited_once_with(
        novel_id="novel-1",
        chapter_number=8,
        operation_id="novel-1:quality-fix:8:dispatch-unique",
    )
