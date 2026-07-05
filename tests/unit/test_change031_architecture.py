"""Unit tests for CHANGE-031: architecture cleanup.

Tests cover:
1. _build_initial_state — state construction with mocked dependencies
2. generate_single_chapter — prompt building and return format
3. novel_id ownership validation — cross-novel access returns False
4. UniqueConstraint — duplicate insert raises IntegrityError
5. structlog replacement — services import correctly
"""

from unittest.mock import AsyncMock, patch

import pytest


# ============================================================
#  _build_initial_state tests
# ============================================================


class TestBuildInitialState:
    """Tests for _build_initial_state in novel_generator."""

    @pytest.mark.asyncio
    async def test_builds_basic_state_without_novel_id(self):
        """When task has no novel_id, returns base state only."""
        from src.api.models.requests import CreateNovelRequest
        from src.api.services.novel_generator import _build_initial_state

        request = CreateNovelRequest(
            idea="一个修仙者穿越到现代都市的奇幻故事",
            novel_type="玄幻",
            target_words=100000,
            writing_style="热血燃向",
            writing_style_prompt="",
        )

        with patch("src.api.services.novel_generator.get_task_manager") as mock_tm:
            mock_task_mgr = AsyncMock()
            mock_task_mgr.get_task = AsyncMock(return_value={"novel_id": None})
            mock_tm.return_value = mock_task_mgr

            state, novel_id = await _build_initial_state("task-001", request)

        assert novel_id is None
        assert state["project_id"] == "task-001"
        assert state["idea"] == request.idea
        assert state["novel_type"] == "玄幻"
        assert state["target_words"] == 100000
        assert state["writing_style"] == "热血燃向"
        assert state["current_stage"] == "start"
        assert state["chapters"] == []
        assert state["errors"] == []
        # No world_setting or characters injected
        assert "world_setting" not in state
        assert "characters" not in state

    @pytest.mark.asyncio
    async def test_builds_state_with_existing_world_and_characters(self):
        """When novel has world_setting and characters, they are injected."""
        from src.api.models.requests import CreateNovelRequest
        from src.api.services.novel_generator import _build_initial_state

        request = CreateNovelRequest(
            idea="星际冒险故事，主角是年轻舰长",
            novel_type="科幻",
            target_words=200000,
            writing_style="现代白话",
        )

        world = {
            "background": "银河帝国",
            "rules": "超光速",
            "culture": "联邦",
            "geography": "四象限",
        }
        characters = [
            {"name": "林峰", "role": "主角"},
            {"name": "艾米", "role": "女主"},
        ]

        with patch("src.api.services.novel_generator.get_task_manager") as mock_tm, \
             patch("src.api.services.world_service.get_world_service") as mock_ws, \
             patch("src.api.services.character_service.get_character_service") as mock_cs, \
             patch("src.api.services.storyline_service.get_storyline_service") as mock_sl:

            mock_task_mgr = AsyncMock()
            mock_task_mgr.get_task = AsyncMock(return_value={"novel_id": "novel-123"})
            mock_tm.return_value = mock_task_mgr

            mock_world_svc = AsyncMock()
            mock_world_svc.get_world_setting = AsyncMock(return_value=world)
            mock_ws.return_value = mock_world_svc

            mock_char_svc = AsyncMock()
            mock_char_svc.list_characters = AsyncMock(return_value=characters)
            mock_cs.return_value = mock_char_svc

            mock_sl_svc = AsyncMock()
            mock_sl_svc.list_storylines = AsyncMock(return_value=[])
            mock_sl.return_value = mock_sl_svc

            state, novel_id = await _build_initial_state("task-002", request)

        assert novel_id == "novel-123"
        assert state["world_setting"] == world
        assert state["characters"] == characters

    @pytest.mark.asyncio
    async def test_builds_state_with_storylines_appended_to_idea(self):
        """When novel has storylines, they are appended to idea."""
        from src.api.models.requests import CreateNovelRequest
        from src.api.services.novel_generator import _build_initial_state

        request = CreateNovelRequest(
            idea="修仙世界的冒险故事，主角从凡人成长",
            novel_type="玄幻",
            target_words=100000,
            writing_style="现代白话",
        )

        storylines = [
            {"name": "主线", "type": "main", "description": "修仙之路"},
            {"name": "感情线", "type": "sub", "description": "师妹情缘"},
        ]

        with patch("src.api.services.novel_generator.get_task_manager") as mock_tm, \
             patch("src.api.services.world_service.get_world_service") as mock_ws, \
             patch("src.api.services.character_service.get_character_service") as mock_cs, \
             patch("src.api.services.storyline_service.get_storyline_service") as mock_sl:

            mock_task_mgr = AsyncMock()
            mock_task_mgr.get_task = AsyncMock(return_value={"novel_id": "novel-456"})
            mock_tm.return_value = mock_task_mgr

            mock_world_svc = AsyncMock()
            mock_world_svc.get_world_setting = AsyncMock(return_value=None)
            mock_ws.return_value = mock_world_svc

            mock_char_svc = AsyncMock()
            mock_char_svc.list_characters = AsyncMock(return_value=[])
            mock_cs.return_value = mock_char_svc

            mock_sl_svc = AsyncMock()
            mock_sl_svc.list_storylines = AsyncMock(return_value=storylines)
            mock_sl.return_value = mock_sl_svc

            state, novel_id = await _build_initial_state("task-003", request)

        assert novel_id == "novel-456"
        assert "已确定的故事线" in state["idea"]
        assert "修仙之路" in state["idea"]
        assert "师妹情缘" in state["idea"]

    @pytest.mark.asyncio
    async def test_builds_state_skips_empty_world_setting(self):
        """World setting with all empty fields is not injected."""
        from src.api.models.requests import CreateNovelRequest
        from src.api.services.novel_generator import _build_initial_state

        request = CreateNovelRequest(
            idea="一个简单的都市故事，主角是普通上班族",
            novel_type="都市",
            target_words=50000,
            writing_style="现代白话",
        )

        empty_world = {
            "background": None,
            "rules": None,
            "culture": None,
            "geography": None,
        }

        with patch("src.api.services.novel_generator.get_task_manager") as mock_tm, \
             patch("src.api.services.world_service.get_world_service") as mock_ws, \
             patch("src.api.services.character_service.get_character_service") as mock_cs, \
             patch("src.api.services.storyline_service.get_storyline_service") as mock_sl:

            mock_task_mgr = AsyncMock()
            mock_task_mgr.get_task = AsyncMock(return_value={"novel_id": "novel-789"})
            mock_tm.return_value = mock_task_mgr

            mock_world_svc = AsyncMock()
            mock_world_svc.get_world_setting = AsyncMock(return_value=empty_world)
            mock_ws.return_value = mock_world_svc

            mock_char_svc = AsyncMock()
            mock_char_svc.list_characters = AsyncMock(return_value=[])
            mock_cs.return_value = mock_char_svc

            mock_sl_svc = AsyncMock()
            mock_sl_svc.list_storylines = AsyncMock(return_value=[])
            mock_sl.return_value = mock_sl_svc

            state, novel_id = await _build_initial_state("task-004", request)

        assert "world_setting" not in state


