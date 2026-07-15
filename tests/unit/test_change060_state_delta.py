from unittest.mock import AsyncMock, patch

import pytest

from src.core.quality.state_delta import (
    DEFAULT_DELTA_SCHEMA,
    extract_state_delta,
    merge_delta_for_context,
)


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


@pytest.mark.asyncio
async def test_extract_state_delta_coerces_invalid_types():
    """LLM 返回字段类型非法时，该字段回退为 schema 默认值，不抛异常、不带 _unverified。"""
    fake_llm_json = '''```json
    {
      "key_events": "should be a list but got string",
      "character_changes": "should be a dict but got string",
      "next_chapter_must_carry": ["正常列表"]
    }
    ```'''
    with patch("src.core.quality.state_delta.get_llm_client") as mock_get:
        client = AsyncMock()
        client.generate = AsyncMock(return_value=fake_llm_json)
        mock_get.return_value = client
        delta = await extract_state_delta(
            chapter_content="正文", chapter_number=5,
            novel_type="玄幻", world_setting="w", characters="c",
        )
    # 类型非法的字段回退为默认值（空 list / 空 dict）
    assert delta["key_events"] == []
    assert delta["character_changes"] == {}
    # 类型正常的字段保留
    assert delta["next_chapter_must_carry"] == ["正常列表"]
    # 成功路径（JSON 能解析），不带 _unverified
    assert delta.get("_unverified") is None


def test_merge_delta_for_context_empty():
    assert merge_delta_for_context(None, {}) == ""


def test_merge_delta_for_context_prev_only():
    prev = {
        "next_chapter_must_carry": ["藏匿残卷", "林炎伤势"],
        "key_events": ["击败林炎", "获得残卷", "闭关", "出关"],
    }
    result = merge_delta_for_context(prev, {})
    assert "上一章要求承接" in result
    assert "藏匿残卷" in result
    # key_events 取最后3条
    assert "出关" in result
    assert "击败林炎" not in result  # 超过3条前的被裁掉


def test_merge_delta_for_context_cur_character_changes():
    cur = {"character_changes": {"陈安": {"位置": "万剑门"}}}
    result = merge_delta_for_context(None, cur)
    assert "人物当前状态" in result
    assert "陈安" in result
    assert "万剑门" in result


def test_merge_delta_for_context_both():
    prev = {"next_chapter_must_carry": ["承接A"], "key_events": ["事件1"]}
    cur = {"character_changes": {"主角": {"情绪": "愤怒"}}}
    result = merge_delta_for_context(prev, cur)
    assert "上一章要求承接" in result
    assert "上一章关键事件" in result
    assert "人物当前状态" in result
