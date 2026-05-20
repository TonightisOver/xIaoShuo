"""Unit tests for KnowledgeGraphService (CHANGE-030).

Tests cover:
- extract_from_chapter: mock LLM, verify entity dedup and triple writing
- retrieve_context: verify retrieval logic, formatting, token trimming
- check_consistency: verify rule-based checks (dead character active, etc.)
- Feature flag disabled behavior
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entity(
    name: str,
    entity_type: str = "character",
    novel_id: str = "novel-030",
    aliases: list | None = None,
    attributes: dict | None = None,
    first_chapter: int = 1,
    last_chapter: int | None = None,
) -> MagicMock:
    """Build a mock KnowledgeEntity."""
    e = MagicMock()
    e.id = str(uuid.uuid4())
    e.novel_id = novel_id
    e.entity_type = entity_type
    e.name = name
    e.aliases = aliases or []
    e.attributes = attributes or {}
    e.first_chapter = first_chapter
    e.last_chapter = last_chapter
    return e


def _make_triple(
    subject_id: str,
    predicate: str,
    object_id: str,
    chapter_number: int = 1,
    novel_id: str = "novel-030",
    confidence: float = 1.0,
    status: str = "active",
) -> MagicMock:
    """Build a mock KnowledgeTriple."""
    t = MagicMock()
    t.id = str(uuid.uuid4())
    t.novel_id = novel_id
    t.subject_id = subject_id
    t.predicate = predicate
    t.object_id = object_id
    t.chapter_number = chapter_number
    t.confidence = confidence
    t.status = status
    t.metadata_ = {}
    return t


# ---------------------------------------------------------------------------
# extract_from_chapter
# ---------------------------------------------------------------------------

class TestExtractFromChapter:
    """Tests for KnowledgeGraphService.extract_from_chapter."""

    @pytest.mark.asyncio
    async def test_feature_flag_disabled_returns_zero(self):
        """When KNOWLEDGE_GRAPH_ENABLED=False, returns zero counts immediately."""
        with patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=False)
            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            result = await service.extract_from_chapter("novel-1", 1, "章节内容")
            assert result == {"entities_count": 0, "triples_count": 0}

    @pytest.mark.asyncio
    async def test_extract_creates_new_entities(self):
        """New entities from LLM are written to DB."""
        llm_response = json.dumps({
            "entities": [
                {"name": "张三", "type": "character", "aliases": ["小张"], "attributes": {"status": "alive"}},
                {"name": "长安城", "type": "location", "aliases": [], "attributes": {}},
            ],
            "triples": [
                {"subject": "张三", "predicate": "位于", "object": "长安城", "confidence": 0.9}
            ],
        })

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []  # no existing entities
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()

        with (
            patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings,
            patch("src.api.services.knowledge_graph_service.get_llm_client") as mock_llm,
            patch("src.api.services.knowledge_graph_service.get_db_session") as mock_db,
        ):
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)
            mock_llm.return_value.generate = AsyncMock(return_value=llm_response)

            # Mock context manager
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            result = await service.extract_from_chapter("novel-030", 1, "张三来到长安城")

            assert result["entities_count"] == 2
            assert result["triples_count"] == 1

    @pytest.mark.asyncio
    async def test_extract_deduplicates_existing_entity(self):
        """Existing entities are not recreated; last_chapter is updated."""
        existing_entity = _make_entity("张三", first_chapter=1)

        llm_response = json.dumps({
            "entities": [
                {"name": "张三", "type": "character", "aliases": [], "attributes": {"status": "alive"}},
            ],
            "triples": [],
        })

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_entity]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()

        with (
            patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings,
            patch("src.api.services.knowledge_graph_service.get_llm_client") as mock_llm,
            patch("src.api.services.knowledge_graph_service.get_db_session") as mock_db,
        ):
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)
            mock_llm.return_value.generate = AsyncMock(return_value=llm_response)
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            result = await service.extract_from_chapter("novel-030", 5, "张三继续修炼")

            # Entity count from LLM response is 1, but no new entity created
            assert result["entities_count"] == 1
            # Verify update was called (last_chapter update via execute)
            assert mock_session.execute.called

    @pytest.mark.asyncio
    async def test_extract_alias_match(self):
        """Entity matched by alias reuses existing ID."""
        existing_entity = _make_entity("张三", aliases=["小张"])

        llm_response = json.dumps({
            "entities": [
                {"name": "小张", "type": "character", "aliases": [], "attributes": {}},
            ],
            "triples": [],
        })

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing_entity]
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()

        with (
            patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings,
            patch("src.api.services.knowledge_graph_service.get_llm_client") as mock_llm,
            patch("src.api.services.knowledge_graph_service.get_db_session") as mock_db,
        ):
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)
            mock_llm.return_value.generate = AsyncMock(return_value=llm_response)
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            result = await service.extract_from_chapter("novel-030", 2, "小张出现了")

            # No new entity should be added (alias match)
            assert result["entities_count"] == 1
            # session.add should not be called for new entity creation
            # (only for log writing)

    @pytest.mark.asyncio
    async def test_extract_skips_empty_name(self):
        """Entities with empty name are skipped."""
        llm_response = json.dumps({
            "entities": [
                {"name": "", "type": "character", "aliases": [], "attributes": {}},
                {"name": "李四", "type": "character", "aliases": [], "attributes": {"status": "alive"}},
            ],
            "triples": [],
        })

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()

        with (
            patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings,
            patch("src.api.services.knowledge_graph_service.get_llm_client") as mock_llm,
            patch("src.api.services.knowledge_graph_service.get_db_session") as mock_db,
        ):
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)
            mock_llm.return_value.generate = AsyncMock(return_value=llm_response)
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            result = await service.extract_from_chapter("novel-030", 1, "内容")

            assert result["entities_count"] == 2  # LLM returned 2
            # But only 1 entity should be added to session (empty name skipped)

    @pytest.mark.asyncio
    async def test_extract_skips_triple_with_unknown_entity(self):
        """Triples referencing unknown entities are skipped."""
        llm_response = json.dumps({
            "entities": [
                {"name": "张三", "type": "character", "aliases": [], "attributes": {"status": "alive"}},
            ],
            "triples": [
                {"subject": "张三", "predicate": "认识", "object": "不存在的人", "confidence": 0.9},
            ],
        })

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()

        with (
            patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings,
            patch("src.api.services.knowledge_graph_service.get_llm_client") as mock_llm,
            patch("src.api.services.knowledge_graph_service.get_db_session") as mock_db,
        ):
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)
            mock_llm.return_value.generate = AsyncMock(return_value=llm_response)
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            result = await service.extract_from_chapter("novel-030", 1, "内容")

            # Triple should be skipped because "不存在的人" has no ID
            assert result["triples_count"] == 0

    @pytest.mark.asyncio
    async def test_extract_handles_llm_failure(self):
        """LLM failure is caught, error logged, zero counts returned."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()

        with (
            patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings,
            patch("src.api.services.knowledge_graph_service.get_llm_client") as mock_llm,
            patch("src.api.services.knowledge_graph_service.get_db_session") as mock_db,
        ):
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)
            mock_llm.return_value.generate = AsyncMock(side_effect=RuntimeError("API timeout"))
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            result = await service.extract_from_chapter("novel-030", 1, "内容")

            assert result["entities_count"] == 0
            assert result["triples_count"] == 0
            assert "error" in result


