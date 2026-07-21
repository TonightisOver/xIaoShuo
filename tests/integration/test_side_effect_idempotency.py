"""Task 11：副作用幂等（StoryBible applied_version + KG 抽取幂等）。

设计依据：docs/superpowers/specs/2026-07-20-long-form-stability-design.md §五 B19/B20。
覆盖：
- update_bible_after_generation(applied_version=N)：Chapter.bible_applied_version>=N
  则跳过 LLM（返回 skipped=True）。
- 成功后写 bible_applied_version=N。
- extract_from_chapter：KnowledgeExtractionLog.status=='completed' 则跳过。
- 传入 applied_version 时 kg_applied_version 哨兵同样生效。
"""

import uuid

import pytest
from sqlalchemy import text

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
                VALUES (1, 'idem_side_test', 'mocked', true)
                ON CONFLICT (id) DO NOTHING
                """
            ),
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
                VALUES (:novel_id, 'Idem Side', '副作用幂等测试的足够长创意描述',
                    '玄幻', 1000000, 'generating', '现代白话', 3000, true, 1, 3, 1,
                    NOW(), NOW())
                """
            ),
            {"novel_id": novel_id},
        )


async def _insert_chapter(novel_id: str, chapter_number: int) -> None:
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO chapters (novel_id, chapter_number, volume_number, title,
                    content, word_count, chapter_type, status, updated_at)
                VALUES (:novel_id, :chapter_number, 1, :title,
                    :content, :word_count, 'normal', 'generated', NOW())
                ON CONFLICT (novel_id, chapter_number) DO UPDATE SET
                    content = :content
                """
            ),
            {
                "novel_id": novel_id,
                "chapter_number": chapter_number,
                "title": f"Chapter {chapter_number}",
                "content": "章节正文内容",
                "word_count": 8,
            },
        )


async def _insert_story_bible(novel_id: str) -> None:
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO story_bibles (novel_id, main_goals, unresolved_hooks,
                    timeline_events, character_cards, updated_at)
                VALUES (:novel_id, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb, '[]'::jsonb,
                    NOW())
                ON CONFLICT (novel_id) DO NOTHING
                """
            ),
            {"novel_id": novel_id},
        )


async def _bible_applied(novel_id: str, chapter_number: int) -> int | None:
    async with get_db_session() as session:
        res = await session.execute(
            text(
                "SELECT bible_applied_version FROM chapters "
                "WHERE novel_id = :nid AND chapter_number = :cn"
            ),
            {"nid": novel_id, "cn": chapter_number},
        )
        return res.scalar_one_or_none()


@pytest.fixture
async def novel_chapter(_db_setup):
    novel_id = f"novel-side-{uuid.uuid4().hex[:8]}"
    await _insert_novel(novel_id)
    await _insert_chapter(novel_id, 1)
    await _insert_story_bible(novel_id)
    return novel_id


# ---------------------------------------------------------------------------
# update_bible_after_generation 幂等（B19）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_bible_skipped_when_already_applied(novel_chapter, monkeypatch):
    """bible_applied_version >= applied_version → 跳过 LLM，返回 skipped=True。"""
    from src.api.services.content.story_bible_service import (
        update_bible_after_generation,
    )

    # 先把哨兵置为 5
    async with get_db_session() as session:
        await session.execute(
            text(
                "UPDATE chapters SET bible_applied_version = 5 "
                "WHERE novel_id = :nid AND chapter_number = 1"
            ),
            {"nid": novel_chapter},
        )

    # 用 applied_version=3（< 5）应被跳过
    summary = await update_bible_after_generation(
        novel_chapter, 1, "新内容", {"chapter": 1}, applied_version=3
    )
    assert summary.get("skipped") is True


@pytest.mark.asyncio
async def test_bible_writes_applied_version_on_success(novel_chapter, monkeypatch):
    """成功后写回 bible_applied_version=N。"""

    # mock LLM 返回空更新（不报错，正常走完）
    from unittest.mock import AsyncMock, MagicMock

    from src.api.services.content.story_bible_service import (
        update_bible_after_generation,
    )

    fake_client = MagicMock()
    fake_client.generate = AsyncMock(return_value='{"new_events": []}')
    monkeypatch.setattr(
        "src.core.llm.client.get_llm_client",
        lambda: fake_client,
    )

    await update_bible_after_generation(
        novel_chapter, 1, "正文内容", {"chapter": 1}, applied_version=7
    )
    assert await _bible_applied(novel_chapter, 1) == 7


# ---------------------------------------------------------------------------
# extract_from_chapter 幂等（B20）
# ---------------------------------------------------------------------------

async def _has_completed_kg_log(novel_id: str, chapter_number: int) -> bool:
    async with get_db_session() as session:
        res = await session.execute(
            text(
                "SELECT COUNT(*) FROM knowledge_extraction_logs "
                "WHERE novel_id = :nid AND chapter_number = :cn AND status = 'completed'"
            ),
            {"nid": novel_id, "cn": chapter_number},
        )
        return res.scalar_one() > 0


@pytest.mark.asyncio
async def test_kg_skipped_when_log_completed(novel_chapter, monkeypatch):
    """已有 completed 抽取日志 → 跳过 LLM，返回 skipped=True。"""
    from src.api.services.knowledge.knowledge_graph_service import (
        KnowledgeGraphService,
    )

    # 插入一条 completed 日志
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO knowledge_extraction_logs (id, novel_id, chapter_number,
                    status, entities_count, triples_count, duration_ms, created_at)
                VALUES ('log-1', :nid, 1, 'completed', 3, 2, 100, NOW())
                """
            ),
            {"nid": novel_chapter},
        )

    monkeypatch.setenv("KNOWLEDGE_GRAPH_ENABLED", "true")
    result = await KnowledgeGraphService().extract_from_chapter(
        novel_chapter, 1, "正文", applied_version=1
    )
    assert result.get("skipped") is True
    assert result["entities_count"] == 3


@pytest.mark.asyncio
async def test_kg_skipped_when_version_sentinel(novel_chapter, monkeypatch):
    """kg_applied_version >= applied_version → 跳过（版本哨兵）。"""
    from src.api.services.knowledge.knowledge_graph_service import (
        KnowledgeGraphService,
    )

    async with get_db_session() as session:
        await session.execute(
            text(
                "UPDATE chapters SET kg_applied_version = 9 "
                "WHERE novel_id = :nid AND chapter_number = 1"
            ),
            {"nid": novel_chapter},
        )

    monkeypatch.setenv("KNOWLEDGE_GRAPH_ENABLED", "true")
    result = await KnowledgeGraphService().extract_from_chapter(
        novel_chapter, 1, "正文", applied_version=5
    )
    assert result.get("skipped") is True
