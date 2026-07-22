"""Task 6：generate_volume_chapters 接入检查点 6 阶段状态机。

设计依据：docs/superpowers/specs/2026-07-20-long-form-stability-design.md §持久化伪代码。

覆盖：
- _run_chapter_stages 单章推进 baseline_persisted → quality_finalized →
  side_effects_recorded → chapter_completed，checkpoint 记录正确 stage +
  last_completed_chapter + active_version_number。
- baseline 版本创建为活跃（带 {op}:baseline:{n} 幂等键），gate 不碰版本。
- lease 丢失（lease_expires_at 过期）时 assert_lease_held 抛 LeaseLost，
  向上传播、不推进 checkpoint、不写垃圾。
- generate_volume_chapters 跳过已完成章节（last_completed_chapter=N → 从 N+1 起）。

版本/激活/幂等/乐观锁语义须真实 DB 验证，故走真实 PG 集成路径
（参照 tests/unit/test_chapter_version_idempotency.py 的 fixture 模式）。
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import text

from src.core.database import Base, get_db_session, get_engine
from src.core.exceptions import LeaseLost
from src.core.quality.gate import GateResult

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
                VALUES (1, 'cp_test_user', 'mocked', true)
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
                "title": "Checkpoint Test",
                "idea": "测试检查点 6 阶段状态机的足够长创意描述",
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


async def _insert_task(
    task_id: str,
    novel_id: str,
    *,
    lease_owner: str = "worker-a",
    lease_offset_minutes: int = 5,
) -> None:
    """插入带 lease 的 running 任务行。lease_offset_minutes<0 表示已过期。"""
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO tasks (task_id, operation_id, novel_id, status, idea,
                    novel_type, target_words, created_at, queue_state, attempt_count,
                    max_attempts, lease_owner, lease_expires_at, owner_id)
                VALUES (:task_id, :operation_id, :novel_id, 'running', :idea,
                    :novel_type, :target_words, NOW(), 'leased', 1, 3,
                    :lease_owner, :lease_expires_at, 1)
                """
            ),
            {
                "task_id": task_id,
                "operation_id": f"{novel_id}:long_form",
                "novel_id": novel_id,
                "idea": "检查点测试任务",
                "novel_type": "玄幻",
                "target_words": 1_000_000,
                "lease_owner": lease_owner,
                "lease_expires_at": datetime.now(UTC)
                + timedelta(minutes=lease_offset_minutes),
            },
        )


async def _insert_checkpoint(
    task_id: str,
    novel_id: str,
    *,
    checkpoint_version: int = 0,
    last_completed_chapter: int = 0,
    current_stage: str = "chapter_planned",
) -> None:
    async with get_db_session() as session:
        await session.execute(
            text(
                """
                INSERT INTO task_checkpoints (task_id, novel_id, operation_id,
                    current_stage, checkpoint_version, status, last_completed_volume,
                    last_completed_chapter, attempt_number, last_event_sequence,
                    pause_requested, recoverable, updated_at)
                VALUES (:task_id, :novel_id, :operation_id, :current_stage,
                    :checkpoint_version, 'running', 0, :last_completed_chapter, 0, 0,
                    false, true, NOW())
                """
            ),
            {
                "task_id": task_id,
                "novel_id": novel_id,
                "operation_id": f"{novel_id}:long_form",
                "current_stage": current_stage,
                "checkpoint_version": checkpoint_version,
                "last_completed_chapter": last_completed_chapter,
            },
        )


async def _read_checkpoint(task_id: str) -> dict:
    async with get_db_session() as session:
        res = await session.execute(
            text(
                "SELECT current_stage, last_completed_chapter, active_version_number, "
                "checkpoint_version FROM task_checkpoints WHERE task_id = :tid"
            ),
            {"tid": task_id},
        )
        row = res.one()
        return {
            "current_stage": row[0],
            "last_completed_chapter": row[1],
            "active_version_number": row[2],
            "checkpoint_version": row[3],
        }


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


async def _active_version(novel_id: str, chapter_number: int) -> int | None:
    async with get_db_session() as session:
        res = await session.execute(
            text(
                "SELECT version_number FROM chapter_versions "
                "WHERE novel_id = :nid AND chapter_number = :cn AND is_active = true"
            ),
            {"nid": novel_id, "cn": chapter_number},
        )
        return res.scalar_one_or_none()