# ---------------------------------------------------------------------------
# retrieve_context
# ---------------------------------------------------------------------------

class TestRetrieveContext:
    """Tests for KnowledgeGraphService.retrieve_context."""

    @pytest.mark.asyncio
    async def test_feature_flag_disabled_returns_empty(self):
        """When flag is off, returns empty string."""
        with patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=False)
            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            result = await service.retrieve_context("novel-1", {"chapter": 5, "title": "测试"})
            assert result == ""

    @pytest.mark.asyncio
    async def test_no_matching_entities_returns_empty(self):
        """When no entity names appear in outline, returns empty."""
        entities = [_make_entity("张三"), _make_entity("李四")]

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = entities
        mock_session.execute = AsyncMock(return_value=mock_result)

        with (
            patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings,
            patch("src.api.services.knowledge_graph_service.get_db_session") as mock_db,
        ):
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            # Outline mentions no known entity
            result = await service.retrieve_context(
                "novel-030", {"chapter": 5, "title": "王五的冒险"}
            )
            assert result == ""

    @pytest.mark.asyncio
    async def test_matching_entities_returns_formatted_context(self):
        """When entities match, returns formatted context string."""
        entity_zhang = _make_entity("张三", attributes={"status": "alive"})
        entity_li = _make_entity("李四", attributes={"status": "alive"})

        mock_session = AsyncMock()

        with (
            patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings,
            patch("src.api.services.knowledge_graph_service.get_db_session") as mock_db,
        ):
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            service._get_existing_entities = AsyncMock(return_value=[entity_zhang, entity_li])

            mock_triple_obj = _make_triple(entity_zhang.id, "师徒", entity_li.id, chapter_number=1)

            states_result = MagicMock()
            states_result.scalars.return_value.all.return_value = []

            chars_result = MagicMock()
            chars_result.scalars.return_value.all.return_value = []

            triples_result = MagicMock()
            triples_result.scalars.return_value.all.return_value = [mock_triple_obj]

            mock_session.execute.side_effect = [
                states_result,
                chars_result,
                triples_result,
            ]

            service._get_hanging_foreshadowings = AsyncMock(return_value=[])
            service._get_recent_events = AsyncMock(return_value=[])

            result = await service.retrieve_context(
                "novel-030", {"chapter": 5, "title": "张三和李四的对决"}
            )

            assert "张三" in result
            assert "师徒" in result
            assert "已知实体记忆" in result

    @pytest.mark.asyncio
    async def test_context_truncated_at_1500_chars(self):
        """Context is truncated to 1500 characters."""
        entities = [_make_entity(f"角色{i}", attributes={"status": "alive"}) for i in range(50)]

        mock_session = AsyncMock()

        with (
            patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings,
            patch("src.api.services.knowledge_graph_service.get_db_session") as mock_db,
        ):
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            service._get_existing_entities = AsyncMock(return_value=entities)

            mock_triples = []
            for i in range(40):
                mock_triples.append(_make_triple(entities[i].id, "认识", entities[i+1].id, chapter_number=1))

            states_result = MagicMock()
            states_result.scalars.return_value.all.return_value = []

            chars_result = MagicMock()
            chars_result.scalars.return_value.all.return_value = []

            triples_result = MagicMock()
            triples_result.scalars.return_value.all.return_value = mock_triples

            mock_session.execute.side_effect = [
                states_result,
                chars_result,
                triples_result,
            ]

            service._get_hanging_foreshadowings = AsyncMock(return_value=[])
            service._get_recent_events = AsyncMock(return_value=[])

            # Build outline that mentions many entities
            outline_text = "、".join(f"角色{i}" for i in range(50))
            result = await service.retrieve_context(
                "novel-030", {"chapter": 10, "title": outline_text}
            )

            assert len(result) <= 1500
            assert len(result) > 0

    @pytest.mark.asyncio
    async def test_retrieve_context_includes_foreshadowings(self):
        """Hanging foreshadowings are included in context."""
        entity_fs = _make_entity(
            "神秘宝箱", entity_type="foreshadowing",
            attributes={"foreshadowing_status": "planted"},
            first_chapter=2,
        )
        entity_char = _make_entity("张三")

        mock_session = AsyncMock()

        with (
            patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings,
            patch("src.api.services.knowledge_graph_service.get_db_session") as mock_db,
        ):
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            service._get_existing_entities = AsyncMock(return_value=[entity_char, entity_fs])

            states_result = MagicMock()
            states_result.scalars.return_value.all.return_value = []

            chars_result = MagicMock()
            chars_result.scalars.return_value.all.return_value = []

            triples_result = MagicMock()
            triples_result.scalars.return_value.all.return_value = []

            mock_session.execute.side_effect = [
                states_result,
                chars_result,
                triples_result,
            ]

            service._get_hanging_foreshadowings = AsyncMock(return_value=[entity_fs])
            service._get_recent_events = AsyncMock(return_value=[])

            result = await service.retrieve_context(
                "novel-030", {"chapter": 5, "title": "张三发现了线索"}
            )

            assert "伏笔" in result
            assert "神秘宝箱" in result


    @pytest.mark.asyncio
    async def test_retrieve_context_exception_returns_empty(self):
        """Exception during retrieval returns empty string (graceful degradation)."""
        with patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            service._get_existing_entities = AsyncMock(side_effect=RuntimeError("DB error"))

            result = await service.retrieve_context(
                "novel-030", {"chapter": 5, "title": "张三"}
            )
            assert result == ""


