"""Regression tests for batched long-form outline generation."""

from unittest.mock import AsyncMock, MagicMock, patch


def _make_request() -> MagicMock:
    request = MagicMock()
    request.writing_style = "现代白话"
    request.writing_style_prompt = ""
    return request


def _make_master_outline() -> dict:
    return {
        "title": "测试小说",
        "synopsis": "测试",
        "volumes": [
            {
                "volume_number": 2,
                "title": "第二卷",
                "summary": "第二卷摘要",
            }
        ],
    }


async def test_generate_outline_batch_pads_missing_chapters_with_expected_numbers():
    from src.api.services.long_form_generation_helpers import _generate_outline_batch

    with patch(
        "src.core.llm.helpers.generate_and_parse_json",
        new_callable=AsyncMock,
    ) as mock_generate:
        mock_generate.return_value = {
            "chapters": [
                {
                    "chapter": 999,
                    "title": "模型返回的一章",
                    "plot": "推进情节",
                }
            ]
        }

        result = await _generate_outline_batch(
            client=MagicMock(),
            master_outline=_make_master_outline(),
            volume_number=2,
            vol_info={"summary": "第二卷摘要"},
            prev_summary="第一卷摘要",
            batch_start=13,
            batch_count=3,
            total_chapters=25,
            words_per_chapter=3000,
            prev_batch_chapters=[{"chapter": 12, "title": "前序章节", "plot": "承上"}],
            style_instruction="保持节奏紧凑",
        )

    assert [chapter["chapter"] for chapter in result] == [13, 14, 15]
    assert result[0]["title"] == "模型返回的一章"
    prompt = mock_generate.await_args.args[1]
    assert prompt.startswith("保持节奏紧凑")
    assert "第12章《前序章节》" in prompt


async def test_generate_volume_outline_splits_large_volume_into_batches():
    from src.api.services.long_form_generation_helpers import generate_volume_outline

    async def make_batch(**kwargs):
        return [
            {"chapter": number, "title": f"第{number}章"}
            for number in range(
                kwargs["batch_start"],
                kwargs["batch_start"] + kwargs["batch_count"],
            )
        ]

    with (
        patch("src.core.llm.client.get_llm_client", return_value=MagicMock()),
        patch("src.core.validation.get_style_instruction", return_value=""),
        patch(
            "src.api.services.long_form_generation_helpers._generate_outline_batch",
            new_callable=AsyncMock,
            side_effect=make_batch,
        ) as mock_batch,
    ):
        result = await generate_volume_outline(
            novel_id="novel-1",
            master_outline=_make_master_outline(),
            volume_number=2,
            chapters_per_volume=25,
            words_per_chapter=3000,
            request=_make_request(),
        )

    assert [call.kwargs["batch_count"] for call in mock_batch.await_args_list] == [
        12,
        12,
        1,
    ]
    assert [chapter["chapter"] for chapter in result["chapters"]] == list(
        range(1, 26)
    )
    assert all(chapter["volume_number"] == 2 for chapter in result["chapters"])


async def test_chapter_generation_uses_target_word_based_max_tokens():
    from src.core.llm.chapter_generator import ChapterGenContext, _generate_single_chapter_inner

    client = AsyncMock()
    client.generate = AsyncMock(return_value="字" * 4000)

    result = await _generate_single_chapter_inner(
        ChapterGenContext(
            client=client,
            chapter_outline={"chapter": 1, "title": "第一章", "plot": "推进"},
            previous_chapter="上一章结尾",
            characters_json="[]",
            world_setting_json="{}",
            target_words=5000,
            blueprint={"chapter_type": "main_advance"},
        )
    )

    assert result["word_count"] == 4000
    client.generate.assert_awaited_once()
    assert client.generate.await_args.kwargs == {
        "max_tokens": 6000,
        "use_flash": True,
    }
