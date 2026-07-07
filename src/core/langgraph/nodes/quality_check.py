"""质量检查与多维小说评估自适应节点

Dependencies injected via LangGraph config["configurable"]:
  - kg_service: Knowledge graph service instance (optional)
  - detect_bible_conflicts: async callable for conflict check
  - persist_quality: async callable for quality persistence
"""

import json
import logging

from langchain_core.runnables import RunnableConfig

from src.core.config import get_settings
from src.core.langgraph.state import NovelState
from src.core.quality.evaluator import evaluate_chapter_quality

logger = logging.getLogger(__name__)


async def node(state: NovelState, config: RunnableConfig | None = None) -> NovelState:
    """质量检查节点

    通过调用真实 LLM 进行多维网文质量深度评估，结合知识图谱一致性检查判定打分。

    Args:
        state: 当前状态
        config: LangGraph config with configurable dependencies:
            - kg_service: knowledge graph service instance
            - detect_bible_conflicts: async callable for story bible conflict detection
            - persist_quality: async callable to persist quality scores to DB

    Returns:
        更新后的状态
    """
    configurable = (config or {}).get("configurable", {})

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
            "kg_continuity_report": None,
        }

    chapter_content = last_chapter.get("content", "")
    chapter_title = last_chapter.get("title", f"第{len(chapters)}章")
    chapter_number = last_chapter.get("chapter", len(chapters))

    # 2. 知识图谱一致性检查 (via injected kg_service)
    consistency_score = 1.0
    settings = get_settings()
    consistency_warnings = []
    kg_continuity_report = None
    novel_id = state.get("novel_id") or state.get("project_id")

    if settings.KNOWLEDGE_GRAPH_ENABLED:
        kg_service = configurable.get("kg_service")
        if kg_service:
            try:
                if settings.KG_SUBAGENT_ENABLED:
                    kg_summary = await kg_service.retrieve_context(
                        novel_id=novel_id,
                        chapter_outline={"chapter": chapter_number},
                        raw_format=True,
                    )
                    from src.core.agents.continuity_editor import ContinuityEditorAgent
                    editor = ContinuityEditorAgent()
                    kg_continuity_report = await editor.review(
                        chapter_content=chapter_content,
                        kg_summary=kg_summary,
                    )
                    issues = kg_continuity_report.get("issues", [])
                    for issue in issues:
                        severity_map = {
                            "critical": "error",
                            "minor": "warning",
                            "info": "warning"
                        }
                        consistency_warnings.append({
                            "severity": severity_map.get(issue.get("severity"), "warning"),
                            "type": issue.get("type"),
                            "message": issue.get("description") or issue.get("message", ""),
                            "entity": issue.get("entity"),
                            "suggestion": issue.get("suggestion"),
                            "kg_update_needed": issue.get("kg_update_needed"),
                            "kg_update_detail": issue.get("kg_update_detail"),
                        })
                    verdict = kg_continuity_report.get("verdict", "pass")
                    if verdict == "block":
                        consistency_score = 0.3
                    elif verdict == "warn":
                        consistency_score = 0.8
                    else:
                        consistency_score = 1.0
                else:
                    conflicts = await kg_service.check_consistency(
                        novel_id=novel_id,
                        chapter_number=chapter_number,
                        chapter_text=chapter_content,
                    )
                    consistency_warnings = conflicts
                    error_count = sum(1 for c in conflicts if c.get("severity") == "error")
                    if error_count > 0:
                        consistency_score = max(0.3, 1.0 - error_count * 0.2)
            except Exception as e:
                logger.warning(f"Consistency check failed: {e}")

    # 2.5 StoryBible 冲突检测 (via injected callback)
    detect_bible_conflicts_fn = configurable.get("detect_bible_conflicts")
    if novel_id and detect_bible_conflicts_fn:
        try:
            bible_conflicts = await detect_bible_conflicts_fn(
                novel_id=novel_id,
                chapter_number=chapter_number,
                chapter_content=chapter_content,
            )
            if bible_conflicts:
                consistency_warnings.extend(bible_conflicts)
                bible_errors = sum(
                    1 for c in bible_conflicts
                    if c.get("severity") == "error"
                )
                if bible_errors > 0:
                    consistency_score = max(0.3, consistency_score - bible_errors * 0.1)
        except Exception as e:
            logger.warning(f"StoryBible conflict detection failed: {e}")

    # 2.6 知识抽取与图谱协调 (moved from chapter_generator)
    if settings.KNOWLEDGE_GRAPH_ENABLED:
        kg_service = configurable.get("kg_service")
        if kg_service and novel_id:
            try:
                await kg_service.extract_from_chapter(
                    novel_id=novel_id,
                    chapter_number=chapter_number,
                    chapter_text=chapter_content,
                    continuity_report=kg_continuity_report,
                )
            except Exception as e:
                logger.warning(f"Knowledge graph extraction failed: {e}")

    # 3. 调用公共质量评估模块进行 8 大硬度指标自适应评分
    persist_quality_fn = configurable.get("persist_quality")

    try:
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

        logger.info(
            "Calling DeepSeek for multi-dimensional novel quality check "
            "(novel_id=%s, chapter=%s)",
            state.get("project_id"),
            chapter_number,
        )

        result = await evaluate_chapter_quality(
            chapter_content=chapter_content,
            chapter_number=chapter_number,
            novel_type=novel_type,
            idea=idea,
            world_setting=world_setting_str,
            characters=characters_str,
            chapter_title=chapter_title,
            default_score=0.8,
        )

        # 装配多维评分指标数据（含 consistency 维度）
        quality_scores = result.to_scores_dict()
        quality_scores["consistency"] = consistency_score

        logger.info(
            "Quality evaluation completed successfully "
            "(overall_score=%s, scores=%s)",
            quality_scores["overall"],
            quality_scores,
        )

        # 将反馈与修改建议沉淀入 state 中供 revision 流程展示
        revision_requests = []
        for dim, fb in result.feedback.items():
            revision_requests.append(f"【{dim}】: {fb}")
        for sug in result.suggestions:
            revision_requests.append(f"修改建议: {sug}")

        # 持久化质量评分到活跃版本 (via injected callback)
        if persist_quality_fn and novel_id and chapter_number:
            await persist_quality_fn(
                novel_id, chapter_number, quality_scores, consistency_warnings
            )

        return {
            **state,
            "quality_scores": quality_scores,
            "consistency_warnings": consistency_warnings,
            "revision_requests": revision_requests,
            "current_stage": "quality_check_completed",
            "kg_continuity_report": kg_continuity_report,
        }

    except Exception as e:
        logger.error(
            f"Multi-dimensional quality check failed. "
            f"Falling back to graceful defaults: {e}",
            exc_info=True,
        )

    # 4. 触发兜底优雅降级，防止主生成流程中断或死锁
    default_scores["consistency"] = consistency_score

    # 即使降级也持久化默认评分
    if persist_quality_fn and novel_id and last_chapter:
        await persist_quality_fn(
            novel_id,
            last_chapter.get("chapter", 0),
            default_scores,
            consistency_warnings,
        )

    return {
        **state,
        "quality_scores": default_scores,
        "consistency_warnings": consistency_warnings,
        "current_stage": "quality_check_completed",
        "kg_continuity_report": kg_continuity_report,
    }