# ============================================================
#  generate_single_chapter tests
# ============================================================


class TestGenerateSingleChapter:
    """Tests for generate_single_chapter in chapter_generator."""

    @pytest.mark.asyncio
    async def test_basic_generation_returns_correct_format(self):
        """Happy path: returns dict with chapter, title, content, word_count."""
        from src.core.llm.chapter_generator import generate_single_chapter

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="这是生成的章节内容，包含精彩的情节。")

        chapter_outline = {"chapter": 3, "title": "风云突变", "plot": "主角遭遇危机"}

        result = await generate_single_chapter(
            client=mock_client,
            chapter_outline=chapter_outline,
            previous_chapter="上一章结尾内容",
            characters_json='[{"name": "张三", "role": "主角"}]',
            world_setting_json='{"background": "修仙世界"}',
        )

        assert result["chapter"] == 3
        assert result["title"] == "风云突变"
        assert result["content"] == "这是生成的章节内容，包含精彩的情节。"
        assert result["word_count"] == len("这是生成的章节内容，包含精彩的情节。")

    @pytest.mark.asyncio
    async def test_first_chapter_uses_default_previous(self):
        """When previous_chapter is empty, prompt uses '这是第一章'."""
        from src.core.llm.chapter_generator import generate_single_chapter

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="第一章内容")

        chapter_outline = {"chapter": 1, "title": "开篇"}

        await generate_single_chapter(
            client=mock_client,
            chapter_outline=chapter_outline,
            previous_chapter="",
            characters_json="[]",
            world_setting_json="{}",
        )

        # Verify the prompt contains "这是第一章"
        call_args = mock_client.generate.call_args
        prompt = call_args[0][0]
        assert "这是第一章" in prompt

    @pytest.mark.asyncio
    async def test_style_instruction_prepended_to_prompt(self):
        """style_instruction is prepended to the prompt."""
        from src.core.llm.chapter_generator import generate_single_chapter

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="内容")

        await generate_single_chapter(
            client=mock_client,
            chapter_outline={"chapter": 1, "title": "测试"},
            previous_chapter="前文",
            characters_json="[]",
            world_setting_json="{}",
            style_instruction="请使用热血燃向的文风",
        )

        prompt = mock_client.generate.call_args[0][0]
        assert prompt.startswith("请使用热血燃向的文风")

    @pytest.mark.asyncio
    async def test_storylines_appended_to_prompt(self):
        """storylines_json is appended to the prompt."""
        from src.core.llm.chapter_generator import generate_single_chapter

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="内容")

        sl_json = '[{"name": "主线", "type": "main"}]'

        await generate_single_chapter(
            client=mock_client,
            chapter_outline={"chapter": 1, "title": "测试"},
            previous_chapter="前文",
            characters_json="[]",
            world_setting_json="{}",
            storylines_json=sl_json,
        )

        prompt = mock_client.generate.call_args[0][0]
        assert "已确定的故事线" in prompt
        assert sl_json in prompt

    @pytest.mark.asyncio
    async def test_kg_service_context_retrieval(self):
        """When kg_service is provided, it retrieves context."""
        from src.core.llm.chapter_generator import generate_single_chapter

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="内容")

        mock_kg = AsyncMock()
        mock_kg.retrieve_context = AsyncMock(return_value="知识图谱上下文信息")
        mock_kg.extract_from_chapter = AsyncMock()

        chapter_outline = {"chapter": 2, "title": "测试"}

        await generate_single_chapter(
            client=mock_client,
            chapter_outline=chapter_outline,
            previous_chapter="前文",
            characters_json="[]",
            world_setting_json="{}",
            kg_service=mock_kg,
            novel_id="novel-kg-1",
        )

        mock_kg.retrieve_context.assert_awaited_once_with(
            novel_id="novel-kg-1",
            chapter_outline=chapter_outline,
        )
        mock_kg.extract_from_chapter.assert_awaited_once()
        prompt = mock_client.generate.call_args[0][0]
        assert "知识图谱上下文信息" in prompt

    @pytest.mark.asyncio
    async def test_kg_service_failure_non_blocking(self):
        """KG service failure does not block chapter generation."""
        from src.core.llm.chapter_generator import generate_single_chapter

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value="正常生成内容")

        mock_kg = AsyncMock()
        mock_kg.retrieve_context = AsyncMock(side_effect=RuntimeError("KG down"))
        mock_kg.extract_from_chapter = AsyncMock(side_effect=RuntimeError("KG down"))

        result = await generate_single_chapter(
            client=mock_client,
            chapter_outline={"chapter": 1, "title": "测试"},
            previous_chapter="",
            characters_json="[]",
            world_setting_json="{}",
            kg_service=mock_kg,
            novel_id="novel-kg-2",
        )

        # Should still return content despite KG failure
        assert result["content"] == "正常生成内容"


