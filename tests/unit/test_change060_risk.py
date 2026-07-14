# tests/unit/test_change060_risk.py
from src.core.quality.risk import RiskLevel, classify_risk


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
