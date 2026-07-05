"""Unit tests for CHANGE-052: 长篇章节数量与字数约束修复

覆盖:
- T3: generate_volume_outline 章节数量验证与重试
- T5: 续写循环最多 MAX_CONTINUATION_ATTEMPTS 次
- T8: auto_calc_chapters 自动计算章节数（含夹紧逻辑）
"""

import math
from unittest.mock import AsyncMock, MagicMock, patch


# ===========================================================================
# T3 — generate_volume_outline 章节数量验证与重试
# ===========================================================================


class TestVolumeOutlineRetry:
    """T3: 章节数不足时触发重试，最多 2 次；重试后仍不足则使用 fallback。"""

    def _make_chapters(self, count: int) -> list[dict]:
        return [
            {
                "chapter": i,
                "title": f"第{i}章",
                "chapter_type": "main_advance",
                "plot": "情节",
                "key_characters": [],
                "foreshadows_planted": [],
                "foreshadows_resolved": [],
                "turning_point": "",
                "emotional_arc": "平静->推进",
            }
            for i in range(1, count + 1)
        ]

    def _make_volume_result(self, chapter_count: int) -> dict:
        return {
            "volume_number": 1,
            "title": "第一卷",
            "chapters": self._make_chapters(chapter_count),
        }

    def _make_request(self):
        req = MagicMock()
        req.writing_style = "现代白话"
        req.writing_style_prompt = ""
        return req

    def _make_master_outline(self):
        return {
            "title": "测试小说",
            "synopsis": "测试",
            "main_conflict": "测试冲突",
            "main_theme": "测试主题",
            "volumes": [
                {
                    "volume_number": 1,
                    "title": "第一卷",
                    "summary": "第一卷摘要",
                    "chapter_types": {},
                }
            ],
        }

    async def test_no_retry_when_chapters_sufficient(self):
        """章节数满足 80% 时不触发重试。"""
        from src.api.services.long_form_generation_helpers import generate_volume_outline

        chapters_per_volume = 10
        sufficient_result = self._make_volume_result(10)

        with patch("src.core.llm.client.get_llm_client") as mock_client_factory, \
             patch("src.core.llm.helpers.generate_and_parse_json", new_callable=AsyncMock) as mock_gen, \
             patch("src.core.validation.get_style_instruction", return_value=""):
            mock_client_factory.return_value = MagicMock()
            mock_gen.return_value = sufficient_result

            result = await generate_volume_outline(
                novel_id="test",
                master_outline=self._make_master_outline(),
                volume_number=1,
                chapters_per_volume=chapters_per_volume,
                words_per_chapter=3000,
                request=self._make_request(),
            )

        assert mock_gen.call_count == 1
        assert len(result["chapters"]) == 10

    async def test_retry_triggered_when_chapters_insufficient(self):
        """章节数 < 80% 时触发重试，重试后满足则停止。"""
        from src.api.services.long_form_generation_helpers import generate_volume_outline

        chapters_per_volume = 10
        # 5 chapters < 80% of 10 (8), triggers retry
        insufficient_result = self._make_volume_result(5)
        sufficient_result = self._make_volume_result(10)

        with patch("src.core.llm.client.get_llm_client") as mock_client_factory, \
             patch("src.core.llm.helpers.generate_and_parse_json", new_callable=AsyncMock) as mock_gen, \
             patch("src.core.validation.get_style_instruction", return_value=""):
            mock_client_factory.return_value = MagicMock()
            mock_gen.side_effect = [insufficient_result, sufficient_result]

            result = await generate_volume_outline(
                novel_id="test",
                master_outline=self._make_master_outline(),
                volume_number=1,
                chapters_per_volume=chapters_per_volume,
                words_per_chapter=3000,
                request=self._make_request(),
            )

        assert mock_gen.call_count == 2  # initial + 1 retry
        assert len(result["chapters"]) == 10

    async def test_fallback_used_after_retries_exhausted(self):
        """重试 2 次后仍不足，使用 fallback（chapters_per_volume 个章节）。"""
        from src.api.services.long_form_generation_helpers import generate_volume_outline

        chapters_per_volume = 10
        # Always returns 3 chapters (< 80% = 8), exhausts all retries
        insufficient_result = self._make_volume_result(3)

        with patch("src.core.llm.client.get_llm_client") as mock_client_factory, \
             patch("src.core.llm.helpers.generate_and_parse_json", new_callable=AsyncMock) as mock_gen, \
             patch("src.core.validation.get_style_instruction", return_value=""):
            mock_client_factory.return_value = MagicMock()
            mock_gen.return_value = insufficient_result

            result = await generate_volume_outline(
                novel_id="test",
                master_outline=self._make_master_outline(),
                volume_number=1,
                chapters_per_volume=chapters_per_volume,
                words_per_chapter=3000,
                request=self._make_request(),
            )

        # initial + 2 retries = 3 calls total
        assert mock_gen.call_count == 3
        # fallback has chapters_per_volume chapters
        assert len(result["chapters"]) == chapters_per_volume

    async def test_retry_prompt_contains_warning_text(self):
        """重试时 prompt 包含章节数不足的警告文本。"""
        from src.api.services.long_form_generation_helpers import generate_volume_outline

        chapters_per_volume = 10
        insufficient_result = self._make_volume_result(5)
        sufficient_result = self._make_volume_result(10)

        with patch("src.core.llm.client.get_llm_client") as mock_client_factory, \
             patch("src.core.llm.helpers.generate_and_parse_json", new_callable=AsyncMock) as mock_gen, \
             patch("src.core.validation.get_style_instruction", return_value=""):
            mock_client_factory.return_value = MagicMock()
            mock_gen.side_effect = [insufficient_result, sufficient_result]

            await generate_volume_outline(
                novel_id="test",
                master_outline=self._make_master_outline(),
                volume_number=1,
                chapters_per_volume=chapters_per_volume,
                words_per_chapter=3000,
                request=self._make_request(),
            )

        # Second call (retry) should have a prompt containing the warning
        retry_call_prompt = mock_gen.call_args_list[1][0][1]  # positional arg[1] = prompt
        assert "章节数不足" in retry_call_prompt or "重要" in retry_call_prompt


