"""质量检查与多维小说评估自适应节点

Dependencies injected via LangGraph config["configurable"]:
  - kg_service: Knowledge graph service instance (optional)
  - detect_bible_conflicts: async callable for conflict check
  - persist_quality: async callable for quality persistence
  - rewrite_service: optional service for L3 automatic rewrite
"""

import json
import logging

from langchain_core.runnables import RunnableConfig

from src.core.config import get_settings
from src.core.langgraph.state import NovelState

# evaluate_chapter_quality 不再由节点直接调用（收敛到 run_quality_gate，Ticket 04）。
# 保留 import 仅为测试 patch 路径稳定：test_change060 patch 本模块符号。
from src.core.quality.evaluator import evaluate_chapter_quality  # noqa: F401

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
            - rewrite_service: optional service for L3 automatic rewrite

    Returns:
        更新后的状态
    """
    configurable = (config or {}).get("configurable", {})

    logger.info("Starting multi-dimensional quality check evaluation")

    # 1. 获取最新生成的章节
    chapters = state.get("chapters", [])
    last_chapter = chapters[-1] if chapters else None

    # 评估失败的兜底：标记为 unverified，overall=None，绝不伪造合格分
    unverified_scores = {
        "overall": None,
        "advancement": None,
        "conflict": None,
        "character_consistency": None,
        "world_consistency": None,
        "foreshadowing": None,
        "pacing": None,
        "readability": None,
        "trope_alignment": None,
        "consistency": 1.0,
        "status": "unverified",
    }

    if not last_chapter:
        logger.warning("No chapters generated yet, using unverified scores")
        return {
            **state,
            "quality_scores": {**unverified_scores, "consistency_blocked": False},
            "current_stage": "quality_check_completed",
            "kg_continuity_report": None,
            "l0_results": [],
        }

    chapter_content = last_chapter.get("content", "")
    chapter_number = last_chapter.get("chapter", len(chapters))

    # NOTE: L0 预筛结果暂仅收集入 state（l0_results），供卷级报告与后续运行时拦截编排使用。
    # 当前不在此节点拦截章节（运行时编排属后续 Task，见计划 §已知局限 2）。
    from src.core.quality.rules import run_l0_rules

    l0_all: list[dict] = []
    avg_wc = sum(len(c.get("content", "")) for c in chapters) / max(len(chapters), 1)
    for idx, ch in enumerate(chapters):
        l0 = run_l0_rules(
            content=ch.get("content", ""),
            word_count=ch.get("word_count"),
            avg_word_count=avg_wc,
            chapter_outline=ch.get("plot") or ch.get("outline"),
            chapter_number=ch.get("chapter", idx + 1),
        )
        l0_all.append(l0)

    # 2. 知识图谱一致性检查 (via injected kg_service)
    # NOTE（Ticket 04）：KG 检查仅产出 consistency_warnings / kg_continuity_report
    # 供下游 human_review 展示 + KG 抽取副作用。一致性硬门禁已收敛到 run_quality_gate
    # （gate 看 L2 评分的 character_consistency/world_consistency < 0.4）。
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
    # NOTE（Ticket 04）：仅收集到 consistency_warnings 供展示，不再触发硬门禁
    # （gate 的硬门禁基于 L2 评分，不消费 detect_bible_conflicts）。
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

    # 3. 质量门禁漏斗（收敛到 run_quality_gate，Ticket 04）
    #    gate 接管：state_delta 抽取 + L0 + L1 风险分级 + L2 评分 + consistency 硬门禁 + L3 改写。
    #    节点保留：KG 一致性检查（§2 产出 consistency_warnings/kg_continuity_report）
    #             + KG 知识抽取副作用（§2.6）。
    #    一致性硬门禁口径变化：gate 看 L2 评分 character_consistency/world_consistency < 0.4，
    #    旧版基于 KG verdict / StoryBible error 的 block 已移除。
    from src.core.quality.gate import GatePersistCallbacks, run_quality_gate

    novel_type = state.get("novel_type", "网络小说")
    idea = state.get("idea", "暂无核心创意描述")
    world_setting_str = (
        json.dumps(state.get("world_setting"), ensure_ascii=False)
        if state.get("world_setting") else "暂无世界观设定"
    )
    characters_str = (
        json.dumps(state.get("characters", []), ensure_ascii=False)
        if state.get("characters") else "暂无人物角色人设"
    )

    # 短篇 LangGraph 暂无 novel_manager 入口，state_delta 仅入 state 不落 DB 行；
    # quality_status 也仅写入 quality_scores，由 persist_quality_fn 持久化。
    async def _noop(*args, **kwargs):
        return None

    persist_quality_fn = configurable.get("persist_quality") or _noop
    rewrite_service = configurable.get("rewrite_service")

    gate_callbacks = GatePersistCallbacks(
        update_state_delta=_noop,
        update_quality_status=_noop,
        persist_quality_scores=persist_quality_fn,
        detect_bible_conflicts=configurable.get("detect_bible_conflicts"),
    )

    try:
        gate_result = await run_quality_gate(
            novel_id=novel_id,
            chapter_number=chapter_number,
            chapter_result={
                "content": chapter_content,
                "word_count": last_chapter.get("word_count", len(chapter_content)),
                "chapter_type": last_chapter.get("chapter_type"),
            },
            chapter_outline=last_chapter.get("plot") or last_chapter.get("outline"),
            novel_type=novel_type,
            idea=idea,
            world_setting=world_setting_str,
            characters=characters_str,
            persist_callbacks=gate_callbacks,
            rewrite_service=rewrite_service,
            chapter_index_in_volume=max(len(chapters) - 1, 0),
        )

        quality_scores = dict(gate_result.quality_scores)
        # 保留 KG 一致性分作参考维度（不参与 block 判定，block 已由 gate 决定）
        quality_scores["consistency"] = consistency_score
        # 翻译 gate quality_status → graph.py 路由期望的标记
        if gate_result.quality_status == "consistency_blocked":
            quality_scores["consistency_blocked"] = True
            quality_scores["status"] = "consistency_blocked"
        elif gate_result.quality_status == "unverified":
            quality_scores["status"] = "unverified"
        elif gate_result.quality_status in ("verified", "failed"):
            quality_scores["status"] = gate_result.quality_status

        # revision_requests：gate 不产出 L2 feedback/suggestions，用 L0 告警兜底
        # 供 human_review 展示（取前 5）。warnings 是 list[dict]（_l0_warnings 产出）。
        revision_requests = [
            f"【L0】: {w.get('message') or w.get('rule', '')}"
            for w in (gate_result.warnings or [])
        ][:5]

        logger.info(
            f"quality_gate_completed novel_id={novel_id} chapter={chapter_number} "
            f"status={gate_result.quality_status} overall={quality_scores.get('overall')} "
            f"l2_evaluated={gate_result.l2_evaluated} rewrite_attempted={gate_result.rewrite_attempted}"
        )

        return {
            **state,
            "quality_scores": quality_scores,
            "consistency_warnings": consistency_warnings,
            "revision_requests": revision_requests,
            "current_stage": "quality_check_completed",
            "kg_continuity_report": kg_continuity_report,
            "l0_results": l0_all,
            "state_delta": gate_result.state_delta,  # 短篇首次有 state_delta（Ticket 04 目标）
        }

    except Exception as e:
        logger.error(
            f"quality gate failed, falling back to unverified: {e}",
            exc_info=True,
        )
        unverified_scores["consistency"] = consistency_score
        if persist_quality_fn and novel_id:
            await persist_quality_fn(novel_id, chapter_number, unverified_scores, consistency_warnings)
        return {
            **state,
            "quality_scores": {**unverified_scores, "consistency_blocked": False},
            "consistency_warnings": consistency_warnings,
            "current_stage": "quality_check_completed",
            "kg_continuity_report": kg_continuity_report,
            "l0_results": l0_all,
        }
