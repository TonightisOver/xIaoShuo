# src/core/quality/gate.py
"""质量门禁编排器 —— 在长篇逐章生成后跑完整漏斗。

编排顺序：抽取 state_delta → L0 规则 → L1 风险分级 → (按需) L2 全文评审 → (按需) L3 候选择优。

核心不变量：任何环节失败都不阻塞调用方——最坏返回 quality_status=unverified，
final_content 为原内容。单章 Token 预算耗尽转人工。
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import structlog

from src.core.config import get_settings
from src.core.quality.evaluator import evaluate_chapter_quality
from src.core.quality.risk import RiskLevel, classify_risk, should_invoke_l2
from src.core.quality.rules import run_l0_rules
from src.core.quality.state_delta import extract_state_delta

logger = structlog.get_logger(__name__)

# 一致性维度低于此值视为 block（硬门禁），无论 overall 多少都不通过
CONSISTENCY_BLOCK_THRESHOLD = 0.4


@dataclass
class GatePersistCallbacks:
    """gate 持久化回调（注入，不直接碰 DB）。"""
    update_state_delta: Callable[[str, int, dict], Awaitable[None]]
    update_quality_status: Callable[[str, int, str], Awaitable[None]]
    persist_quality_scores: Callable[[str, int, dict, list], Awaitable[None]]
    detect_bible_conflicts: Callable | None = None


@dataclass
class GateResult:
    final_content: str
    quality_status: str  # verified / unverified / consistency_blocked / failed
    quality_scores: dict = field(default_factory=dict)
    state_delta: dict = field(default_factory=dict)
    l0_result: dict = field(default_factory=dict)
    risk_level: RiskLevel | None = None
    l2_evaluated: bool = False
    rewrite_attempted: bool = False
    rewrite_improved: bool | None = None
    tokens_used: int = 0
    warnings: list[dict] = field(default_factory=list)


async def run_quality_gate(
    *,
    novel_id: str,
    chapter_number: int,
    chapter_result: dict,
    chapter_outline: dict | None,
    novel_type: str,
    idea: str,
    world_setting: str,
    characters: str,
    persist_callbacks: GatePersistCallbacks,
    rewrite_service: Any | None = None,
    chapter_index_in_volume: int = 0,
) -> GateResult:
    """对单章生成结果跑完整质量漏斗。

    永不抛异常：任何失败返回可用 GateResult（最坏 unverified + 原内容）。
    """
    content = chapter_result.get("content", "") or ""
    word_count = chapter_result.get("word_count", len(content))
    chapter_type = chapter_result.get("chapter_type")
    is_failed = bool(chapter_result.get("generation_failed") or chapter_result.get("paused"))

    # 1. 生成失败/暂停 → 直接标记 failed，跳过漏斗
    if is_failed:
        logger.info("gate_chapter_failed_skip", novel_id=novel_id, chapter=chapter_number)
        await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "failed")
        return GateResult(
            final_content=content, quality_status="failed",
            quality_scores={"overall": None, "status": "unverified"},
        )

    # 2. 抽取 state_delta（flash，必做）→ 持久化
    state_delta: dict = {}
    try:
        state_delta = await extract_state_delta(
            chapter_content=content, chapter_number=chapter_number,
            novel_type=novel_type, world_setting=world_setting, characters=characters,
        )
        await _safe(persist_callbacks.update_state_delta, novel_id, chapter_number, state_delta)
    except Exception as e:
        logger.warning("gate_state_delta_failed", novel_id=novel_id, chapter=chapter_number, error=str(e))
        state_delta = {"_unverified": True}

    # 3. L0 规则门禁（零 Token）
    avg_word = float(word_count)
    l0 = run_l0_rules(
        content=content, word_count=word_count, avg_word_count=avg_word,
        chapter_outline=chapter_outline, chapter_number=chapter_number,
    )

    # 4. L1 风险分级
    risk = classify_risk(l0_rules=l0, chapter_type=chapter_type, is_failed=False)

    # 5. 决定是否走 L2
    if not should_invoke_l2(risk, chapter_index_in_volume):
        await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "verified")
        return GateResult(
            final_content=content, quality_status="verified",
            quality_scores={"overall": None}, state_delta=state_delta,
            l0_result=l0, risk_level=risk, l2_evaluated=False,
            warnings=_l0_warnings(l0),
        )

    # 6. L2 全文评审
    try:
        eval_result = await evaluate_chapter_quality(
            chapter_content=content, chapter_number=chapter_number,
            novel_type=novel_type, idea=idea, world_setting=world_setting,
            characters=characters, default_score=0.5,
        )
    except Exception as e:
        logger.warning("gate_l2_failed", novel_id=novel_id, chapter=chapter_number, error=str(e))
        await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "unverified")
        return GateResult(
            final_content=content, quality_status="unverified",
            quality_scores={"overall": None, "status": "unverified"},
            state_delta=state_delta, l0_result=l0, risk_level=risk,
            l2_evaluated=True, warnings=_l0_warnings(l0),
        )

    scores = eval_result.to_scores_dict()

    # 6a. 一致性硬门禁
    char_cons = scores.get("character_consistency")
    world_cons = scores.get("world_consistency")
    if (isinstance(char_cons, (int, float)) and char_cons < CONSISTENCY_BLOCK_THRESHOLD) or \
       (isinstance(world_cons, (int, float)) and world_cons < CONSISTENCY_BLOCK_THRESHOLD):
        await _safe(persist_callbacks.persist_quality_scores, novel_id, chapter_number, scores, _l0_warnings(l0))
        await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "consistency_blocked")
        return GateResult(
            final_content=content, quality_status="consistency_blocked",
            quality_scores=scores, state_delta=state_delta, l0_result=l0,
            risk_level=risk, l2_evaluated=True, rewrite_attempted=False,
            warnings=_l0_warnings(l0),
        )

    # 6b. 达标 → verified
    settings = get_settings()
    threshold = getattr(settings, "QUALITY_THRESHOLD", 0.7)
    overall = scores.get("overall")
    if isinstance(overall, (int, float)) and overall >= threshold:
        await _safe(persist_callbacks.persist_quality_scores, novel_id, chapter_number, scores, _l0_warnings(l0))
        await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "verified")
        return GateResult(
            final_content=content, quality_status="verified", quality_scores=scores,
            state_delta=state_delta, l0_result=l0, risk_level=risk,
            l2_evaluated=True, warnings=_l0_warnings(l0),
        )

    # 7. L2 不达标 → L3
    if rewrite_service is None:
        await _safe(persist_callbacks.persist_quality_scores, novel_id, chapter_number, scores, _l0_warnings(l0))
        await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "unverified")
        return GateResult(
            final_content=content, quality_status="unverified", quality_scores=scores,
            state_delta=state_delta, l0_result=l0, risk_level=risk,
            l2_evaluated=True, rewrite_attempted=False, warnings=_l0_warnings(l0),
        )

    max_rewrite = getattr(settings, "QUALITY_MAX_REWRITE_PER_CHAPTER", 2)
    rewrite_result = None
    try:
        rewrite_result = await rewrite_service.auto_improve_chapter(
            novel_id=novel_id, chapter_number=chapter_number,
            max_iterations=max_rewrite, target_score=threshold,
        )
    except Exception as e:
        logger.warning("gate_l3_failed", novel_id=novel_id, chapter=chapter_number, error=str(e))

    improved = bool(rewrite_result and rewrite_result.get("reached_target"))
    if improved:
        final_scores = rewrite_result.get("final_scores", scores)
        await _safe(persist_callbacks.persist_quality_scores, novel_id, chapter_number, final_scores, _l0_warnings(l0))
        await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "verified")
        return GateResult(
            final_content=content, quality_status="verified", quality_scores=final_scores,
            state_delta=state_delta, l0_result=l0, risk_level=risk,
            l2_evaluated=True, rewrite_attempted=True, rewrite_improved=True,
            warnings=_l0_warnings(l0),
        )
    await _safe(persist_callbacks.persist_quality_scores, novel_id, chapter_number, scores, _l0_warnings(l0))
    await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "unverified")
    return GateResult(
        final_content=content, quality_status="unverified", quality_scores=scores,
        state_delta=state_delta, l0_result=l0, risk_level=risk,
        l2_evaluated=True, rewrite_attempted=True, rewrite_improved=False,
        warnings=_l0_warnings(l0),
    )


async def _safe(fn, *args, **kwargs):
    """安全调用回调，失败只 log 不抛。"""
    try:
        await fn(*args, **kwargs)
    except Exception as e:
        logger.warning("gate_persist_failed", error=str(e))


def _l0_warnings(l0: dict) -> list[dict]:
    return [
        {"severity": v.get("severity", "warning"), "type": v.get("type"), "message": v.get("message")}
        for v in l0.get("violations", [])
    ]
