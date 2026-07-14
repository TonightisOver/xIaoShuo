from unittest.mock import AsyncMock, patch

import pytest

from src.core.quality.state_delta import DEFAULT_DELTA_SCHEMA, extract_state_delta


def test_default_schema_has_required_keys():
    for k in ["key_events", "character_changes", "timeline_delta",
              "foreshadows_planted", "foreshadows_resolved",
              "unresolved_conflicts", "next_chapter_must_carry"]:
        assert k in DEFAULT_DELTA_SCHEMA


@pytest.mark.asyncio
async def test_extract_state_delta_parses_llm_json():
    fake_llm_json = '''```json
    {
      "key_events": ["陈安击败林炎"],
      "character_changes": {"陈安": {"位置": "万剑门", "情绪": "隐忍"}},
      "timeline_delta": {"推进": "3天"},
      "foreshadows_planted": ["残卷古文"],
      "foreshadows_resolved": [],
      "unresolved_conflicts": ["林炎师姐未现"],
      "next_chapter_must_carry": ["藏匿残卷"]
    }
    ```'''
    with patch("src.core.quality.state_delta.get_llm_client") as mock_get:
        client = AsyncMock()
        client.generate = AsyncMock(return_value=fake_llm_json)
        mock_get.return_value = client
        delta = await extract_state_delta(
            chapter_content="正文内容...", chapter_number=5,
            novel_type="玄幻", world_setting="修真世界", characters="陈安/林炎",
        )
    assert delta["key_events"] == ["陈安击败林炎"]
    assert delta["character_changes"]["陈安"]["位置"] == "万剑门"
    assert delta["next_chapter_must_carry"] == ["藏匿残卷"]


@pytest.mark.asyncio
async def test_extract_state_delta_fallback_on_parse_failure():
    with patch("src.core.quality.state_delta.get_llm_client") as mock_get:
        client = AsyncMock()
        client.generate = AsyncMock(return_value="not json at all")
        mock_get.return_value = client
        delta = await extract_state_delta(
            chapter_content="正文", chapter_number=5,
            novel_type="玄幻", world_setting="w", characters="c",
        )
    # 解析失败应返回 schema 占位 + _unverified 标记，不能抛异常
    assert delta.get("_unverified") is True
    assert delta["key_events"] == []