def _make_chapter_result(chapter_number: int, content: str = "崭新章节正文内容") -> dict:
    return {
        "chapter": chapter_number,
        "title": f"第{chapter_number}章",
        "content": content,
        "word_count": len(content),
        "chapter_type": "normal",
        "volume_number": 1,
        "state_delta": {},
    }


def _verified_gate_result(content: str) -> GateResult:
    """gate 直接判定 verified（不走 L3），final_version_number=None → 沿用 baseline。"""
    return GateResult(
        final_content=content,
        quality_status="verified",
        quality_scores={"overall": 0.8},
        state_delta={},
        final_version_number=None,
    )


@pytest.fixture
async def novel_task(_db_setup):
    """独立 novel + task + checkpoint，避免跨测试污染。"""
    novel_id = f"novel-cp-{uuid.uuid4().hex[:8]}"
    task_id = f"task-cp-{uuid.uuid4().hex[:8]}"
    await _insert_novel(novel_id)
    return novel_id, task_id


# ---------------------------------------------------------------------------
# _run_chapter_stages：单章 4 阶段推进
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_run_chapter_stages_advances_all_stages(novel_task):
    """单章走完 4 阶段，checkpoint 终于 chapter_completed + last_completed_chapter=n。"""
    from src.api.services.generation import long_form_generation_helpers as h

    novel_id, task_id = novel_task
    await _insert_chapter(novel_id, 6, content="占位")
    await _insert_task(task_id, novel_id)
    # _run_chapter_stages 接收已生成的 chapter_result，调用契约要求生成阶段
    # 已持久化；因此 baseline_persisted 的合法前驱是 generation_started。
    await _insert_checkpoint(
        task_id,
        novel_id,
        checkpoint_version=0,
        current_stage="generation_started",
    )

    chapter_result = _make_chapter_result(6)

    with (
        patch(
            "src.core.quality.gate.run_quality_gate",
            new=AsyncMock(return_value=_verified_gate_result(chapter_result["content"])),
        ),
        patch(
            "src.api.services.content.story_bible_service.update_bible_after_generation",
            new=AsyncMock(return_value={}),
        ),
    ):
        new_cpv = await h._run_chapter_stages(
            task_id=task_id,
            novel_id=novel_id,
            worker_id="worker-a",
            operation_id=f"{novel_id}:long_form",
            volume_number=1,
            global_ch_num=6,
            total_chapters=10,
            chapter_start=6,
            completed_before=5,
            ch_outline={"chapter": 6, "title": "第6章"},
            chapter_result=chapter_result,
            vol_ch_idx=0,
            request=None,
            world_str="{}",
            chars_str="{}",
            expected_checkpoint_version=0,
        )

    # 4 阶段 → checkpoint_version 从 0 推进到 4
    assert new_cpv == 4
    cp = await _read_checkpoint(task_id)
    assert cp["current_stage"] == "chapter_completed"
    assert cp["last_completed_chapter"] == 6
    # baseline 版本活跃，gate 未择优出新版本 → active 仍为 baseline
    assert cp["active_version_number"] == await _active_version(novel_id, 6)
    # 只创建了 baseline 一个版本（gate 未走 L3）
    assert await _count_versions(novel_id, 6) == 1


@pytest.mark.asyncio
async def test_run_chapter_stages_baseline_version_active(novel_task):
    """baseline 阶段创建活跃版本；重复调用（幂等键）不产生第二个版本。"""
    from src.api.services.generation import long_form_generation_helpers as h

    novel_id, task_id = novel_task
    await _insert_chapter(novel_id, 1, content="占位")
    await _insert_task(task_id, novel_id)
    await _insert_checkpoint(
        task_id,
        novel_id,
        checkpoint_version=0,
        current_stage="generation_started",
    )

    chapter_result = _make_chapter_result(1)

    with (
        patch(
            "src.core.quality.gate.run_quality_gate",
            new=AsyncMock(return_value=_verified_gate_result(chapter_result["content"])),
        ),
        patch(
            "src.api.services.content.story_bible_service.update_bible_after_generation",
            new=AsyncMock(return_value={}),
        ),
    ):
        await h._run_chapter_stages(
            task_id=task_id, novel_id=novel_id, worker_id="worker-a",
            operation_id=f"{novel_id}:long_form", volume_number=1,
            global_ch_num=1, total_chapters=10, chapter_start=1,
            completed_before=0, ch_outline={"chapter": 1}, chapter_result=chapter_result,
            vol_ch_idx=0, request=None, world_str="{}", chars_str="{}",
            expected_checkpoint_version=0,
        )

    assert await _active_version(novel_id, 1) is not None
    assert await _count_versions(novel_id, 1) == 1


