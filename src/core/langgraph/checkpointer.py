"""Checkpointer 配置"""


from langgraph.checkpoint.memory import MemorySaver


def get_checkpointer() -> MemorySaver:
    """获取 Checkpointer

    根据环境变量选择合适的 Checkpointer：
    - 开发环境：使用 MemorySaver（内存存储，快速但不持久）
    - 生产环境：使用 SqliteSaver（持久化存储，暂未实现）

    Returns:
        Checkpointer 实例
    """
    # 当前仅支持 MemorySaver
    # TODO: 生产环境集成 SqliteSaver
    return MemorySaver()
