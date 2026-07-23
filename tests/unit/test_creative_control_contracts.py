"""Creative Control 契约层单元测试。

覆盖 src/core/creative_control/contracts.py:
- 10 阶段定义
- 产物类型与"哪些产物走通用版本、哪些复用 ChapterVersion"
- 控制状态合法转换
- 依赖图（影响范围计算依据）
"""

from src.core.creative_control.contracts import (
    ARTIFACT_TYPES,
    ARTIFACT_TYPES_VERSIONED_GENERICALLY,
    CREATIVE_STAGES,
    DEPENDENCY_GRAPH,
    ControlStatus,
    CreationMode,
    legal_transitions,
    stage_of,
)

# ---------------------------------------------------------------------------
# 阶段定义
# ---------------------------------------------------------------------------


def test_ten_stages_defined():
    assert [s.number for s in CREATIVE_STAGES] == list(range(1, 11))


def test_stage_names_match_design():
    names = [s.name for s in CREATIVE_STAGES]
    assert names[0] == "创意与项目参数"
    assert names[3] == "全书总纲"
    assert names[5] == "章节蓝图"
    assert names[6] == "章节正文"
    assert names[9] == "定稿"


# ---------------------------------------------------------------------------
# 产物类型与版本化策略
# ---------------------------------------------------------------------------


def test_chapter_uses_chapter_version_not_generic_versioning():
    # 正文（chapter / chapter_version）走 ChapterVersion，不进通用版本表
    assert "chapter_version" in ARTIFACT_TYPES
    assert "chapter_version" not in ARTIFACT_TYPES_VERSIONED_GENERICALLY
    assert "chapter" not in ARTIFACT_TYPES_VERSIONED_GENERICALLY


def test_non_body_artifacts_use_generic_versioning():
    # 世界观/角色/总纲/卷纲/蓝图 走通用 ArtifactVersionStore
    for t in ("world", "character", "master_outline", "volume_outline", "blueprint"):
        assert t in ARTIFACT_TYPES_VERSIONED_GENERICALLY


def test_stage_of_artifact_type():
    assert stage_of("novel") == 1
    assert stage_of("world") == 2
    assert stage_of("character") == 3
    assert stage_of("master_outline") == 4
    assert stage_of("volume_outline") == 5
    assert stage_of("blueprint") == 6
    assert stage_of("chapter") == 7
    assert stage_of("chapter_version") == 7
    assert stage_of("quality") == 8
    assert stage_of("final") == 10


# ---------------------------------------------------------------------------
# 依赖图
# ---------------------------------------------------------------------------


def test_world_upstream_of_character_and_outline():
    downstream = DEPENDENCY_GRAPH["world"]
    assert "character" in downstream
    assert "master_outline" in downstream


def test_character_downstream_reaches_outline_and_blueprint():
    downstream = DEPENDENCY_GRAPH["character"]
    assert "master_outline" in downstream


def test_volume_outline_downstream_only_blueprint_and_chapter():
    downstream = DEPENDENCY_GRAPH["volume_outline"]
    assert "blueprint" in downstream
    assert "chapter" in downstream


def test_blueprint_downstream_is_chapter():
    assert DEPENDENCY_GRAPH["blueprint"] == ["chapter"]


def test_chapter_has_no_downstream_in_graph():
    # 改正文只产生新版本 + unverified，不级联重生成下游
    assert DEPENDENCY_GRAPH.get("chapter", []) == []


# ---------------------------------------------------------------------------
# 控制状态合法转换
# ---------------------------------------------------------------------------


def test_draft_can_start_generating():
    assert ControlStatus.GENERATING in legal_transitions(ControlStatus.DRAFT)


def test_generating_reaches_generated_or_failed():
    t = legal_transitions(ControlStatus.GENERATING)
    assert ControlStatus.GENERATED in t
    assert ControlStatus.FAILED in t


def test_generated_can_be_edited_approved_or_stale():
    t = legal_transitions(ControlStatus.GENERATED)
    assert ControlStatus.EDITED in t
    assert ControlStatus.APPROVED in t
    assert ControlStatus.STALE in t


def test_locked_requires_explicit_confirmation_not_auto_from_generated():
    # locked 不能从 generated 直接进入，必须经 approved
    assert ControlStatus.LOCKED not in legal_transitions(ControlStatus.GENERATED)
    assert ControlStatus.LOCKED in legal_transitions(ControlStatus.APPROVED)


def test_any_status_can_go_stale():
    for status in ControlStatus:
        assert ControlStatus.STALE in legal_transitions(status), status


def test_locked_can_go_stale_or_regenerating():
    t = legal_transitions(ControlStatus.LOCKED)
    assert ControlStatus.STALE in t
    assert ControlStatus.GENERATING in t  # 显式确认重生成
    assert ControlStatus.APPROVED not in t


def test_stale_reaches_generating_or_approved():
    t = legal_transitions(ControlStatus.STALE)
    assert ControlStatus.GENERATING in t
    assert ControlStatus.APPROVED in t


def test_failed_can_retry():
    assert ControlStatus.GENERATING in legal_transitions(ControlStatus.FAILED)


# ---------------------------------------------------------------------------
# CreationMode
# ---------------------------------------------------------------------------


def test_creation_modes():
    assert CreationMode.AUTO.value == "auto"
    assert CreationMode.ASSISTED.value == "assisted"
    assert CreationMode.MANUAL.value == "manual"
