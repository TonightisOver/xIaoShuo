# src/core/quality/rules.py
"""L0 规则门禁 —— 零 Token 的章节质量预筛。

所有检查基于正则/字数/哈希，不调用 LLM。用于：
- 每章生成后立即跑，作为分级漏斗的第一道闸门
- 卷级质量报告的真实数据来源（替代固定 0.7 假分）
"""

import re
from typing import Any

# 阈值
MIN_WORD_COUNT = 800
SHORT_FRACTION_OF_AVG = 0.4   # < 平均字数 40% → 灌水候选
REPETITION_THRESHOLD = 0.5    # 段落重复率超过此值 → 重复告警
OUTLINE_COVERAGE_MIN = 0.2    # 大纲关键词命中率低于此 → 覆盖率告警
SENTENCE_PREFIX_LEN = 8       # 句首 N 字用于句式复用检测
SENTENCE_PREFIX_REPEAT_THRESHOLD = 0.4  # 句首重复率超过此值 → 句式趋同告警


def run_l0_rules(
    *,
    content: str,
    word_count: int | None = None,
    avg_word_count: float = 0.0,
    chapter_outline: str | dict | None = None,
    chapter_number: int = 0,
) -> dict[str, Any]:
    """对单章正文跑零 Token 规则门禁。

    Returns:
        {
          "violations": [{severity, type, message}, ...],
          "filler_flag": bool,
          "filler_score": float,
          "stalled_flag": bool,
          "outline_coverage": float,
        }
    """
    wc = word_count if word_count is not None else len(content)
    violations: list[dict[str, Any]] = []
    filler_score = 0.0

    # 1. 字数
    if wc < MIN_WORD_COUNT:
        violations.append({
            "severity": "warning", "type": "too_short",
            "message": f"字数 {wc} 低于最小阈值 {MIN_WORD_COUNT}",
        })
        filler_score += 0.3

    if avg_word_count > 0 and wc < avg_word_count * SHORT_FRACTION_OF_AVG:
        violations.append({
            "severity": "warning", "type": "abnormally_short",
            "message": f"字数 {wc} 远低于卷均 {int(avg_word_count)}",
        })
        filler_score += 0.4

    # 2. 段落重复率
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", content) if p.strip()]
    if len(paragraphs) >= 2:
        unique = len(set(paragraphs))
        repeat_ratio = 1 - unique / len(paragraphs)
        if repeat_ratio >= REPETITION_THRESHOLD:
            violations.append({
                "severity": "error", "type": "repetitive_paragraphs",
                "message": f"段落重复率 {repeat_ratio:.0%}，疑似注水",
            })
            filler_score += 0.4

    # 3. 句式复用（句首 N 字重复）
    sentences = [s.strip() for s in re.split(r"[。！？!?]", content) if len(s.strip()) >= SENTENCE_PREFIX_LEN]
    if len(sentences) >= 4:
        prefixes = [s[:SENTENCE_PREFIX_LEN] for s in sentences]
        unique_prefixes = len(set(prefixes))
        prefix_repeat = 1 - unique_prefixes / len(prefixes)
        if prefix_repeat >= SENTENCE_PREFIX_REPEAT_THRESHOLD:
            violations.append({
                "severity": "warning", "type": "repetitive_sentence_pattern",
                "message": f"句首重复率 {prefix_repeat:.0%}，句式趋同",
            })

    # 4. 大纲覆盖率（关键词命中）
    outline_coverage = _outline_coverage(content, chapter_outline)
    if outline_coverage < OUTLINE_COVERAGE_MIN:
        violations.append({
            "severity": "warning", "type": "low_outline_coverage",
            "message": f"大纲覆盖率 {outline_coverage:.0%}，正文可能偏离本章大纲",
        })
        # 大纲覆盖率极低 → 停滞候选
        if outline_coverage < 0.1:
            violations.append({
                "severity": "error", "type": "stalled",
                "message": "正文几乎未推进本章大纲，疑似停滞",
            })

    # 5. 失败标记
    if wc == 0 or content.strip().startswith("[章节生成失败"):
        violations.append({
            "severity": "error", "type": "generation_failed",
            "message": "章节生成失败占位内容",
        })
        filler_score += 0.5  # 生成失败的章节一定标记为灌水/失败

    filler_flag = filler_score >= 0.5
    stalled_flag = any(v["type"] == "stalled" for v in violations)

    return {
        "violations": violations,
        "filler_flag": filler_flag,
        "filler_score": min(filler_score, 1.0),
        "stalled_flag": stalled_flag,
        "outline_coverage": outline_coverage,
    }


def _outline_coverage(content: str, outline: Any) -> float:
    """计算正文对大纲关键词的命中率（0-1）。

    用 2-gram 滑片提取大纲中的连续中文双字关键词，
    避免贪婪正则把整段中文当成一个关键词导致覆盖率恒为 0。
    """
    if not outline:
        return 1.0  # 无大纲时不报覆盖率问题
    if isinstance(outline, dict):
        text = " ".join(str(v) for v in outline.values())
    else:
        text = str(outline)
    # 提取所有连续中文片段，再切为 2-gram 关键词
    segments = re.findall(r"[一-龥]+", text)
    keywords: list[str] = []
    for seg in segments:
        for i in range(len(seg) - 1):
            kw = seg[i:i + 2]
            if kw not in keywords:
                keywords.append(kw)
    if not keywords:
        return 1.0
    hit = sum(1 for kw in keywords if kw in content)
    return hit / len(keywords)
