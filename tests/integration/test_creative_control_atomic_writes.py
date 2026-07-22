import uuid

import pytest
from sqlalchemy import select, text

from src.api.models.db_models import (
    ArtifactControl,
    ArtifactVersion,
    Chapter,
    ChapterVersion,
    OperationLog,
    WorldSetting,
)
from src.api.services.creative_control.artifact_write_service import (
    CreativeArtifactWriteService,
)
from src.core.database import Base, get_db_session, get_engine
from src.core.exceptions import StaleChapterVersionError


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
