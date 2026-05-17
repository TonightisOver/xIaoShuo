"""API 数据模型"""

from .requests import CreateNovelRequest
from .responses import (
    ErrorResponse,
    HealthResponse,
    TaskDetailResponse,
    TaskListResponse,
    TaskResponse,
)

__all__ = [
    "CreateNovelRequest",
    "TaskResponse",
    "TaskDetailResponse",
    "TaskListResponse",
    "HealthResponse",
    "ErrorResponse",
]