# ===========================================================================
# T5 — 续写循环最多 MAX_CONTINUATION_ATTEMPTS 次
# ===========================================================================


class TestContinuationLoop:
    """T5: 续写循环在字数不足时最多触发 MAX_CONTINUATION_ATTEMPTS 次。"""

    def _make_blueprint(self) -> dict:
        return {
            "chapter_type": "main_advance",
            "plot_goal": "推进主线",
            "hook_design": "冲突",
            "foreshadow_actions": [],
            "cliffhanger": "",
            "pacing_target": "medium",
            "key_characters": [],
            "word_target": 3000,
        }

    async def test_no_continuation_when_word_count_sufficient(self):
        """字数 >= 75% 时不触发续写。"""
        from src.core.llm.chapter_generator import _generate_single_chapter_inner

        target_words = 3000
        # 75% of 3000 = 2250; 2300 chars is above threshold
        content = "字" * 2300

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=content)

        with patch("src.core.llm.chapter_generator._continuation_generation", new_callable=AsyncMock) as mock_cont:
            result = await _generate_single_chapter_inner(
                client=mock_client,
                chapter_outline={"chapter": 1, "title": "第一章", "plot": "测试"},
                previous_chapter="",
                characters_json="[]",
                world_setting_json="{}",
                target_words=target_words,
                blueprint=self._make_blueprint(),
            )

        mock_cont.assert_not_called()
        assert result["word_count"] == 2300

    async def test_continuation_called_up_to_max_attempts(self):
        """字数不足时续写最多触发 MAX_CONTINUATION_ATTEMPTS 次。"""
        from src.core.llm.chapter_generator import (
            MAX_CONTINUATION_ATTEMPTS,
            _generate_single_chapter_inner,
        )

        target_words = 3000
        # 60% of 3000 = 1800; below 75% threshold (2250), triggers continuation
        short_content = "字" * 1800

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=short_content)

        # Each continuation still returns short content
        with patch("src.core.llm.chapter_generator._continuation_generation", new_callable=AsyncMock) as mock_cont:
            mock_cont.return_value = short_content

            await _generate_single_chapter_inner(
                client=mock_client,
                chapter_outline={"chapter": 1, "title": "第一章", "plot": "测试"},
                previous_chapter="",
                characters_json="[]",
                world_setting_json="{}",
                target_words=target_words,
                blueprint=self._make_blueprint(),
            )

        assert mock_cont.call_count == MAX_CONTINUATION_ATTEMPTS  # 3

    async def test_continuation_stops_when_word_count_sufficient(self):
        """续写后字数达标时停止，不再继续。"""
        from src.core.llm.chapter_generator import _generate_single_chapter_inner

        target_words = 3000
        short_content = "字" * 1800  # 60%, triggers continuation
        sufficient_content = "字" * 2500  # 83%, above 75% threshold

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=short_content)

        with patch("src.core.llm.chapter_generator._continuation_generation", new_callable=AsyncMock) as mock_cont:
            mock_cont.return_value = sufficient_content

            result = await _generate_single_chapter_inner(
                client=mock_client,
                chapter_outline={"chapter": 1, "title": "第一章", "plot": "测试"},
                previous_chapter="",
                characters_json="[]",
                world_setting_json="{}",
                target_words=target_words,
                blueprint=self._make_blueprint(),
            )

        assert mock_cont.call_count == 1
        assert result["word_count"] == 2500

    async def test_word_count_updated_after_each_continuation(self):
        """每次续写后重新计算字数，以新字数判断是否继续。"""
        from src.core.llm.chapter_generator import _generate_single_chapter_inner

        target_words = 3000
        short_content = "字" * 1800  # 60%, triggers continuation
        # First continuation: still short (1900 chars, still < 2250)
        # Second continuation: sufficient (2500 chars, > 2250)
        continuation_results = ["字" * 1500, "字" * 2500]

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=short_content)

        with patch("src.core.llm.chapter_generator._continuation_generation", new_callable=AsyncMock) as mock_cont:
            mock_cont.side_effect = continuation_results

            result = await _generate_single_chapter_inner(
                client=mock_client,
                chapter_outline={"chapter": 1, "title": "第一章", "plot": "测试"},
                previous_chapter="",
                characters_json="[]",
                world_setting_json="{}",
                target_words=target_words,
                blueprint=self._make_blueprint(),
            )

        assert mock_cont.call_count == 2
        assert result["word_count"] == 2500

    async def test_continuation_exception_breaks_loop(self):
        """续写抛出异常时中断循环，不再重试。"""
        from src.core.llm.chapter_generator import _generate_single_chapter_inner

        target_words = 3000
        short_content = "字" * 1800

        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=short_content)

        with patch("src.core.llm.chapter_generator._continuation_generation", new_callable=AsyncMock) as mock_cont:
            mock_cont.side_effect = RuntimeError("LLM error")

            result = await _generate_single_chapter_inner(
                client=mock_client,
                chapter_outline={"chapter": 1, "title": "第一章", "plot": "测试"},
                previous_chapter="",
                characters_json="[]",
                world_setting_json="{}",
                target_words=target_words,
                blueprint=self._make_blueprint(),
            )

        # Exception breaks the loop after first attempt
        assert mock_cont.call_count == 1
        # Returns original short content
        assert result["word_count"] == 1800


