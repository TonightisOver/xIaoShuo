import uuid

import pytest
from sqlalchemy import select, text

from src.api.models.db_models import (
    ArtifactControl,
    ArtifactVersion,
    Chapter,
    ChapterVersion,
    OperationLog,
    Outline,
    Task,
    TaskCheckpoint,
    WorldSetting,
)
from src.api.services.creative_control.artifact_write_service import (
    CreativeArtifactWriteService,
)
from src.api.services.tasks.task_manager import TaskManager
from src.core.database import Base, get_db_session, get_engine
from src.core.exceptions import (
    ArtifactBusyError,
    ArtifactLockedError,
    LeaseLost,
    StaleChapterVersionError,
)


@pytest.fixture(scope="module", autouse=True)
async def _database():
    engine = get_engine()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with get_db_session() as session:
        await session.execute(text(
            "INSERT INTO users (id, username, hashed_password, is_admin) "
            "VALUES (1, 'creative_atomic', 'mocked', true) "
            "ON CONFLICT (id) DO NOTHING"
        ))
    yield
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


async def _seed() -> str:
    novel_id = f"creative-{uuid.uuid4().hex[:10]}"
    async with get_db_session() as session:
        await session.execute(text(
            "INSERT INTO novels "
            "(novel_id, title, idea, novel_type, target_words, status, "
            "writing_style, owner_id, is_long_form, words_per_chapter, "
            "created_at, updated_at) VALUES "
            "(:id, '测试', '创作控制原子写入测试', '玄幻', 100000, "
            "'draft', '现代白话', 1, false, 3000, NOW(), NOW())"
        ), {"id": novel_id})
        session.add_all([
            WorldSetting(novel_id=novel_id, rules="旧规则"),
            ArtifactControl(
                novel_id=novel_id, artifact_type="world", artifact_id=novel_id,
                control_status="generated", version=1, stage=2,
            ),
            ArtifactVersion(
                novel_id=novel_id, artifact_type="world", artifact_id=novel_id,
                version_number=1, content_snapshot={"rules": "旧规则"},
                source="manual", is_active=True,
            ),
            Chapter(
                novel_id=novel_id, chapter_number=1, title="第一章",
                content="旧正文", word_count=3, status="generated",
                quality_status="verified",
            ),
            ChapterVersion(
                novel_id=novel_id, chapter_number=1, version_number=1,
                content="旧正文", word_count=3, source="manual", is_active=True,
            ),
            ArtifactControl(
                novel_id=novel_id, artifact_type="chapter", artifact_id="1",
                control_status="generated", version=1, stage=7,
            ),
        ])
    return novel_id


@pytest.mark.asyncio
async def test_world_edit_and_rollback_are_single_transaction_round_trips():
    novel_id = await _seed()
    service = CreativeArtifactWriteService()

    edited = await service.edit_artifact(
        novel_id=novel_id,
        artifact_type="world",
        artifact_id=novel_id,
        content={"rules": "新规则"},
        expected_control_version=1,
        expected_active_version=None,
        operator_id=1,
    )
    assert (edited.control_version, edited.artifact_version) == (2, 2)

    rolled_back = await service.rollback_artifact(
        novel_id=novel_id,
        artifact_type="world",
        artifact_id=novel_id,
        target_version=1,
        expected_control_version=2,
        expected_active_version=None,
        operator_id=1,
    )
    assert (rolled_back.control_version, rolled_back.artifact_version) == (3, 1)

    async with get_db_session() as session:
        world = (await session.execute(
            select(WorldSetting).where(WorldSetting.novel_id == novel_id)
        )).scalar_one()
        versions = list((await session.execute(
            select(ArtifactVersion).where(ArtifactVersion.novel_id == novel_id)
        )).scalars().all())
        logs = list((await session.execute(
            select(OperationLog).where(OperationLog.novel_id == novel_id)
        )).scalars().all())
    assert world.rules == "旧规则"
    assert [item.version_number for item in versions if item.is_active] == [1]
    assert [item.action for item in logs] == ["edit", "rollback"]


