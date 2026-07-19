"""服务模块"""

from .generation.novel_generator import generate_novel_background
from .tasks.task_manager import TaskManager, get_task_manager

__all__ = [
    "TaskManager",
    "get_task_manager",
    "generate_novel_background",
]
