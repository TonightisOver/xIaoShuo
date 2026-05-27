"""Unit tests for CHANGE-049: 项目优化解耦与冗余消除 — 新增公共模块测试。

覆盖模块:
- src/core/context/novel_context.py (NovelContextBuilder)
- src/core/quality/evaluator.py (evaluate_chapter_quality)
- src/core/llm/helpers.py (generate_and_parse_json)
- src/api/services/ai_generation_service.py (AIGenerationService)
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# 1. NovelContextBuilder Tests
# ---------------------------------------------------------------------------


class TestNovelContextBuilder:
    """Tests for NovelContextBuilder — 统一上下文构建器。"""

    @pytest.fixture
    def builder(self):
        from src.core.context.novel_context import NovelContextBuilder

        return NovelContextBuilder()

    @pytest.fixture
    def mock_session(self):
        """Create a mock AsyncSession with configurable query results."""
        session = AsyncMock()
        return session

    # --- build_generation_context ---

    @pytest.mark.asyncio
    async def test_build_generation_context_happy_path(self, builder, mock_session):
        """正常路径：novel + world + characters + storylines 全部存在。"""
        # Mock Novel
        mock_novel = MagicMock()
        mock_novel.writing_style = "热血燃向"
        mock_novel.writing_style_prompt = ""

        # Mock WorldSetting
        mock_ws = MagicMock()
        mock_ws.background = "修真世界"
        mock_ws.rules = "灵气为本"
        mock_ws.geography = "九州大陆"
        mock_ws.culture = "宗门文化"

        # Mock Characters
        mock_char = MagicMock()
        mock_char.name = "张三"
        mock_char.role = "主角"
        mock_char.personality = "沉稳"
        mock_char.description = "天才修士"

        # Mock Storylines
        mock_sl = MagicMock()
        mock_sl.name = "主线"
        mock_sl.type = "main"
        mock_sl.description = "修仙之路"

        # Configure session.execute to return different results per query
        call_count = {"n": 0}
        results_sequence = []

        # Novel result
        novel_result = MagicMock()
        novel_result.scalar_one_or_none.return_value = mock_novel
        results_sequence.append(novel_result)

        # WorldSetting result (for _build_world_str)
        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = mock_ws
        results_sequence.append(ws_result)

        # Characters result (for _build_chars_str)
        chars_result = MagicMock()
        chars_result.scalars.return_value.all.return_value = [mock_char]
        results_sequence.append(chars_result)

        # Storylines result
        sl_result = MagicMock()
        sl_result.scalars.return_value.all.return_value = [mock_sl]
        results_sequence.append(sl_result)

        async def execute_side_effect(*args, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return results_sequence[idx]

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        ctx = await builder.build_generation_context(mock_session, "novel-001")

        assert "修真世界" in ctx.world_str
        assert "张三" in ctx.chars_str
        assert "主线" in ctx.storylines_str
        assert ctx.style_instruction != ""

    @pytest.mark.asyncio
    async def test_build_generation_context_novel_not_found(
        self, builder, mock_session
    ):
        """novel 不存在时，返回默认值。"""
        # Novel not found
        novel_result = MagicMock()
        novel_result.scalar_one_or_none.return_value = None

        # WorldSetting not found
        ws_result = MagicMock()
        ws_result.scalar_one_or_none.return_value = None

        # No characters
        chars_result = MagicMock()
        chars_result.scalars.return_value.all.return_value = []

        # No storylines
        sl_result = MagicMock()
        sl_result.scalars.return_value.all.return_value = []

        call_count = {"n": 0}
        results_sequence = [novel_result, ws_result, chars_result, sl_result]

        async def execute_side_effect(*args, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return results_sequence[idx]

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        ctx = await builder.build_generation_context(mock_session, "nonexistent")

        assert ctx.world_str == "暂无世界观"
        assert ctx.chars_str == "暂无人物"
        assert ctx.storylines_str == ""
        assert ctx.style_instruction == ""

    # --- build_rewrite_context ---

    @pytest.mark.asyncio
    async def test_build_rewrite_context_happy_path(self, builder, mock_session):
        """改写上下文正常构建：novel + world + outline + chapters + chars + bible。"""
        mock_novel = MagicMock()
        mock_novel.writing_style = "热血"
        mock_novel.writing_style_prompt = "写得热血沸腾"

        mock_ws = MagicMock()
        mock_ws.background = "修真世界"
        mock_ws.geography = "九州"
        mock_ws.culture = "宗门"
        mock_ws.rules = "灵气法则"

        mock_outline = MagicMock()
        mock_outline.content = {"title": "第5章", "summary": "激战"}

        mock_prev_ch = MagicMock()
        mock_prev_ch.content = "前一章内容" * 50

        mock_next_ch = MagicMock()
        mock_next_ch.content = "后一章内容" * 50

        mock_char = MagicMock()
        mock_char.name = "李四"
        mock_char.role = "反派"
        mock_char.description = "阴险狡诈"

        mock_bible = MagicMock()
        mock_bible.worldview_rules = "灵气复苏"
        mock_bible.character_cards = [{"name": "李四", "trait": "阴险"}]
        mock_bible.faction_relations = "正邪对立"
        mock_bible.location_settings = "宗门山"
        mock_bible.prop_settings = "灵剑"
        mock_bible.foreshadowing_list = [{"hint": "暗线"}]
        mock_bible.hard_settings = "不可复活"

        call_count = {"n": 0}
        results_sequence = []

        # Novel
        r = MagicMock()
        r.scalar_one_or_none.return_value = mock_novel
        results_sequence.append(r)
        # WorldSetting
        r = MagicMock()
        r.scalar_one_or_none.return_value = mock_ws
        results_sequence.append(r)
        # Outline
        r = MagicMock()
        r.scalar_one_or_none.return_value = mock_outline
        results_sequence.append(r)
        # Prev chapter
        r = MagicMock()
        r.scalar_one_or_none.return_value = mock_prev_ch
        results_sequence.append(r)
        # Next chapter
        r = MagicMock()
        r.scalar_one_or_none.return_value = mock_next_ch
        results_sequence.append(r)
        # Characters
        r = MagicMock()
        r.scalars.return_value.all.return_value = [mock_char]
        results_sequence.append(r)
        # StoryBible
        r = MagicMock()
        r.scalar_one_or_none.return_value = mock_bible
        results_sequence.append(r)

        async def execute_side_effect(*args, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return results_sequence[idx]

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        ctx = await builder.build_rewrite_context(mock_session, "novel-001", 5)

        assert ctx.writing_style == "写得热血沸腾"
        assert "修真世界" in ctx.world_setting
        assert "第5章" in ctx.chapter_outline
        assert len(ctx.prev_chapter_summary) <= 300
        assert "李四" in ctx.characters
        assert "灵气复苏" in ctx.story_bible

    @pytest.mark.asyncio
    async def test_build_rewrite_context_chapter_not_found(
        self, builder, mock_session
    ):
        """chapter 不存在时，相关字段为空字符串。"""
        call_count = {"n": 0}
        results_sequence = []

        # Novel not found
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        results_sequence.append(r)
        # WorldSetting not found
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        results_sequence.append(r)
        # Outline not found
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        results_sequence.append(r)
        # Prev chapter not found
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        results_sequence.append(r)
        # Next chapter not found
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        results_sequence.append(r)
        # No characters
        r = MagicMock()
        r.scalars.return_value.all.return_value = []
        results_sequence.append(r)
        # No StoryBible
        r = MagicMock()
        r.scalar_one_or_none.return_value = None
        results_sequence.append(r)

        async def execute_side_effect(*args, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return results_sequence[idx]

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        ctx = await builder.build_rewrite_context(mock_session, "novel-001", 99)

        assert ctx.writing_style == ""
        assert ctx.chapter_outline == ""
        assert ctx.prev_chapter_summary == ""
        assert ctx.characters == ""
        assert ctx.story_bible == ""

    # --- build_blueprint_context ---

    @pytest.mark.asyncio
    async def test_build_blueprint_context_happy_path(self, builder, mock_session):
        """蓝图上下文正常构建。"""
        mock_prev_ch = MagicMock()
        mock_prev_ch.content = "前章内容很长" * 100

        mock_bible = MagicMock()
        mock_bible.worldview_rules = "灵气法则"
        mock_bible.hard_settings = "不可复活"
        mock_bible.character_cards = [{"name": "主角"}]
        mock_bible.foreshadowing_list = [{"hint": "伏笔A"}]

        mock_novel = MagicMock()
        mock_novel.is_long_form = False

        call_count = {"n": 0}
        results_sequence = []

        # Prev chapter
        r = MagicMock()
        r.scalar_one_or_none.return_value = mock_prev_ch
        results_sequence.append(r)
        # StoryBible
        r = MagicMock()
        r.scalar_one_or_none.return_value = mock_bible
        results_sequence.append(r)
        # Novel (for is_long_form check)
        r = MagicMock()
        r.scalar_one_or_none.return_value = mock_novel
        results_sequence.append(r)

        async def execute_side_effect(*args, **kwargs):
            idx = call_count["n"]
            call_count["n"] += 1
            return results_sequence[idx]

        mock_session.execute = AsyncMock(side_effect=execute_side_effect)

        ctx = await builder.build_blueprint_context(
            mock_session, "novel-001", 3, {"title": "第3章"}
        )

        assert len(ctx.previous_chapter) <= 500
        assert "灵气法则" in ctx.story_bible
        assert "不可复活" in ctx.story_bible


# ---------------------------------------------------------------------------
# 2. evaluate_chapter_quality Tests
# ---------------------------------------------------------------------------


class TestEvaluateChapterQuality:
    """Tests for evaluate_chapter_quality — 八维质量评估。"""

    @pytest.mark.asyncio
    async def test_evaluate_happy_path(self):
        """正常评估：LLM 返回合法 JSON，解析为 QualityResult。"""
        valid_response = """{
            "scores": {
                "advancement": 0.85,
                "conflict": 0.90,
                "character_consistency": 0.80,
                "world_consistency": 0.95,
                "foreshadowing": 0.75,
                "pacing": 0.80,
                "readability": 0.88,
                "trope_alignment": 0.82
            },
            "feedback": {
                "advancement": "主线推进流畅",
                "conflict": "冲突设计精彩"
            },
            "overall_score": 0.84,
            "suggestions": ["增加伏笔回收"]
        }"""

        with patch(
            "src.core.quality.evaluator.get_llm_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=valid_response)
            mock_get_client.return_value = mock_client

            from src.core.quality.evaluator import evaluate_chapter_quality

            result = await evaluate_chapter_quality(
                chapter_content="张三挥剑斩向妖兽，灵力涌动。",
                chapter_number=1,
                novel_type="玄幻",
                idea="修仙少年逆天改命",
            )

        assert result.overall == 0.84
        assert result.scores["advancement"] == 0.85
        assert result.scores["conflict"] == 0.90
        assert result.scores["world_consistency"] == 0.95
        assert "增加伏笔回收" in result.suggestions
        assert result.feedback.get("advancement") == "主线推进流畅"

    @pytest.mark.asyncio
    async def test_evaluate_malformed_json_fallback(self):
        """LLM 返回 malformed JSON 时，使用 default_score 降级。"""
        malformed = "这不是JSON，只是一段文字"

        with patch(
            "src.core.quality.evaluator.get_llm_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=malformed)
            mock_get_client.return_value = mock_client

            from src.core.quality.evaluator import evaluate_chapter_quality

            result = await evaluate_chapter_quality(
                chapter_content="内容",
                chapter_number=2,
                default_score=0.6,
            )

        # All dimensions should be default_score
        assert result.overall == 0.6
        for dim_score in result.scores.values():
            assert dim_score == 0.6
        assert result.suggestions == []

    @pytest.mark.asyncio
    async def test_evaluate_score_range_validation(self):
        """各评分维度的值应在 0.0-1.0 范围内（由 LLM 返回决定）。"""
        response_with_scores = """{
            "scores": {
                "advancement": 0.0,
                "conflict": 1.0,
                "character_consistency": 0.5,
                "world_consistency": 0.5,
                "foreshadowing": 0.5,
                "pacing": 0.5,
                "readability": 0.5,
                "trope_alignment": 0.5
            },
            "overall_score": 0.5,
            "suggestions": []
        }"""

        with patch(
            "src.core.quality.evaluator.get_llm_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=response_with_scores)
            mock_get_client.return_value = mock_client

            from src.core.quality.evaluator import evaluate_chapter_quality

            result = await evaluate_chapter_quality(
                chapter_content="测试内容",
                chapter_number=1,
            )

        # Verify boundary values are preserved
        assert result.scores["advancement"] == 0.0
        assert result.scores["conflict"] == 1.0
        assert result.overall == 0.5

    @pytest.mark.asyncio
    async def test_evaluate_missing_overall_calculates_average(self):
        """LLM 未返回 overall_score 时，自动计算平均值。"""
        response_no_overall = """{
            "scores": {
                "advancement": 0.80,
                "conflict": 0.80,
                "character_consistency": 0.80,
                "world_consistency": 0.80,
                "foreshadowing": 0.80,
                "pacing": 0.80,
                "readability": 0.80,
                "trope_alignment": 0.80
            },
            "feedback": {},
            "suggestions": []
        }"""

        with patch(
            "src.core.quality.evaluator.get_llm_client"
        ) as mock_get_client:
            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value=response_no_overall)
            mock_get_client.return_value = mock_client

            from src.core.quality.evaluator import evaluate_chapter_quality

            result = await evaluate_chapter_quality(
                chapter_content="测试",
                chapter_number=1,
            )

        assert result.overall == 0.8


# ---------------------------------------------------------------------------
# 3. generate_and_parse_json Tests
# ---------------------------------------------------------------------------


class TestGenerateAndParseJson:
    """Tests for generate_and_parse_json — LLM 调用 + JSON 解析辅助。"""

    @pytest.fixture
    def mock_client(self):
        client = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_normal_json_response(self, mock_client):
        """正常返回：LLM 输出合法 JSON，解析成功。"""
        mock_client.generate = AsyncMock(
            return_value='{"name": "主线", "type": "main"}'
        )

        from src.core.llm.helpers import generate_and_parse_json

        result = await generate_and_parse_json(
            mock_client, "测试prompt", fallback={}
        )

        assert result == {"name": "主线", "type": "main"}

    @pytest.mark.asyncio
    async def test_non_json_response_uses_fallback(self, mock_client):
        """LLM 返回非 JSON 文本时，使用 fallback。"""
        mock_client.generate = AsyncMock(
            return_value="抱歉，我无法生成JSON格式的内容。"
        )

        from src.core.llm.helpers import generate_and_parse_json

        result = await generate_and_parse_json(
            mock_client, "测试prompt", fallback={"default": True}
        )

        assert result == {"default": True}

    @pytest.mark.asyncio
    async def test_fallback_none_behavior(self, mock_client):
        """fallback 为 None 时，解析失败返回 None。"""
        mock_client.generate = AsyncMock(return_value="not json at all")

        from src.core.llm.helpers import generate_and_parse_json

        result = await generate_and_parse_json(
            mock_client, "测试prompt", fallback=None
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_llm_exception_returns_fallback(self, mock_client):
        """LLM 调用抛异常时，返回 fallback 而非崩溃。"""
        mock_client.generate = AsyncMock(
            side_effect=RuntimeError("API timeout")
        )

        from src.core.llm.helpers import generate_and_parse_json

        result = await generate_and_parse_json(
            mock_client, "测试prompt", fallback=[]
        )

        assert result == []

    @pytest.mark.asyncio
    async def test_json_in_markdown_block_extracted(self, mock_client):
        """LLM 返回 markdown 包裹的 JSON 时，仍能正确提取。"""
        wrapped = '```json\n{"key": "value"}\n```'
        mock_client.generate = AsyncMock(return_value=wrapped)

        from src.core.llm.helpers import generate_and_parse_json

        result = await generate_and_parse_json(
            mock_client, "测试prompt", fallback=None
        )

        assert result == {"key": "value"}


# ---------------------------------------------------------------------------
# 4. AIGenerationService Tests
# ---------------------------------------------------------------------------


class TestAIGenerationService:
    """Tests for AIGenerationService — AI 生成故事线/力量体系。"""

    @pytest.mark.asyncio
    async def test_generate_storylines_ai_happy_path(self):
        """正常流程：LLM 返回故事线数组，创建成功。"""
        mock_novel = {
            "novel_type": "玄幻",
            "idea": "少年修仙逆天改命",
        }
        mock_world = {"background": "灵气复苏的世界"}
        mock_characters = [
            {"name": "张三", "role": "主角"},
            {"name": "李四", "role": "反派"},
        ]

        llm_response = [
            {
                "name": "修仙主线",
                "type": "main",
                "description": "张三修仙之路",
                "key_events": [{"chapter": 1, "event": "入门"}],
            },
            {
                "name": "复仇暗线",
                "type": "hidden",
                "description": "李四的阴谋",
                "key_events": [{"chapter": 3, "event": "暗杀"}],
            },
        ]

        with patch(
            "src.api.services.novel_manager.get_novel_manager"
        ) as mock_mgr_fn, patch(
            "src.api.services.storyline_service.get_storyline_service"
        ) as mock_sl_fn, patch(
            "src.core.llm.helpers.safe_json_parse", return_value=llm_response
        ), patch(
            "src.core.llm.client.get_llm_client"
        ) as mock_llm_fn:
            mock_mgr = AsyncMock()
            mock_mgr.get_novel = AsyncMock(return_value=mock_novel)
            mock_mgr.get_world_setting = AsyncMock(return_value=mock_world)
            mock_mgr.list_characters = AsyncMock(return_value=mock_characters)
            mock_mgr_fn.return_value = mock_mgr

            mock_sl_svc = AsyncMock()
            mock_sl_svc.create_storyline = AsyncMock(side_effect=["sl-1", "sl-2"])
            mock_sl_fn.return_value = mock_sl_svc

            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value="[]")
            mock_llm_fn.return_value = mock_client

            from src.api.services.ai_generation_service import AIGenerationService

            service = AIGenerationService()
            result = await service.generate_storylines_ai("novel-001")

        assert len(result) == 2
        assert result[0]["name"] == "修仙主线"
        assert result[1]["name"] == "复仇暗线"
        assert mock_sl_svc.create_storyline.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_storylines_ai_novel_not_found(self):
        """小说不存在时抛出 ValueError。"""
        with patch(
            "src.api.services.novel_manager.get_novel_manager"
        ) as mock_mgr_fn:
            mock_mgr = AsyncMock()
            mock_mgr.get_novel = AsyncMock(return_value=None)
            mock_mgr_fn.return_value = mock_mgr

            from src.api.services.ai_generation_service import AIGenerationService

            service = AIGenerationService()
            with pytest.raises(ValueError, match="小说不存在"):
                await service.generate_storylines_ai("nonexistent")

    @pytest.mark.asyncio
    async def test_generate_power_systems_ai_happy_path(self):
        """力量体系生成正常流程。"""
        mock_novel = {
            "novel_type": "玄幻",
            "idea": "修仙世界等级森严",
        }
        mock_world = {
            "background": "灵气复苏",
            "rules": "修炼突破需要天材地宝",
        }

        llm_response = [
            {
                "name": "修仙境界",
                "description": "灵气修炼体系",
                "levels": [
                    {"name": "练气", "description": "初入修行", "breakthrough": "凝聚灵根"},
                    {"name": "筑基", "description": "根基稳固", "breakthrough": "灵液灌顶"},
                ],
            }
        ]

        with patch(
            "src.api.services.novel_manager.get_novel_manager"
        ) as mock_mgr_fn, patch(
            "src.core.llm.helpers.safe_json_parse", return_value=llm_response
        ), patch(
            "src.core.llm.client.get_llm_client"
        ) as mock_llm_fn:
            mock_mgr = AsyncMock()
            mock_mgr.get_novel = AsyncMock(return_value=mock_novel)
            mock_mgr.get_world_setting = AsyncMock(return_value=mock_world)
            mock_mgr.create_power_system = AsyncMock(return_value="ps-1")
            mock_mgr_fn.return_value = mock_mgr

            mock_client = AsyncMock()
            mock_client.generate = AsyncMock(return_value="[]")
            mock_llm_fn.return_value = mock_client

            from src.api.services.ai_generation_service import AIGenerationService

            service = AIGenerationService()
            result = await service.generate_power_systems_ai("novel-001")

        assert len(result) == 1
        assert result[0]["name"] == "修仙境界"
        assert len(result[0]["levels"]) == 2
        mock_mgr.create_power_system.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_power_systems_ai_novel_not_found(self):
        """小说不存在时抛出 ValueError。"""
        with patch(
            "src.api.services.novel_manager.get_novel_manager"
        ) as mock_mgr_fn:
            mock_mgr = AsyncMock()
            mock_mgr.get_novel = AsyncMock(return_value=None)
            mock_mgr_fn.return_value = mock_mgr

            from src.api.services.ai_generation_service import AIGenerationService

            service = AIGenerationService()
            with pytest.raises(ValueError, match="小说不存在"):
                await service.generate_power_systems_ai("nonexistent")
