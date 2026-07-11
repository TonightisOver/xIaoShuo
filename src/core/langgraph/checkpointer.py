"""Checkpointer 配置"""

import os

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.memory import MemorySaver


def get_checkpointer():
    """获取 Checkpointer

    根据环境变量 CHECKPOINTER_TYPE 选择合适的 Checkpointer：
    - development / memory: 使用 MemorySaver（内存存储，快速但不持久）
    - production / sqlite: 使用 SqliteSaver（持久化存储）

    Returns:
        Checkpointer 实例
    """
    checkpointer_type = os.getenv("CHECKPOINTER_TYPE", "memory").lower()

    if checkpointer_type in ("production", "sqlite"):
        db_path = os.getenv("CHECKPOINTER_DB_PATH", "./data/checkpoints.db")
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        return SqliteSaver.from_conn_string(db_path)

    return MemorySaver()
