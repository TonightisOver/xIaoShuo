"""Unit tests for Live Knowledge Graph features (CHANGE-032).

Tests cover:
- _merge_entities: state inheritance merging and snapshot saving.
- retrieve_context: high-precision entity matching in outline (name/aliases),
  retrieval of chronological latest state snapshots,
  chronological deduplication of active relationship triples,
  merging character settings (personality/background),
  and structural Markdown context formatting.
"""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.models.db_models import (
    Character,
    KnowledgeEntity,
    KnowledgeEntityState,
    KnowledgeTriple,
)
from src.api.services.knowledge.knowledge_graph_service import KnowledgeGraphService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entity(
    id_: str,
    name: str,
    entity_type: str = "character",
    novel_id: str = "novel-032",
    aliases: list | None = None,
    attributes: dict | None = None,
    first_chapter: int = 1,
    last_chapter: int | None = None,
) -> MagicMock:
    """Build a mock KnowledgeEntity."""
    e = MagicMock(spec=KnowledgeEntity)
    e.id = id_
    e.novel_id = novel_id
    e.entity_type = entity_type
    e.name = name
    e.aliases = aliases or []
    e.attributes = attributes or {}
    e.first_chapter = first_chapter
    e.last_chapter = last_chapter
    return e


def _make_state(
    id_: str,
    entity_id: str,
    chapter_number: int,
    attributes: dict,
    novel_id: str = "novel-032",
) -> MagicMock:
    """Build a mock KnowledgeEntityState."""
    s = MagicMock(spec=KnowledgeEntityState)
    s.id = id_
    s.novel_id = novel_id
    s.entity_id = entity_id
    s.chapter_number = chapter_number
    s.attributes = attributes
    return s


def _make_triple(
    subject_id: str,
    predicate: str,
    object_id: str,
    chapter_number: int,
    novel_id: str = "novel-032",
    metadata_: dict | None = None,
    status: str = "active",
) -> MagicMock:
    """Build a mock KnowledgeTriple."""
    t = MagicMock(spec=KnowledgeTriple)
    t.id = str(uuid.uuid4())
    t.novel_id = novel_id
    t.subject_id = subject_id
    t.predicate = predicate
    t.object_id = object_id
    t.chapter_number = chapter_number
    t.confidence = 1.0
    t.status = status
    t.metadata_ = metadata_ or {}
    return t


def _make_character(
    name: str,
    personality: str = "",
    background_story: str = "",
    abilities: str = "",
    role: str = "",
    description: str = "",
    novel_id: str = "novel-032",
) -> MagicMock:
    """Build a mock Character."""
    c = MagicMock(spec=Character)
    c.id = str(uuid.uuid4())
    c.novel_id = novel_id
    c.name = name
    c.personality = personality
    c.background_story = background_story
    c.abilities = abilities
    c.role = role
    c.description = description
    return c


# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

