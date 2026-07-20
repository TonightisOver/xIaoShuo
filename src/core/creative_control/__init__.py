"""Creative Control 包：阶段化创作过程控制层。

设计依据：docs/superpowers/specs/2026-07-21-creative-control-design.md
"""

from src.core.creative_control.contracts import (
    ARTIFACT_TYPES,
    ARTIFACT_TYPES_VERSIONED_GENERICALLY,
    ASSISTED_REVIEW_STAGES,
    CREATIVE_STAGES,
    CreationMode,
    ControlStatus,
    DEPENDENCY_GRAPH,
    OPERATION_ACTIONS,
    is_legal_transition,
    legal_transitions,
    stage_of,
)

__all__ = [
    "ARTIFACT_TYPES",
    "ARTIFACT_TYPES_VERSIONED_GENERICALLY",
    "ASSISTED_REVIEW_STAGES",
    "CREATIVE_STAGES",
    "CreationMode",
    "ControlStatus",
    "DEPENDENCY_GRAPH",
    "OPERATION_ACTIONS",
    "is_legal_transition",
    "legal_transitions",
    "stage_of",
]
