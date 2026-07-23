"""Creative Control 契约层 —— 阶段/产物/状态/依赖图的唯一权威定义。

设计依据：docs/superpowers/specs/2026-07-21-creative-control-design.md

本模块是纯逻辑、无 DB 依赖的契约定义。核心层（gate/evaluator 等）与 API 层
都从这里导入，避免散落多份阶段/状态定义。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class CreationMode(StrEnum):
    """创作模式。auto=连续生成(现状)；assisted=关键阶段等确认；manual=逐阶段。"""

    AUTO = "auto"
    ASSISTED = "assisted"
    MANUAL = "manual"


class ControlStatus(StrEnum):
    """统一控制状态（用户硬约束的 8 态）。"""

    DRAFT = "draft"
    GENERATED = "generated"
    EDITED = "edited"
    APPROVED = "approved"
    LOCKED = "locked"
    STALE = "stale"
    GENERATING = "generating"
    FAILED = "failed"


# 辅助模式下需要等待确认的阶段（1/4/7/9）。
ASSISTED_REVIEW_STAGES: frozenset[int] = frozenset({1, 4, 7, 9})


@dataclass(frozen=True)
class CreativeStage:
    """一个创作阶段。"""

    number: int
    name: str
    artifact_type: str


# 10 阶段（设计文档定义）。
CREATIVE_STAGES: tuple[CreativeStage, ...] = (
    CreativeStage(1, "创意与项目参数", "novel"),
    CreativeStage(2, "世界观与力量体系", "world"),
    CreativeStage(3, "角色设定", "character"),
    CreativeStage(4, "全书总纲", "master_outline"),
    CreativeStage(5, "卷纲", "volume_outline"),
    CreativeStage(6, "章节蓝图", "blueprint"),
    CreativeStage(7, "章节正文", "chapter"),
    CreativeStage(8, "正文质量检查", "quality"),
    CreativeStage(9, "人工确认与版本采纳", "chapter_version"),
    CreativeStage(10, "定稿", "final"),
)

# 全部产物类型。
ARTIFACT_TYPES: tuple[str, ...] = tuple(s.artifact_type for s in CREATIVE_STAGES)

# 合法操作类型（OperationLog.action 取值集合，共 10 类）。
OPERATION_ACTIONS: tuple[str, ...] = (
    "edit",
    "generate",
    "regenerate",
    "lock",
    "unlock",
    "approve",
    "rollback",
    "adopt_candidate",
    "keep_baseline",
    "update_params",
)

# 走通用 ArtifactVersionStore 版本化的产物类型（正文除外，正文复用 ChapterVersion）。
ARTIFACT_TYPES_VERSIONED_GENERICALLY: frozenset[str] = frozenset(
    {"world", "character", "master_outline", "volume_outline", "blueprint"}
)

# 产物类型 -> 所属阶段号。
_STAGE_OF: dict[str, int] = {
    "novel": 1,
    "world": 2,
    "character": 3,
    "master_outline": 4,
    "volume_outline": 5,
    "blueprint": 6,
    "chapter": 7,
    "chapter_version": 7,
    "quality": 8,
    "final": 10,
}


def stage_of(artifact_type: str) -> int:
    """返回产物类型所属的阶段号。未知类型返回 0。"""
    return _STAGE_OF.get(artifact_type, 0)


# 依赖图：上游 -> 直接下游产物类型。
# 用于 ImpactAnalyzer 计算上游修改的受影响范围。
# 注意：chapter 无下游（改正文只产生新版本 + unverified，不级联重生成下游）。
DEPENDENCY_GRAPH: dict[str, list[str]] = {
    "novel": ["world", "master_outline"],
    "world": ["character", "master_outline"],
    "character": ["master_outline"],
    "master_outline": ["volume_outline"],
    "volume_outline": ["blueprint", "chapter"],
    "blueprint": ["chapter"],
    "chapter": [],
    # chapter_version / quality / final 无生成级下游
}


# 控制状态合法转换表（不含自环；STALE 对所有状态可达，单独处理）。
_TRANSITIONS: dict[ControlStatus, frozenset[ControlStatus]] = {
    ControlStatus.DRAFT: frozenset({ControlStatus.GENERATING}),
    ControlStatus.GENERATING: frozenset(
        {ControlStatus.GENERATED, ControlStatus.FAILED}
    ),
    ControlStatus.GENERATED: frozenset(
        {ControlStatus.EDITED, ControlStatus.APPROVED}
    ),
    ControlStatus.EDITED: frozenset(
        {ControlStatus.APPROVED, ControlStatus.GENERATING}
    ),
    ControlStatus.APPROVED: frozenset(
        {ControlStatus.EDITED, ControlStatus.LOCKED, ControlStatus.GENERATING}
    ),
    ControlStatus.LOCKED: frozenset({ControlStatus.GENERATING}),
    ControlStatus.STALE: frozenset(
        {ControlStatus.GENERATING, ControlStatus.APPROVED}
    ),
    ControlStatus.FAILED: frozenset({ControlStatus.GENERATING}),
}


def legal_transitions(status: ControlStatus) -> frozenset[ControlStatus]:
    """返回从给定状态可合法转移到的状态集合（含 STALE，不含自环）。

    STALE 对所有状态可达（上游变更随时可能把任何产物标记过期）。
    """
    base = _TRANSITIONS.get(status, frozenset())
    return base | {ControlStatus.STALE}


def is_legal_transition(from_status: ControlStatus, to_status: ControlStatus) -> bool:
    """是否是合法状态转移。STALE->STALE 不允许（无自环）。"""
    if from_status is to_status:
        return False
    return to_status in legal_transitions(from_status)
