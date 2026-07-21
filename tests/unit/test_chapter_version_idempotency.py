"""Task 5：ChapterVersion 幂等创建 + finalize_chapter_version 原子激活。

设计依据：docs/superpowers/specs/2026-07-20-long-form-stability-design.md
- B18：create_chapter_version 增加 keyword-only idempotency_key，命中已存在键返回其
  version_number，不新建。
- B10：新增 finalize_chapter_version——单事务 with_for_update 锁 Chapter + 所有版本，
  校验当前活跃版本==expected_active_version（不符抛 StaleChapterVersionError），激活
  selected + 清零其余 + 写回 Chapter.content/word_count/quality_status。

幂等语义（查重命中返回 + 部分唯一索引约束）必须用真实 DB 验证，mock 无法覆盖，故走真实
PG 集成路径（参照 tests/integration/test_change044_long_form_api.py 的 fixture 模式）。
"""

import uuid

import pytest
from sqlalchemy import text

from src.api.services.content.chapter_service import ChapterService, chapter_idem_key
from src.core.database import Base, get_db_session, get_engine
from src.core.exceptions import StaleChapterVersionError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
async def _db_setup():
    """建表（含部分唯一索引 uq_chapter_version_active / uq_chapter_version_idem）。

    session scope：整个 session 只建一次，session 结束才 drop_all——避免 module
    teardown drop 破坏后续 tests/unit module（混跑隔离），同时进程结束清库让下一个
    pytest 进程（如 tests/api）拿到干净库。
    """
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # novels.owner_id FK 引用 users，直接插 novel 需先保证 user id=1 存在
    # （conftest 的 mock_get_current_user 仅在 API 调用时 lazy 建 user，本模块不走 client）
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO users (id, username, hashed_password, is_admin)
                VALUES (1, 'idem_test_user', 'mocked', true)
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
                VALUES (:novel_id, :title, :idea, :novel_type, :target_words,
                    :status, :writing_style, :words_per_chapter, :is_long_form,
                    :total_volumes, :chapters_per_volume, :owner_id, NOW(), NOW())
                """
            ),
            {
                "novel_id": novel_id,
                "title": "Idempotency Test",
                "idea": "测试幂等创建与原子激活的足够长创意描述",
                "novel_type": "玄幻",
                "target_words": 1_000_000,
                "status": "generating",
                "writing_style": "现代白话",
                "words_per_chapter": 3000,
                "is_long_form": True,
                "total_volumes": 3,
                "chapters_per_volume": 10,
                "owner_id": 1,
            },
        )


async def _insert_chapter(novel_id: str, chapter_number: int, content: str = "原正文") -> None:
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO chapters (novel_id, chapter_number, volume_number, title,
                    content, word_count, chapter_type, status, updated_at)
                VALUES (:novel_id, :chapter_number, 1, :title,
                    :content, :word_count, 'normal', 'generated', NOW())
                ON CONFLICT (novel_id, chapter_number) DO UPDATE SET
                    content = :content, word_count = :word_count
                """
            ),
            {
                "novel_id": novel_id,
                "chapter_number": chapter_number,
                "title": f"Chapter {chapter_number}",
                "content": content,
                "word_count": len(content),
            },
        )


async def _count_versions(novel_id: str, chapter_number: int) -> int:
    async with get_db_session() as session:
        res = await session.execute(
            text(
                "SELECT COUNT(*) FROM chapter_versions "
                "WHERE novel_id = :nid AND chapter_number = :cn"
            ),
            {"nid": novel_id, "cn": chapter_number},
        )
        return res.scalar_one()


async def _active_version_number(novel_id: str, chapter_number: int) -> int | None:
    async with get_db_session() as session:
        res = await session.execute(
            text(
                "SELECT version_number FROM chapter_versions "
                "WHERE novel_id = :nid AND chapter_number = :cn AND is_active = true"
            ),
            {"nid": novel_id, "cn": chapter_number},
        )
        return res.scalar_one_or_none()


async def _chapter_content(novel_id: str, chapter_number: int) -> str | None:
    async with get_db_session() as session:
        res = await session.execute(
            text(
                "SELECT content FROM chapters "
                "WHERE novel_id = :nid AND chapter_number = :cn"
            ),
            {"nid": novel_id, "cn": chapter_number},
        )
        return res.scalar_one_or_none()


@pytest.fixture
async def fresh_novel_chapter(_db_setup):
    """每个测试独立 novel+chapter，避免版本号/活跃状态跨测试污染。"""
    novel_id = f"novel-idem-{uuid.uuid4().hex[:8]}"
    await _insert_novel(novel_id)
    await _insert_chapter(novel_id, chapter_number=1, content="原正文")
    return novel_id


# ---------------------------------------------------------------------------
# create_chapter_version 幂等（B18）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_version_with_idempotency_key_first_call_creates(fresh_novel_chapter):
    """首次带 idempotency_key 调用创建版本，返回版本号 1。"""
    svc = ChapterService()
    vn = await svc.create_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        content="baseline 正文",
        source="generation",
        is_active=False,
        idempotency_key="op-1:baseline:1",
    )
    assert vn == 1
    assert await _count_versions(fresh_novel_chapter, 1) == 1


