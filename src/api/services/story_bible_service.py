"""故事圣经约束抽取与反向更新服务"""

import json
import logging
from typing import Any

from src.api.models.db_models import StoryBible

logger = logging.getLogger(__name__)


def extract_relevant_constraints(
    bible: StoryBible,
    chapter_outline: dict,
    current_chapter_num: int,
) -> str:
    """根据章节大纲精准抽取相关约束，避免全量注入。

    策略：
    - 全局约束始终包含：worldview_rules, hard_settings, banned_elements
    - 人物卡：只抽取本章出场人物
    - 伏笔：只抽取与本章人物/场景相关的
    - 时间线：最近5章事件
    - 悬念：所有未解决的
    - 主线目标：所有活跃的
    """
    sections: list[str] = []

    # --- 全局约束（始终包含）---
    sections.append("## 世界观规则:")
    sections.append(bible.worldview_rules or "未设定")

    sections.append("\n## 禁止违背的硬设定:")
    sections.append(bible.hard_settings or "未设定")

    banned = bible.banned_elements or []
    if banned:
        sections.append("\n## 禁用元素:")
        for item in banned:
            sections.append(f"- {item.get('element', '?')}: {item.get('reason', '')}")

    # --- 解析本章出场人物和场景 ---
    chapter_characters = _extract_chapter_characters(chapter_outline)
    chapter_locations = _extract_chapter_locations(chapter_outline)

    # --- 人物卡：只抽取出场人物 ---
    all_cards = bible.character_cards or []
    if chapter_characters:
        relevant_cards = [
            card for card in all_cards
            if _character_matches(card, chapter_characters)
        ]
    else:
        relevant_cards = all_cards

    if relevant_cards:
        sections.append("\n## 本章出场人物卡:")
        sections.append(json.dumps(relevant_cards, ensure_ascii=False, indent=2))

    # --- 势力关系（简短，始终包含）---
    if bible.faction_relations:
        sections.append("\n## 势力关系:")
        sections.append(bible.faction_relations)

    # --- 地点设定（如果本章有相关地点）---
    if bible.location_settings:
        sections.append("\n## 地点设定:")
        sections.append(bible.location_settings)

    # --- 伏笔：只抽取与本章人物相关的 ---
    foreshadowings = bible.foreshadowing_list or []
    if foreshadowings and chapter_characters:
        relevant_fs = [
            fs for fs in foreshadowings
            if _foreshadowing_relevant(fs, chapter_characters, chapter_locations)
        ]
    else:
        relevant_fs = foreshadowings

    if relevant_fs:
        sections.append("\n## 相关伏笔:")
        sections.append(json.dumps(relevant_fs, ensure_ascii=False, indent=2))

    # --- 时间线：最近5章事件 ---
    timeline = bible.timeline_events or []
    if timeline:
        recent = [
            ev for ev in timeline
            if ev.get("chapter") and ev["chapter"] >= current_chapter_num - 5
        ]
        if recent:
            sections.append("\n## 近期事件时间线:")
            sections.append(json.dumps(recent, ensure_ascii=False, indent=2))

    # --- 未解决悬念 ---
    hooks = bible.unresolved_hooks or []
    active_hooks = [h for h in hooks if h.get("status") != "resolved"]
    if active_hooks:
        sections.append("\n## 未回收悬念:")
        sections.append(json.dumps(active_hooks, ensure_ascii=False, indent=2))

    # --- 活跃主线目标 ---
    goals = bible.main_goals or []
    active_goals = [g for g in goals if g.get("status") == "active"]
    if active_goals:
        sections.append("\n## 活跃主线目标:")
        sections.append(json.dumps(active_goals, ensure_ascii=False, indent=2))

    return "\n".join(sections)


def _extract_chapter_characters(chapter_outline: dict) -> list[str]:
    """从章节大纲中提取出场人物名称列表"""
    characters = []
    if "characters" in chapter_outline:
        chars = chapter_outline["characters"]
        if isinstance(chars, list):
            for c in chars:
                if isinstance(c, str):
                    characters.append(c)
                elif isinstance(c, dict):
                    characters.append(c.get("name", c.get("character", "")))
    if "scenes" in chapter_outline:
        for scene in chapter_outline.get("scenes", []):
            if isinstance(scene, dict):
                for c in scene.get("characters", []):
                    if isinstance(c, str) and c not in characters:
                        characters.append(c)
    return [c for c in characters if c]


def _extract_chapter_locations(chapter_outline: dict) -> list[str]:
    """从章节大纲中提取场景地点"""
    locations = []
    if "location" in chapter_outline:
        locations.append(chapter_outline["location"])
    if "scene" in chapter_outline:
        locations.append(chapter_outline["scene"])
    if "scenes" in chapter_outline:
        for scene in chapter_outline.get("scenes", []):
            if isinstance(scene, dict) and "location" in scene:
                locations.append(scene["location"])
    return [loc for loc in locations if loc]