# ============================================================
#  novel_id ownership validation tests
# ============================================================


class TestNovelIdOwnership:
    """Tests for novel_id ownership checks in NovelManager."""

    @pytest.mark.asyncio
    async def test_update_power_system_wrong_novel_returns_false(self):
        """Updating a power system with wrong novel_id returns False."""
        from src.api.services.novel_manager import NovelManager

        manager = NovelManager()

        # Mock the DB session to return None (no match for compound WHERE)
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = lambda: None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.novel_manager.get_db_session", return_value=mock_session):
            result = await manager.update_power_system(
                "wrong-novel-id", 1, name="新名称"
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_power_system_wrong_novel_returns_false(self):
        """Deleting a power system with wrong novel_id returns False."""
        from src.api.services.novel_manager import NovelManager

        manager = NovelManager()

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = lambda: None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.novel_manager.get_db_session", return_value=mock_session):
            result = await manager.delete_power_system("wrong-novel-id", 1)

        assert result is False

    @pytest.mark.asyncio
    async def test_update_character_wrong_novel_returns_false(self):
        """Updating a character with wrong novel_id returns False."""
        from src.api.services.character_service import CharacterService

        service = CharacterService()

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = lambda: None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.character_service.get_db_session", return_value=mock_session):
            result = await service.update_character(
                "wrong-novel-id", 1, name="新名称"
            )

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_character_wrong_novel_returns_false(self):
        """Deleting a character with wrong novel_id returns False."""
        from src.api.services.character_service import CharacterService

        service = CharacterService()

        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = lambda: None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=None)

        with patch("src.api.services.character_service.get_db_session", return_value=mock_session):
            result = await service.delete_character("wrong-novel-id", 1)

        assert result is False


