# tests/unit/test_change060_risk.py
from unittest.mock import patch

from src.core.quality.risk import RiskLevel, classify_risk, should_invoke_l2


def test_failed_generation_is_high_risk():
    l0 = {"filler_flag": False, "stalled_flag": False, "violations": [{"type": "generation_failed", "severity": "error"}], "filler_score": 0, "outline_coverage": 0}
    level = classify_risk(l0_rules=l0, chapter_type="normal", is_failed=True)
    assert level == RiskLevel.HIGH


def test_critical_chapter_type_is_high_risk():
    l0 = {"filler_flag": False, "stalled_flag": False, "violations": [], "filler_score": 0, "outline_coverage": 0.8}
    level = classify_risk(l0_rules=l0, chapter_type="climax")
    assert level == RiskLevel.HIGH


def test_clean_normal_chapter_is_low_risk():
    l0 = {"filler_flag": False, "stalled_flag": False, "violations": [], "filler_score": 0, "outline_coverage": 0.9}
    level = classify_risk(l0_rules=l0, chapter_type="normal")
    assert level == RiskLevel.LOW


def test_l0_warning_makes_medium_risk():
    l0 = {"filler_flag": False, "stalled_flag": False, "violations": [{"type": "too_short", "severity": "warning"}], "filler_score": 0.3, "outline_coverage": 0.6}
    level = classify_risk(l0_rules=l0, chapter_type="normal")
    assert level == RiskLevel.MEDIUM


def test_should_invoke_l2_high_always_true():
    # HIGH 风险任意 index 必返回 True
    for idx in [0, 1, 5, 99]:
        assert should_invoke_l2(RiskLevel.HIGH, idx) is True


def test_should_invoke_l2_medium_every_3rd():
    # MEDIUM 每3章抽1（idx%3==0）
    assert should_invoke_l2(RiskLevel.MEDIUM, 0) is True
    assert should_invoke_l2(RiskLevel.MEDIUM, 1) is False
    assert should_invoke_l2(RiskLevel.MEDIUM, 2) is False
    assert should_invoke_l2(RiskLevel.MEDIUM, 3) is True


def test_should_invoke_l2_low_balanced_every_5th():
    # LOW + balanced 每5章抽1（idx%5==0）
    with patch("src.core.quality.risk.get_settings") as mock_s:
        mock_s.return_value.QUALITY_MODE = "balanced"
        assert should_invoke_l2(RiskLevel.LOW, 0) is True
        assert should_invoke_l2(RiskLevel.LOW, 1) is False
        assert should_invoke_l2(RiskLevel.LOW, 5) is True
        assert should_invoke_l2(RiskLevel.LOW, 6) is False


def test_should_invoke_l2_low_economy_never():
    # LOW + economy 不抽检
    with patch("src.core.quality.risk.get_settings") as mock_s:
        mock_s.return_value.QUALITY_MODE = "economy"
        for idx in [0, 1, 5, 100]:
            assert should_invoke_l2(RiskLevel.LOW, idx) is False


def test_should_invoke_l2_low_high_mode_more_frequent():
    # LOW + high 模式应比 balanced 更频繁抽检（%3 而非 %5）
    with patch("src.core.quality.risk.get_settings") as mock_s:
        mock_s.return_value.QUALITY_MODE = "high"
        # idx=3 在 high 模式抽检（%3==0），在 balanced 不抽检（%5!=0）
        assert should_invoke_l2(RiskLevel.LOW, 3) is True
        assert should_invoke_l2(RiskLevel.LOW, 1) is False


def test_should_invoke_l2_unknown_mode_defaults_no_sampling():
    # 未知 QUALITY_MODE 值 → LOW 不抽检（保守）
    with patch("src.core.quality.risk.get_settings") as mock_s:
        mock_s.return_value.QUALITY_MODE = "balansed"  # 拼写错误
        assert should_invoke_l2(RiskLevel.LOW, 0) is False
