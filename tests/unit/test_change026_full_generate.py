"""Unit tests for CHANGE-026: full novel generation new functions.

Tests cover:
- generate_power_systems_ai (StorylineService)
- persist_outlines_from_result (OutlineService)
- generate_auto_conversation (ConversationService)
- _run_sub_feature (novel_generator)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.progress_event_bus import EventType

# ============================================================
#  generate_power_systems_ai  tests
# ============================================================

class TestGeneratePowerSystemsAI:
    """Tests for AIGenerationService.generate_power_systems_ai()."""

    @pytest.mark.asyncio
    async def test_generates_power_systems_from_world_setting(self):
        """Happy path: world setting + novel info produce 1-3 power systems."""
        from src.api.services.ai_generation_service import AIGenerationService

        service = AIGenerationService()

        novel_data = {
            "id": 1, "novel_id": "novel-test-1", "title": "测试",
            "idea": "修仙世界", "novel_type": "玄幻", "target_words": 100000,
            "writing_style": "现代白话", "status": "draft",
        }
        world_data = {
            "background": "上古修仙世界",
            "rules": "灵力运转规则",
            "culture": "宗门体系",
            "geography": "九州大陆",
        }

        llm_response = [
            {"name": "修仙境界", "description": "从凡人到仙尊",
             "levels": [{"name": "炼气", "description": "引气入体", "breakthrough": "感知灵力"}]},
            {"name": "炼器体系", "description": "锻造法器",
             "levels": [{"name": "入门", "description": "基础锻造", "breakthrough": "掌握火候"}]},
        ]

        created_ps = []

        async def mock_create_ps(novel_id, name, description, levels):
            ps_id = len(created_ps) + 1
            created_ps.append({"id": ps_id, "name": name,
                               "description": description, "levels": levels})
            return ps_id

        with patch("src.api.services.world_service.get_world_service") as mock_ws, \
             patch("src.api.services.novel_manager.get_novel_manager") as mock_mgr, \
             patch("src.core.llm.client.get_llm_client") as mock_llm, \
             patch("src.core.llm.helpers.safe_json_parse", return_value=llm_response):

            mock_llm_client = AsyncMock()
            mock_llm_client.generate = AsyncMock(return_value="[{...}]")
            mock_llm.return_value = mock_llm_client

            mock_manager = AsyncMock()
            mock_manager.get_novel = AsyncMock(return_value=novel_data)
            mock_mgr.return_value = mock_manager

            mock_ws_instance = AsyncMock()
            mock_ws_instance.get_world_setting = AsyncMock(return_value=world_data)
            mock_ws_instance.create_power_system = AsyncMock(side_effect=mock_create_ps)
            mock_ws.return_value = mock_ws_instance

            result = await service.generate_power_systems_ai("novel-test-1")

        assert len(result) == 2
        assert result[0]["name"] == "修仙境界"
        assert result[1]["name"] == "炼器体系"
        assert result[0]["id"] == 1
        assert result[1]["id"] == 2

    @pytest.mark.asyncio
    async def test_generates_power_systems_with_empty_world(self):
        """When world_setting is None/empty, still generates with novel info only."""
        from src.api.services.ai_generation_service import AIGenerationService

        service = AIGenerationService()

        novel_data = {
            "id": 1, "novel_id": "novel-test-2", "title": "测试2",
            "idea": "科幻世界", "novel_type": "科幻", "target_words": 80000,
            "writing_style": "现代白话", "status": "draft",
        }

        llm_response = [
            {"name": "科技等级", "description": "从行星到星系文明",
             "levels": [{"name": "L1", "description": "行星文明", "breakthrough": "核聚变"}]},
        ]

        created_ps = []

        async def mock_create_ps(novel_id, name, description, levels):
            created_ps.append({"name": name, "description": description})
            return 1

        with patch("src.api.services.novel_manager.get_novel_manager") as mock_mgr, \
             patch("src.api.services.world_service.get_world_service") as mock_ws, \
             patch("src.core.llm.client.get_llm_client") as mock_llm, \
             patch("src.core.llm.helpers.safe_json_parse", return_value=llm_response):

            mock_llm_client = AsyncMock()
            mock_llm_client.generate = AsyncMock(return_value="[{...}]")
            mock_llm.return_value = mock_llm_client

            mock_manager = AsyncMock()
            mock_manager.get_novel = AsyncMock(return_value=novel_data)
            mock_mgr.return_value = mock_manager

            mock_ws_instance = AsyncMock()
            mock_ws_instance.get_world_setting = AsyncMock(return_value=None)
            mock_ws_instance.create_power_system = AsyncMock(return_value=1)
            mock_ws.return_value = mock_ws_instance

            result = await service.generate_power_systems_ai("novel-test-2")

        assert len(result) == 1
        assert result[0]["name"] == "科技等级"

    @pytest.mark.asyncio
    async def test_raises_when_novel_not_found(self):
        """Raises ValueError when novel does not exist."""
        from src.api.services.ai_generation_service import AIGenerationService

        service = AIGenerationService()

        with patch("src.api.services.novel_manager.get_novel_manager") as mock_mgr:
            mock_manager = AsyncMock()
            mock_manager.get_novel = AsyncMock(return_value=None)
            mock_mgr.return_value = mock_manager

            with pytest.raises(ValueError, match="小说不存在"):
                await service.generate_power_systems_ai("nonexistent")

    @pytest.mark.asyncio
    async def test_handles_llm_returning_invalid_json(self):
        """Falls back to empty list when LLM returns unparseable content."""
        from src.api.services.ai_generation_service import AIGenerationService

        service = AIGenerationService()

        novel_data = {
            "id": 1, "novel_id": "novel-test-3", "title": "测试3",
            "idea": "测试", "novel_type": "玄幻", "target_words": 100000,
            "writing_style": "现代白话", "status": "draft",
        }

        with patch("src.api.services.novel_manager.get_novel_manager") as mock_mgr, \
             patch("src.core.llm.client.get_llm_client") as mock_llm, \
             patch("src.core.llm.helpers.safe_json_parse", return_value=[]) as mock_parse:

            mock_llm_client = AsyncMock()
            mock_llm_client.generate = AsyncMock(return_value="garbage text")
            mock_llm.return_value = mock_llm_client

            mock_manager = AsyncMock()
            mock_manager.get_novel = AsyncMock(return_value=novel_data)
            mock_manager.get_world_setting = AsyncMock(return_value={})
            mock_mgr.return_value = mock_manager

            result = await service.generate_power_systems_ai("novel-test-3")

        assert result == []
        mock_parse.assert_called_once()

    @pytest.mark.asyncio
    async def test_handles_llm_returning_singular_dict(self):
        """Falls back to empty list when LLM returns a dict instead of list."""
        from src.api.services.ai_generation_service import AIGenerationService

        service = AIGenerationService()

        novel_data = {
            "id": 1, "novel_id": "novel-test-3b", "title": "测试3b",
            "idea": "测试", "novel_type": "玄幻", "target_words": 100000,
            "writing_style": "现代白话", "status": "draft",
        }

        with patch("src.api.services.novel_manager.get_novel_manager") as mock_mgr, \
             patch("src.core.llm.client.get_llm_client") as mock_llm, \
             patch("src.core.llm.helpers.safe_json_parse", return_value={"name": "单一体系"}):

            mock_llm_client = AsyncMock()
            mock_llm_client.generate = AsyncMock(return_value="{\"name\": \"单一体系\"}")
            mock_llm.return_value = mock_llm_client

            mock_manager = AsyncMock()
            mock_manager.get_novel = AsyncMock(return_value=novel_data)
            mock_manager.get_world_setting = AsyncMock(return_value={})
            mock_mgr.return_value = mock_manager

            result = await service.generate_power_systems_ai("novel-test-3b")

        assert result == []

    @pytest.mark.asyncio
    async def test_skips_items_without_name(self):
        """Items in the LLM response without a 'name' field are skipped."""
        from src.api.services.ai_generation_service import AIGenerationService

        service = AIGenerationService()

        novel_data = {
            "id": 1, "novel_id": "novel-test-4", "title": "测试4",
            "idea": "测试", "novel_type": "玄幻", "target_words": 100000,
            "writing_style": "现代白话", "status": "draft",
        }

        llm_response = [
            {"name": "体系A", "description": "有效", "levels": []},
            {"description": "无名称，应跳过", "levels": []},
            {"name": "体系B", "description": "有效", "levels": []},
        ]

        created_ps = []

        async def mock_create_ps(novel_id, name, description, levels):
            created_ps.append({"name": name})
            return len(created_ps)

        with patch("src.api.services.novel_manager.get_novel_manager") as mock_mgr, \
             patch("src.api.services.world_service.get_world_service") as mock_ws, \
             patch("src.core.llm.client.get_llm_client") as mock_llm, \
             patch("src.core.llm.helpers.safe_json_parse", return_value=llm_response):

            mock_llm_client = AsyncMock()
            mock_llm_client.generate = AsyncMock(return_value="[{...}]")
            mock_llm.return_value = mock_llm_client

            mock_manager = AsyncMock()
            mock_manager.get_novel = AsyncMock(return_value=novel_data)
            mock_mgr.return_value = mock_manager

            mock_ws_instance = AsyncMock()
            mock_ws_instance.get_world_setting = AsyncMock(return_value={})
            mock_ws_instance.create_power_system = AsyncMock(side_effect=mock_create_ps)
            mock_ws.return_value = mock_ws_instance

            result = await service.generate_power_systems_ai("novel-test-4")

        assert len(result) == 2
        names = [r["name"] for r in result]
        assert "体系A" in names
        assert "体系B" in names


# ============================================================
#  persist_outlines_from_result  tests
# ============================================================

class TestPersistOutlinesFromResult:
    """Tests for OutlineService.persist_outlines_from_result()."""

    @pytest.mark.asyncio
    async def test_persists_master_volumes_and_chapters(self):
        """Full result with master_outline, volumes with chapters."""
        from src.api.services.outline_service import OutlineService

        service = OutlineService()

        result = {
            "master_outline": {
                "premise": "核心前提测试",
                "main_conflict": "主要冲突",
                "plot_arcs": [],
                "ending": "结局",
                "themes": ["成长"],
            },
            "volumes": [
                {
                    "volume_number": 1,
                    "title": "第一卷",
                    "summary": "开篇",
                    "chapters": [
                        {"chapter": 1, "title": "第一章", "plot": "开场"},
                        {"chapter": 2, "title": "第二章", "plot": "发展"},
                    ],
                },
                {
                    "volume_number": 2,
                    "title": "第二卷",
                    "summary": "中篇",
                    "chapters": [
                        {"chapter": 3, "title": "第三章", "plot": "转折"},
                    ],
                },
            ],
            "chapter_outlines": [
                {"chapter": 10, "title": "独立章节", "plot": "独立情节"},
            ],
        }

        upsert_master_calls = []
        upsert_volume_calls = []
        upsert_chapter_calls = []

        async def mock_upsert_master(novel_id, content):
            upsert_master_calls.append((novel_id, content))

        async def mock_upsert_volume(novel_id, vol_num, content):
            upsert_volume_calls.append((novel_id, vol_num, content))

        async def mock_upsert_chapter(novel_id, vol_num, ch_num, content):
            upsert_chapter_calls.append((novel_id, vol_num, ch_num, content))

        with patch.object(service, "upsert_master_outline", side_effect=mock_upsert_master), \
             patch.object(service, "upsert_volume_outline", side_effect=mock_upsert_volume), \
             patch.object(service, "upsert_chapter_outline", side_effect=mock_upsert_chapter):

            persisted = await service.persist_outlines_from_result("novel-a", result)

        assert persisted["master"] is True
        assert persisted["volumes"] == 2
        assert persisted["chapters"] == 4  # 2 (vol1) + 1 (vol2) + 1 (standalone)

        # Verify master
        assert len(upsert_master_calls) == 1
        assert upsert_master_calls[0][0] == "novel-a"
        assert upsert_master_calls[0][1]["premise"] == "核心前提测试"

        # Verify volumes
        assert len(upsert_volume_calls) == 2
        assert upsert_volume_calls[0][1] == 1
        assert upsert_volume_calls[1][1] == 2

        # Verify chapters
        assert len(upsert_chapter_calls) == 4  # 2+1+1(standalone)
        ch_nums = sorted(c[2] for c in upsert_chapter_calls)
        assert ch_nums == [1, 2, 3, 10]

    @pytest.mark.asyncio
    async def test_persists_standalone_chapters_only(self):
        """Result with only chapter_outlines (no volumes)."""
        from src.api.services.outline_service import OutlineService

        service = OutlineService()

        result = {
            "chapter_outlines": [
                {"chapter": 1, "title": "第一章", "plot": "开场"},
                {"chapter": 2, "title": "第二章", "plot": "发展"},
            ],
        }

        upsert_chapter_calls = []

        async def mock_upsert_chapter(novel_id, vol_num, ch_num, content):
            upsert_chapter_calls.append((novel_id, vol_num, ch_num, content))

        with patch.object(service, "upsert_master_outline", new_callable=AsyncMock), \
             patch.object(service, "upsert_volume_outline", new_callable=AsyncMock), \
             patch.object(service, "upsert_chapter_outline", side_effect=mock_upsert_chapter):

            persisted = await service.persist_outlines_from_result("novel-b", result)

        assert persisted["master"] is False
        assert persisted["volumes"] == 0
        assert persisted["chapters"] == 2
        # Standalone chapters use volume_number=0
        for call in upsert_chapter_calls:
            assert call[1] == 0  # volume_number

    @pytest.mark.asyncio
    async def test_persists_empty_result_gracefully(self):
        """Empty result dict produces zero counts, no errors."""
        from src.api.services.outline_service import OutlineService

        service = OutlineService()

        persisted = await service.persist_outlines_from_result("novel-c", {})

        assert persisted == {"master": False, "volumes": 0, "chapters": 0}

    @pytest.mark.asyncio
    async def test_persists_volumes_without_chapters(self):
        """Volumes with no nested chapters key are handled."""
        from src.api.services.outline_service import OutlineService

        service = OutlineService()

        result = {
            "volumes": [
                {"volume_number": 1, "title": "第一卷", "summary": "开篇"},
                {"volume_number": 2, "title": "第二卷", "summary": "中篇"},
            ],
        }

        upsert_volume_calls = []

        async def mock_upsert_volume(novel_id, vol_num, content):
            upsert_volume_calls.append((novel_id, vol_num, content))

        with patch.object(service, "upsert_master_outline", new_callable=AsyncMock), \
             patch.object(service, "upsert_volume_outline", side_effect=mock_upsert_volume), \
             patch.object(service, "upsert_chapter_outline", new_callable=AsyncMock):

            persisted = await service.persist_outlines_from_result("novel-d", result)

        assert persisted["volumes"] == 2
        assert persisted["chapters"] == 0
        assert len(upsert_volume_calls) == 2

    @pytest.mark.asyncio
    async def test_plot_arcs_fallback_not_dict(self):
        """When master_outline is missing and plot_arcs is a list (not dict),
        the master outline should still be created via the else branch."""
        from src.api.services.outline_service import OutlineService

        service = OutlineService()

        result = {
            "plot_arcs": [{"name": "主线", "description": "主要情节"}],
        }

        upsert_master_calls = []

        async def mock_upsert_master(novel_id, content):
            upsert_master_calls.append((novel_id, content))

        with patch.object(service, "upsert_master_outline", side_effect=mock_upsert_master), \
             patch.object(service, "upsert_volume_outline", new_callable=AsyncMock), \
             patch.object(service, "upsert_chapter_outline", new_callable=AsyncMock):

            persisted = await service.persist_outlines_from_result("novel-e", result)

        # plot_arcs (list) is truthy so master creation is attempted
        # But isinstance(master_data, dict) check should be False for a list
        # so it goes to the else branch creating a dict with premise=str(list)
        assert persisted["master"] is True
        assert len(upsert_master_calls) == 1
        # The stored content should contain a 'premise' key
        assert "premise" in upsert_master_calls[0][1]

    @pytest.mark.asyncio
    async def test_skips_non_dict_chapters_in_volumes(self):
        """Chapters that are not dicts are skipped."""
        from src.api.services.outline_service import OutlineService

        service = OutlineService()

        result = {
            "volumes": [
                {
                    "volume_number": 1,
                    "title": "第一卷",
                    "chapters": [
                        {"chapter": 1, "title": "有效"},
                        "not a dict",
                        123,
                        None,
                        {"chapter": 2, "title": "也有效"},
                    ],
                },
            ],
        }

        upsert_chapter_calls = []

        async def mock_upsert_chapter(novel_id, vol_num, ch_num, content):
            upsert_chapter_calls.append(ch_num)

        with patch.object(service, "upsert_master_outline", new_callable=AsyncMock), \
             patch.object(service, "upsert_volume_outline", new_callable=AsyncMock), \
             patch.object(service, "upsert_chapter_outline", side_effect=mock_upsert_chapter):

            persisted = await service.persist_outlines_from_result("novel-f", result)

        assert persisted["chapters"] == 2
        assert upsert_chapter_calls == [1, 2]


# ============================================================
#  generate_auto_conversation  tests
# ============================================================

class TestGenerateAutoConversation:
    """Tests for ConversationService.generate_auto_conversation()."""

    @pytest.mark.asyncio
    async def test_creates_conversation_with_ai_suggestion(self):
        """Happy path: creates conversation with user+assistant messages."""
        from src.api.services.conversation_service import ConversationService

        service = ConversationService()

        novel_data = {
            "id": 1, "novel_id": "novel-cc-1", "title": "星辰大海",
            "idea": "星际冒险故事", "novel_type": "科幻", "target_words": 100000,
            "writing_style": "现代白话", "status": "draft",
        }
        world_data = {
            "background": "银河帝国时代",
            "rules": "超光速航行",
            "culture": "多种族联邦",
            "geography": "银河系四象限",
        }
        characters = [
            {"id": 1, "name": "林峰", "role": "主角", "description": "年轻舰长"},
            {"id": 2, "name": "艾米", "role": "女主", "description": "外星公主"},
        ]

        messages_added = []

        async def mock_add_message(**kwargs):
            messages_added.append(kwargs)
            return len(messages_added)

        with patch("src.api.services.novel_manager.get_novel_manager") as mock_mgr, \
             patch("src.api.services.conversation_service.get_llm_client") as mock_llm, \
             patch.object(service, "create_conversation") as mock_create_conv:

            mock_llm_client = AsyncMock()
            mock_llm_client.generate = AsyncMock(
                return_value="当前设定较为完善。建议加强人物弧光设计，让主角经历更明显的成长转折。"
            )
            mock_llm.return_value = mock_llm_client

            mock_manager = AsyncMock()
            mock_manager.get_novel = AsyncMock(return_value=novel_data)
            mock_manager.get_world_setting = AsyncMock(return_value=world_data)
            mock_manager.list_characters = AsyncMock(return_value=characters)
            mock_mgr.return_value = mock_manager

            mock_create_conv.return_value = 42  # conv_id

            # Patch Message model and get_db_session to avoid real DB
            with patch("src.api.services.conversation_service.Message") as mock_msg_cls, \
                 patch("src.api.services.conversation_service.get_db_session") as mock_db_session:

                mock_msg_instance = MagicMock()
                mock_msg_cls.return_value = mock_msg_instance

                mock_session = AsyncMock()
                mock_session.__aenter__ = AsyncMock(return_value=mock_session)
                mock_session.__aexit__ = AsyncMock(return_value=None)
                mock_session.add = MagicMock()
                mock_session.flush = AsyncMock()
                mock_db_session.return_value = mock_session

                result = await service.generate_auto_conversation("novel-cc-1")

        assert result["conversation_id"] == 42
        assert result["topic"] == "小说设定完善 — 星辰大海"
        assert len(result["suggestion_preview"]) > 0

    @pytest.mark.asyncio
    async def test_raises_when_novel_not_found(self):
        """Raises ValueError when novel does not exist."""
        from src.api.services.conversation_service import ConversationService

        service = ConversationService()

        with patch("src.api.services.novel_manager.get_novel_manager") as mock_mgr:
            mock_manager = AsyncMock()
            mock_manager.get_novel = AsyncMock(return_value=None)
            mock_mgr.return_value = mock_manager

            with pytest.raises(ValueError, match="小说不存在"):
                await service.generate_auto_conversation("nonexistent")

    @pytest.mark.asyncio
    async def test_handles_minimal_settings(self):
        """Works with novel that has no world_setting or characters."""
        from src.api.services.conversation_service import ConversationService

        service = ConversationService()

        novel_data = {
            "id": 1, "novel_id": "novel-cc-3", "title": "简单故事",
            "idea": "一个简单故事", "novel_type": "都市", "target_words": 50000,
            "writing_style": "现代白话", "status": "draft",
        }

        with patch("src.api.services.novel_manager.get_novel_manager") as mock_mgr, \
             patch("src.api.services.conversation_service.get_llm_client") as mock_llm, \
             patch.object(service, "create_conversation") as mock_create_conv, \
             patch("src.api.services.conversation_service.Message") as mock_msg_cls, \
             patch("src.api.services.conversation_service.get_db_session") as mock_db_session:

            mock_llm_client = AsyncMock()
            mock_llm_client.generate = AsyncMock(return_value="设定较为简单，建议补充更多细节。")
            mock_llm.return_value = mock_llm_client

            mock_manager = AsyncMock()
            mock_manager.get_novel = AsyncMock(return_value=novel_data)
            mock_manager.get_world_setting = AsyncMock(return_value={})
            mock_manager.list_characters = AsyncMock(return_value=[])
            mock_mgr.return_value = mock_manager

            mock_create_conv.return_value = 10

            mock_msg_instance = MagicMock()
            mock_msg_cls.return_value = mock_msg_instance

            mock_session = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.add = MagicMock()
            mock_session.flush = AsyncMock()
            mock_db_session.return_value = mock_session

            result = await service.generate_auto_conversation("novel-cc-3")

        assert result["conversation_id"] == 10
        assert "suggestion_preview" in result


# ============================================================
#  _run_sub_feature  tests
# ============================================================

class TestRunSubFeature:
    """Tests for _run_sub_feature() in novel_generator module."""

    @pytest.mark.asyncio
    async def test_sub_feature_power_systems(self):
        """_run_sub_feature dispatches to generate_power_systems_ai correctly."""
        from src.api.models.requests import CreateNovelRequest
        from src.api.services.novel_generator import _run_sub_feature

        event_bus_events = []

        class FakeEventBus:
            async def publish(self, event):
                event_bus_events.append(event)

        class FakeTaskManager:
            async def update_status(self, task_id, status, progress=None):
                pass

        request = CreateNovelRequest(
            idea="一个修仙者穿越到现代都市的奇幻故事",
            novel_type="玄幻",
            target_words=100000,
            writing_style="现代白话",
        )

        with patch(
            "src.api.services.chapter_generation_utils.get_event_bus"
        ) as mock_bus, patch(
            "src.api.services.novel_generator.get_task_manager"
        ) as mock_tm, patch(
            "src.api.services.ai_generation_service.get_ai_generation_service"
        ) as mock_sl:

            mock_bus.return_value = FakeEventBus()
            mock_tm.return_value = FakeTaskManager()

            mock_sl_instance = AsyncMock()
            mock_sl_instance.generate_power_systems_ai = AsyncMock(
                return_value=[{"id": 1, "name": "修仙体系", "description": "desc", "levels": []}]
            )
            mock_sl.return_value = mock_sl_instance

            await _run_sub_feature(
                task_id="task-ps",
                novel_id="novel-ps",
                result={},
                request=request,
                feature_index=7,
                feature_name="power_systems",
                label="力量体系",
            )

        # Verify events (FakeEventBus stores progress_event objects)
        start_event = next(
            (e for e in event_bus_events if e.event_type == EventType.SUB_FEATURE_START), None
        )
        complete_event = next(
            (e for e in event_bus_events if e.event_type == EventType.SUB_FEATURE_COMPLETE), None
        )

        assert start_event is not None, f"Events captured: {event_bus_events}"
        assert start_event.data["feature"] == "power_systems"
        assert start_event.data["label"] == "力量体系"

        assert complete_event is not None, f"Events captured: {event_bus_events}"
        assert complete_event.data["feature"] == "power_systems"
        assert complete_event.data["count"] == 1

        mock_sl_instance.generate_power_systems_ai.assert_awaited_once_with("novel-ps")

    @pytest.mark.asyncio
    async def test_sub_feature_skips_when_novel_id_is_none(self):
        """When novel_id is None, sub-feature should be skipped (only events
        emitted, no service methods called)."""
        from src.api.models.requests import CreateNovelRequest
        from src.api.services.novel_generator import _run_sub_feature

        event_bus_events = []

        class FakeEventBus:
            async def publish(self, event):
                event_bus_events.append(event)

        class FakeTaskManager:
            async def update_status(self, task_id, status, progress=None):
                pass

        request = CreateNovelRequest(
            idea="一个修仙者穿越到现代都市的奇幻故事",
            novel_type="玄幻",
            target_words=100000,
            writing_style="现代白话",
        )

        with patch("src.api.services.chapter_generation_utils.get_event_bus") as mock_bus, \
             patch("src.api.services.novel_generator.get_task_manager") as mock_tm:

            mock_bus.return_value = FakeEventBus()
            mock_tm.return_value = FakeTaskManager()

            await _run_sub_feature(
                task_id="task-none",
                novel_id=None,
                result={},
                request=request,
                feature_index=8,
                feature_name="outline_persist",
                label="大纲持久化",
            )

        # Should emit start (since feature matches none of the
        # branches that need novel_id), then update_status
        from src.api.services.progress_event_bus import EventType
        start_exists = any(
            getattr(e, 'event_type', None) is EventType.SUB_FEATURE_START
            for e in event_bus_events
        )
        assert start_exists, f"Events captured: {event_bus_events}"

    @pytest.mark.asyncio
    async def test_sub_feature_handles_error_gracefully(self):
        """When a sub-feature throws, it should emit an ERROR event with
        non_blocking=True and NOT re-raise."""
        from src.api.models.requests import CreateNovelRequest
        from src.api.services.novel_generator import _run_sub_feature

        event_bus_events = []

        class FakeEventBus:
            async def publish(self, event):
                event_bus_events.append(event)

        class FakeTaskManager:
            async def update_status(self, task_id, status, progress=None):
                pass

        request = CreateNovelRequest(
            idea="一个修仙者穿越到现代都市的奇幻故事",
            novel_type="玄幻",
            target_words=100000,
            writing_style="现代白话",
        )

        with patch("src.api.services.chapter_generation_utils.get_event_bus") as mock_bus, \
             patch("src.api.services.novel_generator.get_task_manager") as mock_tm, \
             patch(
                "src.api.services.ai_generation_service.get_ai_generation_service"
             ) as mock_sl:

            mock_bus.return_value = FakeEventBus()
            mock_tm.return_value = FakeTaskManager()

            mock_sl_instance = AsyncMock()
            mock_sl_instance.generate_power_systems_ai = AsyncMock(
                side_effect=RuntimeError("LLM API timeout")
            )
            mock_sl.return_value = mock_sl_instance

            # Should NOT raise
            await _run_sub_feature(
                task_id="task-err",
                novel_id="novel-err",
                result={},
                request=request,
                feature_index=7,
                feature_name="power_systems",
                label="力量体系",
            )

        # Should have START, ERROR (non_blocking) events
        from src.api.services.progress_event_bus import EventType
        error_event = next(
            (e for e in event_bus_events if e.event_type is EventType.ERROR), None
        )
        assert error_event is not None, f"Events captured: {event_bus_events}"
        assert error_event.data["feature"] == "power_systems"
        assert error_event.data["non_blocking"] is True
        assert "LLM API timeout" in error_event.data["error"]

    @pytest.mark.asyncio
    async def test_sub_feature_percentage_calculation(self):
        """Verify percentage is calculated for each feature_index."""
        from src.api.services.novel_generator import _full_generate_percentage

        # 13 stages, 0-based index
        assert _full_generate_percentage(0) == 7    # 1/13 ~= 7%
        assert _full_generate_percentage(6) == 53   # 7/13 ~= 53%
        assert _full_generate_percentage(12) == 100  # 13/13 = 100%
        assert _full_generate_percentage(7) == 61   # 8/13 ~= 61%


# ============================================================
#  _full_generate_percentage  tests
# ============================================================

class TestFullGeneratePercentage:
    """Tests for percentage calculation helper."""

    def test_boundaries(self):
        from src.api.services.novel_generator import _full_generate_percentage

        # First stage = 1/13 * 100 = 7 (floor)
        assert _full_generate_percentage(0) == 7

        # Middle stage
        assert _full_generate_percentage(6) == 53  # 7/13 * 100

        # Last stage = 100
        assert _full_generate_percentage(12) == 100

    def test_monotonic(self):
        """Percentage should increase monotonically with index."""
        from src.api.services.novel_generator import _full_generate_percentage

        prev = -1
        for i in range(13):
            pct = _full_generate_percentage(i)
            assert pct >= prev, f"Not monotonic at index {i}"
            prev = pct