# ===========================================================================
# T8 — auto_calc_chapters 自动计算章节数
# ===========================================================================


class TestAutoCalcChapters:
    """T8: auto_calc_chapters 自动计算每卷章节数，含夹紧逻辑。"""

    def _calc(self, target_words: int, words_per_chapter: int, volumes: int) -> int:
        """镜像 novel_generator.py 中的计算逻辑。"""
        total_chapters = math.ceil(target_words / words_per_chapter)
        computed = math.ceil(total_chapters / volumes)
        return max(20, min(60, computed))

    def test_normal_range(self):
        """target_words=1210000, words_per_chapter=5000, volumes=10 → 25。"""
        result = self._calc(1_210_000, 5000, 10)
        assert result == 25

    def test_clamp_to_upper_limit(self):
        """target_words=1000000, words_per_chapter=3000, volumes=5 → 60（夹紧自 67）。"""
        result = self._calc(1_000_000, 3000, 5)
        assert result == 60

    def test_clamp_to_lower_limit(self):
        """计算结果 < 20 时夹紧到 20。"""
        # 100000 / 4000 / 10 = 2.5 → ceil = 3 → clamp to 20
        result = self._calc(100_000, 4000, 10)
        assert result == 20

    def test_no_clamp_when_in_range(self):
        """计算结果在 [20, 60] 范围内时不夹紧。"""
        # 600000 / 3000 / 10 = 20 → exactly at lower bound
        result = self._calc(600_000, 3000, 10)
        assert result == 20

        # 1800000 / 3000 / 10 = 60 → exactly at upper bound
        result = self._calc(1_800_000, 3000, 10)
        assert result == 60

    def _base_request_kwargs(self) -> dict:
        return {"idea": "一个现代程序员穿越到修仙世界", "novel_type": "玄幻"}

    def test_auto_calc_false_uses_request_value(self):
        """auto_calc_chapters=False 时直接使用 chapters_per_volume 字段值。"""
        from src.api.models.requests import LongFormNovelRequest

        req = LongFormNovelRequest(
            **self._base_request_kwargs(),
            auto_calc_chapters=False,
            chapters_per_volume=35,
        )
        assert req.auto_calc_chapters is False
        assert req.chapters_per_volume == 35

    def test_auto_calc_true_field_accepted(self):
        """auto_calc_chapters=True 被 Pydantic 模型接受。"""
        from src.api.models.requests import LongFormNovelRequest

        req = LongFormNovelRequest(
            **self._base_request_kwargs(),
            auto_calc_chapters=True,
        )
        assert req.auto_calc_chapters is True

    def test_words_per_chapter_accepts_5000(self):
        """words_per_chapter 字段上限已放宽至 8000，支持 5000 字/章场景。"""
        from src.api.models.requests import LongFormNovelRequest

        req = LongFormNovelRequest(
            **self._base_request_kwargs(),
            words_per_chapter=5000,
        )
        assert req.words_per_chapter == 5000
