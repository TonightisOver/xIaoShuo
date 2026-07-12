"""LangGraph 节点单元测试"""

from unittest.mock import MagicMock, patch

import pytest

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


def create_initial_state() -> NovelState:
    """创建初始状态"""
    return {
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


@pytest.mark.asyncio
async def test_idea_expansion_node():
    """测试创意扩展节点"""
    state = create_initial_state()
    result = await idea_expansion.node(state)

    assert "扩展后的创意" in result["idea"] or result["idea"] != state["idea"]
    assert result["current_stage"] == "idea_expansion_completed"


@pytest.mark.asyncio
async def test_world_building_node():
    """测试世界观构建节点"""
    state = create_initial_state()
    result = await world_building.node(state)

    assert result["world_setting"] is not None
    assert "background" in result["world_setting"]
    assert result["current_stage"] == "world_building_completed"


@pytest.mark.asyncio
async def test_character_design_node():
    """测试人物设计节点"""
    state = create_initial_state()
    state["world_setting"] = {"background": "test", "rules": "test"}
    result = await character_design.node(state)

    assert len(result["characters"]) > 0
    assert len(result["relationships"]) > 0
    assert result["current_stage"] == "character_design_completed"


@pytest.mark.asyncio
async def test_outline_generation_node():
    """测试大纲生成节点"""
    state = create_initial_state()
    state["world_setting"] = {"background": "test"}
    state["characters"] = [{"name": "test"}]
    result = await outline_generation.node(state)

    assert result["outline"] is not None
    assert len(result["chapter_outlines"]) > 0
    assert result["current_stage"] == "outline_generation_completed"


@pytest.mark.asyncio
async def test_chapter_generation_node():
    """测试章节生成节点"""
    state = create_initial_state()
    state["world_setting"] = {"background": "test"}
    state["characters"] = [{"name": "test"}]
    state["chapter_outlines"] = [{"chapter": 1, "title": "test", "plot": "test"}]
    result = await chapter_generation.node(state)

    assert len(result["chapters"]) > 0
    assert result["chapters"][0]["chapter"] == 1
    assert result["current_stage"] == "chapter_generation_completed"


@pytest.mark.asyncio
async def test_quality_check_node():
    """测试质量检查节点"""
    state = create_initial_state()
    result = await quality_check.node(state)

    assert "overall" in result["quality_scores"]
    assert result["quality_scores"]["overall"] > 0
    assert result["current_stage"] == "quality_check_completed"


def test_human_review_node():
    """测试人工审核节点（真 HITL 模式：HITL_AUTO_APPROVE=False 时返回 pending）"""
    from src.core.config import get_settings
    with patch("src.core.langgraph.nodes.human_review.get_settings") as ms:
        ms.return_value = MagicMock(HITL_AUTO_APPROVE=False)
        state = create_initial_state()
        result = human_review.node(state)

    assert result["approval_status"] == "pending"
    assert result["current_stage"] == "human_review"


def test_human_review_auto_approve():
    """测试 auto-approve 模式：HITL_AUTO_APPROVE=True 时直接通过"""
    with patch("src.core.langgraph.nodes.human_review.get_settings") as ms:
        ms.return_value = MagicMock(HITL_AUTO_APPROVE=True)
        state = create_initial_state()
        state["chapters"] = [{"chapter": 1, "title": "第一章", "content": "..."}]
        result = human_review.node(state)

    assert result["approval_status"] == "approved"
    assert result["current_stage"] == "approved"
    assert "review_data" in result