@pytest.mark.asyncio
async def test_first_partial_edit_creates_full_baseline_and_full_new_snapshot():
    novel_id = await _seed()
    async with get_db_session() as session:
        await session.execute(
            text("DELETE FROM artifact_versions WHERE novel_id = :novel_id"),
            {"novel_id": novel_id},
        )
        await session.execute(
            text(
                "UPDATE world_settings SET background = '旧背景' "
                "WHERE novel_id = :novel_id"
            ),
            {"novel_id": novel_id},
        )

    edited = await CreativeArtifactWriteService().edit_artifact(
        novel_id=novel_id,
        artifact_type="world",
        artifact_id=novel_id,
        content={"rules": "局部新规则"},
        expected_control_version=1,
        expected_active_version=None,
        operator_id=1,
    )
    assert edited.artifact_version == 2

    async with get_db_session() as session:
        versions = list((await session.execute(
            select(ArtifactVersion)
            .where(ArtifactVersion.novel_id == novel_id)
            .order_by(ArtifactVersion.version_number)
        )).scalars().all())

    assert versions[0].content_snapshot["background"] == "旧背景"
    assert versions[0].content_snapshot["rules"] == "旧规则"
    assert versions[1].content_snapshot["background"] == "旧背景"
    assert versions[1].content_snapshot["rules"] == "局部新规则"


@pytest.mark.asyncio
async def test_stale_chapter_edit_rolls_back_every_related_write():
    novel_id = await _seed()
    service = CreativeArtifactWriteService()
    first = await service.edit_artifact(
        novel_id=novel_id,
        artifact_type="chapter",
        artifact_id="1",
        content="新正文",
        expected_control_version=1,
        expected_active_version=1,
        operator_id=1,
    )
    assert (first.control_version, first.artifact_version) == (2, 2)

    with pytest.raises(StaleChapterVersionError):
        await service.edit_artifact(
            novel_id=novel_id,
            artifact_type="chapter",
            artifact_id="1",
            content="并发覆盖",
            expected_control_version=2,
            expected_active_version=1,
            operator_id=1,
        )

    async with get_db_session() as session:
        chapter = (await session.execute(
            select(Chapter).where(
                Chapter.novel_id == novel_id, Chapter.chapter_number == 1
            )
        )).scalar_one()
        versions = list((await session.execute(
            select(ChapterVersion).where(ChapterVersion.novel_id == novel_id)
        )).scalars().all())
        control = (await session.execute(
            select(ArtifactControl).where(
                ArtifactControl.novel_id == novel_id,
                ArtifactControl.artifact_type == "chapter",
            )
        )).scalar_one()
    assert chapter.content == "新正文"
    assert control.version == 2
    assert len(versions) == 2
    assert [item.version_number for item in versions if item.is_active] == [2]


@pytest.mark.asyncio
async def test_lock_sets_single_source_of_truth_and_blocks_generation():
    from src.core.creative_control.control_service import CreativeControlService
    from src.core.creative_control.scope_planner import GenerationScopePlanner

    novel_id = await _seed()
    controls = CreativeControlService()
    approved = await controls.approve(
        novel_id, "chapter", "1", expected_version=1, operator_id=1
    )
    locked = await controls.lock(
        novel_id, "chapter", "1", expected_version=approved, operator_id=1
    )

    assert locked == 3
    assert await GenerationScopePlanner()._load_locked_chapters(novel_id) == [1]
    with pytest.raises(ArtifactLockedError):
        await controls.assert_generation_allowed(novel_id, "chapter", "1")


