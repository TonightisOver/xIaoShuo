"""CreativeArtifactWriteService 首次生成边界测试。"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.services.creative_control.artifact_write_service import (
    CreativeArtifactWriteService,
)


@pytest.mark.asyncio
async def test_missing_product_has_no_baseline_before_first_generation():
    service = CreativeArtifactWriteService()
    service._adapters.load_in_session = AsyncMock(
        side_effect=ValueError("artifact not found: blueprint/9")
    )
    session = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    session.add = MagicMock()

    await service._ensure_baseline_snapshot_in_session(
        session, "novel-1", "blueprint", "9", None
    )

    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_generated_artifact_can_record_control_in_same_transaction(monkeypatch):
    service = CreativeArtifactWriteService()
    service._controls.assert_generation_allowed_in_session = AsyncMock()
    service._ensure_baseline_snapshot_in_session = AsyncMock()
    service._adapters.save_in_session = AsyncMock(return_value={"plot_goal": "目标"})
    service._snapshot_in_session = AsyncMock(return_value=1)
    service._controls.record_generated_in_session = AsyncMock(
        return_value={"version": 1}
    )
    session = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session

    monkeypatch.setattr(
        "src.api.services.creative_control.artifact_write_service.get_db_session",
        fake_session,
    )

    version = await service.record_generated_artifact(
        novel_id="novel-1",
        artifact_type="blueprint",
        artifact_id="9",
        content={"plot_goal": "目标"},
        task_id="sync-9",
        operation_id="sync-9",
        record_control=True,
        generation_meta={"source": "synchronous_dependency"},
    )

    assert version == 1
    service._controls.record_generated_in_session.assert_awaited_once()
    assert (
        service._controls.record_generated_in_session.await_args.args[0]
        is session
    )
