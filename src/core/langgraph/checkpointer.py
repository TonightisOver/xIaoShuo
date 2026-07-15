"""Checkpointer 配置

支持两种模式：
- memory（默认）：MemorySaver，内存存储，进程重启丢失。开发/测试用。
- sqlite：AsyncSqliteSaver，持久化到文件。支持 LangGraph interrupt/resume
  跨进程恢复（HITL 审核必需）。需在 app lifespan 中调 setup_persistent_checkpointer()。

修复历史 bug：SqliteSaver.from_conn_string 返回 context manager，旧代码直接
return 它当 saver 用，sqlite 模式从未真正初始化（连接未建立）。改用
AsyncSqliteSaver 并在 lifespan 中 async with 持有。
"""

import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver

# 全局 checkpointer 实例（lifespan 启动时初始化 sqlite，或 fallback memory）
_checkpointer: Any = None
# sqlite async context 的退出钩子（lifespan shutdown 时调）
_sqlite_cm: Any = None


def get_checkpointer() -> Any:
    """获取 checkpointer。

    返回 lifespan 中初始化的持久化 checkpointer（sqlite 模式），
    或首次调用时 lazy 创建的 MemorySaver（memory 模式）。
    """
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = MemorySaver()
    return _checkpointer


async def setup_persistent_checkpointer() -> None:
    """在 app lifespan 启动时初始化持久化 checkpointer。

    仅当 CHECKPOINTER_TYPE=sqlite 时生效，创建 AsyncSqliteSaver 并 async with 持有。
    失败时降级到 MemorySaver（不阻断启动）。
    """
    global _checkpointer, _sqlite_cm

    checkpointer_type = os.getenv("CHECKPOINTER_TYPE", "memory").lower()
    if checkpointer_type not in ("production", "sqlite"):
        return  # memory 模式：lazy 创建即可

    db_path = os.getenv("CHECKPOINTER_DB_PATH", "./data/checkpoints.db")
    try:
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

        cm = AsyncSqliteSaver.from_conn_string(db_path)
        saver = await cm.__aenter__()
        try:
            await saver.setup()  # 建表（幂等）
        except Exception:
            pass
        _checkpointer = saver
        _sqlite_cm = cm
        import structlog
        structlog.get_logger(__name__).info(
            "persistent_checkpointer_initialized", type="sqlite", path=db_path
        )
    except Exception as e:
        import structlog
        structlog.get_logger(__name__).warning(
            "persistent_checkpointer_setup_failed_fallback_memory", error=str(e)
        )
        _checkpointer = MemorySaver()


async def teardown_persistent_checkpointer() -> None:
    """在 app lifespan 关闭时释放持久化 checkpointer 资源。"""
    global _checkpointer, _sqlite_cm
    if _sqlite_cm is not None:
        try:
            await _sqlite_cm.__aexit__(None, None, None)
        except Exception:
            pass
        _sqlite_cm = None
    _checkpointer = None