@pytest.mark.asyncio
async def test_run_chapter_stages_lease_lost_raises(novel_task):
    """lease 过期时首个 assert_lease_held 抛 LeaseLost，不推进 checkpoint。"""
    from src.api.services.generation import long_form_generation_helpers as h

    novel_id, task_id = novel_task
    await _insert_chapter(novel_id, 3, content="占位")
    await _insert_task(task_id, novel_id, lease_offset_minutes=-5)  # 已过期
    await _insert_checkpoint(task_id, novel_id, checkpoint_version=0)

    chapter_result = _make_chapter_result(3)

    with (
        patch(
            "src.core.quality.gate.run_quality_gate",
            new=AsyncMock(return_value=_verified_gate_result(chapter_result["content"])),
        ),
        patch(
            "src.api.services.content.story_bible_service.update_bible_after_generation",
            new=AsyncMock(return_value={}),
        ),
        pytest.raises(LeaseLost),
    ):
        await h._run_chapter_stages(
            task_id=task_id, novel_id=novel_id, worker_id="worker-a",
            operation_id=f"{novel_id}:long_form", volume_number=1,
            global_ch_num=3, total_chapters=10, chapter_start=1,
            completed_before=0, ch_outline={"chapter": 3}, chapter_result=chapter_result,
            vol_ch_idx=0, request=None, world_str="{}", chars_str="{}",
            expected_checkpoint_version=0,
        )

    # checkpoint 未推进（仍在初始 chapter_planned / version 0）
    cp = await _read_checkpoint(task_id)
    assert cp["checkpoint_version"] == 0
    assert cp["current_stage"] == "chapter_planned"


@pytest.mark.asyncio
async def test_run_chapter_stages_wrong_worker_lease_lost(novel_task):
    """lease_owner 不匹配（另一 worker 抢占）时抛 LeaseLost。"""
    from src.api.services.generation import long_form_generation_helpers as h

    novel_id, task_id = novel_task
    await _insert_chapter(novel_id, 2, content="占位")
    await _insert_task(task_id, novel_id, lease_owner="worker-other")
    await _insert_checkpoint(task_id, novel_id, checkpoint_version=0)

    chapter_result = _make_chapter_result(2)

    with (
        patch(
            "src.core.quality.gate.run_quality_gate",
            new=AsyncMock(return_value=_verified_gate_result(chapter_result["content"])),
        ),
        patch(
            "src.api.services.content.story_bible_service.update_bible_after_generation",
            new=AsyncMock(return_value={}),
        ),
        pytest.raises(LeaseLost),
    ):
        await h._run_chapter_stages(
            task_id=task_id, novel_id=novel_id, worker_id="worker-a",
            operation_id=f"{novel_id}:long_form", volume_number=1,
            global_ch_num=2, total_chapters=10, chapter_start=1,
            completed_before=0, ch_outline={"chapter": 2}, chapter_result=chapter_result,
            vol_ch_idx=0, request=None, world_str="{}", chars_str="{}",
            expected_checkpoint_version=0,
        )