@pytest.mark.asyncio
async def test_generated_volume_outline_updates_body_and_version_atomically():
    novel_id = await _seed()
    async with get_db_session() as session:
        session.add_all([
            Outline(
                novel_id=novel_id,
                level="volume",
                volume_number=1,
                content={"title": "旧卷纲", "chapters": []},
            ),
            ArtifactControl(
                novel_id=novel_id,
                artifact_type="volume_outline",
                artifact_id="1",
                control_status="generating",
                version=2,
                stage=5,
            ),
            ArtifactVersion(
                novel_id=novel_id,
                artifact_type="volume_outline",
                artifact_id="1",
                version_number=1,
                content_snapshot={"title": "旧卷纲", "chapters": []},
                source="manual",
                is_active=True,
            ),
        ])

    version = await CreativeArtifactWriteService().record_generated_artifact(
        novel_id=novel_id,
        artifact_type="volume_outline",
        artifact_id="1",
        content={"title": "新卷纲", "chapters": [{"chapter": 1}]},
        task_id="task-volume-1",
        operation_id="op-volume-1",
        model="deepseek",
    )

    async with get_db_session() as session:
        outline = (await session.execute(
            select(Outline).where(
                Outline.novel_id == novel_id,
                Outline.level == "volume",
                Outline.volume_number == 1,
            )
        )).scalar_one()
        versions = list((await session.execute(
            select(ArtifactVersion)
            .where(
                ArtifactVersion.novel_id == novel_id,
                ArtifactVersion.artifact_type == "volume_outline",
                ArtifactVersion.artifact_id == "1",
            )
            .order_by(ArtifactVersion.version_number)
        )).scalars().all())

    assert version == 2
    assert outline.content["title"] == "新卷纲"
    assert [item.version_number for item in versions if item.is_active] == [2]
    assert versions[1].content_snapshot == {
        "title": "新卷纲",
        "chapters": [{"chapter": 1}],
    }
    assert versions[1].task_id == "task-volume-1"
    assert versions[1].operation_id == "op-volume-1"


@pytest.mark.asyncio
async def test_task_creation_atomically_reserves_chapter_and_rejects_overlap():
    novel_id = await _seed()
    manager = TaskManager()
    task_id = await manager.create_task(
        idea="并发占用测试",
        novel_type="玄幻",
        target_words=100000,
        novel_id=novel_id,
        owner_id=1,
        task_type="novel.chapters",
        task_payload={"novel_id": novel_id, "chapter_start": 1, "chapter_end": 1},
        operation_id=f"{novel_id}:chapters:1-1:first",
        generation_targets=[{
            "artifact_type": "chapter",
            "artifact_id": "1",
            "expected_version": 1,
        }],
    )

    async with get_db_session() as session:
        task = (await session.execute(
            select(Task).where(Task.task_id == task_id)
        )).scalar_one()
        control = (await session.execute(
            select(ArtifactControl).where(
                ArtifactControl.novel_id == novel_id,
                ArtifactControl.artifact_type == "chapter",
                ArtifactControl.artifact_id == "1",
            )
        )).scalar_one()

    assert control.control_status == "generating"
    assert control.generation_meta["task_id"] == task_id
    assert task.task_payload["control_targets"] == [{
        "artifact_type": "chapter",
        "artifact_id": "1",
        "generating_version": 2,
    }]

    with pytest.raises(ArtifactBusyError):
        await manager.create_task(
            idea="重叠任务",
            novel_type="玄幻",
            target_words=100000,
            novel_id=novel_id,
            owner_id=1,
            task_type="novel.chapters",
            task_payload={"novel_id": novel_id, "chapter_start": 1, "chapter_end": 1},
            operation_id=f"{novel_id}:chapters:1-1:second",
            generation_targets=[{
                "artifact_type": "chapter",
                "artifact_id": "1",
            }],
        )

    async with get_db_session() as session:
        task_count = (await session.execute(
            select(Task).where(Task.novel_id == novel_id)
        )).scalars().all()
    assert len(task_count) == 1


@pytest.mark.asyncio
async def test_partial_chapter_failure_finishes_task_and_controls_atomically():
    novel_id = await _seed()
    manager = TaskManager()
    task_id = await manager.create_task(
        idea="部分失败测试",
        novel_type="玄幻",
        target_words=100000,
        novel_id=novel_id,
        owner_id=1,
        task_type="novel.chapters",
        task_payload={"novel_id": novel_id, "chapter_start": 1, "chapter_end": 1},
        operation_id=f"{novel_id}:partial",
        generation_targets=[{"artifact_type": "chapter", "artifact_id": "1"}],
    )

    await manager.complete_task(
        task_id,
        {"chapters": [{"chapter": 1, "generation_failed": True}]},
    )

    async with get_db_session() as session:
        task = (await session.execute(
            select(Task).where(Task.task_id == task_id)
        )).scalar_one()
        control = (await session.execute(
            select(ArtifactControl).where(
                ArtifactControl.novel_id == novel_id,
                ArtifactControl.artifact_type == "chapter",
                ArtifactControl.artifact_id == "1",
            )
        )).scalar_one()
    assert task.status == "partially_completed"
    assert control.control_status == "failed"
    assert control.generation_meta["status"] == "failed"


