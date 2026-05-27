"""Unit tests for CHANGE-025 fixes: outline multi-volume and arc generation."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


class TestOutlineVolumeNumberFix:
    """Tests for generate_volume_outlines volume_number fallback fix."""

    @pytest.mark.asyncio
    async def test_volume_number_uses_index_when_missing(self):
        """LLM response without volume_number should use enumerated index."""
        from src.api.services.outline_service import OutlineService

        service = OutlineService()

        # LLM returns volumes without volume_number field
        llm_volumes = [
            {"title": "第一卷", "summary": "开篇"},
            {"title": "第二卷", "summary": "发展"},
            {"title": "第三卷", "summary": "高潮"},
        ]

        saved = {}

        async def mock_upsert(novel_id, vol_num, content):
            saved[vol_num] = content

        async def mock_get_master(novel_id):
            return {"id": 1, "content": {"premise": "test"}, "status": "draft", "updated_at": None}

        with patch.object(service, "get_master_outline", side_effect=mock_get_master), \
             patch.object(service, "upsert_volume_outline", side_effect=mock_upsert), \
             patch("src.api.services.outline_service.get_llm_client") as mock_llm, \
             patch("src.api.services.outline_service.generate_and_parse_json", return_value=llm_volumes):

            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value="[]")
            mock_llm.return_value = mock_client

            result = await service.generate_volume_outlines("novel1", "玄幻", 100000)

        # All three volumes should be saved with correct indices
        assert 1 in saved
        assert 2 in saved
        assert 3 in saved
        assert saved[1]["volume_number"] == 1
        assert saved[2]["volume_number"] == 2
        assert saved[3]["volume_number"] == 3

    @pytest.mark.asyncio
    async def test_volume_number_preserved_when_present(self):
        """LLM response with explicit volume_number should use that value."""
        from src.api.services.outline_service import OutlineService

        service = OutlineService()

        llm_volumes = [
            {"volume_number": 2, "title": "第二卷"},
            {"volume_number": 3, "title": "第三卷"},
        ]

        saved = {}

        async def mock_upsert(novel_id, vol_num, content):
            saved[vol_num] = content

        async def mock_get_master(novel_id):
            return {"id": 1, "content": {}, "status": "draft", "updated_at": None}

        with patch.object(service, "get_master_outline", side_effect=mock_get_master), \
             patch.object(service, "upsert_volume_outline", side_effect=mock_upsert), \
             patch("src.api.services.outline_service.get_llm_client") as mock_llm, \
             patch("src.api.services.outline_service.generate_and_parse_json", return_value=llm_volumes):

            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value="[]")
            mock_llm.return_value = mock_client

            await service.generate_volume_outlines("novel1", "玄幻", 100000)

        # Explicit volume numbers should be preserved
        assert 2 in saved
        assert 3 in saved
        assert 1 not in saved


class TestArcGenerationFix:
    """Tests for generate_arcs_ai actual character ID mapping fix."""

    @pytest.mark.asyncio
    async def test_arcs_use_actual_character_ids(self):
        """Arc generation should map to actual DB character IDs, not LLM-invented ones."""
        from src.api.services.ai_generation_service import AIGenerationService

        service = AIGenerationService()

        actual_characters = [
            {"id": 101, "name": "张三", "role": "主角"},
            {"id": 202, "name": "李四", "role": "配角"},
        ]

        # LLM returns arcs with fake IDs (1, 2) not matching actual DB IDs
        llm_arcs = [
            {"character_id": 1, "arc_type": "growth", "description": "成长弧"},
            {"character_id": 2, "arc_type": "fall", "description": "堕落弧"},
        ]

        created_arcs = []

        async def mock_create_arc(novel_id, character_id, arc_type, description, stages):
            arc_id = 1000 + len(created_arcs)
            created_arcs.append({"id": arc_id, "character_id": character_id})
            return arc_id

        with patch("src.api.services.novel_manager.get_novel_manager") as mock_mgr, \
             patch("src.core.llm.client.get_llm_client") as mock_llm, \
             patch("src.core.llm.helpers.safe_json_parse", return_value=llm_arcs), \
             patch("src.api.services.storyline_service.get_storyline_service") as mock_sl:

            mock_sl_instance = AsyncMock()
            mock_sl_instance.create_character_arc = AsyncMock(side_effect=mock_create_arc)
            mock_sl_instance.list_storylines = AsyncMock(return_value=[])
            mock_sl.return_value = mock_sl_instance

            mock_manager = AsyncMock()
            mock_manager.list_characters = AsyncMock(return_value=actual_characters)
            mock_mgr.return_value = mock_manager

            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value="[]")
            mock_llm.return_value = mock_client

            result = await service.generate_arcs_ai("novel1")

        # Should use actual character IDs (101, 202), not LLM's fake IDs (1, 2)
        assert len(result) == 2
        assert result[0]["character_id"] == 101
        assert result[1]["character_id"] == 202

    @pytest.mark.asyncio
    async def test_arcs_limited_to_available_characters(self):
        """If LLM returns more arcs than characters, extras are skipped."""
        from src.api.services.ai_generation_service import AIGenerationService

        service = AIGenerationService()

        actual_characters = [{"id": 10, "name": "主角", "role": "主角"}]
        llm_arcs = [
            {"character_id": 1, "arc_type": "growth", "description": "弧1"},
            {"character_id": 2, "arc_type": "fall", "description": "弧2"},
            {"character_id": 3, "arc_type": "flat", "description": "弧3"},
        ]

        created_count = 0

        async def mock_create_arc(novel_id, character_id, arc_type, description, stages):
            nonlocal created_count
            created_count += 1
            return created_count

        with patch("src.api.services.novel_manager.get_novel_manager") as mock_mgr, \
             patch("src.core.llm.client.get_llm_client") as mock_llm, \
             patch("src.core.llm.helpers.safe_json_parse", return_value=llm_arcs), \
             patch("src.api.services.storyline_service.get_storyline_service") as mock_sl:

            mock_sl_instance = AsyncMock()
            mock_sl_instance.create_character_arc = AsyncMock(side_effect=mock_create_arc)
            mock_sl_instance.list_storylines = AsyncMock(return_value=[])
            mock_sl.return_value = mock_sl_instance

            mock_manager = AsyncMock()
            mock_manager.list_characters = AsyncMock(return_value=actual_characters)
            mock_mgr.return_value = mock_manager

            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value="[]")
            mock_llm.return_value = mock_client

            result = await service.generate_arcs_ai("novel1")

        # Only 1 arc created (limited by number of characters)
        assert len(result) == 1
        assert result[0]["character_id"] == 10

    @pytest.mark.asyncio
    async def test_arcs_returns_empty_when_no_characters(self):
        """Arc generation returns empty list when no characters exist."""
        from src.api.services.ai_generation_service import AIGenerationService

        service = AIGenerationService()

        with patch("src.api.services.novel_manager.get_novel_manager") as mock_mgr:
            mock_manager = AsyncMock()
            mock_manager.list_characters = AsyncMock(return_value=[])
            mock_mgr.return_value = mock_manager

            result = await service.generate_arcs_ai("novel1")

        assert result == []
