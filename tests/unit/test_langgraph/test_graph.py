"""LangGraph graph 模块单元测试"""

from unittest.mock import MagicMock, patch

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


# ── I1: 质量循环可配置测试 ──────────────────────────────────────


def _quality_state(overall: float, regen_count: int = 0) -> NovelState:
    return {
        "project_id": "test", "novel_type": "玄幻", "target_words": 100000,
        "idea": "test", "world_setting": None, "characters": [], "relationships": {},
        "outline": None, "chapter_outlines": [], "chapters": [],
        "current_stage": "quality_check", "approval_status": "pending",
        "revision_requests": [], "quality_scores": {"overall": overall},
        "errors": [], "_regeneration_count": regen_count,
    }


class TestQualityLoopConfig:
    """I1 — 质量循环可配置。"""

    def test_loop_disabled_skips_regeneration(self):
        """QUALITY_LOOP_ENABLED=False 时低质量也直接通过，不重生成。"""
        with patch("src.core.langgraph.graph.get_settings") as ms:
            ms.return_value = MagicMock(
                QUALITY_LOOP_ENABLED=False, QUALITY_THRESHOLD=0.8,
                MAX_REGENERATION_ATTEMPTS=2,
            )
            assert should_continue(_quality_state(0.3)) == "human_review"

    def test_loop_enabled_low_quality_regenerates(self):
        """QUALITY_LOOP_ENABLED=True 时低质量触发重生成。"""
        with patch("src.core.langgraph.graph.get_settings") as ms:
            ms.return_value = MagicMock(
                QUALITY_LOOP_ENABLED=True, QUALITY_THRESHOLD=0.8,
                MAX_REGENERATION_ATTEMPTS=2,
            )
            assert should_continue(_quality_state(0.5, regen_count=0)) == "regenerate"

    def test_high_quality_passes_with_loop_enabled(self):
        """高质量达标时通过（循环开启）。"""
        with patch("src.core.langgraph.graph.get_settings") as ms:
            ms.return_value = MagicMock(
                QUALITY_LOOP_ENABLED=True, QUALITY_THRESHOLD=0.8,
                MAX_REGENERATION_ATTEMPTS=2,
            )
            assert should_continue(_quality_state(0.9)) == "human_review"

    def test_max_attempts_reached_passes(self):
        """重试次数达上限时即使低质量也通过（避免无限循环）。"""
        with patch("src.core.langgraph.graph.get_settings") as ms:
            ms.return_value = MagicMock(
                QUALITY_LOOP_ENABLED=True, QUALITY_THRESHOLD=0.8,
                MAX_REGENERATION_ATTEMPTS=2,
            )
            assert should_continue(_quality_state(0.3, regen_count=2)) == "human_review"

    def test_custom_threshold_applied(self):
        """自定义阈值生效（设 0.6，0.65 通过）。"""
        with patch("src.core.langgraph.graph.get_settings") as ms:
            ms.return_value = MagicMock(
                QUALITY_LOOP_ENABLED=True, QUALITY_THRESHOLD=0.6,
                MAX_REGENERATION_ATTEMPTS=2,
            )
            assert should_continue(_quality_state(0.65)) == "human_review"
            assert should_continue(_quality_state(0.55)) == "regenerate"

    def test_volume_graph_uses_same_config(self):
        """卷级路由同样受 QUALITY_LOOP_ENABLED 控制。"""
        from src.core.langgraph.graph import _should_continue_volume
        with patch("src.core.langgraph.graph.get_settings") as ms:
            ms.return_value = MagicMock(
                QUALITY_LOOP_ENABLED=False, QUALITY_THRESHOLD=0.8,
                MAX_REGENERATION_ATTEMPTS=2,
            )
            assert _should_continue_volume(_quality_state(0.3)) == "review"
