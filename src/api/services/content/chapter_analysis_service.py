"""章节剧情分析服务 — AI 提取伏笔/钩子/情节点/角色事件"""

from __future__ import annotations

from typing import Any

import structlog

logger = structlog.get_logger(__name__)

# Annotation types and their display properties
ANNOTATION_TYPES = {
    "foreshadow": {"label": "伏笔", "color": "purple"},
    "hook": {"label": "钩子", "color": "orange"},
    "plot_point": {"label": "情节", "color": "blue"},
    "character_event": {"label": "角色", "color": "green"},
}

ANALYSIS_PROMPT_TEMPLATE = """\
你是专业的网文编辑，请分析以下章节内容，提取结构化标注。

章节内容：
{content}

请提取以下类型的标注，输出 JSON 数组：
- foreshadow（伏笔）：悬念、暗示、未解释的线索
- hook（钩子）：吸引读者继续阅读的元素
- plot_point（情节点）：推进主线剧情的关键事件
- character_event（角色事件）：角色的重要行为/变化/对话

每个标注 JSON：{{"type", "start", "end", "label", "description"}}

只输出 JSON 数组，不要其他内容。
"""


async def analyze_chapter_content(
    client: Any,
    content: str,
) -> list[dict[str, Any]]:
    """Analyze chapter content and return structured annotations."""
    if not content or len(content) < 100:
        return []

    prompt = ANALYSIS_PROMPT_TEMPLATE.format(content=content[:6000])
    try:
        raw = await client.generate(prompt, max_tokens=2000, use_flash=True)
        from src.core.json_utils import safe_json_parse

        result = safe_json_parse(raw)
        if isinstance(result, list):
            return [
                _validate_annotation(a, len(content))
                for a in result
                if isinstance(a, dict)
            ]
    except Exception as exc:
        logger.warning("chapter_analysis_failed", error=str(exc))
    return []


def _validate_annotation(
    raw: dict[str, Any],
    content_length: int,
) -> dict[str, Any]:
    """Validate and normalize a single annotation."""
    ann_type = raw.get("type", "plot_point")
    if ann_type not in ANNOTATION_TYPES:
        ann_type = "plot_point"
    if content_length <= 0:
        content_length = 1
    try:
        start = int(raw.get("start", 0))
        end = int(raw.get("end", start + 50))
    except (ValueError, TypeError):
        start, end = 0, min(50, content_length)
    start = max(0, min(start, content_length - 1))
    end = max(start + 1, min(end, content_length))
    return {
        "type": ann_type,
        "start": start,
        "end": end,
        "label": str(raw.get("label", ""))[:50],
        "description": str(raw.get("description", ""))[:200],
    }


def get_analysis_summary(
    annotations: list[dict[str, Any]],
) -> dict[str, int]:
    """Count annotations by type."""
    summary: dict[str, int] = {t: 0 for t in ANNOTATION_TYPES}
    for ann in annotations:
        t = ann.get("type", "")
        if t in summary:
            summary[t] += 1
    summary["total"] = len(annotations)
    return summary
