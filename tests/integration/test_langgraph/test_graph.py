"""LangGraph 流程集成测试"""

import pytest

from src.core.langgraph.graph import create_novel_graph
from src.core.langgraph.state import NovelState


@pytest.mark.asyncio
async def test_novel_creation_flow():
    """测试完整的小说创作流程"""
    # 创建图
    graph = create_novel_graph()

    # 初始状态
    initial_state: NovelState = {
        "project_id": "test-123",
        "novel_type": "玄幻",
        "target_words": 100000,
        "idea": "一个修仙者的故事",
        "world_setting": None,
        "characters": [],
        "relationships": {},
        "outline": None,
        "chapter_outlines": [],
        "chapters": [],
        "current_stage": "init",
        "approval_status": "pending",
        "revision_requests": [],
        "quality_scores": {},
        "errors": [],
    }

    # 执行流程
    config = {"configurable": {"thread_id": "test-thread"}}
    final_state = await graph.ainvoke(initial_state, config=config)

    # 验证结果
    assert final_state["current_stage"] == "human_review"
    assert final_state["world_setting"] is not None
    assert len(final_state["characters"]) > 0
    assert final_state["outline"] is not None
    assert len(final_state["chapters"]) > 0
    assert "overall" in final_state["quality_scores"]


@pytest.mark.asyncio
async def test_quality_check_routing():
    """测试质量检查路由"""
    from src.core.langgraph.graph import should_continue

    # 测试高质量分数 -> human_review
    high_quality_state: NovelState = {
        "project_id": "test",
        "novel_type": "玄幻",
        "target_words": 100000,
        "idea": "test",
        "world_setting": None,
        "characters": [],
        "relationships": {},
        "outline": None,
        "chapter_outlines": [],
        "chapters": [],
        "current_stage": "quality_check",
        "approval_status": "pending",
        "revision_requests": [],
        "quality_scores": {"overall": 0.85},
        "errors": [],
    }
    assert should_continue(high_quality_state) == "human_review"

    # 测试低质量分数 -> regenerate
    low_quality_state: NovelState = {
        **high_quality_state,
        "quality_scores": {"overall": 0.6},
    }
    assert should_continue(low_quality_state) == "regenerate"
