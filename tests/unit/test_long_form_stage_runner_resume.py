"""单章持久化状态机必须从检查点阶段继续，而不是从 baseline 重跑。"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.api.services.generation.chapter_recovery import RecoveryAction
from src.core.quality.gate import GateResult


@pytest.mark.asyncio
async def test_load_persisted_chapter_result_uses_requested_version_content() -> None:
    from src.api.services.generation import long_form_generation_helpers as helpers

    chapter_service = SimpleNamespace(
        get_chapter_version=AsyncMock(
            return_value={
                "version_number": 4,
                "content": "最终版本正文",
                "word_count": 6,
            }
        )
    )
    manager = SimpleNamespace(
        get_chapter=AsyncMock(
            return_value={"chapter": 7, "title": "第七章", "content": "旧正文"}
        )
    )
    with (
        patch(
            "src.api.services.content.chapter_service.get_chapter_service",
            return_value=chapter_service,
        ),
        patch(
            "src.api.services.content.novel_manager.get_novel_manager",
            return_value=manager,
        ),
    ):
        result = await helpers._load_persisted_chapter_result("novel-1", 7, 4)

    assert result["content"] == "最终版本正文"
    assert result["word_count"] == 6
    chapter_service.get_chapter_version.assert_awaited_once_with("novel-1", 7, 4)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("action", "advance_count", "gate_count", "side_effect_count"),
    [
        (RecoveryAction.RUN_QUALITY, 3, 1, 1),
        (RecoveryAction.RUN_SIDE_EFFECTS, 2, 0, 1),
        (RecoveryAction.COMPLETE_CHAPTER, 1, 0, 0),
    ],
)
async def test_run_chapter_stages_resumes_without_replaying_completed_phases(
    action: RecoveryAction,
    advance_count: int,
    gate_count: int,
    side_effect_count: int,
) -> None:
    from src.api.services.generation import long_form_generation_helpers as helpers

    store = SimpleNamespace(
        assert_lease_held=AsyncMock(),
        advance_checkpoint=AsyncMock(side_effect=range(11, 11 + advance_count)),
        allocate_event_sequence=AsyncMock(return_value=7),
    )
    manager = SimpleNamespace(
        update_state_delta=AsyncMock(),
        update_quality_status=AsyncMock(),
    )
    chapter_service = SimpleNamespace(
        create_chapter_version=AsyncMock(return_value=2),
        finalize_chapter_version=AsyncMock(),
        get_chapter_version=AsyncMock(
            return_value={"version_number": 2, "content": "持久化正文"}
        ),
    )
    gate = AsyncMock(
        return_value=GateResult(
            final_content="持久化正文",
            quality_status="verified",
            quality_scores={"overall": 0.8},
            state_delta={},
            final_version_number=None,
        )
    )
    bible = AsyncMock()
    kg_extract = AsyncMock()
    progress_service = SimpleNamespace(update_volume_status=AsyncMock())
    chapter_result = {
        "chapter": 7,
        "title": "第七章",
        "content": "持久化正文",
        "word_count": 5,
        "chapter_type": "normal",
    }

    with (
        patch(
            "src.api.services.tasks.checkpoint_store.get_checkpoint_store",
            return_value=store,
        ),
        patch(
            "src.api.services.content.novel_manager.get_novel_manager",
            return_value=manager,
        ),
        patch(
            "src.api.services.content.chapter_service.get_chapter_service",
            return_value=chapter_service,
        ),
        patch("src.core.quality.gate.run_quality_gate", new=gate),
        patch(
            "src.api.services.content.story_bible_service.update_bible_after_generation",
            new=bible,
        ),
        patch(
            "src.api.services.knowledge.knowledge_graph_service.KnowledgeGraphService"
        ) as kg_service,
        patch.object(helpers, "persist_single_chapter", new=AsyncMock()) as persist,
        patch.object(helpers, "_sync_chapter_type_to_db", new=AsyncMock()),
        patch.object(helpers, "_emit_progress", new=AsyncMock()),
        patch.object(
            helpers,
            "get_long_form_progress_service",
            return_value=progress_service,
        ),
    ):
        kg_service.return_value.extract_from_chapter = kg_extract
        result = await helpers._run_chapter_stages(
            task_id="task-1",
            novel_id="novel-1",
            worker_id="worker-1",
            operation_id="op-1",
            volume_number=1,
            global_ch_num=7,
            total_chapters=10,
            chapter_start=1,
            completed_before=0,
            ch_outline={"chapter": 7, "title": "第七章"},
            chapter_result=chapter_result,
            vol_ch_idx=6,
            request=None,
            world_str="{}",
            chars_str="{}",
            expected_checkpoint_version=10,
            recovery_action=action,
            active_version_number=2,
        )

    assert result == 10 + advance_count
    assert store.advance_checkpoint.await_count == advance_count
    assert gate.await_count == gate_count
    assert bible.await_count == side_effect_count
    assert kg_extract.await_count == side_effect_count
    persist.assert_not_awaited()
    chapter_service.create_chapter_version.assert_not_awaited()


@pytest.mark.asyncio
async def test_required_side_effect_failure_marks_checkpoint_retryable() -> None:
    from src.api.services.generation import long_form_generation_helpers as helpers

    store = SimpleNamespace(
        assert_lease_held=AsyncMock(),
        advance_checkpoint=AsyncMock(),
        mark_failed=AsyncMock(return_value=True),
    )
    manager = SimpleNamespace(
        update_state_delta=AsyncMock(),
        update_quality_status=AsyncMock(),
    )
    chapter_service = SimpleNamespace(
        create_chapter_version=AsyncMock(),
        finalize_chapter_version=AsyncMock(),
        get_chapter_version=AsyncMock(return_value={"content": "最终正文"}),
    )
    bible = AsyncMock(side_effect=RuntimeError("bible unavailable"))

    with (
        patch(
            "src.api.services.tasks.checkpoint_store.get_checkpoint_store",
            return_value=store,
        ),
        patch(
            "src.api.services.content.novel_manager.get_novel_manager",
            return_value=manager,
        ),
        patch(
            "src.api.services.content.chapter_service.get_chapter_service",
            return_value=chapter_service,
        ),
        patch(
            "src.api.services.content.story_bible_service.update_bible_after_generation",
            new=bible,
        ),
        pytest.raises(RuntimeError, match="story_bible"),
    ):
        await helpers._run_chapter_stages(
            task_id="task-1",
            novel_id="novel-1",
            worker_id="worker-1",
            operation_id="op-1",
            volume_number=1,
            global_ch_num=7,
            total_chapters=10,
            chapter_start=1,
            completed_before=0,
            ch_outline={"chapter": 7},
            chapter_result={"chapter": 7, "content": "最终正文"},
            vol_ch_idx=6,
            request=None,
            world_str="{}",
            chars_str="{}",
            expected_checkpoint_version=10,
            recovery_action=RecoveryAction.RUN_SIDE_EFFECTS,
            active_version_number=2,
        )

    store.mark_failed.assert_awaited_once_with(
        "task-1",
        "worker-1",
        category="side_effect_retryable",
        detail={"chapter_number": 7, "component": "story_bible"},
        recoverable=True,
    )
    store.advance_checkpoint.assert_not_awaited()
