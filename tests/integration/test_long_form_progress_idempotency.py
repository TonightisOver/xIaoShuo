"""长篇进度初始化的数据库级幂等与并发覆盖。"""

import asyncio
import uuid

import pytest
from sqlalchemy import text

from src.api.services.generation.long_form_progress_service import (
    LongFormProgressService,
)
from src.core.database import Base, get_db_session, get_engine


@pytest.fixture(scope="module")
async def _db_setup():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO users (id, username, hashed_password, is_admin)
                VALUES (1, 'progress_test_user', 'mocked', true)
                ON CONFLICT (id) DO NOTHING
                """
            )
        )
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _insert_novel(novel_id: str) -> None:
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO novels (novel_id, title, idea, novel_type, target_words,
                    status, writing_style, words_per_chapter, is_long_form, total_volumes,
                    chapters_per_volume, owner_id, created_at, updated_at)
                VALUES (:novel_id, 'Progress Test', :idea, '玄幻', 1000000,
                    'generating', '现代白话', 3000, true, 3, 10, 1, NOW(), NOW())
                """
            ),
            {"novel_id": novel_id, "idea": "验证长篇进度初始化并发幂等的足够长描述"},
        )


async def _progress_rows(novel_id: str) -> list[tuple[int, str, int]]:
    async with get_db_session() as session:
        result = await session.execute(
            text(
                """
                SELECT volume_number, status, chapters_completed
                FROM long_form_progress
                WHERE novel_id = :novel_id
                ORDER BY volume_number
                """
            ),
            {"novel_id": novel_id},
        )
        return [(row[0], row[1], row[2]) for row in result.all()]


@pytest.mark.asyncio
async def test_initialize_progress_is_concurrent_and_state_preserving(_db_setup):
    novel_id = f"novel-progress-{uuid.uuid4().hex[:8]}"
    await _insert_novel(novel_id)
    service = LongFormProgressService()

    first, second = await asyncio.gather(
        service.initialize_progress(novel_id, 3, 10),
        service.initialize_progress(novel_id, 3, 10),
    )

    assert [row["volume_number"] for row in first] == [1, 2, 3]
    assert [row["volume_number"] for row in second] == [1, 2, 3]
    assert await _progress_rows(novel_id) == [
        (1, "pending", 0),
        (2, "pending", 0),
        (3, "pending", 0),
    ]

    async with get_db_session() as session:
        await session.execute(
            text(
                """
                UPDATE long_form_progress
                SET status = 'completed', chapters_completed = 10
                WHERE novel_id = :novel_id AND volume_number = 1
                """
            ),
            {"novel_id": novel_id},
        )

    replayed = await service.initialize_progress(novel_id, 3, 10)

    assert replayed[0]["status"] == "completed"
    assert await _progress_rows(novel_id) == [
        (1, "completed", 10),
        (2, "pending", 0),
        (3, "pending", 0),
    ]
