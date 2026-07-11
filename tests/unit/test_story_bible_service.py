"""StoryBibleService 三层架构核心逻辑单元测试。

覆盖范围:
- extract_relevant_constraints: 设定一致性维护（精准抽取约束、None/空边界、人物匹配、伏笔相关性过滤）
- _build_constraint_summary_for_detection: 冲突检测约束摘要构建
- detect_bible_conflicts: conflict 检测主路径
    * 规则检测：伏笔遗忘（forgotten_hook）、已回收伏笔跳过、无 planted_chapter 跳过、阈值边界
    * LLM 检测：合并冲突、无冲突、解析失败降级、LLM 异常降级
    * 无 StoryBible 时返回空
- update_bible_after_generation: 持久化主路径（CRUD 合并）
    * timeline_events 合并、unresolved_hooks 新增+回收、character_updates 匹配+新建
    * goal_progress 进展更新、无 LLM 输出降级、无 StoryBible 早返回

外部依赖均被 mock:
- get_db_session (async context manager, 返回 mock session) — patch src.core.database.get_db_session
- get_llm_client — patch src.core.llm.client.get_llm_client
- safe_json_parse — patch src.core.json_utils.safe_json_parse

被测方法本身的逻辑（抽取/过滤/合并/检测）真实执行，不 mock。
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 测试夹具：构造 StoryBible mock 与 mock_db_session
# ---------------------------------------------------------------------------

def _make_bible(**kwargs):
    """构造一个 MagicMock StoryBible，所有字段可自定义。"""
    bible = MagicMock()
    bible.worldview_rules = kwargs.get("worldview_rules", "")
    bible.hard_settings = kwargs.get("hard_settings", "")
    bible.banned_elements = kwargs.get("banned_elements", [])
    bible.character_cards = kwargs.get("character_cards", [])
    bible.faction_relations = kwargs.get("faction_relations", "")
    bible.location_settings = kwargs.get("location_settings", "")
    bible.foreshadowing_list = kwargs.get("foreshadowing_list", [])
    bible.timeline_events = kwargs.get("timeline_events", [])
    bible.unresolved_hooks = kwargs.get("unresolved_hooks", [])
    bible.main_goals = kwargs.get("main_goals", [])
    return bible


def _make_db_session(bible=None):
    """构造 mock async session，execute 返回指定 bible（或 None）。"""
    mock_session = AsyncMock()
    mock_result = MagicMock()
    if bible is None:
        mock_result.scalar_one_or_none.return_value = None
    else:
        mock_result.scalar_one_or_none.return_value = bible
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    return mock_session


def _patch_db(mock_session):
    """返回一个 patcher，把 src.core.database.get_db_session 替换为 yield mock_session 的 async ctx mgr。"""

    @asynccontextmanager
    async def _mock_get_db():
        yield mock_session

    return patch("src.core.database.get_db_session", _mock_get_db)


def _patch_llm(response_str='{"conflicts": []}'):
    """patch LLM client，generate 返回固定字符串。"""
    mock_client = MagicMock()
    mock_client.generate = AsyncMock(return_value=response_str)
    return patch("src.core.llm.client.get_llm_client", return_value=mock_client), mock_client


def _patch_json_parse(parsed):
    """patch safe_json_parse 返回固定解析结果。"""
    return patch("src.core.json_utils.safe_json_parse", return_value=parsed)


# ===========================================================================
# 1. extract_relevant_constraints — 设定一致性维护
# ===========================================================================

class TestExtractRelevantConstraints:
    """测试约束精准抽取逻辑（一致性维护）。"""

    def test_global_constraints_included_with_unfilled_fields(self):
        """未设定字段（空串/None）应回退为「未设定」占位。"""
        from src.api.services.story_bible_service import extract_relevant_constraints

        bible = _make_bible(worldview_rules="", hard_settings=None, banned_elements=[])
        result = extract_relevant_constraints(bible, {}, 1)
        assert "未设定" in result
        assert "## 世界观规则:" in result
        # banned 为空时不应出现「禁用元素」段
        assert "禁用元素" not in result

    def test_banned_elements_listed(self):
        """banned_elements 非空时应列出每一项 element 与 reason。"""
        from src.api.services.story_bible_service import extract_relevant_constraints

        bible = _make_bible(banned_elements=[
            {"element": "魔法", "reason": "低魔世界"},
            {"element": "穿越", "reason": "无穿越"},
        ])
        result = extract_relevant_constraints(bible, {}, 1)
        assert "魔法: 低魔世界" in result
        assert "穿越: 无穿越" in result

    def test_foreshadowing_filtered_by_chapter_characters(self):
        """伏笔只抽取与本章出场人物相关的，不相关的应被过滤掉。"""
        from src.api.services.story_bible_service import extract_relevant_constraints

        bible = _make_bible(foreshadowing_list=[
            {"description": "张三发现的秘密", "related_characters": ["张三"]},
            {"description": "无关伏笔", "related_characters": ["路人甲"]},
        ])
        outline = {"characters": ["张三"]}
        result = extract_relevant_constraints(bible, outline, 3)
        assert "张三发现的秘密" in result
        assert "无关伏笔" not in result

    def test_foreshadowing_kept_all_when_no_chapter_characters(self):
        """章节无出场人物时，伏笔不过滤（全部保留）。"""
        from src.api.services.story_bible_service import extract_relevant_constraints

        bible = _make_bible(foreshadowing_list=[
            {"description": "伏笔A", "related_characters": ["路人甲"]},
        ])
        result = extract_relevant_constraints(bible, {}, 3)
        assert "伏笔A" in result

    def test_active_goals_only_included(self):
        """仅活跃（status=active）主线目标被纳入。"""
        from src.api.services.story_bible_service import extract_relevant_constraints

        bible = _make_bible(main_goals=[
            {"description": "目标A", "status": "active"},
            {"description": "目标B", "status": "completed"},
        ])
        result = extract_relevant_constraints(bible, {}, 5)
        assert "目标A" in result
        assert "目标B" not in result

    def test_resolved_hooks_excluded(self):
        """已回收（status=resolved）悬念不纳入未回收悬念段。"""
        from src.api.services.story_bible_service import extract_relevant_constraints

        bible = _make_bible(unresolved_hooks=[
            {"description": "悬念A", "status": "hanging"},
            {"description": "悬念B", "status": "resolved"},
        ])
        result = extract_relevant_constraints(bible, {}, 5)
        assert "悬念A" in result
        assert "悬念B" not in result


# ===========================================================================
# 2. _build_constraint_summary_for_detection — 约束摘要构建
# ===========================================================================

class TestBuildConstraintSummaryForDetection:
    """测试用于冲突检测的约束摘要构建。"""

    def test_empty_bible_returns_empty_string(self):
        from src.api.services.story_bible_service import _build_constraint_summary_for_detection

        bible = _make_bible()
        assert _build_constraint_summary_for_detection(bible) == ""

    def test_all_sections_present(self):
        from src.api.services.story_bible_service import _build_constraint_summary_for_detection

        bible = _make_bible(
            character_cards=[{"name": "张三"}],
            worldview_rules="世界观X",
            hard_settings="硬设定Y",
            banned_elements=[{"element": "魔法"}],
            timeline_events=[{"chapter": i} for i in range(20)],
        )
        result = _build_constraint_summary_for_detection(bible)
        assert "人物卡:" in result
        assert "世界观规则:" in result
        assert "硬设定:" in result
        assert "禁用元素:" in result
        assert "近期时间线:" in result
        assert "张三" in result

    def test_timeline_truncated_to_last_10(self):
        """近期时间线只取最后 10 条。"""
        import json

        from src.api.services.story_bible_service import _build_constraint_summary_for_detection

        events = [{"chapter": i, "event": f"e{i}"} for i in range(20)]
        bible = _make_bible(timeline_events=events)
        result = _build_constraint_summary_for_detection(bible)
        # 解析结果中时间线段
        timeline_section = result.split("## 近期时间线:")[1]
        parsed = json.loads(timeline_section.strip())
        assert len(parsed) == 10
        assert parsed[-1]["chapter"] == 19
        assert parsed[0]["chapter"] == 10


# ===========================================================================
# 3. detect_bible_conflicts — conflict 检测主路径
# ===========================================================================

class TestDetectBibleConflicts:
    """测试冲突检测：规则检测（伏笔遗忘）+ LLM 检测 + 异常降级。"""

    @pytest.mark.asyncio
    async def test_no_bible_returns_empty(self):
        """无 StoryBible 时返回空列表，不调用 LLM。"""
        from src.api.services.story_bible_service import detect_bible_conflicts

        mock_session = _make_db_session(bible=None)
        llm_patch, mock_client = _patch_llm()

        with _patch_db(mock_session), llm_patch:
            conflicts = await detect_bible_conflicts("novel-x", 5, "内容")

        assert conflicts == []
        mock_client.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_forgotten_hook_over_10_chapters(self):
        """planted_chapter 超过 10 章未回收 → forgotten_hook 冲突。"""
        from src.api.services.story_bible_service import detect_bible_conflicts

        bible = _make_bible(unresolved_hooks=[
            {"description": "远古伏笔", "status": "hanging", "planted_chapter": 1},
        ])
        mock_session = _make_db_session(bible=bible)
        llm_patch, _ = _patch_llm('{"conflicts": []}')

        with _patch_db(mock_session), llm_patch:
            conflicts = await detect_bible_conflicts("novel-1", 15, "章节内容")

        forgotten = [c for c in conflicts if c["type"] == "forgotten_hook"]
        assert len(forgotten) == 1
        assert forgotten[0]["chapters_since"] == 14
        assert forgotten[0]["severity"] == "warning"

    @pytest.mark.asyncio
    async def test_forgotten_hook_boundary_exactly_10_no_conflict(self):
        """恰好 10 章差（chapter - planted == 10）不触发，需 >10。"""
        from src.api.services.story_bible_service import detect_bible_conflicts

        bible = _make_bible(unresolved_hooks=[
            {"description": "伏笔", "status": "hanging", "planted_chapter": 5},
        ])
        mock_session = _make_db_session(bible=bible)
        llm_patch, _ = _patch_llm('{"conflicts": []}')

        with _patch_db(mock_session), llm_patch:
            conflicts = await detect_bible_conflicts("novel-1", 15, "章节内容")

        forgotten = [c for c in conflicts if c["type"] == "forgotten_hook"]
        assert len(forgotten) == 0

    @pytest.mark.asyncio
    async def test_resolved_hook_skipped_in_rule_check(self):
        """已回收伏笔即使 planted 很久也不触发 forgotten_hook。"""
        from src.api.services.story_bible_service import detect_bible_conflicts

        bible = _make_bible(unresolved_hooks=[
            {"description": "已解决伏笔", "status": "resolved", "planted_chapter": 1},
        ])
        mock_session = _make_db_session(bible=bible)
        llm_patch, _ = _patch_llm('{"conflicts": []}')

        with _patch_db(mock_session), llm_patch:
            conflicts = await detect_bible_conflicts("novel-1", 50, "章节内容")

        assert not any(c["type"] == "forgotten_hook" for c in conflicts)

    @pytest.mark.asyncio
    async def test_hook_without_planted_chapter_skipped(self):
        """planted_chapter 缺失或非 int 时跳过规则检测。"""
        from src.api.services.story_bible_service import detect_bible_conflicts

        bible = _make_bible(unresolved_hooks=[
            {"description": "无章节伏笔", "status": "hanging"},  # 无 planted_chapter
            {"description": "字符串章节", "status": "hanging", "planted_chapter": "1"},
        ])
        mock_session = _make_db_session(bible=bible)
        llm_patch, _ = _patch_llm('{"conflicts": []}')

        with _patch_db(mock_session), llm_patch:
            conflicts = await detect_bible_conflicts("novel-1", 100, "章节内容")

        assert not any(c["type"] == "forgotten_hook" for c in conflicts)

    @pytest.mark.asyncio
    async def test_llm_conflicts_merged(self):
        """LLM 返回的冲突应合并进结果。"""
        from src.api.services.story_bible_service import detect_bible_conflicts

        bible = _make_bible()
        mock_session = _make_db_session(bible=bible)
        llm_conflicts = [
            {"type": "character_drift", "severity": "error", "description": "性格漂移"},
            {"type": "timeline", "severity": "warning", "description": "时间线冲突"},
        ]
        llm_patch, _ = _patch_llm('{"conflicts": [..]}')
        json_patch = _patch_json_parse({"conflicts": llm_conflicts})

        with _patch_db(mock_session), llm_patch, json_patch:
            conflicts = await detect_bible_conflicts("novel-1", 3, "内容")

        assert len(conflicts) == 2
        assert conflicts[0]["description"] == "性格漂移"

    @pytest.mark.asyncio
    async def test_llm_parse_failure_returns_empty_llm_conflicts(self):
        """LLM 响应解析失败（返回 None）时，不应追加 LLM 冲突（规则冲突仍保留）。"""
        from src.api.services.story_bible_service import detect_bible_conflicts

        bible = _make_bible(unresolved_hooks=[
            {"description": "远古", "status": "hanging", "planted_chapter": 1},
        ])
        mock_session = _make_db_session(bible=bible)
        llm_patch, _ = _patch_llm("garbage")
        json_patch = _patch_json_parse(None)

        with _patch_db(mock_session), llm_patch, json_patch:
            conflicts = await detect_bible_conflicts("novel-1", 20, "内容")

        # 规则冲突保留，LLM 冲突为空
        assert len(conflicts) == 1
        assert conflicts[0]["type"] == "forgotten_hook"

    @pytest.mark.asyncio
    async def test_llm_exception_degraded_gracefully(self):
        """LLM 调用抛异常时，捕获并降级（规则冲突仍返回，不炸）。"""
        from src.api.services.story_bible_service import detect_bible_conflicts

        bible = _make_bible(unresolved_hooks=[
            {"description": "远古", "status": "hanging", "planted_chapter": 1},
        ])
        mock_session = _make_db_session(bible=bible)

        mock_client = MagicMock()
        mock_client.generate = AsyncMock(side_effect=RuntimeError("LLM down"))
        llm_patch = patch("src.core.llm.client.get_llm_client", return_value=mock_client)

        with _patch_db(mock_session), llm_patch:
            conflicts = await detect_bible_conflicts("novel-1", 20, "内容")

        # LLM 异常被吞，规则冲突仍返回
        assert len(conflicts) == 1
        assert conflicts[0]["type"] == "forgotten_hook"

    @pytest.mark.asyncio
    async def test_llm_conflicts_not_dict_ignored(self):
        """LLM 解析结果不是 dict 时，不追加冲突。"""
        from src.api.services.story_bible_service import detect_bible_conflicts

        bible = _make_bible()
        mock_session = _make_db_session(bible=bible)
        llm_patch, _ = _patch_llm("[]")
        # safe_json_parse 返回 list 而非 dict
        json_patch = _patch_json_parse([1, 2, 3])

        with _patch_db(mock_session), llm_patch, json_patch:
            conflicts = await detect_bible_conflicts("novel-1", 3, "内容")

        assert conflicts == []


# ===========================================================================
# 4. update_bible_after_generation — 持久化合并主路径（CRUD）
# ===========================================================================

class TestUpdateBibleAfterGeneration:
    """测试章节生成后的 StoryBible 合并持久化逻辑。"""

    @pytest.mark.asyncio
    async def test_no_bible_returns_zero_summary(self):
        """无 StoryBible 时返回全 0 摘要，不调用 LLM。"""
        from src.api.services.story_bible_service import update_bible_after_generation

        mock_session = _make_db_session(bible=None)
        llm_patch, mock_client = _patch_llm()

        with _patch_db(mock_session), llm_patch:
            summary = await update_bible_after_generation(
                "novel-x", 5, "章节正文", {"title": "测试"}
            )

        assert summary == {"new_events": 0, "new_hooks": 0, "resolved_hooks": 0, "character_updates": 0}
        mock_client.generate.assert_not_called()
        mock_session.commit.assert_not_called()

    @pytest.mark.asyncio
    async def test_timeline_events_merged(self):
        """new_events 应追加到 timeline_events 并计数。"""
        from src.api.services.story_bible_service import update_bible_after_generation

        bible = _make_bible(timeline_events=[{"chapter": 1, "event": "旧事件"}])
        mock_session = _make_db_session(bible=bible)
        updates = {"new_events": [{"chapter": 5, "event": "新事件", "characters": ["甲"]}]}
        llm_patch, _ = _patch_llm("{}")
        json_patch = _patch_json_parse(updates)

        with _patch_db(mock_session), llm_patch, json_patch:
            summary = await update_bible_after_generation(
                "novel-1", 5, "正文", {"title": "第5章"}
            )

        assert summary["new_events"] == 1
        assert len(bible.timeline_events) == 2
        assert bible.timeline_events[1]["event"] == "新事件"
        mock_session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_hooks_new_and_resolved(self):
        """new_hooks 追加，resolved_hooks 关键词匹配回收旧悬念。"""
        from src.api.services.story_bible_service import update_bible_after_generation

        bible = _make_bible(unresolved_hooks=[
            {"description": "神秘宝藏", "status": "hanging"},
            {"description": "无关悬念", "status": "hanging"},
        ])
        mock_session = _make_db_session(bible=bible)
        updates = {
            "new_hooks": [{"description": "新悬念", "planted_chapter": 5, "status": "hanging"}],
            "resolved_hooks": ["宝藏"],
        }
        llm_patch, _ = _patch_llm("{}")
        json_patch = _patch_json_parse(updates)

        with _patch_db(mock_session), llm_patch, json_patch:
            summary = await update_bible_after_generation(
                "novel-1", 5, "正文", {}
            )

        assert summary["new_hooks"] == 1
        assert summary["resolved_hooks"] == 1
        # 「神秘宝藏」被关键词「宝藏」命中 → resolved
        statuses = {h["description"]: h["status"] for h in bible.unresolved_hooks}
        assert statuses["神秘宝藏"] == "resolved"
        assert statuses["无关悬念"] == "hanging"
        # 新悬念已追加
        assert any(h["description"] == "新悬念" for h in bible.unresolved_hooks)

    @pytest.mark.asyncio
    async def test_already_resolved_hook_not_re_counted(self):
        """已 resolved 的悬念在 resolved_keywords 处理时应跳过（不重复计数）。"""
        from src.api.services.story_bible_service import update_bible_after_generation

        bible = _make_bible(unresolved_hooks=[
            {"description": "宝藏X", "status": "resolved"},
        ])
        mock_session = _make_db_session(bible=bible)
        updates = {"resolved_hooks": ["宝藏X"]}
        llm_patch, _ = _patch_llm("{}")
        json_patch = _patch_json_parse(updates)

        with _patch_db(mock_session), llm_patch, json_patch:
            summary = await update_bible_after_generation("novel-1", 5, "正文", {})

        assert summary["resolved_hooks"] == 0

    @pytest.mark.asyncio
    async def test_character_update_matches_existing_card(self):
        """character_updates 命中已有人物卡 → 更新该卡，计数 +1。"""
        from src.api.services.story_bible_service import update_bible_after_generation

        bible = _make_bible(character_cards=[
            {"name": "张三", "personality": "冷酷", "level": 1},
        ])
        mock_session = _make_db_session(bible=bible)
        updates = {
            "character_updates": [
                {"name": "张三", "updates": {"level": 2, "title": "剑客"}},
            ]
        }
        llm_patch, _ = _patch_llm("{}")
        json_patch = _patch_json_parse(updates)

        with _patch_db(mock_session), llm_patch, json_patch:
            summary = await update_bible_after_generation("novel-1", 5, "正文", {})

        assert summary["character_updates"] == 1
        # 同一张卡被 update，不应新增
        assert len(bible.character_cards) == 1
        card = bible.character_cards[0]
        assert card["level"] == 2
        assert card["title"] == "剑客"
        assert card["personality"] == "冷酷"  # 原有字段保留

    @pytest.mark.asyncio
    async def test_character_update_creates_new_card_when_no_match(self):
        """character_updates 未命中 → 新建人物卡。"""
        from src.api.services.story_bible_service import update_bible_after_generation

        bible = _make_bible(character_cards=[{"name": "李四"}])
        mock_session = _make_db_session(bible=bible)
        updates = {
            "character_updates": [
                {"name": "王五", "updates": {"role": "反派"}},
            ]
        }
        llm_patch, _ = _patch_llm("{}")
        json_patch = _patch_json_parse(updates)

        with _patch_db(mock_session), llm_patch, json_patch:
            summary = await update_bible_after_generation("novel-1", 5, "正文", {})

        assert summary["character_updates"] == 1
        assert len(bible.character_cards) == 2
        new_card = [c for c in bible.character_cards if c.get("name") == "王五"][0]
        assert new_card["role"] == "反派"

    @pytest.mark.asyncio
    async def test_goal_progress_updates_matched_goal(self):
        """goal_progress 命中目标描述关键词 → 更新 progress。"""
        from src.api.services.story_bible_service import update_bible_after_generation

        bible = _make_bible(main_goals=[
            {"description": "寻找上古神器", "status": "active", "progress": ""},
        ])
        mock_session = _make_db_session(bible=bible)
        updates = {
            "goal_progress": [
                {"description": "神器", "progress": "已找到线索"},
            ]
        }
        llm_patch, _ = _patch_llm("{}")
        json_patch = _patch_json_parse(updates)

        with _patch_db(mock_session), llm_patch, json_patch:
            summary = await update_bible_after_generation("novel-1", 5, "正文", {})

        assert bible.main_goals[0]["progress"] == "已找到线索"

    @pytest.mark.asyncio
    async def test_llm_parse_failure_returns_zero_summary(self):
        """LLM 响应解析失败 → 返回全 0 摘要，不修改 bible。"""
        from src.api.services.story_bible_service import update_bible_after_generation

        bible = _make_bible(timeline_events=[], unresolved_hooks=[], character_cards=[])
        mock_session = _make_db_session(bible=bible)
        llm_patch, _ = _patch_llm("garbage")
        json_patch = _patch_json_parse(None)

        with _patch_db(mock_session), llm_patch, json_patch:
            summary = await update_bible_after_generation("novel-1", 5, "正文", {})

        assert summary == {"new_events": 0, "new_hooks": 0, "resolved_hooks": 0, "character_updates": 0}
        # 无变更不应 commit（早 return 在 commit 之前）
        mock_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_updates_dict_treated_as_no_update(self):
        """safe_json_parse 返回空 dict {} → `not updates` 为真，走早 return，不 commit。"""
        from src.api.services.story_bible_service import update_bible_after_generation

        bible = _make_bible(
            timeline_events=[{"chapter": 1}],
            unresolved_hooks=[{"description": "x", "status": "hanging"}],
            character_cards=[{"name": "甲"}],
            main_goals=[{"description": "g", "status": "active"}],
        )
        mock_session = _make_db_session(bible=bible)
        llm_patch, _ = _patch_llm("{}")
        # 注意：源码 `if not updates or not isinstance(updates, dict)` 对空 dict 直接判定为 falsy → 早 return
        json_patch = _patch_json_parse({})

        with _patch_db(mock_session), llm_patch, json_patch:
            summary = await update_bible_after_generation("novel-1", 5, "正文", {})

        assert summary == {"new_events": 0, "new_hooks": 0, "resolved_hooks": 0, "character_updates": 0}
        mock_session.commit.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_chapter_content_truncated_to_6000(self):
        """超长章节正文应被截断到 6000 字符再传给 LLM。"""
        from src.api.services.story_bible_service import update_bible_after_generation

        bible = _make_bible()
        mock_session = _make_db_session(bible=bible)
        long_content = "x" * 10000
        llm_patch, mock_client = _patch_llm("{}")
        json_patch = _patch_json_parse({})

        with _patch_db(mock_session), llm_patch, json_patch:
            await update_bible_after_generation("novel-1", 5, long_content, {"title": "t"})

        # generate 被调用，prompt 中含截断后的内容
        call_args = mock_client.generate.call_args
        prompt_arg = call_args.args[0]
        assert "x" * 6000 in prompt_arg
        assert "x" * 6001 not in prompt_arg
