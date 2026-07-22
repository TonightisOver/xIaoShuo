"""长篇章节检查点到恢复动作的纯逻辑映射。"""

from enum import StrEnum


class RecoveryAction(StrEnum):
    """恢复时下一项允许执行的章节动作。"""

    GENERATE = "generate"
    RUN_QUALITY = "run_quality"
    RUN_SIDE_EFFECTS = "run_side_effects"
    COMPLETE_CHAPTER = "complete_chapter"
    SKIP_COMPLETED = "skip_completed"


class RetryableChapterSideEffectError(RuntimeError):
    """Story Bible 或知识图谱写入失败，可从质量完成点重试。"""

    def __init__(self, component: str, chapter_number: int) -> None:
        self.component = component
        self.chapter_number = chapter_number
        super().__init__(
            f"required side effect failed: {component}, chapter={chapter_number}"
        )


_RESUME_ACTION: dict[str, RecoveryAction] = {
    "chapter_planned": RecoveryAction.GENERATE,
    "generation_started": RecoveryAction.GENERATE,
    "baseline_persisted": RecoveryAction.RUN_QUALITY,
    "quality_finalized": RecoveryAction.RUN_SIDE_EFFECTS,
    "side_effects_recorded": RecoveryAction.COMPLETE_CHAPTER,
    "chapter_completed": RecoveryAction.SKIP_COMPLETED,
}


def resolve_recovery_action(
    current_stage: str,
    checkpoint_chapter: int | None,
    target_chapter: int,
) -> RecoveryAction:
    """根据检查点阶段确定目标章节从哪一阶段继续。"""
    if checkpoint_chapter is not None and checkpoint_chapter > target_chapter:
        raise ValueError("checkpoint chapter is ahead of target chapter")
    if checkpoint_chapter != target_chapter:
        return RecoveryAction.GENERATE
    return _RESUME_ACTION.get(current_stage, RecoveryAction.GENERATE)