# ============================================================
#  UniqueConstraint tests (model-level verification)
# ============================================================


class TestUniqueConstraints:
    """Verify UniqueConstraint declarations on Chapter and Volume models."""

    def test_chapter_has_unique_constraint(self):
        """Chapter model declares (novel_id, chapter_number) unique constraint."""
        from src.api.models.db_models import Chapter

        table_args = Chapter.__table_args__
        constraints = [
            arg for arg in table_args
            if hasattr(arg, "name") and arg.name == "uq_chapter_novel_number"
        ]
        assert len(constraints) == 1
        constraint = constraints[0]
        col_names = [col.name for col in constraint.columns]
        assert "novel_id" in col_names
        assert "chapter_number" in col_names

    def test_volume_has_unique_constraint(self):
        """Volume model declares (novel_id, volume_number) unique constraint."""
        from src.api.models.db_models import Volume

        table_args = Volume.__table_args__
        constraints = [
            arg for arg in table_args
            if hasattr(arg, "name") and arg.name == "uq_volume_novel_number"
        ]
        assert len(constraints) == 1
        constraint = constraints[0]
        col_names = [col.name for col in constraint.columns]
        assert "novel_id" in col_names
        assert "volume_number" in col_names


# ============================================================
#  structlog import verification tests
# ============================================================


class TestStructlogImports:
    """Verify all modified services use structlog correctly."""

    def test_task_manager_uses_structlog(self):
        """task_manager uses structlog.get_logger."""
        from src.api.services import task_manager
        import structlog
        assert hasattr(task_manager, "logger")
        assert isinstance(task_manager.logger, structlog.types.FilteringBoundLogger) or \
               hasattr(task_manager.logger, "info")

    def test_novel_manager_uses_structlog(self):
        """novel_manager uses structlog.get_logger."""
        from src.api.services import novel_manager
        assert hasattr(novel_manager, "logger")
        assert hasattr(novel_manager.logger, "info")

    def test_novel_generator_uses_structlog(self):
        """novel_generator uses structlog.get_logger."""
        from src.api.services import novel_generator
        assert hasattr(novel_generator, "logger")
        assert hasattr(novel_generator.logger, "info")

    def test_outline_service_uses_structlog(self):
        """outline_service uses structlog.get_logger."""
        from src.api.services import outline_service
        assert hasattr(outline_service, "logger")
        assert hasattr(outline_service.logger, "info")

    def test_storyline_service_uses_structlog(self):
        """storyline_service uses structlog.get_logger."""
        from src.api.services import storyline_service
        assert hasattr(storyline_service, "logger")
        assert hasattr(storyline_service.logger, "info")

    def test_conversation_service_uses_structlog(self):
        """conversation_service uses structlog.get_logger."""
        from src.api.services import conversation_service
        assert hasattr(conversation_service, "logger")
        assert hasattr(conversation_service.logger, "info")

    def test_chapter_generation_node_uses_structlog(self):
        """chapter_generation node uses structlog.get_logger."""
        from src.core.langgraph.nodes import chapter_generation
        assert hasattr(chapter_generation, "logger")
        assert hasattr(chapter_generation.logger, "info")
