"""LangGraph 流程图定义"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.core.langgraph.nodes import (
    chapter_generation,
    character_design,
    human_review,
    idea_expansion,
    outline_generation,
    quality_check,
    world_building,
)
from src.core.langgraph.state import NovelState

MAX_REGENERATION_ATTEMPTS = 2


def should_continue(state: NovelState) -> str:
    """条件路由：根据质量分数决定下一步

    Args:
        state: 当前状态

    Returns:
        下一个节点的名称
    """
    quality_score = state.get("quality_scores", {}).get("overall", 0)
    regeneration_count = state.get("_regeneration_count", 0)
    if quality_score >= 0.8 or regeneration_count >= MAX_REGENERATION_ATTEMPTS:
        return "human_review"
    else:
        return "regenerate"


def create_novel_graph() -> CompiledStateGraph:
    """创建小说创作流程图

    Returns:
        编译后的 StateGraph
    """
    # 创建图
    graph = StateGraph(NovelState)

    # 添加节点
    graph.add_node("idea_expansion", idea_expansion.node)
    graph.add_node("world_building", world_building.node)
    graph.add_node("character_design", character_design.node)
    graph.add_node("outline_generation", outline_generation.node)
    graph.add_node("chapter_generation", chapter_generation.node)
    graph.add_node("quality_check", quality_check.node)
    graph.add_node("human_review", human_review.node)

    # 设置入口点
    graph.set_entry_point("idea_expansion")

    # 添加边
    graph.add_edge("idea_expansion", "world_building")
    graph.add_edge("world_building", "character_design")
    graph.add_edge("character_design", "outline_generation")
    graph.add_edge("outline_generation", "chapter_generation")
    graph.add_edge("chapter_generation", "quality_check")

    # 添加条件路由
    graph.add_conditional_edges(
        "quality_check",
        should_continue,
        {
            "human_review": "human_review",
            "regenerate": "chapter_generation",
        },
    )

    graph.add_edge("human_review", END)

    # 配置 checkpointer
    checkpointer = MemorySaver()

    return graph.compile(checkpointer=checkpointer)


def _should_continue_volume(state: NovelState) -> str:
    """条件路由：根据质量分数决定下一步（卷级）

    Args:
        state: 当前状态

    Returns:
        下一个节点的名称
    """
    quality_score = state.get("quality_scores", {}).get("overall", 0)
    regeneration_count = state.get("_regeneration_count", 0)
    if quality_score >= 0.8 or regeneration_count >= MAX_REGENERATION_ATTEMPTS:
        return "review"
    else:
        return "regenerate"


def create_volume_generation_graph() -> CompiledStateGraph:
    """创建单卷生成流程图

    用于百万字长篇的逐卷生成，包含7个标准节点：
    idea_expansion -> world_building -> character_design -> outline_generation
    -> chapter_generation -> quality_check -> human_review

    Returns:
        编译后的 StateGraph
    """
    graph = StateGraph(NovelState)

    # 添加节点
    graph.add_node("idea_expansion", idea_expansion.node)
    graph.add_node("world_building", world_building.node)
    graph.add_node("character_design", character_design.node)
    graph.add_node("outline_generation", outline_generation.node)
    graph.add_node("chapter_generation", chapter_generation.node)
    graph.add_node("quality_check", quality_check.node)
    graph.add_node("human_review", human_review.node)

    # 设置入口点
    graph.set_entry_point("idea_expansion")

    # 添加边
    graph.add_edge("idea_expansion", "world_building")
    graph.add_edge("world_building", "character_design")
    graph.add_edge("character_design", "outline_generation")
    graph.add_edge("outline_generation", "chapter_generation")
    graph.add_edge("chapter_generation", "quality_check")

    # 添加条件路由
    graph.add_conditional_edges(
        "quality_check",
        _should_continue_volume,
        {
            "review": "human_review",
            "regenerate": "chapter_generation",
        },
    )

    graph.add_edge("human_review", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)


def create_long_form_graph() -> CompiledStateGraph:
    """创建百万字长篇生成主图

    三级大纲 + 按卷流式生成架构：
    1. 总纲生成 (master_outline_generation)
    2. 卷纲细化 (volume_outline_generation) -- 由外部循环调用
    3. 卷内7节点流水线 (volume_generation_graph) -- 由外部循环调用

    本图只包含总纲生成节点，卷纲和卷内流水线由编排函数控制。

    Returns:
        编译后的 StateGraph
    """
    graph = StateGraph(NovelState)

    # 添加节点
    graph.add_node(
        "master_outline_generation",
        outline_generation.master_outline_generation_node,
    )

    # 设置入口点
    graph.set_entry_point("master_outline_generation")

    # 单节点直接结束
    graph.add_edge("master_outline_generation", END)

    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer)
