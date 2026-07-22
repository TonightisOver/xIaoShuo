"""长篇章节检查点恢复动作解析测试。"""

import pytest

from src.api.services.generation.chapter_recovery import (
    RecoveryAction,
    resolve_recovery_action,
)


@pytest.mark.parametrize(
    ("stage", "checkpoint_chapter", "target_chapter", "expected"),
    [
        ("chapter_planned", 7, 7, RecoveryAction.GENERATE),
        ("generation_started", 7, 7, RecoveryAction.GENERATE),
        ("baseline_persisted", 7, 7, RecoveryAction.RUN_QUALITY),
        ("quality_finalized", 7, 7, RecoveryAction.RUN_SIDE_EFFECTS),
        ("side_effects_recorded", 7, 7, RecoveryAction.COMPLETE_CHAPTER),
        ("chapter_completed", 7, 7, RecoveryAction.SKIP_COMPLETED),
        ("volume_end", 7, 8, RecoveryAction.GENERATE),
        ("task_end", 7, 8, RecoveryAction.GENERATE),
    ],
)
def test_resolve_recovery_action(
    stage: str,
    checkpoint_chapter: int,
    target_chapter: int,
    expected: RecoveryAction,
) -> None:
    assert (
        resolve_recovery_action(stage, checkpoint_chapter, target_chapter)
        is expected
    )


def test_recovery_rejects_checkpoint_ahead_of_target() -> None:
    with pytest.raises(ValueError, match="checkpoint chapter"):
        resolve_recovery_action("quality_finalized", 8, 7)

