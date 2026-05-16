"""LangGraph graph 模块单元测试"""

from src.core.langgraph.graph import create_novel_graph, should_continue
from src.core.langgraph.state import NovelState


def test_should_continue_high_quality() -> None:
    """测试高质量分数路由到 human_review"""
    state: NovelState = {
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
    assert should_continue(state) == "human_review"


def test_should_continue_low_quality() -> None:
    """测试低质量分数路由到 regenerate"""
    state: NovelState = {
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
        "quality_scores": {"overall": 0.6},
        "errors": [],
    }
    assert should_continue(state) == "regenerate"


def test_should_continue_boundary() -> None:
    """测试边界值（0.8）路由到 human_review"""
    state: NovelState = {
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
        "quality_scores": {"overall": 0.8},
        "errors": [],
    }
    assert should_continue(state) == "human_review"


def test_should_continue_no_quality_score() -> None:
    """测试无质量分数时路由到 regenerate"""
    state: NovelState = {
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
        "quality_scores": {},
        "errors": [],
    }
    assert should_continue(state) == "regenerate"


def test_create_novel_graph() -> None:
    """测试创建小说流程图"""
    graph = create_novel_graph()
    assert graph is not None
    # 验证图已编译
    assert hasattr(graph, "invoke")
    assert hasattr(graph, "ainvoke")