def _character_matches(card: dict, chapter_characters: list[str]) -> bool:
    """判断人物卡是否与本章出场人物匹配"""
    card_name = card.get("name", card.get("character_name", ""))
    for ch_name in chapter_characters:
        if ch_name in card_name or card_name in ch_name:
            return True
    return False


def _foreshadowing_relevant(
    fs: dict, characters: list[str], locations: list[str]
) -> bool:
    """判断伏笔是否与本章人物/场景相关"""
    fs_chars = fs.get("related_characters", [])
    if isinstance(fs_chars, list):
        for fc in fs_chars:
            for ch in characters:
                if ch in str(fc) or str(fc) in ch:
                    return True
    desc = fs.get("description", "")
    for ch in characters:
        if ch in desc:
            return True
    for loc in locations:
        if loc in desc:
            return True
    return False


UPDATE_BIBLE_PROMPT = """你是一个小说数据分析助手。请从以下新生成的章节内容中提取结构化信息，用于更新故事圣经。

【章节信息】
- 章节序号：{chapter_number}
- 章节大纲摘要：{outline_summary}

【章节正文】
{chapter_content}

请提取以下信息，严格输出 JSON 格式：
```json
{{
  "new_events": [
    {{"chapter": {chapter_number}, "event": "事件描述", "characters": ["人物1"], "timestamp_in_story": "故事内时间"}}
  ],
  "new_hooks": [
    {{"description": "悬念描述", "planted_chapter": {chapter_number}, "related_characters": ["人物"], "status": "hanging"}}
  ],
  "resolved_hooks": ["已回收悬念的描述关键词"],
  "character_updates": [
    {{"name": "人物名", "updates": {{"新属性": "值"}}}}
  ],
  "goal_progress": [
    {{"description": "目标描述关键词", "progress": "进展描述"}}
  ]
}}
```

注意：
- 只提取本章新出现的信息，不要重复已有内容
- 如果某个类别没有新信息，返回空列表
- resolved_hooks 只需要给出能匹配到已有悬念的关键词
"""


async def update_bible_after_generation(
    novel_id: str,
    chapter_number: int,
    chapter_content: str,
    chapter_outline: dict,
) -> dict[str, Any]:
    """章节生成后用 LLM 分析内容并自动更新 StoryBible。

    Returns:
        更新摘要 dict
    """
    from sqlalchemy import select

    from src.api.models.db_models import StoryBible
    from src.core.database import get_db_session
    from src.core.llm.client import get_llm_client

    summary: dict[str, Any] = {"new_events": 0, "new_hooks": 0, "resolved_hooks": 0, "character_updates": 0}

    async with get_db_session() as session:
        result = await session.execute(
            select(StoryBible).where(StoryBible.novel_id == novel_id)
        )
        bible = result.scalar_one_or_none()
        if not bible:
            logger.warning("No StoryBible found for novel %s, skipping update", novel_id)
            return summary

        outline_summary = json.dumps(
            {k: v for k, v in chapter_outline.items() if k in ("title", "summary", "characters", "scenes")},
            ensure_ascii=False,
        )

        prompt = UPDATE_BIBLE_PROMPT.format(
            chapter_number=chapter_number,
            outline_summary=outline_summary,
            chapter_content=chapter_content[:6000],
        )

        client = get_llm_client()
        response_str = await client.generate(prompt, max_tokens=2000)

        from src.core.json_utils import safe_json_parse
        updates = safe_json_parse(response_str)
        if not updates or not isinstance(updates, dict):
            logger.warning("Failed to parse LLM response for bible update")
            return summary

        # Merge timeline_events
        new_events = updates.get("new_events", [])
        if new_events:
            timeline = list(bible.timeline_events or [])
            timeline.extend(new_events)
            bible.timeline_events = timeline
            summary["new_events"] = len(new_events)

        # Merge unresolved_hooks
        new_hooks = updates.get("new_hooks", [])
        resolved_keywords = updates.get("resolved_hooks", [])
        hooks = list(bible.unresolved_hooks or [])

        if resolved_keywords:
            for hook in hooks:
                if hook.get("status") == "resolved":
                    continue
                desc = hook.get("description", "")
                for kw in resolved_keywords:
                    if kw and kw in desc:
                        hook["status"] = "resolved"
                        summary["resolved_hooks"] += 1
                        break

        if new_hooks:
            hooks.extend(new_hooks)
            summary["new_hooks"] = len(new_hooks)

        bible.unresolved_hooks = hooks

        # Merge character_updates
        char_updates = updates.get("character_updates", [])
        if char_updates:
            cards = list(bible.character_cards or [])
            for cu in char_updates:
                name = cu.get("name", "")
                upd = cu.get("updates", {})
                matched = False
                for card in cards:
                    if _character_matches(card, [name]):
                        card.update(upd)
                        matched = True
                        summary["character_updates"] += 1
                        break
                if not matched and name:
                    cards.append({"name": name, **upd})
                    summary["character_updates"] += 1
            bible.character_cards = cards

        # Merge goal_progress
        goal_progress = updates.get("goal_progress", [])
        if goal_progress:
            goals = list(bible.main_goals or [])
            for gp in goal_progress:
                kw = gp.get("description", "")
                progress = gp.get("progress", "")
                for goal in goals:
                    if kw and kw in goal.get("description", ""):
                        goal["progress"] = progress
                        break
            bible.main_goals = goals

        await session.commit()
        logger.info("StoryBible updated after chapter %d: %s", chapter_number, summary)

    return summary


