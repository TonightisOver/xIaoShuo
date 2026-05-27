"""章节质量评估公共逻辑 — 统一 Prompt、解析、fallback"""

import structlog

from src.core.json_utils import safe_json_parse
from src.core.llm.client import get_llm_client

logger = structlog.get_logger(__name__)

QUALITY_DIMENSIONS = [
    "advancement",
    "conflict",
    "character_consistency",
    "world_consistency",
    "foreshadowing",
    "pacing",
    "readability",
    "trope_alignment",
]

EVALUATION_PROMPT = """你是一位极其严苛的网文总编辑，专门负责评估生成的小说章节质量。
请根据小说的定位、核心创意、世界观、人物角色人设，对最新的章节文本进行多维度、高精度的硬度评估。

【小说背景上下文】
- 小说类型：{novel_type}
- 核心创意/简况：{idea}
- 世界观设定：{world_setting}
- 登场人物人设：{characters}

【待评估章节】
- 章节标题：{chapter_title}
- 章节序号：{chapter_number}
- 章节内容：
---
{chapter_content}
---

请针对以下 8 个维度，分别给出 0.0 到 1.0 的分数（0.0 最差，1.0 完美），
并附带 1-2 句极其精炼的专业反馈意见：
1. advancement (主线推进度)：本章是否实质推进主线（剧情是否注水）？
2. conflict (冲突与悬念度)：本章是否有冲突/钩子，是否具有爽点和危机期待感？
3. character_consistency (角色一致性)：人物行为是否符合人设，是否脱离既定人设？
4. world_consistency (世界观一致性)：是否遵守世界设定规则，是否出现了新设定但未登记？
5. foreshadowing (伏笔与回收)：是否有伏笔种下或精彩回收？
6. pacing (叙事节奏控制)：是否节奏拖沓，节奏是否拖泥带水？
7. readability (表达精炼度)：是否存在重复描写、车轱辘话、语病或低级段落重复？
8. trope_alignment (网络爽点题材契合度)：是否符合目标题材套路，能否带给读者强烈的爽感？

【输出格式要求】
必须严格输出且仅输出一个合法的 JSON 对象，格式如下，
不要包含 markdown 代码块包装以外的任何闲聊或解释：
```json
{{
  "scores": {{
    "advancement": 0.85,
    "conflict": 0.90,
    "character_consistency": 0.80,
    "world_consistency": 0.95,
    "foreshadowing": 0.85,
    "pacing": 0.75,
    "readability": 0.80,
    "trope_alignment": 0.85
  }},
  "feedback": {{
    "advancement": "反馈内容...",
    "conflict": "反馈内容...",
    "character_consistency": "反馈内容...",
    "world_consistency": "反馈内容...",
    "foreshadowing": "反馈内容...",
    "pacing": "反馈内容...",
    "readability": "反馈内容...",
    "trope_alignment": "反馈内容..."
  }},
  "overall_score": 0.84,
  "suggestions": [
    "修改建议 1...",
    "修改建议 2..."
  ]
}}
```
"""

class QualityResult:
    """质量评估结果"""

    def __init__(
        self,
        scores: dict[str, float],
        overall: float,
        feedback: dict[str, str] | None = None,
        suggestions: list[str] | None = None,
    ):
        self.scores = scores
        self.overall = overall
        self.feedback = feedback or {}
        self.suggestions = suggestions or []

    def to_scores_dict(self) -> dict[str, float]:
        """返回兼容旧接口的 scores dict（含 overall 键）"""
        result = dict(self.scores)
        result["overall"] = self.overall
        return result


async def evaluate_chapter_quality(
    *,
    chapter_content: str,
    chapter_number: int,
    novel_type: str = "网络小说",
    idea: str = "暂无核心创意描述",
    world_setting: str = "未设定",
    characters: str = "未设定",
    chapter_title: str = "",
    max_tokens: int = 1500,
    content_limit: int = 8000,
    default_score: float = 0.5,
) -> QualityResult:
    """调用 LLM 进行八维质量评估。

    Args:
        chapter_content: 章节正文
        chapter_number: 章节序号
        novel_type: 小说类型
        idea: 核心创意
        world_setting: 世界观设定文本
        characters: 人物角色描述文本
        chapter_title: 章节标题（可选）
        max_tokens: LLM 最大输出 token
        content_limit: 章节内容截断长度
        default_score: 解析失败时的默认分数

    Returns:
        QualityResult 包含 scores、overall、feedback、suggestions
    """
    if not chapter_title:
        chapter_title = f"第{chapter_number}章"

    prompt = EVALUATION_PROMPT.format(
        novel_type=novel_type,
        idea=idea,
        world_setting=world_setting,
        characters=characters,
        chapter_title=chapter_title,
        chapter_number=chapter_number,
        chapter_content=chapter_content[:content_limit],
    )

    client = get_llm_client()
    raw_response = await client.generate(prompt, max_tokens=max_tokens)

    eval_result = safe_json_parse(raw_response, fallback=None)

    if eval_result and isinstance(eval_result, dict) and "scores" in eval_result:
        scores = eval_result["scores"]
        feedback = eval_result.get("feedback", {})
        suggestions = eval_result.get("suggestions", [])
        overall_val = eval_result.get("overall_score")

        # 确保所有维度都有 float 值
        parsed_scores: dict[str, float] = {}
        for dim in QUALITY_DIMENSIONS:
            parsed_scores[dim] = float(scores.get(dim, default_score))

        # 计算 overall
        if overall_val is not None:
            overall = float(overall_val)
        else:
            valid_scores = list(parsed_scores.values())
            overall = (
                round(sum(valid_scores) / len(valid_scores), 4)
                if valid_scores
                else default_score
            )

        return QualityResult(
            scores=parsed_scores,
            overall=overall,
            feedback=feedback if isinstance(feedback, dict) else {},
            suggestions=suggestions if isinstance(suggestions, list) else [],
        )

    # 解析失败 — 返回默认分数
    logger.warning(
        "quality_eval_parse_failed",
        chapter_number=chapter_number,
        raw_length=len(raw_response) if raw_response else 0,
    )
    default_scores = {dim: default_score for dim in QUALITY_DIMENSIONS}
    return QualityResult(scores=default_scores, overall=default_score)