@pytest.mark.asyncio
async def test_retry_keeps_reservation_and_exhaustion_fails_it_atomically():
    novel_id = await _seed()
    manager = TaskManager()
    task_id = await manager.create_task(
        idea="重试占用测试",
        novel_type="玄幻",
        target_words=100000,
        novel_id=novel_id,
        owner_id=1,
        task_type="novel.chapters",
        task_payload={"novel_id": novel_id, "chapter_start": 1, "chapter_end": 1},
        operation_id=f"{novel_id}:retry",
        max_attempts=2,
        generation_targets=[{"artifact_type": "chapter", "artifact_id": "1"}],
    )
    async with get_db_session() as session:
        await session.execute(
            text(
                "UPDATE tasks SET status='running', queue_state='leased', "
                "attempt_count=1, lease_owner='worker-a', "
                "lease_expires_at=NOW() + INTERVAL '5 minutes' "
                "WHERE task_id=:task_id"
            ),
            {"task_id": task_id},
        )

    assert await manager.retry_or_fail_claim(task_id, "worker-a", "暂时失败", 0)
    async with get_db_session() as session:
        control = (await session.execute(
            select(ArtifactControl).where(
                ArtifactControl.novel_id == novel_id,
                ArtifactControl.artifact_type == "chapter",
                ArtifactControl.artifact_id == "1",
            )
        )).scalar_one()
    assert control.control_status == "generating"

    async with get_db_session() as session:
        await session.execute(
            text(
                "UPDATE tasks SET status='running', queue_state='leased', "
                "attempt_count=2, lease_owner='worker-b', "
                "lease_expires_at=NOW() + INTERVAL '5 minutes' "
                "WHERE task_id=:task_id"
            ),
            {"task_id": task_id},
        )
    assert not await manager.retry_or_fail_claim(task_id, "worker-b", "最终失败", 0)
    async with get_db_session() as session:
        control = (await session.execute(
            select(ArtifactControl).where(
                ArtifactControl.novel_id == novel_id,
                ArtifactControl.artifact_type == "chapter",
                ArtifactControl.artifact_id == "1",
            )
        )).scalar_one()
    assert control.control_status == "failed"


@pytest.mark.asyncio
async def test_manual_retry_reacquires_failed_controls_and_resets_attempts():
    novel_id = await _seed()
    manager = TaskManager()
    operation_id = f"{novel_id}:manual-retry"
    task_id = await manager.create_task(
        idea="人工重试占用测试",
        novel_type="玄幻",
        target_words=100000,
        novel_id=novel_id,
        owner_id=1,
        task_type="novel.chapters",
        task_payload={"novel_id": novel_id, "chapter_start": 1, "chapter_end": 1},
        operation_id=operation_id,
        max_attempts=2,
        generation_targets=[{"artifact_type": "chapter", "artifact_id": "1"}],
    )
    async with get_db_session() as session:
        task = (await session.execute(
            select(Task).where(Task.task_id == task_id)
        )).scalar_one()
        task.attempt_count = task.max_attempts
        session.add(TaskCheckpoint(
            task_id=task_id,
            novel_id=novel_id,
            operation_id=operation_id,
            current_stage="chapter_completed",
            status="failed",
            failure_category="recoverable",
            recoverable=True,
        ))

    await manager.fail_task(task_id, "达到自动重试上限")
    result = await manager.retry_task(task_id)
    assert result.requeued is True

    async with get_db_session() as session:
        task = (await session.execute(
            select(Task).where(Task.task_id == task_id)
        )).scalar_one()
        control = (await session.execute(
            select(ArtifactControl).where(
                ArtifactControl.novel_id == novel_id,
                ArtifactControl.artifact_type == "chapter",
                ArtifactControl.artifact_id == "1",
            )
        )).scalar_one()
    assert task.status == "pending"
    assert task.queue_state == "queued"
    assert task.attempt_count == 0
    assert task.completed_at is None
    assert control.control_status == "generating"
    assert control.generation_meta["task_id"] == task_id
    assert task.task_payload["control_targets"][0]["generating_version"] == control.version


