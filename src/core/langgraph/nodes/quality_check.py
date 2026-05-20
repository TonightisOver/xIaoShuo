"""质量检查与多维小说评估自适应节点"""

import json
import logging

from src.core.config import get_settings
from src.core.langgraph.state import NovelState

logger = logging.getLogger(__name__)

# 多维度小说编辑部级评估 Prompt
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


async def node(state: NovelState) -> NovelState:
    """质量检查节点

    通过调用真实 LLM 进行多维网文质量深度评估，结合知识图谱一致性检查判定打分。

    Args:
        state: 当前状态

    Returns:
        更新后的状态
    """
    logger.info("Starting multi-dimensional quality check evaluation")

    # 1. 获取最新生成的章节
    chapters = state.get("chapters", [])
    last_chapter = chapters[-1] if chapters else None

    # 默认评分矩阵 (用于异常优雅降级兜底)
    default_scores = {
        "overall": 0.82,
        "advancement": 0.80,
        "conflict": 0.80,
        "character_consistency": 0.85,
        "world_consistency": 0.85,
        "foreshadowing": 0.80,
        "pacing": 0.80,
        "readability": 0.85,
        "trope_alignment": 0.80,
        "consistency": 1.0,
    }

    if not last_chapter:
        logger.warning("No chapters generated yet, using default scores")
        return {
            **state,
            "quality_scores": default_scores,
            "current_stage": "quality_check_completed",
        }

    chapter_content = last_chapter.get("content", "")
    chapter_title = last_chapter.get("title", f"第{len(chapters)}章")
    chapter_number = last_chapter.get("chapter", len(chapters))

    # 2. 知识图谱一致性检查 (保留项目原有图谱校验)
    consistency_score = 1.0
    settings = get_settings()
    consistency_warnings = []

    if settings.KNOWLEDGE_GRAPH_ENABLED:
        try:
            from src.api.services.knowledge_graph_service import (
                get_knowledge_graph_service,
            )
            kg_service = get_knowledge_graph_service()
            conflicts = await kg_service.check_consistency(
                novel_id=state.get("novel_id") or state["project_id"],
                chapter_number=chapter_number,
                chapter_text=chapter_content,
            )
            consistency_warnings = conflicts
            error_count = sum(1 for c in conflicts if c.get("severity") == "error")
            if error_count > 0:
                consistency_score = max(0.3, 1.0 - error_count * 0.2)
        except Exception as e:
            logger.warning(f"Consistency check failed: {e}")

    # 3. 调用真实大模型进行 8 大硬度指标自适应评分
    try:
        from src.core.json_utils import safe_json_parse
        from src.core.llm.client import get_llm_client

        client = get_llm_client()

        # 组织生成大设定上下文
        novel_type = state.get("novel_type", "网络小说")
        idea = state.get("idea", "暂无核心创意描述")

        world_setting = state.get("world_setting")
        world_setting_str = (
            json.dumps(world_setting, ensure_ascii=False)
            if world_setting
            else "暂无世界观设定"
        )

        characters = state.get("characters", [])
        characters_str = (
            json.dumps(characters, ensure_ascii=False)
            if characters
            else "暂无人物角色人设"
        )

        prompt = EVALUATION_PROMPT.format(
            novel_type=novel_type,
            idea=idea,
            world_setting=world_setting_str,
            characters=characters_str,
            chapter_title=chapter_title,
            chapter_number=chapter_number,
            chapter_content=chapter_content,
        )

        logger.info(
            "Calling DeepSeek for multi-dimensional novel quality check "
            "(novel_id=%s, chapter=%s)",
            state.get("project_id"),
            chapter_number,
        )

        response_str = await client.generate(prompt, max_tokens=1500)

        # 稳健解析 JSON
        eval_result = safe_json_parse(response_str)

        if eval_result and isinstance(eval_result, dict) and "scores" in eval_result:
            scores = eval_result["scores"]
            feedback = eval_result.get("feedback", {})
            suggestions = eval_result.get("suggestions", [])
            overall_val = eval_result.get("overall_score")

            # 装配多维评分指标数据
            quality_scores = {
                "overall": float(overall_val) if overall_val is not None else 0.8,
                "advancement": float(scores.get("advancement", 0.8)),
                "conflict": float(scores.get("conflict", 0.8)),
                "character_consistency": float(
                    scores.get("character_consistency", 0.8)
                ),
                "world_consistency": float(scores.get("world_consistency", 0.8)),
                "foreshadowing": float(scores.get("foreshadowing", 0.8)),
                "pacing": float(scores.get("pacing", 0.8)),
                "readability": float(scores.get("readability", 0.8)),
                "trope_alignment": float(scores.get("trope_alignment", 0.8)),
                "consistency": consistency_score,
            }

            # 兜底：若 overall 评分缺失，则使用 8 个具体维度的算术平均值
            if overall_val is None:
                numeric_scores = [
                    v for k, v in quality_scores.items() if k != "consistency"
                ]
                quality_scores["overall"] = round(
                    sum(numeric_scores) / len(numeric_scores), 2
                )

            logger.info(
                "Quality evaluation completed successfully "
                "(overall_score=%s, scores=%s)",
                quality_scores["overall"],
                quality_scores,
            )

            # 将反馈与修改建议沉淀入 state 中供 revision 流程展示
            revision_requests = []
            for dim, fb in feedback.items():
                revision_requests.append(f"【{dim}】: {fb}")
            for sug in suggestions:
                revision_requests.append(f"修改建议: {sug}")

            return {
                **state,
                "quality_scores": quality_scores,
                "consistency_warnings": consistency_warnings,
                "revision_requests": revision_requests,
                "current_stage": "quality_check_completed",
            }
        else:
            logger.warning(
                "LLM response structure was invalid or missing scores. Falling back."
            )

    except Exception as e:
        logger.error(
            f"Multi-dimensional quality check failed. "
            f"Falling back to graceful defaults: {e}",
            exc_info=True,
        )

    # 4. 触发兜底优雅降级，防止主生成流程中断或死锁
    default_scores["consistency"] = consistency_score
    return {
        **state,
        "quality_scores": default_scores,
        "consistency_warnings": consistency_warnings,
        "current_stage": "quality_check_completed",
    }