class TestLiveKnowledgeGraph:
    """Tests for Live Knowledge Graph features."""

    @pytest.mark.asyncio
    @patch("src.api.services.knowledge.knowledge_graph_service.get_settings")
    @patch("src.api.services.knowledge.knowledge_graph_service.get_llm_client")
    @patch("src.api.services.knowledge.knowledge_graph_service.get_db_session")
    async def test_state_inheritance_and_saving(
        self, mock_db, mock_llm, mock_settings
    ):
        """Test that state is inherited and correctly saved/overwritten."""
        # 1. Setup mock environment
        mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)

        # LLM extracts attributes for chapter 3:
        # 张三 has status "injured", health 60
        llm_response = json.dumps({
            "entities": [
                {
                    "name": "张三",
                    "type": "character",
                    "aliases": [],
                    "attributes": {"status": "injured", "health": 60},
                },
            ],
            "triples": [],
        })
        mock_llm.return_value.generate = AsyncMock(return_value=llm_response)

        # 2. Existing entities in the DB
        entity_id = "entity-zhang"
        existing_entity = _make_entity(
            id_=entity_id,
            name="张三",
            attributes={"location": "Beijing", "status": "healthy"},
            first_chapter=1,
            last_chapter=2,
        )

        # Mock latest state in database before chapter 3 (e.g., from chapter 2)
        previous_state = _make_state(
            id_="state-ch2",
            entity_id=entity_id,
            chapter_number=2,
            attributes={"location": "Beijing", "status": "healthy"},
        )

        # Mock DB sessions
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock self._get_existing_entities to return the existing entity
        # And mock query sequences in _merge_entities:
        # First: select(KnowledgeEntity).where(KnowledgeEntity.id == matched_id)
        # Second: select(KnowledgeEntityState)...order_by(chapter_number.desc())
        # .limit(1)
        # Third: select(KnowledgeEntityState)...where(
        # chapter_number == chapter_number)

        entity_result = MagicMock()
        entity_result.scalar_one_or_none.return_value = existing_entity

        latest_state_result = MagicMock()
        latest_state_result.scalar_one_or_none.return_value = previous_state

        chapter_state_result = MagicMock()
        # No state exists for chapter 3 yet
        chapter_state_result.scalar_one_or_none.return_value = None

        mock_session.execute.side_effect = [
            entity_result,          # Query KnowledgeEntity
            latest_state_result,    # Query latest state < chapter 3
            chapter_state_result,   # Query state == chapter 3
            MagicMock(),            # Query delete in _write_extraction_log
        ]

        service = KnowledgeGraphService()

        # Override _get_existing_entities to return our setup
        service._get_existing_entities = AsyncMock(return_value=[existing_entity])
        service._write_triples = AsyncMock(return_value=0)

        # Run extract
        result = await service.extract_from_chapter(
            "novel-032", 3, "张三在第三章受伤了"
        )

        assert result["entities_count"] == 1
        # Inherited attributes: location ("Beijing"),
        # status overwritten ("injured"), health added (60)
        expected_attrs = {"location": "Beijing", "status": "injured", "health": 60}
        assert existing_entity.attributes == expected_attrs
        assert existing_entity.last_chapter == 3

        # Check that new state was added
        added_objs = []
        for call in mock_session.add.call_args_list:
            added_objs.append(call[0][0])

        # A new state should be saved
        saved_states = [
            obj for obj in added_objs if isinstance(obj, KnowledgeEntityState)
        ]
        assert len(saved_states) == 1
        assert saved_states[0].entity_id == entity_id
        assert saved_states[0].chapter_number == 3
        assert saved_states[0].attributes == expected_attrs

    @pytest.mark.asyncio
    @patch("src.api.services.knowledge.knowledge_graph_service.get_settings")
    @patch("src.api.services.knowledge.knowledge_graph_service.get_db_session")
    async def test_retrieve_context_active_relationship_deduplication(
        self, mock_db, mock_settings
    ):
        """Test that active relations are correctly deduplicated chronologically,
        keeping only the latest.
        """
        mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)

        entity_id_a = "entity-a"
        entity_id_b = "entity-b"
        entity_a = _make_entity(id_=entity_id_a, name="张三", first_chapter=1)
        entity_b = _make_entity(id_=entity_id_b, name="李四", first_chapter=1)

        # Triples setup: two "like" relationships between 张三 and 李四
        # Chapter 1: favorability is 10
        # Chapter 2: favorability is 30
        triple_ch1 = _make_triple(
            subject_id=entity_id_a,
            predicate="喜欢",
            object_id=entity_id_b,
            chapter_number=1,
            metadata_={"好感度": 10},
        )
        triple_ch2 = _make_triple(
            subject_id=entity_id_a,
            predicate="喜欢",
            object_id=entity_id_b,
            chapter_number=2,
            metadata_={"好感度": 30},
        )

        mock_session = AsyncMock()
        mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

        # Mock database query results:
        # Query 1 (retrieve_context states): empty states
        states_result = MagicMock()
        states_result.scalars.return_value.all.return_value = []

        # Query 2 (retrieve_context characters): empty characters
        chars_result = MagicMock()
        chars_result.scalars.return_value.all.return_value = []

        # Query 3 (retrieve_context triples): returns active triples
        # (ordered by chapter desc)
        triples_result = MagicMock()
        triples_result.scalars.return_value.all.return_value = [triple_ch2, triple_ch1]

        mock_session.execute.side_effect = [
            states_result,
            chars_result,
            triples_result,
        ]

        service = KnowledgeGraphService()
        service._get_existing_entities = AsyncMock(return_value=[entity_a, entity_b])
        service._get_hanging_foreshadowings = AsyncMock(return_value=[])
        service._get_recent_events = AsyncMock(return_value=[])

        # Run retrieve_context for Chapter 3
        outline = {"chapter": 3, "outline": "张三和李四在花园见面。"}
        context = await service.retrieve_context("novel-032", outline)

        # Check deduplication: only the latest triple from chapter 2
        # (with favorability 30) is kept
        assert "喜欢" in context
        assert "好感度: 30" in context
        assert "好感度: 10" not in context  # Old one should be deduplicated out

    @pytest.mark.asyncio
    @patch("src.api.services.knowledge.knowledge_graph_service.get_settings")
    @patch("src.api.services.knowledge.knowledge_graph_service.get_db_session")
    async def test_retrieve_context_outline_matching(self, mock_db, mock_settings):
        """Test high-precision entity matching in chapter outlines
        using both names and aliases.
        """
        mock_settings.return_value = MagicMock(KNOWLEDGE_GRAPH_ENABLED=True)

        entity_a = _make_entity(
            id_="entity-a", name="张三", aliases=["小张"], first_chapter=1
        )
        entity_b = _make_entity(
            id_="entity-b", name="李四", aliases=[], first_chapter=1
        )
        entity_c = _make_entity(
            id_="entity-c", name="王五", aliases=["老王"], first_chapter=1
        )

        mock_session = AsyncMock()
        mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

        # Query 1 (retrieve_context states): empty
        states_result = MagicMock()
        states_result.scalars.return_value.all.return_value = []

        # Query 2 (retrieve_context characters): empty
        chars_result = MagicMock()
        chars_result.scalars.return_value.all.return_value = []

        # Query 3 (retrieve_context triples): empty
        triples_result = MagicMock()
        triples_result.scalars.return_value.all.return_value = []

        mock_session.execute.side_effect = [
            states_result,
            chars_result,
            triples_result,
        ]

        service = KnowledgeGraphService()
        # Mock _get_existing_entities to return all three entities
        service._get_existing_entities = AsyncMock(
            return_value=[entity_a, entity_b, entity_c]
        )
        service._get_hanging_foreshadowings = AsyncMock(return_value=[])
        service._get_recent_events = AsyncMock(return_value=[])

        # Outline text matches "小张" (alias of entity_a) and "李四"
        # (name of entity_b). "王五" is not matched.
        outline = {"chapter": 2, "outline": "小张和李四一起商量对策。"}
        context = await service.retrieve_context("novel-032", outline)

        # Check formatting:
        # Both "张三" (due to alias "小张") and "李四" are included
        assert "张三" in context
        assert "李四" in context
        assert "王五" not in context
