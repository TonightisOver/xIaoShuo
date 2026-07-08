"""Unit tests for CHANGE-035: Story Bible, Three-Layer Graph, and Chapter Planning Check."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.models.db_models import StoryBible
from src.api.routes.story_bible import get_story_bible, update_story_bible
from src.api.services.knowledge_graph_service import KnowledgeGraphService
from src.core.llm.chapter_generator import generate_single_chapter

# ---------------------------------------------------------------------------
# Test Component 1: Story Bible Database Model & CRUD Endpoints
# ---------------------------------------------------------------------------

class TestStoryBibleAPI:
    """Tests for the Story Bible endpoints and model."""

    @pytest.mark.asyncio
    async def test_get_story_bible_auto_initialization(self):
        """When a Story Bible does not exist, GET should auto-initialize and return an empty bible."""
        novel_id = "test-novel-035"
        mock_session = AsyncMock()

        # Mock Novel query result (first call)
        from src.api.models.db_models import Novel
        mock_novel = Novel(novel_id=novel_id, title="测试小说")
        mock_novel_result = MagicMock()
        mock_novel_result.scalar_one_or_none.return_value = mock_novel

        # Mock StoryBible query result (second call)
        mock_bible_result = MagicMock()
        mock_bible_result.scalar_one_or_none.return_value = None  # Bible doesn't exist yet

        mock_session.execute = AsyncMock(side_effect=[mock_novel_result, mock_bible_result])
        mock_session.add = MagicMock()
        mock_session.flush = AsyncMock()

        with patch("src.api.routes.story_bible.get_db_session") as mock_db:
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await get_story_bible(novel_id=novel_id)

            # Check that it returned an auto-initialized StoryBible
            assert result.novel_id == novel_id
            assert result.worldview_rules == ""
            assert result.character_cards == []
            assert result.faction_relations == ""
            assert result.hard_settings == ""

            # Check that DB session added the newly created bible record
            assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_update_story_bible_success(self):
        """PUT /story-bible should correctly update provided fields."""
        novel_id = "test-novel-035"
        existing_bible = StoryBible(
            novel_id=novel_id,
            worldview_rules="旧世界观设定",
            character_cards=[],
            faction_relations="旧势力关系",
            location_settings="旧地点",
            prop_settings="旧道具",
            foreshadowing_list=[],
            hard_settings="旧硬设定"
        )

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_bible
        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.add = MagicMock()

        # Update body
        from pydantic import BaseModel
        class StoryBibleUpdateMock(BaseModel):
            worldview_rules: str | None = None
            character_cards: list | None = None
            faction_relations: str | None = None
            location_settings: str | None = None
            prop_settings: str | None = None
            foreshadowing_list: list | None = None
            hard_settings: str | None = None

        update_body = StoryBibleUpdateMock(
            worldview_rules="新世界观规则",
            hard_settings="禁止吃西红柿",
            character_cards=[{"name": "主角小帅", "role": "主角"}]
        )

        with patch("src.api.routes.story_bible.get_db_session") as mock_db:
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            result = await update_story_bible(novel_id=novel_id, body=update_body)

            assert result.worldview_rules == "新世界观规则"
            assert result.hard_settings == "禁止吃西红柿"
            assert len(result.character_cards) == 1
            assert result.character_cards[0]["name"] == "主角小帅"
            assert result.faction_relations == "旧势力关系"  # Unchanged

            assert mock_session.add.called


# ---------------------------------------------------------------------------
# Test Component 2: Three-Layer Knowledge Graph Parsing
# ---------------------------------------------------------------------------

class TestThreeLayerGraph:
    """Tests for Three-Layer Graph segmentation and clustering in KnowledgeGraphService."""

    @pytest.mark.asyncio
    async def test_get_three_layer_graph_clustering(self):
        """Should segment entities and triples into Character, Plot, and Foreshadowing graphs."""
        novel_id = "test-novel-035"

        # Mock Entities
        e1 = MagicMock()
        e1.id = "char-1"
        e1.entity_type = "character"
        e1.name = "林动"
        e1.attributes = {"status": "alive"}
        e1.first_chapter = 1
        e1.last_chapter = 5

        e2 = MagicMock()
        e2.id = "char-2"
        e2.entity_type = "character"
        e2.name = "绫清竹"
        e2.attributes = {"status": "alive"}
        e2.first_chapter = 2
        e2.last_chapter = 5

        e3 = MagicMock()
        e3.id = "event-1"
        e3.entity_type = "event"
        e3.name = "大炎王朝宗族大会"
        e3.attributes = {"description": "林动在大会上战胜林琅天"}
        e3.first_chapter = 3
        e3.last_chapter = 4

        e4 = MagicMock()
        e4.id = "foreshadowing-1"
        e4.entity_type = "foreshadowing"
        e4.name = "祖符的秘密"
        e4.attributes = {"foreshadowing_status": "planted", "description": "神秘石符的真正来历"}
        e4.first_chapter = 1
        e4.last_chapter = 1

        # Mock Triples
        t1 = MagicMock()
        t1.id = "triple-1"
        t1.subject_id = "char-1"
        t1.predicate = "倾慕"
        t1.object_id = "char-2"
        t1.chapter_number = 2
        t1.confidence = 0.95
        t1.status = "active"

        t2 = MagicMock()
        t2.id = "triple-2"
        t2.subject_id = "char-1"
        t2.predicate = "持有"
        t2.object_id = "foreshadowing-1"
        t2.chapter_number = 1
        t2.confidence = 0.99
        t2.status = "active"

        mock_session = AsyncMock()
        mock_result_ent = MagicMock()
        mock_result_ent.scalars.return_value.all.return_value = [e1, e2, e3, e4]
        mock_result_trip = MagicMock()
        mock_result_trip.scalars.return_value.all.return_value = [t1, t2]

        # First query: entities, Second query: triples
        mock_session.execute = AsyncMock(side_effect=[mock_result_ent, mock_result_trip])

        with patch("src.api.services.knowledge_graph_service.get_db_session") as mock_db:
            mock_db.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_db.return_value.__aexit__ = AsyncMock(return_value=False)

            service = KnowledgeGraphService()
            graph = await service.get_three_layer_graph(novel_id)

            # 1. Verify Character Graph
            char_g = graph["character_graph"]
            assert len(char_g["nodes"]) == 2
            assert any(node["name"] == "林动" for node in char_g["nodes"])
            assert any(node["name"] == "绫清竹" for node in char_g["nodes"])
            assert len(char_g["edges"]) == 1
            assert char_g["edges"][0]["predicate"] == "倾慕"

            # 2. Verify Plot/Event Graph (should sort and inject time flow edge)
            plot_g = graph["plot_graph"]
            assert len(plot_g["nodes"]) == 1
            assert plot_g["nodes"][0]["name"] == "大炎王朝宗族大会"
            # Since there is only 1 event, there are no narrative timeline flow edges
            assert len(plot_g["edges"]) == 0

            # 3. Verify Foreshadowing Graph (should include associated character node to prevent isolation)
            fore_g = graph["foreshadowing_graph"]
            assert len(fore_g["nodes"]) >= 1
            assert any(node["name"] == "祖符的秘密" for node in fore_g["nodes"])
            # Since char-1 (林动) is linked via t2, it should be pulled in as extra node
            assert any(node["name"] == "林动" for node in fore_g["nodes"])
            assert len(fore_g["edges"]) == 1
            assert fore_g["edges"][0]["predicate"] == "持有"


# ---------------------------------------------------------------------------
# Test Component 3: Chapter Planning Pre-Check Node Cascade Generation
# ---------------------------------------------------------------------------

class TestChapterPlanningCheckCascade:
    """Tests for the dual-cascade chapter generation + planning precheck process."""

    @pytest.mark.asyncio
    async def test_generate_single_chapter_with_planning(self):
        """Should execute dual-stage generation: 1st stage for plan, 2nd stage for content."""
        client = AsyncMock()
        # First return: Mock Planning Check document, Second return: Mock Chapter text
        mock_plan = """# 章节规划单
