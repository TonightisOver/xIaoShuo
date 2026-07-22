"""持久化任务 dispatcher 的白名单与参数重建测试。"""

from unittest.mock import AsyncMock, patch

import pytest

from src.api.models.requests import CreateNovelRequest, LongFormNovelRequest


def _create_request() -> CreateNovelRequest:
    return CreateNovelRequest(
        idea="一个程序员穿越到修仙世界并重建宗门的故事",
        novel_type="玄幻",
        target_words=100000,
    )


def _long_request() -> LongFormNovelRequest:
    return LongFormNovelRequest(
        idea="一个程序员穿越到修仙世界并写下百万字传奇的故事",
        novel_type="玄幻",
        target_words=1_000_000,
        volumes=10,
        chapters_per_volume=40,
        words_per_chapter=3000,
    )


@pytest.mark.asyncio
async def test_dispatches_standard_generation_with_rebuilt_request():
    from src.api.services.tasks.task_dispatcher import TaskType, dispatch_task

    handler = AsyncMock()
    request = _create_request()
    with patch(
        "src.api.services.generation.novel_generator.generate_novel_background", handler
    ):
        await dispatch_task(
            {
                "task_id": "task-1",
                "task_type": TaskType.NOVEL_GENERATE.value,
                "task_payload": {
                    "request": request.model_dump(mode="json")
                },
            }
        )

    handler.assert_awaited_once()
    task_id, rebuilt = handler.await_args.args
    assert task_id == "task-1"
    assert isinstance(rebuilt, CreateNovelRequest)
    assert rebuilt == request


@pytest.mark.asyncio
async def test_dispatches_full_generation():
    from src.api.services.tasks.task_dispatcher import TaskType, dispatch_task

    handler = AsyncMock()
    request = _create_request()
    with patch(
        "src.api.services.generation.novel_generator.generate_novel_full_background",
        handler,
    ):
        await dispatch_task(
            {
                "task_id": "task-2",
                "task_type": TaskType.NOVEL_FULL_GENERATE.value,
                "task_payload": {
                    "request": request.model_dump(mode="json")
                },
            }
        )

    handler.assert_awaited_once()
    assert isinstance(handler.await_args.args[1], CreateNovelRequest)


@pytest.mark.asyncio
async def test_dispatches_long_form_generation():
    from src.api.services.tasks.task_dispatcher import TaskType, dispatch_task

    handler = AsyncMock()
    request = _long_request()
    with patch(
        "src.api.services.generation.long_form_generation_helpers.generate_long_form_background",
        handler,
    ):
        await dispatch_task(
            {
                "task_id": "task-3",
                "task_type": TaskType.NOVEL_LONG_FORM.value,
                "task_payload": {
                    "novel_id": "novel-3",
                    "request": request.model_dump(mode="json"),
                },
            }
        )

    task_id, novel_id, rebuilt = handler.await_args.args
    assert (task_id, novel_id) == ("task-3", "novel-3")
    assert isinstance(rebuilt, LongFormNovelRequest)
    assert rebuilt == request
    # B1: worker_id 缺省注入为 None（离线/直调场景）
    assert handler.await_args.kwargs.get("worker_id") is None


@pytest.mark.asyncio
async def test_dispatches_volume_generation():
    from src.api.services.tasks.task_dispatcher import TaskType, dispatch_task

    handler = AsyncMock()
    with patch(
        "src.api.services.generation.long_form_generation_helpers.generate_volume_background",
        handler,
    ):
        await dispatch_task(
            {
                "task_id": "task-4",
                "task_type": TaskType.NOVEL_VOLUME.value,
                "task_payload": {
                    "novel_id": "novel-4",
                    "volume_number": 7,
                },
            }
        )

    handler.assert_awaited_once_with("task-4", "novel-4", 7, worker_id=None)


@pytest.mark.asyncio
async def test_dispatches_chapter_range_generation():
    from src.api.services.tasks.task_dispatcher import TaskType, dispatch_task

    handler = AsyncMock()
    with patch(
        "src.api.services.generation.long_form_generation_helpers.generate_chapters_background",
        handler,
    ):
        await dispatch_task(
            {
                "task_id": "task-5",
                "task_type": TaskType.NOVEL_CHAPTERS.value,
                "task_payload": {
                    "novel_id": "novel-5",
                    "chapter_start": 11,
                    "chapter_end": 20,
                },
            }
        )

    handler.assert_awaited_once_with("task-5", "novel-5", 11, 20, worker_id=None)


@pytest.mark.asyncio
async def test_dispatches_blueprint_generation():
    from src.api.services.tasks.task_dispatcher import TaskType, dispatch_task

    handler = AsyncMock()
    with patch(
        "src.api.services.generation.creative_control_tasks.generate_blueprint_background",
        handler,
    ):
        await dispatch_task({
            "task_id": "task-blueprint",
            "task_type": TaskType.NOVEL_BLUEPRINT.value,
            "worker_id": "worker-1",
            "task_payload": {"novel_id": "novel-1", "chapter_number": 8},
        })

    handler.assert_awaited_once_with(
        "task-blueprint", "novel-1", 8, worker_id="worker-1"
    )


@pytest.mark.asyncio
async def test_dispatches_quality_fix():
    from src.api.services.tasks.task_dispatcher import TaskType, dispatch_task

    handler = AsyncMock()
    with patch(
        "src.api.services.generation.creative_control_tasks.fix_quality_background",
        handler,
    ):
        await dispatch_task({
            "task_id": "task-quality",
            "task_type": TaskType.NOVEL_QUALITY_FIX.value,
            "task_payload": {
                "novel_id": "novel-1",
                "chapter_number": 9,
                "issue_ids": ["issue-1"],
            },
        })

    handler.assert_awaited_once_with(
        "task-quality", "novel-1", 9,
        issue_ids=["issue-1"], worker_id=None,
    )