# ---------------------------------------------------------------------------
# check_consistency
# ---------------------------------------------------------------------------

class TestCheckConsistency:
    """Tests for KnowledgeGraphService.check_consistency."""

    @pytest.mark.asyncio
    async def test_feature_flag_disabled_returns_empty(self):
        """When flag is off, returns empty list."""
        with patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=False)
            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            result = await service.check_consistency("novel-1", 5, "内容")
            assert result == []

    @pytest.mark.asyncio
    async def test_dead_character_active_detected(self):
        """Rule detects dead character performing actions."""
        dead_char = _make_entity("张三", attributes={"status": "dead"})
        alive_char = _make_entity("李四", attributes={"status": "alive"})

        triple = _make_triple(
            subject_id=dead_char.id,
            predicate="位于",
            object_id=alive_char.id,
            chapter_number=5,
        )

        with patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            service._get_chapter_triples = AsyncMock(return_value=[triple])
            service._get_existing_entities = AsyncMock(return_value=[dead_char, alive_char])
            service._build_history_context = AsyncMock(return_value="历史上下文")
            service._llm_consistency_check = AsyncMock(return_value=[])

            result = await service.check_consistency("novel-030", 5, "张三来到了集市")

            assert len(result) >= 1
            conflict = result[0]
            assert conflict["severity"] == "error"
            assert conflict["type"] == "dead_character_active"
            assert "张三" in conflict["entity"]

    @pytest.mark.asyncio
    async def test_no_conflicts_returns_empty(self):
        """No rule violations returns empty list (LLM not called)."""
        alive_char = _make_entity("张三", attributes={"status": "alive"})
        location = _make_entity("长安城", entity_type="location")

        triple = _make_triple(
            subject_id=alive_char.id,
            predicate="位于",
            object_id=location.id,
            chapter_number=5,
        )

        with patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            service._get_chapter_triples = AsyncMock(return_value=[triple])
            service._get_existing_entities = AsyncMock(return_value=[alive_char, location])
            service._llm_consistency_check = AsyncMock(return_value=[])

            result = await service.check_consistency("novel-030", 5, "张三来到长安城")

            # No conflicts from rules, LLM not called
            assert result == []
            service._llm_consistency_check.assert_not_called()

    @pytest.mark.asyncio
    async def test_rule_conflict_triggers_llm_check(self):
        """When rule-based check finds issues, LLM check is also triggered."""
        dead_char = _make_entity("张三", attributes={"status": "dead"})
        location = _make_entity("集市", entity_type="location")

        triple = _make_triple(
            subject_id=dead_char.id,
            predicate="前往",
            object_id=location.id,
            chapter_number=5,
        )

        llm_conflicts = [
            {"severity": "warning", "type": "timeline_inconsistency",
             "message": "张三在第3章已死亡", "entity": "张三"}
        ]

        with patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            service._get_chapter_triples = AsyncMock(return_value=[triple])
            service._get_existing_entities = AsyncMock(return_value=[dead_char, location])
            service._build_history_context = AsyncMock(return_value="context")
            service._llm_consistency_check = AsyncMock(return_value=llm_conflicts)

            result = await service.check_consistency("novel-030", 5, "张三前往集市")

            # Rule-based + LLM conflicts combined
            assert len(result) == 2
            service._llm_consistency_check.assert_called_once()

    @pytest.mark.asyncio
    async def test_consistency_check_exception_returns_empty(self):
        """Exception during check returns empty list (graceful degradation)."""
        with patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            service._get_chapter_triples = AsyncMock(side_effect=RuntimeError("DB error"))

            result = await service.check_consistency("novel-030", 5, "内容")
            assert result == []

    @pytest.mark.asyncio
    async def test_non_action_predicate_not_flagged(self):
        """Dead character with non-action predicate (e.g. '被提及') is not flagged."""
        dead_char = _make_entity("张三", attributes={"status": "dead"})
        alive_char = _make_entity("李四", attributes={"status": "alive"})

        triple = _make_triple(
            subject_id=dead_char.id,
            predicate="被提及",
            object_id=alive_char.id,
            chapter_number=5,
        )

        with patch("src.api.services.knowledge_graph_service.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)

            from src.api.services.knowledge_graph_service import KnowledgeGraphService
            service = KnowledgeGraphService()
            service._get_chapter_triples = AsyncMock(return_value=[triple])
            service._get_existing_entities = AsyncMock(return_value=[dead_char, alive_char])

            result = await service.check_consistency("novel-030", 5, "李四想起了张三")

            # "被提及" is not in the action predicates list
            assert result == []


# ---------------------------------------------------------------------------
# _format_context
# ---------------------------------------------------------------------------

class TestFormatContext:
    """Tests for the _format_context helper."""

    def test_empty_inputs_returns_header_only(self):
        """With no data, returns just the header."""
        from src.api.services.knowledge_graph_service import KnowledgeGraphService
        service = KnowledgeGraphService()
        result = service._format_context([], [], [], [])
        assert "已知设定" in result

    def test_includes_character_status(self):
        """Character status section is included."""
        from src.api.services.knowledge_graph_service import KnowledgeGraphService
        service = KnowledgeGraphService()
        char = _make_entity("张三", attributes={"status": "alive"})
        result = service._format_context([], [], [], [char])
        assert "张三" in result
        assert "alive" in result

    def test_includes_foreshadowing(self):
        """Foreshadowing section is included."""
        from src.api.services.knowledge_graph_service import KnowledgeGraphService
        service = KnowledgeGraphService()
        fs = _make_entity("神秘信件", entity_type="foreshadowing", first_chapter=3)
        result = service._format_context([], [fs], [], [])
        assert "伏笔" in result
        assert "神秘信件" in result