@pytest.mark.asyncio
async def test_abort_finishes_reserved_controls_in_same_transaction():
    novel_id = await _seed()
    manager = TaskManager()
    operation_id = f"{novel_id}:abort"
    task_id = await manager.create_task(
        idea="人工中止占用测试",
        novel_type="玄幻",
        target_words=100000,
        novel_id=novel_id,
        owner_id=1,
        task_type="novel.chapters",
        task_payload={"novel_id": novel_id, "chapter_start": 1, "chapter_end": 1},
        operation_id=operation_id,
        generation_targets=[{"artifact_type": "chapter", "artifact_id": "1"}],
    )
    async with get_db_session() as session:
        session.add(TaskCheckpoint(
            task_id=task_id,
            novel_id=novel_id,
            operation_id=operation_id,
            current_stage="chapter_started",
            status="running",
        ))

    result = await manager.abort_task(task_id)
    assert result.requeued is True

    async with get_db_session() as session:
        task = (await session.execute(
            select(Task).where(Task.task_id == task_id)
        )).scalar_one()
        control = (await session.execute(
            select(ArtifactControl).where(
                ArtifactControl.novel_id == novel_id,
                ArtifactControl.artifact_type == "chapter",
                ArtifactControl.artifact_id == "1",
            )
        )).scalar_one()
    assert task.status == "failed"
    assert control.control_status == "failed"
    assert control.generation_meta["status"] == "failed"


@pytest.mark.asyncio
async def test_stale_attempt_cannot_write_after_new_worker_claims_task():
    from src.core.creative_control.control_service import (
        CreativeControlService,
        bind_generation_task,
    )

    novel_id = await _seed()
    manager = TaskManager()
    task_id = await manager.create_task(
        idea="fencing 测试",
        novel_type="玄幻",
        target_words=100000,
        novel_id=novel_id,
        owner_id=1,
        task_type="novel.chapters",
        task_payload={"novel_id": novel_id, "chapter_start": 1, "chapter_end": 1},
        operation_id=f"{novel_id}:fence",
        generation_targets=[{"artifact_type": "chapter", "artifact_id": "1"}],
    )
    async with get_db_session() as session:
        await session.execute(
            text(
                "UPDATE tasks SET status='running', queue_state='leased', "
                "attempt_count=2, lease_owner='worker-new', "
                "lease_expires_at=NOW() + INTERVAL '5 minutes' "
                "WHERE task_id=:task_id"
            ),
            {"task_id": task_id},
        )

    bind_generation_task(task_id, worker_id="worker-old", attempt_count=1)
    with pytest.raises(LeaseLost):
        await CreativeControlService().assert_generation_allowed(
            novel_id, "chapter", "1"
        )
    from src.api.services.content.chapter_service import get_chapter_service

    with pytest.raises(LeaseLost):
        await get_chapter_service().finalize_chapter_version(
            novel_id,
            1,
            expected_active_version=1,
            selected_version=1,
        )
    with pytest.raises(LeaseLost):
        await get_chapter_service().update_state_delta(
            novel_id, 1, {"stale_worker": True}
        )
    with pytest.raises(LeaseLost):
        await get_chapter_service().update_quality_status(
            novel_id, 1, "failed"
        )

    from src.api.services.content.world_service import get_world_service

    with pytest.raises(LeaseLost):
        await get_world_service().create_power_system(
            novel_id, "旧 worker 的力量体系"
        )

    from src.api.services.generation.chapter_persistence_service import (
        persist_langgraph_result,
    )

    with pytest.raises(LeaseLost):
        await persist_langgraph_result(
            novel_id,
            {"chapters": [{"chapter": 1, "content": "旧 worker 覆盖"}]},
        )

    from src.api.services.generation.chapter_persistence_service import (
        persist_quality_to_version,
    )

    with pytest.raises(LeaseLost):
        await persist_quality_to_version(
            novel_id, 1, {"overall": 0.1}, [{"type": "stale_worker"}]
        )

    from src.api.services.generation.long_form_generation_helpers import (
        _persist_quality_for_gate,
    )

    with pytest.raises(LeaseLost):
        await _persist_quality_for_gate(
            novel_id, 1, {"overall": 0.2}, [{"type": "stale_worker"}]
        )

    with pytest.raises(LeaseLost):
        await CreativeControlService().record_generated(
            novel_id,
            "chapter",
            "1",
            generation_meta={"source": "stale_worker"},
        )
