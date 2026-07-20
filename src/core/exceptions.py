"""Domain-specific exceptions for the xIaoShuo backend."""

from __future__ import annotations


class PersistenceError(RuntimeError):
    """Raised when a critical persistence operation fails.

    Callers should treat this as a task-level failure: the requested write did
    not reach durable storage and the upstream generation flow must not be
    considered complete.
    """


class LeaseLost(Exception):
    """Worker 不再持有任务租约，必须停止后续写入。

    由 lease 守卫（assert_lease_held / advance_checkpoint）抛出。
    _run_claim 识别后干净退出，不调 release_claim / retry_or_fail_claim。
    """

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"lease lost for task {task_id}")


class CheckpointConflict(Exception):
    """checkpoint_version 乐观锁冲突：另一 worker 已推进检查点。"""

    def __init__(self, task_id: str, expected_version: int) -> None:
        self.task_id = task_id
        self.expected_version = expected_version
        super().__init__(
            f"checkpoint conflict for task {task_id}: "
            f"expected version {expected_version}"
        )


class StaleChapterVersionError(Exception):
    """The caller attempted to finalize against a no-longer-active baseline."""

    def __init__(
        self,
        novel_id: str,
        chapter_number: int,
        expected: int,
        actual: int | None,
    ) -> None:
        self.novel_id = novel_id
        self.chapter_number = chapter_number
        self.expected = expected
        self.actual = actual
        super().__init__(
            f"stale chapter version for {novel_id} ch{chapter_number}: "
            f"expected active={expected}, actual={actual}"
        )


class PausedExit(Exception):
    """Worker 在安全边界确认暂停后干净退出。

    与 LeaseLost 一样由 _run_claim 识别后跳过 release_claim。
    """

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"paused exit for task {task_id}")


# ---------------------------------------------------------------------------
# Creative Control：阶段控制层异常（映射 HTTP 409）
# 设计依据：docs/superpowers/specs/2026-07-21-creative-control-design.md
# ---------------------------------------------------------------------------


class ArtifactConflictError(Exception):
    """expected_version 与当前 control version 不符（HTTP 409）。

    前端应提示用户刷新、比较或合并，禁止基于旧页面覆盖新版本。
    """

    def __init__(
        self,
        novel_id: str,
        artifact_type: str,
        artifact_id: str,
        expected_version: int,
        current_version: int,
    ) -> None:
        self.novel_id = novel_id
        self.artifact_type = artifact_type
        self.artifact_id = artifact_id
        self.expected_version = expected_version
        self.current_version = current_version
        super().__init__(
            f"artifact conflict for {novel_id} {artifact_type}={artifact_id}: "
            f"expected version {expected_version}, current {current_version}"
        )


class ArtifactLockedError(Exception):
    """产物已锁定，且未带 force=True（HTTP 409）。

    锁定内容不被后台自动生成覆盖；重生成锁定内容必须显式确认。
    """

    def __init__(
        self, novel_id: str, artifact_type: str, artifact_id: str
    ) -> None:
        self.novel_id = novel_id
        self.artifact_type = artifact_type
        self.artifact_id = artifact_id
        super().__init__(
            f"artifact locked: {novel_id} {artifact_type}={artifact_id}"
        )


class ArtifactBusyError(Exception):
    """产物正在生成中，拒绝并发写（HTTP 409）。"""

    def __init__(
        self, novel_id: str, artifact_type: str, artifact_id: str
    ) -> None:
        self.novel_id = novel_id
        self.artifact_type = artifact_type
        self.artifact_id = artifact_id
        super().__init__(
            f"artifact busy (generating): {novel_id} {artifact_type}={artifact_id}"
        )

