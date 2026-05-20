"""API 响应模型"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class TaskResponse(BaseModel):
    """任务创建响应"""

    task_id: str = Field(..., description="任务 ID")
    status: str = Field(..., description="任务状态")
    created_at: datetime = Field(..., description="创建时间")
    estimated_duration_minutes: int = Field(..., description="预计耗时（分钟）")


class TaskProgress(BaseModel):
    """任务进度"""

    current_stage: str = Field(..., description="当前阶段")
    completed_chapters: int = Field(..., description="已完成章节数")
    total_chapters: int = Field(default=0, description="总章节数")
    percentage: int = Field(..., description="完成百分比")


class TaskDetailResponse(BaseModel):
    """任务详情响应"""

    task_id: str = Field(..., description="任务 ID")
    novel_id: str | None = Field(None, description="关联小说项目 ID")
    status: str = Field(..., description="任务状态: pending/running/completed/failed")
    progress: TaskProgress | None = Field(None, description="任务进度")
    created_at: datetime = Field(..., description="创建时间")
    started_at: datetime | None = Field(None, description="开始时间")
    completed_at: datetime | None = Field(None, description="完成时间")
    estimated_completion: datetime | None = Field(None, description="预计完成时间")
    result: dict[str, Any] | None = Field(None, description="生成结果")
    errors: list[str] = Field(default_factory=list, description="错误列表")


class TaskSummary(BaseModel):
    """任务摘要"""

    task_id: str
    novel_id: str | None = None
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    novel_type: str | None = None
    target_words: int | None = None
    idea: str | None = None


class TaskListResponse(BaseModel):
    """任务列表响应"""

    tasks: list[TaskSummary]
    total: int
    limit: int
    offset: int


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = Field(..., description="服务状态")
    version: str = Field(..., description="API 版本")
    timestamp: datetime = Field(..., description="当前时间")


class ErrorDetail(BaseModel):
    """错误详情"""

    code: str = Field(..., description="错误代码")
    message: str = Field(..., description="错误消息")
    details: dict[str, Any] | None = Field(None, description="详细信息")


class ErrorResponse(BaseModel):
    """错误响应"""

    error: ErrorDetail


# --- Project / Novel response models ---


class NovelSummaryResponse(BaseModel):
    """小说列表项"""

    novel_id: str
    title: str | None = None
    novel_type: str
    target_words: int
    status: str
    writing_style: str
    created_at: datetime
    updated_at: datetime


class NovelDetailResponse(NovelSummaryResponse):
    """小说详情"""

    idea: str
    custom_style_description: str | None = None
    writing_style_prompt: str | None = None
    completed_at: datetime | None = None


class NovelListResponse(BaseModel):
    """小说列表 + 分页"""

    novels: list[NovelSummaryResponse]
    total: int
    limit: int
    offset: int


class CreateResponse(BaseModel):
    """创建资源响应"""

    novel_id: str
    status: str


class StatusResponse(BaseModel):
    """通用状态响应"""

    status: str


class ChapterResponse(BaseModel):
    """章节响应"""

    novel_id: str
    chapter_number: int
    title: str | None = None
    content: str | None = None
    word_count: int = 0
    status: str
    volume_number: int | None = None
    updated_at: datetime


class VolumeResponse(BaseModel):
    """卷响应"""

    novel_id: str
    volume_number: int
    title: str | None = None
    summary: str | None = None
    status: str
    chapter_start: int | None = None
    chapter_end: int | None = None
    updated_at: datetime

