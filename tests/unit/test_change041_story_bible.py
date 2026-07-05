"""Unit tests for CHANGE-041: StoryBible constraint system."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.story_bible_service import (
    _character_matches,
    _extract_chapter_characters,
    _extract_chapter_locations,
    _foreshadowing_relevant,
    extract_relevant_constraints,
)

# ===========================================================================
# 1. extract_relevant_constraints - precise extraction
# ===========================================================================

class TestExtractRelevantConstraints:
    """Test precise constraint extraction from StoryBible."""

    def _make_bible(self, **kwargs):
        bible = MagicMock()
        bible.worldview_rules = kwargs.get("worldview_rules", "魔法世界")
        bible.hard_settings = kwargs.get("hard_settings", "不能飞")
        bible.banned_elements = kwargs.get("banned_elements", [])
        bible.character_cards = kwargs.get("character_cards", [])
        bible.faction_relations = kwargs.get("faction_relations", "")
        bible.location_settings = kwargs.get("location_settings", "")
        bible.prop_settings = kwargs.get("prop_settings", "")
        bible.foreshadowing_list = kwargs.get("foreshadowing_list", [])
        bible.timeline_events = kwargs.get("timeline_events", [])
        bible.unresolved_hooks = kwargs.get("unresolved_hooks", [])
        bible.main_goals = kwargs.get("main_goals", [])
        return bible

    def test_global_constraints_always_included(self):
        bible = self._make_bible(worldview_rules="灵气复苏", hard_settings="禁止穿越")
        result = extract_relevant_constraints(bible, {}, 1)
        assert "灵气复苏" in result
        assert "禁止穿越" in result

    def test_only_relevant_characters_extracted(self):
        bible = self._make_bible(character_cards=[
            {"name": "张三", "personality": "冷酷"},
            {"name": "李四", "personality": "热情"},
            {"name": "王五", "personality": "狡猾"},
        ])
        outline = {"characters": ["张三", "王五"]}
        result = extract_relevant_constraints(bible, outline, 5)
        assert "张三" in result
        assert "王五" in result
        assert "李四" not in result

    def test_all_characters_when_no_outline_characters(self):
        bible = self._make_bible(character_cards=[
            {"name": "张三", "personality": "冷酷"},
            {"name": "李四", "personality": "热情"},
        ])
        result = extract_relevant_constraints(bible, {}, 1)
        assert "张三" in result
        assert "李四" in result

    def test_timeline_only_recent_5_chapters(self):
        events = [
            {"chapter": i, "event": f"事件{i}", "characters": []}
            for i in range(1, 11)
        ]
        bible = self._make_bible(timeline_events=events)
        result = extract_relevant_constraints(bible, {}, 10)
        assert "事件5" in result
        assert "事件10" in result
        assert "事件4" not in result

    def test_unresolved_hooks_excludes_resolved(self):
        hooks = [
            {"description": "悬念A", "status": "hanging"},
            {"description": "悬念B", "status": "resolved"},
        ]
        bible = self._make_bible(unresolved_hooks=hooks)
        result = extract_relevant_constraints(bible, {}, 5)
        assert "悬念A" in result
        assert "悬念B" not in result

    def test_active_goals_only(self):
        goals = [
            {"description": "目标1", "status": "active"},
            {"description": "目标2", "status": "completed"},
        ]
        bible = self._make_bible(main_goals=goals)
        result = extract_relevant_constraints(bible, {}, 5)
        assert "目标1" in result
        assert "目标2" not in result

    def test_banned_elements_included(self):
        bible = self._make_bible(banned_elements=[
            {"element": "穿越", "reason": "不符合设定"}
        ])
        result = extract_relevant_constraints(bible, {}, 1)
        assert "穿越" in result

    def test_relevant_foreshadowing_only(self):
        bible = self._make_bible(
            foreshadowing_list=[
                {"description": "张三的秘密", "related_characters": ["张三"]},
                {"description": "李四的阴谋", "related_characters": ["李四"]},
            ]
        )
        outline = {"characters": ["张三"]}
        result = extract_relevant_constraints(bible, outline, 5)
        assert "张三的秘密" in result
        assert "李四的阴谋" not in result


# ===========================================================================
# 2. Helper functions
# ===========================================================================

class TestHelperFunctions:

    def test_extract_chapter_characters_from_list(self):
        outline = {"characters": ["张三", "李四"]}
        assert _extract_chapter_characters(outline) == ["张三", "李四"]

    def test_extract_chapter_characters_from_dicts(self):
        outline = {"characters": [{"name": "张三"}, {"name": "李四"}]}
        assert _extract_chapter_characters(outline) == ["张三", "李四"]

    def test_extract_chapter_characters_from_scenes(self):
        outline = {"scenes": [{"characters": ["张三"]}, {"characters": ["李四"]}]}
        result = _extract_chapter_characters(outline)
        assert "张三" in result
        assert "李四" in result

    def test_extract_locations(self):
        outline = {"location": "京城", "scenes": [{"location": "皇宫"}]}
        result = _extract_chapter_locations(outline)
        assert "京城" in result
        assert "皇宫" in result

    def test_character_matches_exact(self):
        assert _character_matches({"name": "张三"}, ["张三"]) is True

    def test_character_matches_partial(self):
        assert _character_matches({"name": "张三丰"}, ["张三"]) is True

    def test_character_no_match(self):
        assert _character_matches({"name": "李四"}, ["张三"]) is False

    def test_foreshadowing_relevant_by_character(self):
        fs = {"description": "某事", "related_characters": ["张三"]}
        assert _foreshadowing_relevant(fs, ["张三"], []) is True

    def test_foreshadowing_irrelevant(self):
        fs = {"description": "某事", "related_characters": ["李四"]}
        assert _foreshadowing_relevant(fs, ["张三"], []) is False

    def test_foreshadowing_relevant_by_description(self):
        fs = {"description": "张三发现了宝藏", "related_characters": []}
        assert _foreshadowing_relevant(fs, ["张三"], []) is True


# ===========================================================================
# 3. detect_bible_conflicts - forgotten hooks rule
# ===========================================================================

class TestDetectBibleConflicts:

    @pytest.mark.asyncio
    async def test_forgotten_hook_detection(self):
        from unittest.mock import MagicMock

        bible = MagicMock()
        bible.unresolved_hooks = [
            {"description": "远古伏笔", "status": "hanging", "planted_chapter": 1},
            {"description": "近期伏笔", "status": "hanging", "planted_chapter": 10},
            {"description": "已解决", "status": "resolved", "planted_chapter": 1},
        ]
        bible.character_cards = []
        bible.worldview_rules = ""
        bible.hard_settings = ""
        bible.banned_elements = []
        bible.timeline_events = []

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = bible
        mock_session.execute = AsyncMock(return_value=mock_result)

        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def mock_get_db():
            yield mock_session

        with patch("src.core.database.get_db_session", mock_get_db):
            with patch("src.core.llm.client.get_llm_client") as mock_llm:
                mock_client = MagicMock()
                mock_client.generate = AsyncMock(return_value='{"conflicts": []}')
                mock_llm.return_value = mock_client

                from src.api.services.story_bible_service import detect_bible_conflicts
                conflicts = await detect_bible_conflicts("novel-1", 15, "章节内容")

        forgotten = [c for c in conflicts if c["type"] == "forgotten_hook"]
        assert len(forgotten) == 1
        assert "远古伏笔" in forgotten[0]["description"]
        assert forgotten[0]["chapters_since"] == 14


# ===========================================================================
# 4. API model fields
# ===========================================================================

class TestAPIModels:

    def test_response_model_has_new_fields(self):
        from src.api.routes.story_bible import StoryBibleResponse
        fields = StoryBibleResponse.model_fields
        assert "timeline_events" in fields
        assert "unresolved_hooks" in fields
        assert "main_goals" in fields
        assert "banned_elements" in fields

    def test_update_model_has_new_fields(self):
        from src.api.routes.story_bible import StoryBibleUpdate
        fields = StoryBibleUpdate.model_fields
        assert "timeline_events" in fields
        assert "unresolved_hooks" in fields
        assert "main_goals" in fields
        assert "banned_elements" in fields

    def test_response_defaults_to_empty_lists(self):
        from src.api.routes.story_bible import StoryBibleResponse
        resp = StoryBibleResponse(novel_id="test")
        assert resp.timeline_events == []
        assert resp.unresolved_hooks == []
        assert resp.main_goals == []
        assert resp.banned_elements == []


# ===========================================================================
# 5. DB model fields
# ===========================================================================

class TestDBModel:

    def test_story_bible_has_new_columns(self):
        from src.api.models.db_models import StoryBible
        mapper = StoryBible.__table__.columns
        assert "timeline_events" in mapper
        assert "unresolved_hooks" in mapper
        assert "main_goals" in mapper
        assert "banned_elements" in mapper
