# src/core/quality/risk.py
"""L1 风险分级 —— 基于 L0 规则结果决定是否调用 LLM 评审。

规则做闸门：正常章节只走 L0+L1，几乎不烧 Token；
只有高风险章触发 L2 LLM 全文评估，仅不达标章触发 L3 改写。
"""

from enum import StrEnum
from typing import Any

from src.core.config import get_settings


class RiskLevel(StrEnum):
    LOW = "low"       # 直接通过，不调 LLM
    MEDIUM = "medium"  # 按抽检比例决定是否调 LLM
    HIGH = "high"     # 必调 LLM 全文评审


def classify_risk(
    *,
    l0_rules: dict[str, Any],
    chapter_type: str | None = None,
    is_failed: bool = False,
) -> RiskLevel:
    """根据 L0 规则结果与章节类型分级。

    高风险条件（任一满足）：
      - 生成失败
      - 章节类型属于关键章节（开篇/高潮/反转/卷末/结局）
      - L0 出现 error 级违规
      - filler_flag 或 stalled_flag 为 True

    中风险：
      - L0 出现 warning 级违规

    低风险：
      - L0 干净且非关键章节
    """
    settings = get_settings()
    critical_types = set(getattr(settings, "QUALITY_CRITICAL_CHAPTER_TYPES", ()))

    if is_failed:
        return RiskLevel.HIGH

    if chapter_type and chapter_type in critical_types:
        return RiskLevel.HIGH

    violations = l0_rules.get("violations", [])
    if any(v.get("severity") == "error" for v in violations):
        return RiskLevel.HIGH
    if l0_rules.get("filler_flag") or l0_rules.get("stalled_flag"):
        return RiskLevel.HIGH
    if any(v.get("severity") == "warning" for v in violations):
        return RiskLevel.MEDIUM

    return RiskLevel.LOW


def should_invoke_l2(
    risk: RiskLevel,
    chapter_index_in_volume: int,
) -> bool:
    """决定是否对该章调用 L2 LLM 评审。

    - HIGH：必调（失败/关键章/严重告警）
    - MEDIUM：每 3 章抽 1 章（index%3==0，含第1章作为冷启动基线）
    - LOW：按 QUALITY_MODE 决定——
        high 模式每 3 章抽 1 章（更激进，质量优先）
        balanced 模式每 5 章抽 1 章（均衡）
        economy 模式不抽检（成本优先）
        未知模式保守不抽检

    注：index=0 时各取模均为 0，第1章会被抽检，作为冷启动基线校准。
    """
    settings = get_settings()
    mode = getattr(settings, "QUALITY_MODE", "balanced")

    if risk == RiskLevel.HIGH:
        return True
    if risk == RiskLevel.MEDIUM:
        return chapter_index_in_volume % 3 == 0
    # LOW
    if mode == "high":
        return chapter_index_in_volume % 3 == 0
    if mode == "balanced":
        return chapter_index_in_volume % 5 == 0
    return False  # economy 或未知模式：不抽检低风险
