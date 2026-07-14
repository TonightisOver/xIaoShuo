"""结构化状态增量 —— 每章生成后抽取，替代"正文前 N 字截取"作为长期记忆。

用于：
- L1 风险分级（比对状态增量而非全文）
- 连续章/卷级检查（只传增量，不传正文，降 Token）
- 下一章生成的衔接上下文
"""

import json
from typing import Any

import structlog

from src.core.json_utils import safe_json_parse
from src.core.llm.client import get_llm_client

logger = structlog.get_logger(__name__)

DEFAULT_DELTA_SCHEMA: dict[str, Any] = {
    "key_events": [],
    "causes": [],
    "character_changes": {},
    "timeline_delta": {},
    "foreshadows_planted": [],
    "foreshadows_resolved": [],
    "unresolved_conflicts": [],
    "next_chapter_must_carry": [],
}

EXTRACT_PROMPT = """你是小说连续性编辑器。请从本章正文中抽取结构化状态增量，供下一章生成与长期一致性检查使用。

【小说背景】
- 类型：{novel_type}
- 世界观：{world_setting}
- 人物：{characters}

【本章正文】
---
{chapter_content}
---

请抽取并仅输出一个 JSON 对象，字段如下：
{{
  "key_events": ["本章关键事件1", ...],
  "causes": ["导致这些事件的因果1", ...],
  "character_changes": {{ "人物名": {{"位置": "...", "情绪": "...", "能力": "...", "新物品": [...], "关系变化": "..."}}, ... }},
  "timeline_delta": {{ "推进": "N天/N月", "now": "主线时间锚点" }},
  "foreshadows_planted": ["新埋伏笔1", ...],
  "foreshadows_resolved": ["本章回收的伏笔1", ...],
  "unresolved_conflicts": ["未解决的冲突1", ...],
  "next_chapter_must_carry": ["下一章必须承接的状态1", ...]
}}

只输出 JSON，不要任何解释或闲聊。
"""


async def extract_state_delta(
    *,
    chapter_content: str,
    chapter_number: int,
    novel_type: str = "网络小说",
    world_setting: str = "",
    characters: str = "",
    content_limit: int = 6000,
) -> dict[str, Any]:
    """调用 LLM 抽取本章状态增量。失败时返回 schema 占位 + _unverified 标记。"""
    prompt = EXTRACT_PROMPT.format(
        novel_type=novel_type,
        world_setting=world_setting or "未设定",
        characters=characters or "未设定",
        chapter_content=chapter_content[:content_limit],
        chapter_number=chapter_number,
    )
    try:
        client = get_llm_client()
        raw = await client.generate(prompt, max_tokens=1500)
        parsed = safe_json_parse(raw, fallback=None)
        if isinstance(parsed, dict):
            # 合并 schema，补全缺失字段
            delta = {k: parsed.get(k, v) for k, v in DEFAULT_DELTA_SCHEMA.items()}
            return delta
    except Exception as e:
        logger.warning("state_delta_extract_failed", chapter=chapter_number, error=str(e))

    # 解析失败 —— 返回占位 + unverified 标记（绝不抛异常阻断主流程）
    fallback = dict(DEFAULT_DELTA_SCHEMA)
    fallback["_unverified"] = True
    return fallback


def merge_delta_for_context(prev_delta: dict[str, Any] | None, cur_delta: dict[str, Any]) -> str:
    """把多章状态增量合并为供下一章生成用的衔接上下文文本。"""
    if not prev_delta and not cur_delta:
        return ""
    parts: list[str] = []
    if prev_delta:
        carry = prev_delta.get("next_chapter_must_carry") or []
        if carry:
            parts.append("上一章要求承接：" + "；".join(carry))
        evts = prev_delta.get("key_events") or []
        if evts:
            parts.append("上一章关键事件：" + "；".join(evts[-3:]))
    if cur_delta:
        ch = cur_delta.get("character_changes") or {}
        if ch:
            parts.append("人物当前状态：" + json.dumps(ch, ensure_ascii=False))
    return "\n".join(parts)