@pytest.mark.asyncio
async def test_dispatches_volume_outline_generation():
    from src.api.services.tasks.task_dispatcher import TaskType, dispatch_task

    handler = AsyncMock()
    with patch(
        "src.api.services.generation.creative_control_tasks.generate_volume_outline_background",
        handler,
    ):
        await dispatch_task({
            "task_id": "task-volume-outline",
            "task_type": TaskType.NOVEL_VOLUME_OUTLINE.value,
            "task_payload": {"novel_id": "novel-1", "volume_number": 2},
        })

    handler.assert_awaited_once_with(
        "task-volume-outline", "novel-1", 2, worker_id=None
    )


@pytest.mark.asyncio
async def test_control_target_is_completed_after_generation_task():
    from src.api.services.tasks.task_dispatcher import TaskType, dispatch_task

    handler = AsyncMock()
    with patch(
        "src.api.services.generation.long_form_generation_helpers.generate_chapters_background",
        handler,
    ), patch(
        "src.core.creative_control.control_service.CreativeControlService"
    ) as controls, patch(
        "src.api.services.tasks.task_dispatcher.get_task_manager"
    ) as task_manager:
        controls.return_value.complete_generating = AsyncMock(return_value=3)
        task_manager.return_value.get_task = AsyncMock(
            return_value={"status": "completed", "error": None}
        )
        await dispatch_task({
            "task_id": "task-controlled",
            "task_type": TaskType.NOVEL_CHAPTERS.value,
            "task_payload": {
                "novel_id": "novel-1",
                "chapter_start": 7,
                "chapter_end": 7,
                "control_target": {
                    "artifact_type": "chapter",
                    "artifact_id": "7",
                    "generating_version": 2,
                },
            },
        })

    controls.return_value.complete_generating.assert_awaited_once()
    assert controls.return_value.complete_generating.await_args.kwargs["expected_version"] == 2


@pytest.mark.asyncio
async def test_control_target_is_failed_when_handler_swallows_task_failure():
    from src.api.services.tasks.task_dispatcher import TaskType, dispatch_task

    handler = AsyncMock()
    with patch(
        "src.api.services.generation.long_form_generation_helpers.generate_chapters_background",
        handler,
    ), patch(
        "src.core.creative_control.control_service.CreativeControlService"
    ) as controls, patch(
        "src.api.services.tasks.task_dispatcher.get_task_manager"
    ) as task_manager:
        task_manager.return_value.get_task = AsyncMock(
            return_value={"status": "failed", "error": "模型超时"}
        )
        controls.return_value.fail_generating = AsyncMock(return_value=3)
        await dispatch_task({
            "task_id": "task-controlled-failed",
            "task_type": TaskType.NOVEL_CHAPTERS.value,
            "task_payload": {
                "novel_id": "novel-1",
                "chapter_start": 7,
                "chapter_end": 7,
                "control_target": {
                    "artifact_type": "chapter",
                    "artifact_id": "7",
                    "generating_version": 2,
                },
            },
        })

    controls.return_value.fail_generating.assert_awaited_once()
    controls.return_value.complete_generating.assert_not_called()


@pytest.mark.asyncio
async def test_worker_id_from_claim_propagates_to_long_form_handler():
    """B1: _run_claim 注入的 worker_id 应透传给长篇 handler 做 lease 守卫。"""
    from src.api.services.tasks.task_dispatcher import TaskType, dispatch_task

    handler = AsyncMock()
    request = _long_request()
    with patch(
        "src.api.services.generation.long_form_generation_helpers.generate_long_form_background",
        handler,
    ):
        await dispatch_task(
            {
                "task_id": "task-7",
                "task_type": TaskType.NOVEL_LONG_FORM.value,
                "worker_id": "worker-abc",
                "task_payload": {
                    "novel_id": "novel-7",
                    "request": request.model_dump(mode="json"),
                },
            }
        )

    assert handler.await_args.kwargs.get("worker_id") == "worker-abc"


@pytest.mark.asyncio
async def test_dispatches_pipeline_resume():
    from src.api.services.tasks.task_dispatcher import TaskType, dispatch_task

    handler = AsyncMock()
    decision = {
        "approval_status": "revision",
        "revision_instructions": "加强冲突",
    }
    with patch("src.api.services.generation.novel_generator.resume_pipeline", handler):
        await dispatch_task(
            {
                "task_id": "task-6",
                "task_type": TaskType.PIPELINE_RESUME.value,
                "task_payload": {"decision": decision},
            }
        )

    handler.assert_awaited_once_with("task-6", decision)


@pytest.mark.asyncio
async def test_rejects_unknown_task_type():
    from src.api.services.tasks.task_dispatcher import dispatch_task

    with pytest.raises(ValueError, match="Unsupported task type"):
        await dispatch_task(
            {
                "task_id": "task-x",
                "task_type": "python.call:anything",
                "task_payload": {},
            }
        )


@pytest.mark.asyncio
async def test_rejects_malformed_payload_before_handler_call():
    from src.api.services.tasks.task_dispatcher import TaskType, dispatch_task

    handler = AsyncMock()
    with patch(
        "src.api.services.generation.novel_generator.generate_novel_background", handler
    ), pytest.raises(KeyError):
        await dispatch_task(
            {
                "task_id": "task-bad",
                "task_type": TaskType.NOVEL_GENERATE.value,
                "task_payload": {},
            }
        )

    handler.assert_not_awaited()