@pytest.mark.asyncio
async def test_create_version_same_idempotency_key_returns_existing_no_duplicate(
    fresh_novel_chapter,
):
    """同 idempotency_key 第二次调用返回已存在版本号，DB 版本数不增。"""
    svc = ChapterService()
    key = "op-1:baseline:1"
    first = await svc.create_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        content="baseline 正文",
        source="generation",
        is_active=False,
        idempotency_key=key,
    )
    # 第二次带不同 content 但同 key——必须命中返回 first，不新建
    second = await svc.create_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        content="另一个正文应当被忽略",
        source="generation",
        is_active=False,
        idempotency_key=key,
    )
    assert second == first
    assert await _count_versions(fresh_novel_chapter, 1) == 1


@pytest.mark.asyncio
async def test_create_version_without_idempotency_key_still_works(fresh_novel_chapter):
    """无 idempotency_key 走原有 max+1 路径，每次新建——向后兼容（手动/回滚）。"""
    svc = ChapterService()
    v1 = await svc.create_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        content="手动版本A",
        source="manual",
    )
    v2 = await svc.create_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        content="手动版本B",
        source="manual",
    )
    assert v1 == 1 and v2 == 2
    assert await _count_versions(fresh_novel_chapter, 1) == 2


@pytest.mark.asyncio
async def test_create_version_different_idempotency_keys_create_distinct(
    fresh_novel_chapter,
):
    """不同 idempotency_key 视为不同写操作，各自新建。"""
    svc = ChapterService()
    baseline = await svc.create_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        content="baseline",
        source="generation",
        is_active=False,
        idempotency_key="op-1:baseline:1",
    )
    activate = await svc.create_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        content="candidate",
        source="ai_rewrite",
        is_active=False,
        idempotency_key="op-1:activate:1",
    )
    assert baseline == 1 and activate == 2
    assert await _count_versions(fresh_novel_chapter, 1) == 2


# ---------------------------------------------------------------------------
# finalize_chapter_version 原子激活（B10）
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_finalize_activates_selected_and_clears_others(fresh_novel_chapter):
    """finalize 激活 selected 版本，清零其余，写回 Chapter.content。"""
    svc = ChapterService()
    v1 = await svc.create_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        content="baseline",
        source="generation",
        is_active=False,
        idempotency_key="op-1:baseline:1",
    )
    v2 = await svc.create_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        content="candidate 改写",
        source="ai_rewrite",
        is_active=False,
        idempotency_key="op-1:activate:1",
    )
    # 当前无活跃版本（expected_active_version=None 表示从无活跃态首次激活）
    ok = await svc.finalize_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        expected_active_version=None,
        selected_version=v2,
    )
    assert ok is True
    assert await _active_version_number(fresh_novel_chapter, 1) == v2
    assert await _chapter_content(fresh_novel_chapter, 1) == "candidate 改写"


@pytest.mark.asyncio
async def test_finalize_stale_active_raises(fresh_novel_chapter):
    """expected_active_version 与当前活跃版本不符时抛 StaleChapterVersionError。"""
    svc = ChapterService()
    v1 = await svc.create_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        content="baseline",
        source="generation",
        is_active=True,  # 创建即激活，v1 成为活跃
        idempotency_key="op-1:baseline:1",
    )
    # 调用方基于过期页面以为活跃是 v1，但其实已被并发改为别的值——这里模拟 expected 不符
    with pytest.raises(StaleChapterVersionError):
        await svc.finalize_chapter_version(
            novel_id=fresh_novel_chapter,
            chapter_number=1,
            expected_active_version=v1 + 999,  # 故意不符
            selected_version=v1,
        )


@pytest.mark.asyncio
async def test_finalize_idempotent_when_already_active(fresh_novel_chapter):
    """恢复场景：selected 已是活跃版本，expected 匹配——幂等返回成功，不报错。"""
    svc = ChapterService()
    v1 = await svc.create_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        content="baseline",
        source="generation",
        is_active=True,
        idempotency_key="op-1:baseline:1",
    )
    ok = await svc.finalize_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        expected_active_version=v1,
        selected_version=v1,
    )
    assert ok is True
    assert await _active_version_number(fresh_novel_chapter, 1) == v1


@pytest.mark.asyncio
async def test_finalize_single_active_invariant_after_switch(fresh_novel_chapter):
    """finalize 切换活跃版本后，每章恰好一个 is_active=True（部分唯一索引保证）。"""
    svc = ChapterService()
    v1 = await svc.create_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        content="baseline",
        source="generation",
        is_active=True,
        idempotency_key="op-1:baseline:1",
    )
    v2 = await svc.create_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        content="改写候选",
        source="ai_rewrite",
        is_active=False,
        idempotency_key="op-1:activate:1",
    )
    await svc.finalize_chapter_version(
        novel_id=fresh_novel_chapter,
        chapter_number=1,
        expected_active_version=v1,
        selected_version=v2,
    )
    # 部分唯一索引保证：仍只有 v2 活跃
    assert await _active_version_number(fresh_novel_chapter, 1) == v2


# ---------------------------------------------------------------------------
# 幂等键构造 helper（重构步）
# ---------------------------------------------------------------------------

def test_chapter_idem_key_format():
    """幂等键格式 {operation_id}:{kind}:{chapter_number}。"""
    assert chapter_idem_key("novel-1:NOVEL_LONG_FORM", "baseline", 3) == (
        "novel-1:NOVEL_LONG_FORM:baseline:3"
    )
    assert chapter_idem_key("novel-1:volume:2", "activate", 17) == (
        "novel-1:volume:2:activate:17"
    )
