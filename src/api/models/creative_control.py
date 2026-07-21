"""Creative Control API 请求/响应模型。"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class EditArtifactRequest(BaseModel):
    """人工编辑产物（带乐观锁）。

    content 兼容两种形态：结构化产物（世界观/角色/大纲等）用 dict；
    正文（chapter）是纯文本，用 str。
    """

    content: dict[str, Any] | str
    expected_version: int = Field(ge=0)


class RegenerateRequest(BaseModel):
    """重新生成当前阶段产物。"""

    expected_version: int = Field(ge=0)
    scope: dict[str, Any] | None = None
    force: bool = False
    reason: str | None = Field(default=None, max_length=500)


class LockRequest(BaseModel):
    expected_version: int = Field(ge=0)


class SetStatusRequest(BaseModel):
    """approve / mark-stale 等通用状态转移。"""

    expected_version: int = Field(ge=0)
    reason: str | None = Field(default=None, max_length=500)


class GenerateScopeRequest(BaseModel):
    """生成范围控制。"""

    mode: Literal[
        "chapters", "volume", "continue",
        "blueprint_only", "content_only", "fix_quality",
    ] = "chapters"
    chapter_start: int | None = Field(default=None, ge=1)
    chapter_end: int | None = Field(default=None, ge=1)
    volume_number: int | None = Field(default=None, ge=1)
    chapter_number: int | None = Field(default=None, ge=1)
    issue_ids: list[str] | None = None
    skip_confirmed: bool = False
    respect_locked: bool = True
    words_per_chapter: int = Field(default=3000, ge=100)


class SetModeRequest(BaseModel):
    """切换创作模式。"""

    creation_mode: Literal["auto", "assisted", "manual"]


class ArtifactControlResponse(BaseModel):
    novel_id: str
    artifact_type: str
    artifact_id: str
    control_status: str
    locked: bool
    version: int
    stage: int
    awaiting_review: bool
    stale_reason: str | None = None
    generation_meta: dict[str, Any] | None = None
