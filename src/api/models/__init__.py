"""API 数据模型"""

from .requests import CreateNovelRequest
from .responses import (
    TaskResponse,
    TaskDetailResponse,
    TaskListResponse,
    HealthResponse,
    ErrorResponse,
)

__all__ = [
    "CreateNovelRequest",
    "TaskResponse",
    "TaskDetailResponse",
    "TaskListResponse",
    "HealthResponse",
    "ErrorResponse",
]
