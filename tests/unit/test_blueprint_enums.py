"""蓝图枚举契约：值必须与 prompts.py 现有字面量严格一致，禁止发明。"""

from src.core.creative_control.blueprint_enums import (
    BLUEPRINT_FIELD_OPTIONS,
    BlueprintPacing,
    ChapterType,
    ForeshadowAction,
)


def test_chapter_type_values_match_prompts():
    assert {e.value for e in ChapterType} == {
        "main_advance", "climax", "aftermath", "daily", "setup"
    }


def test_pacing_values_match_prompts():
    assert {e.value for e in BlueprintPacing} == {"fast", "medium", "slow"}


def test_foreshadow_action_values_match_prompts():
    assert {e.value for e in ForeshadowAction} == {
        "plant", "callback", "advance"
    }


def test_options_dict_exposes_all_enums():
    assert set(BLUEPRINT_FIELD_OPTIONS["chapter_type"]) == {
        e.value for e in ChapterType
    }
    assert set(BLUEPRINT_FIELD_OPTIONS["pacing_target"]) == {
        e.value for e in BlueprintPacing
    }
    assert set(BLUEPRINT_FIELD_OPTIONS["foreshadow_action"]) == {
        e.value for e in ForeshadowAction
    }