# ---------------------------------------------------------------------------
# generate_volume_chapters：崩溃恢复跳过已完成章节
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gvc_skips_completed_chapters_on_resume(novel_task):
    """checkpoint last_completed_chapter=5 时，从第 6 章开始，前 5 章不重新生成。"""
    from src.api.services.generation import long_form_generation_helpers as h

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id)
    await _insert_checkpoint(
        task_id, novel_id, checkpoint_version=7, last_completed_chapter=5,
        current_stage="chapter_completed",
    )

    # 卷纲含 6 章（全局章号 1-6）；前 5 章已完成应跳过，仅第 6 章走生成。
    vol_outline = {
        "chapters": [{"chapter": n, "title": f"第{n}章", "plot": "推进"} for n in range(1, 7)]
    }

    generated_calls: list[int] = []

    async def _fake_stream(ctx):
        ch_num = ctx.chapter_outline["chapter"]
        generated_calls.append(ch_num)
        return _make_chapter_result(ch_num)

    async def _fake_stages(**kwargs):
        # 记录进入阶段机的章号，返回递增 checkpoint_version
        return kwargs["expected_checkpoint_version"] + 4

    with (
        patch(
            "src.core.llm.chapter_generator.generate_chapter_stream",
            new=AsyncMock(side_effect=_fake_stream),
        ),
        patch.object(h, "_run_chapter_stages", new=AsyncMock(side_effect=_fake_stages)),
        patch.object(h, "_get_story_bible_context", new=AsyncMock(return_value=None)),
        patch.object(h, "_get_blueprint", new=AsyncMock(return_value=None)),
        patch.object(h, "_emit_progress", new=AsyncMock()),
    ):
        await h.generate_volume_chapters(
            task_id=task_id,
            novel_id=novel_id,
            volume_number=1,
            chapter_start=1,
            chapter_end=6,
            vol_outline=vol_outline,
            words_per_chapter=3000,
            request=None,
            worker_id="worker-a",
        )

    # 只有第 6 章被生成，前 5 章跳过
    assert generated_calls == [6]


# ---------------------------------------------------------------------------
# Task 7：协作式暂停 —— pause_requested=True 时在安全边界抛 PausedExit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_gvc_pause_requested_raises_paused_exit(novel_task):
    """checkpoint.pause_requested=True 时，generate_volume_chapters 在进入下一章
    生成之前抛 PausedExit，不生成任何章节，且经 mark_paused 释放队列占用。"""
    from src.api.services.generation import long_form_generation_helpers as h
    from src.core.exceptions import PausedExit

    novel_id, task_id = novel_task
    await _insert_task(task_id, novel_id)
    # 上一章已完成（last_completed_chapter=5），pause_requested=True。
    await _insert_checkpoint(
        task_id, novel_id, checkpoint_version=7, last_completed_chapter=5,
        current_stage="chapter_completed",
    )
    async with get_db_session() as session:
        await session.execute(
            text(
                "UPDATE task_checkpoints SET pause_requested = true "
                "WHERE task_id = :tid"
            ),
            {"tid": task_id},
        )

    vol_outline = {
        "chapters": [{"chapter": n, "title": f"第{n}章", "plot": "推进"} for n in range(1, 7)]
    }

    generated_calls: list[int] = []

    async def _fake_stream(ctx):
        generated_calls.append(ctx.chapter_outline["chapter"])
        return _make_chapter_result(ctx.chapter_outline["chapter"])

    with (
        patch(
            "src.core.llm.chapter_generator.generate_chapter_stream",
            new=AsyncMock(side_effect=_fake_stream),
        ),
        patch.object(h, "_get_story_bible_context", new=AsyncMock(return_value=None)),
        patch.object(h, "_get_blueprint", new=AsyncMock(return_value=None)),
        patch.object(h, "_emit_progress", new=AsyncMock()),
        pytest.raises(PausedExit),
    ):
        await h.generate_volume_chapters(
            task_id=task_id,
            novel_id=novel_id,
            volume_number=1,
            chapter_start=1,
            chapter_end=6,
            vol_outline=vol_outline,
            words_per_chapter=3000,
            request=None,
            worker_id="worker-a",
        )

    # 未生成任何章节（在安全边界即停）
    assert generated_calls == []
    # checkpoint.status 推进为 paused；暂停发生在下一章开始前，因此保留
    # 最后一个已完成的安全阶段 chapter_completed，不能伪造第 6 章已经规划。
    # Task 队列占用释放（queue_state=idle + 清 lease），由 worker 在抛
    # PausedExit 之前调用 mark_paused 完成。
    async with get_db_session() as session:
        res = await session.execute(
            text(
                "SELECT status, current_stage FROM task_checkpoints "
                "WHERE task_id = :tid"
            ),
            {"tid": task_id},
        )
        cp_status, cp_stage = res.one()
        assert cp_status == "paused"
        assert cp_stage == "chapter_completed"
        res2 = await session.execute(
            text(
                "SELECT queue_state, lease_owner FROM tasks WHERE task_id = :tid"
            ),
            {"tid": task_id},
        )
        row = res2.one()
        assert row[0] == "idle"
        assert row[1] is None
