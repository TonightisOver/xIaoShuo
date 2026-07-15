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
    api_key_configured: bool = Field(True, description="API Key 是否已配置（非占位符）")


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
    active_task_id: str | None = None


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


# --- Long-form novel models ---


class LongFormTaskResponse(BaseModel):
    """长篇任务响应"""

    task_id: str = Field(..., description="任务 ID")
    novel_id: str = Field(..., description="小说 ID")
    status: str = Field(..., description="任务状态")
    total_volumes: int = Field(..., description="总卷数")
    total_chapters: int = Field(..., description="总章节数")
    target_words: int = Field(..., description="目标总字数")
    volumes_completed: int = Field(default=0, description="已完成卷数")
    chapters_completed: int = Field(default=0, description="已完成章节数")
    created_at: datetime = Field(..., description="创建时间")
    estimated_duration_hours: float = Field(default=0.0, description="预计耗时（小时）")


class VolumeQualityReport(BaseModel):
    """单卷质量报告"""

    volume_number: int = Field(..., description="卷号")
    chapter_count: int = Field(..., description="章节数")
    total_word_count: int = Field(..., description="总字数")
    avg_scores: dict[str, float] = Field(default_factory=dict, description="8维度均值")
    score_trends: dict[str, list[float]] = Field(
        default_factory=dict, description="8维度按章节的变化序列"
    )
    warnings: list[str] = Field(default_factory=list, description="质量警告")
    filler_chapters: list[int] = Field(
        default_factory=list, description="检测到的注水章节号"
    )
    stalled_chapters: list[int] = Field(
        default_factory=list, description="主线停滞章节号"
    )
    has_unverified: bool = Field(
        default=False, description="本卷是否含未评估章节（生成失败或从未评分）"
    )


class QualityReport(BaseModel):
    """完整质量报告"""

    novel_id: str = Field(..., description="小说 ID")
    total_volumes: int = Field(..., description="总卷数")
    completed_volumes: int = Field(..., description="已完成卷数")
    overall_avg_scores: dict[str, float] = Field(
        default_factory=dict, description="全局8维度均值"
    )
    volume_reports: list[VolumeQualityReport] = Field(
        default_factory=list, description="各卷质量报告"
    )
    foreshadow_summary: dict[str, Any] = Field(
        default_factory=dict, description="伏笔追踪"
    )
    character_appearance: dict[str, Any] = Field(
        default_factory=dict, description="人物出场统计"
    )


class FillerDetectionResult(BaseModel):
    """注水检测结果"""

    novel_id: str = Field(..., description="小说 ID")
    total_chapters: int = Field(..., description="总章节数")
    filler_chapters: list[dict[str, Any]] = Field(
        default_factory=list, description="注水章节列表"
    )
    filler_ratio: float = Field(default=0.0, description="注水比例")
    recommendations: list[str] = Field(default_factory=list, description="处理建议")


class ForeshadowTrackerResult(BaseModel):
    """伏笔追踪结果"""

    novel_id: str = Field(..., description="小说 ID")
    total_foreshadows: int = Field(..., description="总伏笔数")
    planted: list[dict[str, Any]] = Field(
        default_factory=list, description="已种下的伏笔"
    )
    resolved: list[dict[str, Any]] = Field(
        default_factory=list, description="已回收的伏笔"
    )
    dangling: list[dict[str, Any]] = Field(
        default_factory=list, description="悬挂未回收的伏笔"
    )
    resolution_rate: float = Field(default=0.0, description="回收率")


class LongFormProgressResponse(BaseModel):
    """百万字长篇进度响应"""

    novel_id: str = Field(..., description="小说 ID")
    total_volumes: int = Field(..., description="总卷数")
    completed_volumes: int = Field(default=0, description="已完成卷数")
    current_volume: int | None = Field(None, description="当前卷号")
    total_chapters: int = Field(..., description="总章节数")
    chapters_completed: int = Field(default=0, description="已完成章节数")
    total_word_count: int = Field(default=0, description="已生成总字数")
    target_words: int = Field(..., description="目标总字数")
    progress_percentage: float = Field(default=0.0, description="完成百分比")
    volume_details: list[dict[str, Any]] = Field(
        default_factory=list, description="各卷详情"
    )
    errors: list[str] = Field(default_factory=list, description="错误列表")

