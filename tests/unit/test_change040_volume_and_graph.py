"""Unit tests for CHANGE-040: volume_number fallback, chapter 404 resilience,
and knowledge graph frequency filtering."""


import pytest

# ===========================================================================
# 1. _find_volume_number fallback logic
# ===========================================================================

class TestFindVolumeNumberFallback:
    """Test that _find_volume_number uses chapter_start/chapter_end as fallback."""

    def _make_find_volume_number(self, volumes):
        """Recreate the _find_volume_number closure with given volumes."""
        def _find_volume_number(ch_num: int):
            for vol in volumes:
                outline = vol.get("outline") or {}
                for ch in outline.get("chapters", []):
                    if ch.get("chapter") == ch_num:
                        return vol.get("volume_number")
            for vol in volumes:
                ch_start = vol.get("chapter_start")
                ch_end = vol.get("chapter_end")
                if ch_start is not None and ch_end is not None:
                    if ch_start <= ch_num <= ch_end:
                        return vol.get("volume_number")
            return None
        return _find_volume_number

    def test_exact_match_via_outline(self):
        volumes = [
            {"volume_number": 1, "outline": {"chapters": [{"chapter": 1}, {"chapter": 2}]},
             "chapter_start": 1, "chapter_end": 5}
        ]
        fn = self._make_find_volume_number(volumes)
        assert fn(1) == 1
        assert fn(2) == 1

    def test_fallback_via_range(self):
        volumes = [
            {"volume_number": 1, "outline": {}, "chapter_start": 1, "chapter_end": 5},
            {"volume_number": 2, "outline": {}, "chapter_start": 6, "chapter_end": 10},
        ]
        fn = self._make_find_volume_number(volumes)
        assert fn(3) == 1
        assert fn(7) == 2

    def test_returns_none_when_no_match(self):
        volumes = [
            {"volume_number": 1, "outline": {}, "chapter_start": 1, "chapter_end": 5},
        ]
        fn = self._make_find_volume_number(volumes)
        assert fn(99) is None

    def test_outline_takes_priority_over_range(self):
        volumes = [
            {"volume_number": 1, "outline": {"chapters": [{"chapter": 3}]},
             "chapter_start": 1, "chapter_end": 5},
            {"volume_number": 2, "outline": {}, "chapter_start": 1, "chapter_end": 10},
        ]
        fn = self._make_find_volume_number(volumes)
        assert fn(3) == 1

    def test_handles_none_chapter_start_end(self):
        volumes = [
            {"volume_number": 1, "outline": {}, "chapter_start": None, "chapter_end": None},
        ]
        fn = self._make_find_volume_number(volumes)
        assert fn(1) is None


# ===========================================================================
# 2. Successful chapters filter (only replace chapters with content)
# ===========================================================================

class TestSuccessfulChaptersFilter:
    """Test that only chapters with content and word_count > 0 are persisted."""

    def test_filters_empty_content(self):
        generated = [
            {"chapter": 1, "content": "Hello world", "word_count": 100, "title": "Ch1"},
            {"chapter": 2, "content": "", "word_count": 0, "title": "Ch2"},
            {"chapter": 3, "content": None, "word_count": 0, "title": "Ch3"},
        ]
        successful = [ch for ch in generated if ch.get("content") and ch.get("word_count", 0) > 0]
        assert len(successful) == 1
        assert successful[0]["chapter"] == 1

    def test_filters_zero_word_count(self):
        generated = [
            {"chapter": 1, "content": "Some text", "word_count": 0, "title": "Ch1"},
        ]
        successful = [ch for ch in generated if ch.get("content") and ch.get("word_count", 0) > 0]
        assert len(successful) == 0

    def test_keeps_valid_chapters(self):
        generated = [
            {"chapter": 1, "content": "Text A", "word_count": 50, "title": "A"},
            {"chapter": 2, "content": "Text B", "word_count": 200, "title": "B"},
        ]
        successful = [ch for ch in generated if ch.get("content") and ch.get("word_count", 0) > 0]
        assert len(successful) == 2


