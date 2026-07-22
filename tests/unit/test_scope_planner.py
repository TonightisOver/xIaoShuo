"""GenerationScopePlanner 单元测试。

覆盖生成范围意图 → 现有端点 payload 翻译 + 锁定/已确认过滤 + 预览。
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.creative_control.scope_planner import (
    GenerationScopeIntent,
    GenerationScopePlanner,
)


def _intent(**kw):
    base = dict(
        novel_id="novel-1",
        mode="chapters",  # chapters / volume / continue / blueprint_only / content_only / fix_quality
        chapter_start=None,
        chapter_end=None,
        volume_number=None,
        chapter_number=None,
        chapter_numbers=None,
        issue_ids=None,
        skip_confirmed=False,
        respect_locked=True,
        words_per_chapter=3000,
    )
    base.update(kw)
    return GenerationScopeIntent(**base)


# ---------------------------------------------------------------- chapters


@pytest.mark.asyncio
async def test_plan_single_chapter_translates_to_range_payload():
    planner = GenerationScopePlanner()
    with patch.object(planner, "_load_locked_chapters", new=AsyncMock(return_value=[])), \
         patch.object(planner, "_load_confirmed_chapters", new=AsyncMock(return_value=[])):
        plan = await planner.plan(_intent(mode="chapters", chapter_start=5, chapter_end=5))
    assert plan.endpoint == "generate-chapters"
    assert plan.payload == {"chapter_start": 5, "chapter_end": 5}
    assert 5 in plan.target_chapters
    assert plan.skipped_locked == []


@pytest.mark.asyncio
async def test_plan_range_excludes_locked_chapters():
    planner = GenerationScopePlanner()
    with patch.object(planner, "_load_locked_chapters", new=AsyncMock(return_value=[3, 4])), \
         patch.object(planner, "_load_confirmed_chapters", new=AsyncMock(return_value=[])):
        plan = await planner.plan(_intent(mode="chapters", chapter_start=2, chapter_end=5))
    # 锁定的 3,4 被排除出 target，进 skipped_locked
    assert set(plan.target_chapters) == {2, 5}
    assert set(plan.skipped_locked) == {3, 4}


@pytest.mark.asyncio
async def test_plan_range_skips_confirmed_when_requested():
    planner = GenerationScopePlanner()
    with patch.object(planner, "_load_locked_chapters", new=AsyncMock(return_value=[])), \
         patch.object(planner, "_load_confirmed_chapters", new=AsyncMock(return_value=[2])):
        plan = await planner.plan(
            _intent(mode="chapters", chapter_start=2, chapter_end=4, skip_confirmed=True)
        )
    assert 2 not in plan.target_chapters
    assert 2 in plan.skipped_confirmed


# ---------------------------------------------------------------- volume


@pytest.mark.asyncio
async def test_plan_volume_translates_to_volume_endpoint():
    planner = GenerationScopePlanner()
    with patch.object(planner, "_load_locked_chapters", new=AsyncMock(return_value=[])), \
         patch.object(planner, "_load_confirmed_chapters", new=AsyncMock(return_value=[])), \
         patch.object(planner, "_load_volume_chapters", new=AsyncMock(return_value=[10, 11, 12])):
        plan = await planner.plan(_intent(mode="volume", volume_number=2))
    assert plan.endpoint == "generate-volume"
    assert plan.payload == {"volume_number": 2}
    assert set(plan.target_chapters) == {10, 11, 12}


# ---------------------------------------------------------------- continue


@pytest.mark.asyncio
async def test_plan_continue_from_chapter():
    planner = GenerationScopePlanner()
    with patch.object(planner, "_load_locked_chapters", new=AsyncMock(return_value=[])), \
         patch.object(planner, "_load_confirmed_chapters", new=AsyncMock(return_value=[])), \
         patch.object(planner, "_load_total_chapters", new=AsyncMock(return_value=8)):
        plan = await planner.plan(_intent(mode="continue", chapter_number=5))
    assert plan.endpoint == "generate-chapters"
    assert plan.payload["chapter_start"] == 5
    assert plan.payload["chapter_end"] == 8


# ---------------------------------------------------------------- blueprint / content / fix_quality


@pytest.mark.asyncio
async def test_plan_blueprint_only():
    planner = GenerationScopePlanner()
    with patch.object(planner, "_load_locked_blueprints", new=AsyncMock(return_value=[])), \
         patch.object(planner, "_load_confirmed_blueprints", new=AsyncMock(return_value=[])):
        plan = await planner.plan(_intent(mode="blueprint_only", chapter_number=5))
    assert plan.endpoint == "blueprint/generate"
    assert plan.payload == {"chapter_numbers": [5]}


@pytest.mark.asyncio
async def test_plan_content_only_flag():
    planner = GenerationScopePlanner()
    with patch.object(planner, "_load_locked_chapters", new=AsyncMock(return_value=[])), \
         patch.object(planner, "_load_confirmed_chapters", new=AsyncMock(return_value=[])):
        plan = await planner.plan(
            _intent(mode="content_only", chapter_start=5, chapter_end=5)
        )
    assert plan.endpoint == "generate-chapters"
    assert plan.payload.get("regenerate_content_only") is True


@pytest.mark.asyncio
async def test_plan_fix_quality_translates_to_auto_improve():
    planner = GenerationScopePlanner()
    plan = await planner.plan(
        _intent(mode="fix_quality", chapter_number=5, issue_ids=["issue-1", "issue-2"])
    )
    assert plan.endpoint == "auto-improve"
    assert plan.payload == {"chapter_number": 5, "issue_ids": ["issue-1", "issue-2"]}


# ---------------------------------------------------------------- preview


@pytest.mark.asyncio
async def test_preview_returns_chapters_tokens_and_impact():
    planner = GenerationScopePlanner()
    with patch.object(planner, "_load_locked_chapters", new=AsyncMock(return_value=[])), \
         patch.object(planner, "_load_confirmed_chapters", new=AsyncMock(return_value=[])), \
         patch.object(planner, "_load_volume_chapters", new=AsyncMock(return_value=[10, 11, 12, 13])), \
         patch.object(planner, "analyze_impact", new=AsyncMock(return_value={"regenerable": [], "to_mark_stale": []})):
        preview = await planner.preview(_intent(mode="volume", volume_number=2))
    assert preview.estimated_chapters == 4
    # tokens = words_per_chapter(3000) * chapters(4) * 1.5 heuristic
    assert preview.estimated_tokens == 3000 * 4 * 1.5
    assert "regenerable" in preview.impact
    assert "to_mark_stale" in preview.impact


@pytest.mark.asyncio
async def test_preview_accounts_for_locked_exclusion():
    planner = GenerationScopePlanner()
    with patch.object(planner, "_load_locked_chapters", new=AsyncMock(return_value=[11])), \
         patch.object(planner, "_load_confirmed_chapters", new=AsyncMock(return_value=[])), \
         patch.object(planner, "_load_volume_chapters", new=AsyncMock(return_value=[10, 11, 12, 13])), \
         patch.object(planner, "analyze_impact", new=AsyncMock(return_value={"regenerable": [], "to_mark_stale": []})):
        preview = await planner.preview(_intent(mode="volume", volume_number=2))
    assert preview.estimated_chapters == 3  # 11 被锁排除


# ---------------------------------------------------------------- blueprint batch


@pytest.mark.asyncio
async def test_plan_blueprint_only_multi_chapter_uses_chapter_numbers():
    planner = GenerationScopePlanner()
    with patch.object(planner, "_load_locked_blueprints", new=AsyncMock(return_value=[])), \
         patch.object(planner, "_load_confirmed_blueprints", new=AsyncMock(return_value=[])):
        plan = await planner.plan(_intent(
            mode="blueprint_only", chapter_numbers=[3, 5, 1]
        ))
    assert plan.endpoint == "blueprint/generate"
    assert plan.target_chapters == [1, 3, 5]  # 排序去重
    assert plan.payload.get("chapter_numbers") == [1, 3, 5]


@pytest.mark.asyncio
async def test_plan_blueprint_only_single_chapter_still_works():
    """单章兼容：无 chapter_numbers 时退回 chapter_number。"""
    planner = GenerationScopePlanner()
    with patch.object(planner, "_load_locked_blueprints", new=AsyncMock(return_value=[])), \
         patch.object(planner, "_load_confirmed_blueprints", new=AsyncMock(return_value=[])):
        plan = await planner.plan(_intent(mode="blueprint_only", chapter_number=7))
    assert plan.endpoint == "blueprint/generate"
    assert plan.target_chapters == [7]


@pytest.mark.asyncio
async def test_plan_blueprint_only_rejects_over_50():
    planner = GenerationScopePlanner()
    with pytest.raises(ValueError, match="50"):
        await planner.plan(_intent(
            mode="blueprint_only", chapter_numbers=list(range(1, 52))
        ))


@pytest.mark.asyncio
async def test_plan_blueprint_only_filters_by_blueprint_type_control():
    """respect_locked/skip_confirmed 按 blueprint 类型 control 过滤，非 chapter 类型。"""
    planner = GenerationScopePlanner()
    with patch.object(planner, "_load_locked_blueprints", new=AsyncMock(return_value=[3])), \
         patch.object(planner, "_load_confirmed_blueprints", new=AsyncMock(return_value=[5])):
        plan = await planner.plan(_intent(
            mode="blueprint_only", chapter_numbers=[1, 3, 5, 7],
            respect_locked=True, skip_confirmed=True,
        ))
    assert plan.target_chapters == [1, 7]
    assert plan.skipped_locked == [3]
    assert plan.skipped_confirmed == [5]