1. **本章目标**：林动获得大荒囚天指
2. **本章冲突**：大荒碑守护兽林琅天阻挠
3. **本章出场人物**：林动，林琅天
4. **必须遵循的旧设定**：林动有神秘石符，林琅天是宗族天骄
5. **本章种下的新伏笔**：大荒碑底部的神秘魔眼
6. **本章回收的历史伏笔**：无
7. **本章结尾钩子**：魔眼突然睁开！
"""
        mock_chapter_text = """第十章 大荒碑前！
林动深吸一口气，神秘石符在手心微微发烫。而在对面，林琅天一袭白衣，神色傲然……
"""
        client.generate = AsyncMock(side_effect=[mock_plan, mock_chapter_text])

        chapter_outline = {"chapter": 10, "title": "大荒碑前", "plot": "林动参悟武学"}
        previous_chapter = "林动来到大荒古原"
        characters_json = "[]"
        world_setting_json = "{}"

        # Story bible context is now passed as a parameter (caller responsibility)
        story_bible_context = (
            "## 世界观规则:\n天玄大陆，百家争鸣\n\n"
            "## 禁止违背的硬设定:\n不能使用热武器"
        )

        # Mock kg retrieve_context
        kg_mock = AsyncMock()
        kg_mock.retrieve_context = AsyncMock(return_value="【图谱记忆】林动与林琅天有仇怨")
        kg_mock.extract_from_chapter = AsyncMock()

        # Mock KG_SUBAGENT_ENABLED=False to prevent MemoryCurator from
        # replacing story_bible_context with a curator-generated memo
        with patch("src.core.config.get_settings") as mock_settings:
            mock_settings.return_value = MagicMock(KG_SUBAGENT_ENABLED=False, SPEC="Settings")
            result = await generate_single_chapter(
            client=client,
            chapter_outline=chapter_outline,
            previous_chapter=previous_chapter,
            characters_json=characters_json,
            world_setting_json=world_setting_json,
            kg_service=kg_mock,
            novel_id="novel-plan-test",
            story_bible_context=story_bible_context,
        )

        # 1. Verify two LLM calls were made
        assert client.generate.call_count == 2

        # 2. Check the first call (planning prompt) variables
        first_call_prompt = client.generate.call_args_list[0][0][0]
        assert "章节规划单" in first_call_prompt or "规划任务" in first_call_prompt
        assert "天玄大陆，百家争鸣" in first_call_prompt  # Bible context passed in
        assert "【图谱记忆】" in first_call_prompt         # KG context retrieved

        # 3. Check the second call (chapter generation prompt) variables
        second_call_prompt = client.generate.call_args_list[1][0][0]
        assert "章节生成依据规划单与约束" in second_call_prompt
        assert "林动获得大荒囚天指" in second_call_prompt  # Plan injected!
        assert "神秘魔眼" in second_call_prompt            # Plan injected!

        # 4. Verify result formatting
        assert result["chapter"] == 10
        assert result["title"] == "大荒碑前"
        assert result["content"] == mock_chapter_text
        assert result["word_count"] > 0

        # 5. 知识抽取已移至 quality_check 节点，本章节生成不负责抽取
        assert kg_mock.retrieve_context.called