CONFLICT_DETECTION_PROMPT = """你是一个小说一致性审核专家。请对比以下章节内容与故事圣经约束，检测冲突。

【故事圣经约束】
{bible_constraints}

【待检测章节】
- 章节序号：{chapter_number}
- 章节内容：
{chapter_content}

请检测以下类型的冲突：
1. 人物性格漂移：人物行为是否与人物卡中的性格描述矛盾
2. 时间线冲突：事件顺序是否与已记录的时间线矛盾
3. 设定矛盾：是否违反世界观规则、硬设定或禁用元素

严格输出 JSON 格式：
```json
{{
  "conflicts": [
    {{"type": "character_drift|timeline|setting_violation", "severity": "error|warning", "description": "具体冲突描述", "evidence": "章节中的相关文本片段"}}
  ]
}}
```

如果没有发现冲突，返回空列表。只报告确定的冲突，不要猜测。
"""


async def detect_bible_conflicts(
    novel_id: str,
    chapter_number: int,
    chapter_content: str,
) -> list[dict]:
    """检测章节与 StoryBible 的冲突，包括 LLM 检测和规则检测。"""
    from sqlalchemy import select

    from src.api.models.db_models import StoryBible
    from src.core.database import get_db_session

    conflicts: list[dict] = []

    async with get_db_session() as session:
        result = await session.execute(
            select(StoryBible).where(StoryBible.novel_id == novel_id)
        )
        bible = result.scalar_one_or_none()
        if not bible:
            return conflicts

        # 规则检测：伏笔遗忘（不需要 LLM）
        hooks = bible.unresolved_hooks or []
        for hook in hooks:
            if hook.get("status") == "resolved":
                continue
            planted = hook.get("planted_chapter")
            if planted and isinstance(planted, int):
                if chapter_number - planted > 10:
                    conflicts.append({
                        "type": "forgotten_hook",
                        "severity": "warning",
                        "description": f"伏笔已超过10章未回收: {hook.get('description', '未知')}",
                        "planted_chapter": planted,
                        "chapters_since": chapter_number - planted,
                    })

        # LLM 检测：性格漂移、时间线冲突、设定矛盾
        try:
            from src.core.llm.client import get_llm_client

            bible_constraints = _build_constraint_summary_for_detection(bible)

            prompt = CONFLICT_DETECTION_PROMPT.format(
                bible_constraints=bible_constraints,
                chapter_number=chapter_number,
                chapter_content=chapter_content[:5000],
            )

            client = get_llm_client()
            response_str = await client.generate(prompt, max_tokens=1500)

            from src.core.json_utils import safe_json_parse
            result_data = safe_json_parse(response_str)
            if result_data and isinstance(result_data, dict):
                llm_conflicts = result_data.get("conflicts", [])
                conflicts.extend(llm_conflicts)

        except Exception as e:
            logger.warning("LLM conflict detection failed: %s", e)

    return conflicts


def _build_constraint_summary_for_detection(bible: StoryBible) -> str:
    """构建用于冲突检测的约束摘要"""
    parts = []
    if bible.character_cards:
        parts.append("## 人物卡:")
        parts.append(json.dumps(bible.character_cards, ensure_ascii=False, indent=2))
    if bible.worldview_rules:
        parts.append("\n## 世界观规则:")
        parts.append(bible.worldview_rules)
    if bible.hard_settings:
        parts.append("\n## 硬设定:")
        parts.append(bible.hard_settings)
    if bible.banned_elements:
        parts.append("\n## 禁用元素:")
        parts.append(json.dumps(bible.banned_elements, ensure_ascii=False, indent=2))
    if bible.timeline_events:
        recent = bible.timeline_events[-10:]
        parts.append("\n## 近期时间线:")
        parts.append(json.dumps(recent, ensure_ascii=False, indent=2))
    return "\n".join(parts)