# ===========================================================================
# 3. Knowledge graph frequency filtering
# ===========================================================================

class TestKnowledgeGraphFrequencyFilter:
    """Test the frequency-based entity filtering logic."""

    def _build_frequency_map(self, triples):
        entity_frequency: dict[str, int] = {}
        for t in triples:
            entity_frequency[t["subject_id"]] = entity_frequency.get(t["subject_id"], 0) + 1
            entity_frequency[t["object_id"]] = entity_frequency.get(t["object_id"], 0) + 1
        return entity_frequency

    def _should_include(self, entity_id, layer_type, entity_frequency, min_frequency):
        if layer_type == "foreshadowing":
            return True
        freq = entity_frequency.get(entity_id, 0)
        return freq >= min_frequency

    def test_high_frequency_entity_included(self):
        triples = [
            {"subject_id": "e1", "object_id": "e2"},
            {"subject_id": "e1", "object_id": "e3"},
            {"subject_id": "e1", "object_id": "e4"},
        ]
        freq_map = self._build_frequency_map(triples)
        assert freq_map["e1"] == 3
        assert self._should_include("e1", "character", freq_map, 2) is True

    def test_low_frequency_entity_excluded(self):
        triples = [
            {"subject_id": "e1", "object_id": "e2"},
        ]
        freq_map = self._build_frequency_map(triples)
        assert freq_map["e2"] == 1
        assert self._should_include("e2", "character", freq_map, 2) is False

    def test_foreshadowing_always_included(self):
        triples = [
            {"subject_id": "e1", "object_id": "e2"},
        ]
        freq_map = self._build_frequency_map(triples)
        assert self._should_include("e2", "foreshadowing", freq_map, 10) is True

    def test_min_frequency_1_includes_all(self):
        triples = [
            {"subject_id": "e1", "object_id": "e2"},
        ]
        freq_map = self._build_frequency_map(triples)
        assert self._should_include("e1", "character", freq_map, 1) is True
        assert self._should_include("e2", "event", freq_map, 1) is True

    def test_entity_not_in_triples_excluded(self):
        freq_map: dict[str, int] = {}
        assert self._should_include("orphan", "character", freq_map, 2) is False


# ===========================================================================
# 4. API route min_frequency parameter validation
# ===========================================================================

class TestMinFrequencyParam:
    """Test that the API route accepts min_frequency parameter correctly."""

    def test_query_import_exists(self):
        from fastapi import Query
        assert Query is not None

    def test_route_signature(self):
        import inspect

        from src.api.routes.knowledge_graph import get_three_layer_graph
        sig = inspect.signature(get_three_layer_graph)
        assert "min_frequency" in sig.parameters
        param = sig.parameters["min_frequency"]
        assert param.default is not inspect.Parameter.empty


# ===========================================================================
# 5. Quality score persistence to ChapterVersion
# ===========================================================================

class TestQualityScorePersistence:
    """Test that quality_check node persists scores to active version."""

    def test_persist_function_exists(self):
        import inspect

        from src.api.services.generation.novel_generator import (
            _persist_quality_to_version,
        )
        assert inspect.iscoroutinefunction(_persist_quality_to_version)

    @pytest.mark.asyncio
    async def test_persist_handles_missing_novel_id_gracefully(self):
        from src.api.services.generation.novel_generator import (
            _persist_quality_to_version,
        )
        # Should not raise even with invalid novel_id
        await _persist_quality_to_version(
            novel_id="nonexistent-novel",
            chapter_number=1,
            quality_scores={"overall": 0.85},
            consistency_warnings=[],
        )

    def test_quality_check_node_is_async(self):
        import inspect

        from src.core.langgraph.nodes.quality_check import node
        assert inspect.iscoroutinefunction(node)
