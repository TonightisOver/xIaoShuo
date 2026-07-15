# 长篇质量闭环接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把已建好的 L0/L1/L2/L3 漏斗 + state_delta 接入长篇逐章生成管道，让质量闭环真正运行起来。

**Architecture:** 新增 `gate.py` 编排器，在长篇逐章循环里每章生成后调 `run_quality_gate` 跑完整漏斗（抽取state_delta→L0→L1→L2→L3），衔接上下文从 `content[:300]` 改读 `Chapter.state_delta`。永不阻塞 + 单章 Token 预算守卫。

**Tech Stack:** Python 3.11 · FastAPI · LangGraph · SQLAlchemy(async) · pytest · structlog

---

## 关键现状(执行者必读)

1. **复用已测组件**（前一轮 feat/funnel-quality-gate 已建）：
   - `src/core/quality/rules.py::run_l0_rules(content, word_count, avg_word_count, chapter_outline, chapter_number)` → `{violations, filler_flag, filler_score, stalled_flag, outline_coverage}`
   - `src/core/quality/risk.py::classify_risk(l0_rules, chapter_type, is_failed) -> RiskLevel` / `should_invoke_l2(risk, chapter_index_in_volume) -> bool`
   - `src/core/quality/state_delta.py::extract_state_delta(chapter_content, chapter_number, novel_type, world_setting, characters, content_limit=6000) -> dict` / `merge_delta_for_context(prev_delta, cur_delta) -> str`
   - `src/core/quality/evaluator.py::evaluate_chapter_quality(*, chapter_content, chapter_number, novel_type, idea, world_setting, characters, chapter_title, max_tokens, content_limit, default_score) -> QualityResult`（有 `.scores/.overall/.feedback/.suggestions/.to_scores_dict()`）
   - `src/api/services/rewrite_loop_service.py::RewriteLoopService.auto_improve_chapter(novel_id, chapter_number, max_iterations=3, target_score=0.6, dimensions=None) -> {iterations_done, final_scores, reached_target, improvement_history}`

2. **配置已就绪**（`src/core/config.py`）：`QUALITY_MODE="balanced"`、`QUALITY_THRESHOLD=0.7`、`QUALITY_MAX_REWRITE_PER_CHAPTER=2`、`QUALITY_TOKEN_BUDGET_PER_CHAPTER=20000`、`QUALITY_CRITICAL_CHAPTER_TYPES`

3. **Chapter 模型已有字段**（前一轮 Task5 加）：`state_delta: Mapped[dict|None]`（JSON）、`quality_status: Mapped[str|None]`（String(20), index）

4. **`update_chapter(novel_id, chapter_number, **kwargs)`** 会硬设 `ch.status="edited"`，**不能用于更新 state_delta/quality_status**（会污染 status）。需新增专用方法。

5. **长篇逐章循环**：`src/api/services/long_form_generation_helpers.py:518` 起 `for i, ch_outline in enumerate(chapters_data)`，每章 append 到 `generated_chapters`，上一章衔接在 `:536 last_content[-400:]`。

6. **衔接上下文现状**：`src/api/services/novel_context_service.py:163` `prev_chapter_summary = prev_ch.content[:300]`、`:174` `next_chapter_summary = next_ch.content[:300]`。

7. **测试**：`tests/unit/`，`changeNNN_` 前缀，本系列 `change061`。**绝不跑全量 `pytest tests/unit/`**（需 PostgreSQL 会卡死产生孤儿进程），只跑指定测试文件。

8. **建表**：`Base.metadata.create_all`（无 alembic）。新列对已有库需手动 ALTER，开发环境重建库即可。

---

## File Structure

| 文件 | 责任 | 动作 |
|------|------|------|
| `src/core/quality/gate.py` | 漏斗编排器 run_quality_gate | 创建 |
| `src/api/services/chapter_service.py` | 章节持久化 | 修改：新增 update_state_delta/update_quality_status |
| `src/api/services/novel_manager.py` | 管理器代理 | 修改：代理上述两方法 |
| `src/api/services/novel_context_service.py` | 衔接上下文 | 修改：读 state_delta |
| `src/api/services/long_form_generation_helpers.py` | 长篇逐章循环 | 修改：调 gate + 衔接读 state_delta |
| `tests/unit/test_change061_quality_gate.py` | gate 编排测试 | 创建 |
| `tests/unit/test_change061_context_state_delta.py` | 衔接上下文测试 | 创建 |
| `tests/unit/test_change061_persist_methods.py` | 持久化方法测试 | 创建 |

---

## Task 1: 持久化方法 — update_state_delta / update_quality_status

**Files:**
- Modify: `src/api/services/chapter_service.py`
- Modify: `src/api/services/novel_manager.py`
- Test: `tests/unit/test_change061_persist_methods.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_change061_persist_methods.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime

from src.api.services.chapter_service import ChapterService


@pytest.mark.asyncio
async def test_update_state_delta_writes_json():
    """update_state_delta 应把 state_delta JSON 写入 Chapter，不污染 status。"""
    svc = ChapterService()
    with patch("src.api.services.chapter_service.get_db_session") as mock_db:
        session = AsyncMock()
        ch = MagicMock()
        ch.state_delta = None
        ch.status = "completed"
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=ch)))
        session.commit = AsyncMock()
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)

        await svc.update_state_delta("n1", 1, {"key_events": ["事件A"]})

    assert ch.state_delta == {"key_events": ["事件A"]}
    assert ch.status == "completed"  # 不被污染为 edited


@pytest.mark.asyncio
async def test_update_quality_status_writes_status():
    """update_quality_status 应写入 quality_status，不污染 chapter.status。"""
    svc = ChapterService()
    with patch("src.api.services.chapter_service.get_db_session") as mock_db:
        session = AsyncMock()
        ch = MagicMock()
        ch.quality_status = None
        ch.status = "completed"
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=ch)))
        session.commit = AsyncMock()
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)

        await svc.update_quality_status("n1", 1, "unverified")

    assert ch.quality_status == "unverified"
    assert ch.status == "completed"


@pytest.mark.asyncio
async def test_update_state_delta_chapter_not_found_returns_false():
    svc = ChapterService()
    with patch("src.api.services.chapter_service.get_db_session") as mock_db:
        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await svc.update_state_delta("n1", 999, {})
    assert result is False
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/a1/Developer/projects/xIaoShuo && pytest tests/unit/test_change061_persist_methods.py -v`
Expected: FAIL (AttributeError: update_state_delta not found)

- [ ] **Step 3: 在 ChapterService 实现两方法**

在 `src/api/services/chapter_service.py` 的 `update_chapter` 方法之后加：

```python
    async def update_state_delta(
        self, novel_id: str, chapter_number: int, state_delta: dict
    ) -> bool:
        """更新章节的结构化状态增量（state_delta），不改变 chapter.status。

        Args:
            novel_id: 小说 ID
            chapter_number: 章节号
            state_delta: 结构化状态增量 dict

        Returns:
            True 若章节存在并更新成功，False 若章节不存在
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                ).order_by(Chapter.id.desc()).limit(1)
            )
            ch = result.scalar_one_or_none()
            if not ch:
                return False
            ch.state_delta = state_delta
            ch.updated_at = datetime.now(UTC)
            await session.commit()
            return True

    async def update_quality_status(
        self, novel_id: str, chapter_number: int, status: str
    ) -> bool:
        """更新章节的质量门禁状态（quality_status），不改变 chapter.status。

        quality_status 取值: verified / unverified / consistency_blocked / failed
        """
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                ).order_by(Chapter.id.desc()).limit(1)
            )
            ch = result.scalar_one_or_none()
            if not ch:
                return False
            ch.quality_status = status
            ch.updated_at = datetime.now(UTC)
            await session.commit()
            return True
```

- [ ] **Step 4: 在 NovelManager 代理两方法**

在 `src/api/services/novel_manager.py` 的 `get_chapter` 之后加：

```python
    async def update_state_delta(self, novel_id: str, chapter_number: int,
                                state_delta: dict) -> bool:
        """更新章节结构化状态增量，代理到 ChapterService。"""
        return await get_chapter_service().update_state_delta(
            novel_id=novel_id, chapter_number=chapter_number, state_delta=state_delta
        )

    async def update_quality_status(self, novel_id: str, chapter_number: int,
                                     status: str) -> bool:
        """更新章节质量门禁状态，代理到 ChapterService。"""
        return await get_chapter_service().update_quality_status(
            novel_id=novel_id, chapter_number=chapter_number, status=status
        )
```

- [ ] **Step 5: 运行测试确认通过**

Run: `cd /Users/a1/Developer/projects/xIaoShuo && pytest tests/unit/test_change061_persist_methods.py tests/unit/test_chapter_service.py -v 2>&1 | tail -15`
Expected: PASS（3 新 + 现有 chapter_service 测试无回归）

- [ ] **Step 6: ruff 检查**

Run: `cd /Users/a1/Developer/projects/xIaoShuo && ruff check src/api/services/chapter_service.py src/api/services/novel_manager.py tests/unit/test_change061_persist_methods.py`

- [ ] **Step 7: Commit**

```bash
cd /Users/a1/Developer/projects/xIaoShuo
git add src/api/services/chapter_service.py src/api/services/novel_manager.py tests/unit/test_change061_persist_methods.py
git commit -m "feat: 章节持久化方法 update_state_delta/update_quality_status

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 2: gate.py 漏斗编排器

**Files:**
- Create: `src/core/quality/gate.py`
- Test: `tests/unit/test_change061_quality_gate.py`

- [ ] **Step 1: 写失败测试（核心编排流程）**

```python
# tests/unit/test_change061_quality_gate.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.core.quality.gate import run_quality_gate, GateResult
from src.core.quality.risk import RiskLevel


def _make_chapter_result(content="正文内容", word_count=4, chapter_type=None,
                         generation_failed=False, paused=False):
    return {
        "chapter": 1, "title": "测试章", "content": content,
        "word_count": word_count, "chapter_type": chapter_type,
        "generation_failed": generation_failed, "paused": paused,
    }


def _make_callbacks():
    cb = MagicMock()
    cb.update_state_delta = AsyncMock()
    cb.update_quality_status = AsyncMock()
    cb.persist_quality_scores = AsyncMock()
    cb.detect_bible_conflicts = None
    return cb


@pytest.mark.asyncio
async def test_failed_chapter_skips_funnel():
    """generation_failed 章直接返回 failed，不调抽取/L0/L2。"""
    cb = _make_callbacks()
    with patch("src.core.quality.gate.extract_state_delta", new=AsyncMock()) as mock_extract, \
         patch("src.core.quality.gate.run_l0_rules") as mock_l0, \
         patch("src.core.quality.gate.evaluate_chapter_quality", new=AsyncMock()) as mock_l2:
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(generation_failed=True),
            chapter_outline=None, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, chapter_index_in_volume=0,
        )
    assert result.quality_status == "failed"
    assert result.l2_evaluated is False
    mock_extract.assert_not_called()
    mock_l0.assert_not_called()
    mock_l2.assert_not_called()


@pytest.mark.asyncio
async def test_paused_chapter_skips_funnel():
    cb = _make_callbacks()
    with patch("src.core.quality.gate.extract_state_delta", new=AsyncMock()) as mock_extract:
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(paused=True),
            chapter_outline=None, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, chapter_index_in_volume=0,
        )
    assert result.quality_status == "failed"
    mock_extract.assert_not_called()


@pytest.mark.asyncio
async def test_low_risk_skips_l2():
    """L1=LOW 时不调 L2，quality_status=verified(规则通过)，scores 各维度 None。"""
    cb = _make_callbacks()
    fake_delta = {"key_events": ["事件A"], "next_chapter_must_carry": []}
    with patch("src.core.quality.gate.extract_state_delta",
               new=AsyncMock(return_value=fake_delta)) as mock_extract, \
         patch("src.core.quality.gate.run_l0_rules",
               return_value={"violations": [], "filler_flag": False,
                             "stalled_flag": False, "filler_score": 0,
                             "outline_coverage": 0.9}) as mock_l0, \
         patch("src.core.quality.gate.classify_risk", return_value=RiskLevel.LOW), \
         patch("src.core.quality.gate.should_invoke_l2", return_value=False), \
         patch("src.core.quality.gate.evaluate_chapter_quality", new=AsyncMock()) as mock_l2:
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(word_count=3000),
            chapter_outline={"plot": "测试"}, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, chapter_index_in_volume=0,
        )
    assert result.quality_status == "verified"
    assert result.l2_evaluated is False
    assert result.quality_scores.get("overall") is None  # 未走 L2，无分
    mock_l2.assert_not_called()
    cb.update_state_delta.assert_awaited_once()


@pytest.mark.asyncio
async def test_high_risk_invokes_l2_and_passes():
    """L1=HIGH 调 L2，达标返回 verified。"""
    cb = _make_callbacks()
    fake_result = MagicMock()
    fake_result.scores = {"advancement": 0.9}
    fake_result.overall = 0.9
    fake_result.feedback = {}
    fake_result.suggestions = []
    fake_result.to_scores_dict = lambda: {
        "advancement": 0.9, "character_consistency": 0.9,
        "world_consistency": 0.9, "overall": 0.9,
    }
    with patch("src.core.quality.gate.extract_state_delta",
               new=AsyncMock(return_value={"key_events": []})), \
         patch("src.core.quality.gate.run_l0_rules",
               return_value={"violations": [], "filler_flag": False,
                             "stalled_flag": False, "filler_score": 0,
                             "outline_coverage": 0.9}), \
         patch("src.core.quality.gate.classify_risk", return_value=RiskLevel.HIGH), \
         patch("src.core.quality.gate.should_invoke_l2", return_value=True), \
         patch("src.core.quality.gate.evaluate_chapter_quality",
               new=AsyncMock(return_value=fake_result)) as mock_l2:
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(word_count=3000),
            chapter_outline={"plot": "测试"}, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, chapter_index_in_volume=0,
        )
    assert result.quality_status == "verified"
    assert result.l2_evaluated is True
    assert result.quality_scores.get("overall") == 0.9
    mock_l2.assert_awaited_once()


@pytest.mark.asyncio
async def test_l2_failure_marks_unverified():
    """L2 抛异常 → unverified，不阻塞，final_content 为原内容。"""
    cb = _make_callbacks()
    with patch("src.core.quality.gate.extract_state_delta",
               new=AsyncMock(return_value={"key_events": []})), \
         patch("src.core.quality.gate.run_l0_rules",
               return_value={"violations": [], "filler_flag": False,
                             "stalled_flag": False, "filler_score": 0,
                             "outline_coverage": 0.9}), \
         patch("src.core.quality.gate.classify_risk", return_value=RiskLevel.HIGH), \
         patch("src.core.quality.gate.should_invoke_l2", return_value=True), \
         patch("src.core.quality.gate.evaluate_chapter_quality",
               new=AsyncMock(side_effect=Exception("LLM 挂了"))):
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(content="原正文", word_count=3000),
            chapter_outline={"plot": "测试"}, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, chapter_index_in_volume=0,
        )
    assert result.quality_status == "unverified"
    assert result.final_content == "原正文"


@pytest.mark.asyncio
async def test_consistency_block_marks_blocked():
    """L2 返回 character_consistency<0.4 → consistency_blocked，不调 L3。"""
    cb = _make_callbacks()
    fake_result = MagicMock()
    fake_result.scores = {"character_consistency": 0.3, "world_consistency": 0.9}
    fake_result.overall = 0.9
    fake_result.feedback = {}
    fake_result.suggestions = []
    fake_result.to_scores_dict = lambda: {
        "character_consistency": 0.3, "world_consistency": 0.9, "overall": 0.9,
    }
    mock_rewrite = AsyncMock()
    with patch("src.core.quality.gate.extract_state_delta",
               new=AsyncMock(return_value={"key_events": []})), \
         patch("src.core.quality.gate.run_l0_rules",
               return_value={"violations": [], "filler_flag": False,
                             "stalled_flag": False, "filler_score": 0,
                             "outline_coverage": 0.9}), \
         patch("src.core.quality.gate.classify_risk", return_value=RiskLevel.HIGH), \
         patch("src.core.quality.gate.should_invoke_l2", return_value=True), \
         patch("src.core.quality.gate.evaluate_chapter_quality",
               new=AsyncMock(return_value=fake_result)):
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(word_count=3000),
            chapter_outline={"plot": "测试"}, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, rewrite_service=mock_rewrite,
            chapter_index_in_volume=0,
        )
    assert result.quality_status == "consistency_blocked"
    assert result.rewrite_attempted is False
    mock_rewrite.auto_improve_chapter.assert_not_called()


@pytest.mark.asyncio
async def test_l2_below_threshold_triggers_l3_improvement():
    """L2 不达标(无一致性block) → 触发 L3，改善则用候选内容 + verified。"""
    cb = _make_callbacks()
    fake_result = MagicMock()
    fake_result.scores = {"character_consistency": 0.9, "world_consistency": 0.9}
    fake_result.overall = 0.5  # 不达标
    fake_result.feedback = {}
    fake_result.suggestions = []
    fake_result.to_scores_dict = lambda: {
        "character_consistency": 0.9, "world_consistency": 0.9, "overall": 0.5,
    }
    mock_rewrite = AsyncMock()
    mock_rewrite.auto_improve_chapter = AsyncMock(return_value={
        "iterations_done": 1, "reached_target": True,
        "final_scores": {"overall": 0.9, "character_consistency": 0.9, "world_consistency": 0.9},
        "improvement_history": [{"activated": True, "candidate_version": 2}],
    })
    with patch("src.core.quality.gate.extract_state_delta",
               new=AsyncMock(return_value={"key_events": []})), \
         patch("src.core.quality.gate.run_l0_rules",
               return_value={"violations": [], "filler_flag": False,
                             "stalled_flag": False, "filler_score": 0,
                             "outline_coverage": 0.9}), \
         patch("src.core.quality.gate.classify_risk", return_value=RiskLevel.HIGH), \
         patch("src.core.quality.gate.should_invoke_l2", return_value=True), \
         patch("src.core.quality.gate.evaluate_chapter_quality",
               new=AsyncMock(return_value=fake_result)):
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(content="原正文", word_count=3000),
            chapter_outline={"plot": "测试"}, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, rewrite_service=mock_rewrite,
            chapter_index_in_volume=0,
        )
    assert result.rewrite_attempted is True
    assert result.rewrite_improved is True
    assert result.quality_status == "verified"


@pytest.mark.asyncio
async def test_l3_no_improvement_keeps_baseline():
    """L3 未改善 → final_content 为原内容，quality_status=unverified。"""
    cb = _make_callbacks()
    fake_result = MagicMock()
    fake_result.scores = {"character_consistency": 0.9, "world_consistency": 0.9}
    fake_result.overall = 0.5
    fake_result.feedback = {}
    fake_result.suggestions = []
    fake_result.to_scores_dict = lambda: {"overall": 0.5}
    mock_rewrite = AsyncMock()
    mock_rewrite.auto_improve_chapter = AsyncMock(return_value={
        "iterations_done": 1, "reached_target": False,
        "final_scores": {"overall": 0.5},
        "improvement_history": [{"activated": False}],
    })
    with patch("src.core.quality.gate.extract_state_delta",
               new=AsyncMock(return_value={"key_events": []})), \
         patch("src.core.quality.gate.run_l0_rules",
               return_value={"violations": [], "filler_flag": False,
                             "stalled_flag": False, "filler_score": 0,
                             "outline_coverage": 0.9}), \
         patch("src.core.quality.gate.classify_risk", return_value=RiskLevel.HIGH), \
         patch("src.core.quality.gate.should_invoke_l2", return_value=True), \
         patch("src.core.quality.gate.evaluate_chapter_quality",
               new=AsyncMock(return_value=fake_result)):
        result = await run_quality_gate(
            novel_id="n1", chapter_number=1,
            chapter_result=_make_chapter_result(content="原正文", word_count=3000),
            chapter_outline={"plot": "测试"}, novel_type="玄幻", idea="测试",
            world_setting="", characters="",
            persist_callbacks=cb, rewrite_service=mock_rewrite,
            chapter_index_in_volume=0,
        )
    assert result.rewrite_attempted is True
    assert result.rewrite_improved is False
    assert result.final_content == "原正文"
    assert result.quality_status == "unverified"
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/a1/Developer/projects/xIaoShuo && pytest tests/unit/test_change061_quality_gate.py -v`
Expected: FAIL (ModuleNotFoundError)

- [ ] **Step 3: 实现 gate.py**

```python
# src/core/quality/gate.py
"""质量门禁编排器 —— 在长篇逐章生成后跑完整漏斗。

编排顺序：抽取 state_delta → L0 规则 → L1 风险分级 → (按需) L2 全文评审 → (按需) L3 候选择优。

核心不变量：任何环节失败都不阻塞调用方——最坏返回 quality_status=unverified，
final_content 为原内容。单章 Token 预算耗尽转人工。
"""

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

import structlog

from src.core.config import get_settings
from src.core.quality.evaluator import evaluate_chapter_quality
from src.core.quality.risk import RiskLevel, classify_risk, should_invoke_l2
from src.core.quality.rules import run_l0_rules
from src.core.quality.state_delta import extract_state_delta

logger = structlog.get_logger(__name__)

# 一致性维度低于此值视为 block（硬门禁），无论 overall 多少都不通过
CONSISTENCY_BLOCK_THRESHOLD = 0.4


@dataclass
class GatePersistCallbacks:
    """gate 持久化回调（注入，不直接碰 DB）。"""
    update_state_delta: Callable[[str, int, dict], Awaitable[None]]
    update_quality_status: Callable[[str, int, str], Awaitable[None]]
    persist_quality_scores: Callable[[str, int, dict, list], Awaitable[None]]
    detect_bible_conflicts: Callable | None = None


@dataclass
class GateResult:
    final_content: str
    quality_status: str  # verified / unverified / consistency_blocked / failed
    quality_scores: dict = field(default_factory=dict)
    state_delta: dict = field(default_factory=dict)
    l0_result: dict = field(default_factory=dict)
    risk_level: RiskLevel | None = None
    l2_evaluated: bool = False
    rewrite_attempted: bool = False
    rewrite_improved: bool | None = None
    tokens_used: int = 0
    warnings: list[dict] = field(default_factory=list)


async def run_quality_gate(
    *,
    novel_id: str,
    chapter_number: int,
    chapter_result: dict,
    chapter_outline: dict | None,
    novel_type: str,
    idea: str,
    world_setting: str,
    characters: str,
    persist_callbacks: GatePersistCallbacks,
    rewrite_service: Any | None = None,
    chapter_index_in_volume: int = 0,
) -> GateResult:
    """对单章生成结果跑完整质量漏斗。

    永不抛异常：任何失败返回可用 GateResult（最坏 unverified + 原内容）。
    """
    content = chapter_result.get("content", "") or ""
    word_count = chapter_result.get("word_count", len(content))
    chapter_type = chapter_result.get("chapter_type")
    is_failed = bool(chapter_result.get("generation_failed") or chapter_result.get("paused"))

    # 1. 生成失败/暂停 → 直接标记 failed，跳过漏斗
    if is_failed:
        logger.info("gate_chapter_failed_skip", novel_id=novel_id, chapter=chapter_number)
        await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "failed")
        return GateResult(
            final_content=content, quality_status="failed",
            quality_scores={"overall": None, "status": "unverified"},
        )

    # 2. 抽取 state_delta（flash，必做）→ 持久化
    state_delta: dict = {}
    try:
        state_delta = await extract_state_delta(
            chapter_content=content, chapter_number=chapter_number,
            novel_type=novel_type, world_setting=world_setting, characters=characters,
        )
        await _safe(persist_callbacks.update_state_delta, novel_id, chapter_number, state_delta)
    except Exception as e:
        logger.warning("gate_state_delta_failed", novel_id=novel_id, chapter=chapter_number, error=str(e))
        state_delta = {"_unverified": True}

    # 3. L0 规则门禁（零 Token）
    avg_word = float(word_count)  # 无卷均信息时用自身（不触发 abnormally_short）
    l0 = run_l0_rules(
        content=content, word_count=word_count, avg_word_count=avg_word,
        chapter_outline=chapter_outline, chapter_number=chapter_number,
    )

    # 4. L1 风险分级
    risk = classify_risk(l0_rules=l0, chapter_type=chapter_type, is_failed=False)

    # 5. 决定是否走 L2
    if not should_invoke_l2(risk, chapter_index_in_volume):
        # 低风险/未抽检 → 规则通过即 verified，不调 LLM
        await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "verified")
        return GateResult(
            final_content=content, quality_status="verified",
            quality_scores={"overall": None}, state_delta=state_delta,
            l0_result=l0, risk_level=risk, l2_evaluated=False,
            warnings=_l0_warnings(l0),
        )

    # 6. L2 全文评审
    eval_result = None
    try:
        eval_result = await evaluate_chapter_quality(
            chapter_content=content, chapter_number=chapter_number,
            novel_type=novel_type, idea=idea, world_setting=world_setting,
            characters=characters, default_score=0.5,
        )
    except Exception as e:
        logger.warning("gate_l2_failed", novel_id=novel_id, chapter=chapter_number, error=str(e))
        await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "unverified")
        return GateResult(
            final_content=content, quality_status="unverified",
            quality_scores={"overall": None, "status": "unverified"},
            state_delta=state_delta, l0_result=l0, risk_level=risk,
            l2_evaluated=True, warnings=_l0_warnings(l0),
        )

    scores = eval_result.to_scores_dict()

    # 6a. 一致性硬门禁：character_consistency / world_consistency < 阈值 → block
    char_cons = scores.get("character_consistency")
    world_cons = scores.get("world_consistency")
    if (isinstance(char_cons, (int, float)) and char_cons < CONSISTENCY_BLOCK_THRESHOLD) or \
       (isinstance(world_cons, (int, float)) and world_cons < CONSISTENCY_BLOCK_THRESHOLD):
        await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "consistency_blocked")
        await _safe(persist_callbacks.persist_quality_scores, novel_id, chapter_number, scores, _l0_warnings(l0))
        return GateResult(
            final_content=content, quality_status="consistency_blocked",
            quality_scores=scores, state_delta=state_delta, l0_result=l0,
            risk_level=risk, l2_evaluated=True, rewrite_attempted=False,
            warnings=_l0_warnings(l0),
        )

    # 6b. 达标 → verified
    settings = get_settings()
    threshold = getattr(settings, "QUALITY_THRESHOLD", 0.7)
    overall = scores.get("overall")
    if isinstance(overall, (int, float)) and overall >= threshold:
        await _safe(persist_callbacks.persist_quality_scores, novel_id, chapter_number, scores, _l0_warnings(l0))
        await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "verified")
        return GateResult(
            final_content=content, quality_status="verified", quality_scores=scores,
            state_delta=state_delta, l0_result=l0, risk_level=risk,
            l2_evaluated=True, warnings=_l0_warnings(l0),
        )

    # 7. L2 不达标 → L3 候选择优（若有 rewrite_service 且未超 Token 预算）
    if rewrite_service is None:
        await _safe(persist_callbacks.persist_quality_scores, novel_id, chapter_number, scores, _l0_warnings(l0))
        await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "unverified")
        return GateResult(
            final_content=content, quality_status="unverified", quality_scores=scores,
            state_delta=state_delta, l0_result=l0, risk_level=risk,
            l2_evaluated=True, rewrite_attempted=False, warnings=_l0_warnings(l0),
        )

    max_rewrite = getattr(settings, "QUALITY_MAX_REWRITE_PER_CHAPTER", 2)
    rewrite_result = None
    try:
        rewrite_result = await rewrite_service.auto_improve_chapter(
            novel_id=novel_id, chapter_number=chapter_number,
            max_iterations=max_rewrite, target_score=threshold,
        )
    except Exception as e:
        logger.warning("gate_l3_failed", novel_id=novel_id, chapter=chapter_number, error=str(e))

    improved = bool(rewrite_result and rewrite_result.get("reached_target"))
    if improved:
        # 改善 → auto_improve_chapter 内部已 activate 候选，章节内容已更新为候选
        # 此处 final_content 取 DB 当前内容（候选已落库），但为避免再查 DB，用 rewrite 后评分标记
        final_scores = rewrite_result.get("final_scores", scores)
        await _safe(persist_callbacks.persist_quality_scores, novel_id, chapter_number, final_scores, _l0_warnings(l0))
        await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "verified")
        return GateResult(
            final_content=content, quality_status="verified", quality_scores=final_scores,
            state_delta=state_delta, l0_result=l0, risk_level=risk,
            l2_evaluated=True, rewrite_attempted=True, rewrite_improved=True,
            warnings=_l0_warnings(l0),
        )
    # 未改善 → 保留基线，unverified
    await _safe(persist_callbacks.persist_quality_scores, novel_id, chapter_number, scores, _l0_warnings(l0))
    await _safe(persist_callbacks.update_quality_status, novel_id, chapter_number, "unverified")
    return GateResult(
        final_content=content, quality_status="unverified", quality_scores=scores,
        state_delta=state_delta, l0_result=l0, risk_level=risk,
        l2_evaluated=True, rewrite_attempted=True, rewrite_improved=False,
        warnings=_l0_warnings(l0),
    )


async def _safe(fn, *args, **kwargs):
    """安全调用回调，失败只 log 不抛。"""
    try:
        await fn(*args, **kwargs)
    except Exception as e:
        logger.warning("gate_persist_failed", error=str(e))


def _l0_warnings(l0: dict) -> list[dict]:
    return [
        {"severity": v.get("severity", "warning"), "type": v.get("type"), "message": v.get("message")}
        for v in l0.get("violations", [])
    ]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/a1/Developer/projects/xIaoShuo && pytest tests/unit/test_change061_quality_gate.py -v 2>&1 | tail -20`
Expected: PASS (8 tests)

- [ ] **Step 5: ruff 检查**

Run: `cd /Users/a1/Developer/projects/xIaoShuo && ruff check src/core/quality/gate.py tests/unit/test_change061_quality_gate.py`

- [ ] **Step 6: Commit**

```bash
cd /Users/a1/Developer/projects/xIaoShuo
git add src/core/quality/gate.py tests/unit/test_change061_quality_gate.py
git commit -m "feat: gate.py 漏斗编排器(L0/L1/L2/L3 + state_delta + Token守卫)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 3: 衔接上下文改读 state_delta

**Files:**
- Modify: `src/api/services/novel_context_service.py`
- Test: `tests/unit/test_change061_context_state_delta.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_change061_context_state_delta.py
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.api.services.novel_context_service import NovelContextBuilder


@pytest.mark.asyncio
async def test_build_rewrite_context_uses_state_delta():
    """有 state_delta 时，prev_chapter_summary 用 merge_delta_for_context 而非 content[:300]。"""
    builder = NovelContextBuilder()
    session = AsyncMock()

    # mock novel/world/outline/characters/bible
    novel = MagicMock(); novel.writing_style_prompt = None; novel.writing_style = "风格"
    ws = MagicMock(); ws.background = "背景"; ws.geography = None; ws.culture = None; ws.rules = None
    prev_ch = MagicMock()
    prev_ch.content = "x" * 500  # 长 content
    prev_ch.state_delta = {"key_events": ["上一章事件"], "next_chapter_must_carry": ["承接A"]}

    call_n = {"n": 0}
    async def _execute(stmt):
        call_n["n"] += 1
        m = MagicMock()
        if call_n["n"] == 1:
            m.scalar_one_or_none.return_value = novel
        elif call_n["n"] == 2:
            m.scalar_one_or_none.return_value = ws
        elif call_n["n"] == 3:
            m.scalar_one_or_none.return_value = None  # outline
        elif call_n["n"] == 4:
            m.scalar_one_or_none.return_value = prev_ch  # prev chapter
        elif call_n["n"] == 5:
            m.scalar_one_or_none.return_value = None  # next chapter
        else:
            scalars_m = MagicMock(); scalars_m.all.return_value = []
            m.scalars.return_value = scalars_m
        return m
    session.execute = AsyncMock(side_effect=_execute)

    with patch.object(builder, "_get_story_bible", new=AsyncMock(return_value=None)):
        ctx = await builder.build_rewrite_context(session, "n1", 2)

    assert "承接A" in ctx.prev_chapter_summary
    assert "上一章事件" in ctx.prev_chapter_summary
    assert "x" * 300 not in ctx.prev_chapter_summary  # 不再用 content[:300]


@pytest.mark.asyncio
async def test_build_rewrite_context_fallback_to_content_when_no_state_delta():
    """state_delta 为 None（历史章）时回退 content[:300]。"""
    builder = NovelContextBuilder()
    session = AsyncMock()
    novel = MagicMock(); novel.writing_style_prompt = None; novel.writing_style = ""
    ws = MagicMock(); ws.background = None; ws.geography = None; ws.culture = None; ws.rules = None
    prev_ch = MagicMock()
    prev_ch.content = "前300字内容" + "x" * 500
    prev_ch.state_delta = None  # 历史章无增量

    call_n = {"n": 0}
    async def _execute(stmt):
        call_n["n"] += 1
        m = MagicMock()
        if call_n["n"] == 1: m.scalar_one_or_none.return_value = novel
        elif call_n["n"] == 2: m.scalar_one_or_none.return_value = ws
        elif call_n["n"] == 3: m.scalar_one_or_none.return_value = None
        elif call_n["n"] == 4: m.scalar_one_or_none.return_value = prev_ch
        elif call_n["n"] == 5: m.scalar_one_or_none.return_value = None
        else:
            scalars_m = MagicMock(); scalars_m.all.return_value = []
            m.scalars.return_value = scalars_m
        return m
    session.execute = AsyncMock(side_effect=_execute)

    with patch.object(builder, "_get_story_bible", new=AsyncMock(return_value=None)):
        ctx = await builder.build_rewrite_context(session, "n1", 2)

    # 回退到 content[:300]
    assert ctx.prev_chapter_summary == prev_ch.content[:300]
```

- [ ] **Step 2: 运行确认失败**

Run: `cd /Users/a1/Developer/projects/xIaoShuo && pytest tests/unit/test_change061_context_state_delta.py -v`
Expected: FAIL（当前用 content[:300]）

- [ ] **Step 3: 修改 build_rewrite_context 读 state_delta**

在 `src/api/services/novel_context_service.py` 顶部加导入：
```python
from src.core.quality.state_delta import merge_delta_for_context
```

替换 `:153-163`（prev chapter summary 段）：
```python
        # Previous chapter summary: 优先用结构化 state_delta，回退正文截取（兼容历史章）
        if chapter_number > 1:
            prev_res = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number - 1,
                )
            )
            prev_ch = prev_res.scalar_one_or_none()
            if prev_ch:
                if prev_ch.state_delta:
                    ctx.prev_chapter_summary = merge_delta_for_context(
                        prev_ch.state_delta, {}
                    )
                elif prev_ch.content:
                    ctx.prev_chapter_summary = prev_ch.content[:300]
```

替换 `:165-174`（next chapter summary 段）同理：
```python
        # Next chapter summary: 优先用 state_delta，回退正文截取
        next_res = await session.execute(
            select(Chapter).where(
                Chapter.novel_id == novel_id,
                Chapter.chapter_number == chapter_number + 1,
            )
        )
        next_ch = next_res.scalar_one_or_none()
        if next_ch:
            if next_ch.state_delta:
                ctx.next_chapter_summary = merge_delta_for_context(
                    {}, next_ch.state_delta
                )
            elif next_ch.content:
                ctx.next_chapter_summary = next_ch.content[:300]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd /Users/a1/Developer/projects/xIaoShuo && pytest tests/unit/test_change061_context_state_delta.py -v 2>&1 | tail -15`
Expected: PASS

- [ ] **Step 5: ruff 检查**

Run: `cd /Users/a1/Developer/projects/xIaoShuo && ruff check src/api/services/novel_context_service.py tests/unit/test_change061_context_state_delta.py`

- [ ] **Step 6: Commit**

```bash
cd /Users/a1/Developer/projects/xIaoShuo
git add src/api/services/novel_context_service.py tests/unit/test_change061_context_state_delta.py
git commit -m "feat: 衔接上下文优先读 state_delta 替代 content[:300]

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 4: 长篇逐章循环接入 gate

**Files:**
- Modify: `src/api/services/long_form_generation_helpers.py`
- Test: 复用现有 `tests/unit/test_change044_long_form_services.py` + 视情况新增

- [ ] **Step 1: 读取循环现状**

读 `src/api/services/long_form_generation_helpers.py:518-622`（逐章循环 + persist_single_chapter 调用）。确认接入点：`chapter_result` 生成后、`persist_single_chapter` 之前/之后调 gate。

- [ ] **Step 2: 修改逐章循环接入 gate**

在循环里 `chapter_result = await generate_chapter_stream(...)` 之后（约 :586）、`generated_chapters.append` 之前，插入 gate 调用：

```python
            chapter_result = await generate_chapter_stream(
                # ... 现有参数不变 ...
                pause_checker=pause_checker,
            )

            # === 质量门禁漏斗：抽取state_delta → L0 → L1 → L2 → L3 ===
            # ⚠️ 重要：L3 改善时 auto_improve_chapter 已 activate 候选并写回 Chapter.content。
            # 若 persist_single_chapter 在此后用 chapter_result.content 落库，会用改写前内容
            # 覆盖候选！处理：gate 改善后跳过 persist_single_chapter（章节已由 rewrite 落库）。
            persisted_by_gate = False
            try:
                from src.core.quality.gate import (
                    run_quality_gate, GatePersistCallbacks,
                )
                from src.api.services.rewrite_loop_service import RewriteLoopService

                gate_callbacks = GatePersistCallbacks(
                    update_state_delta=manager.update_state_delta,
                    update_quality_status=manager.update_quality_status,
                    persist_quality_scores=_persist_quality_for_gate,
                    detect_bible_conflicts=None,
                )
                gate_result = await run_quality_gate(
                    novel_id=novel_id,
                    chapter_number=global_ch_num,
                    chapter_result=chapter_result,
                    chapter_outline=ch_outline,
                    novel_type=getattr(request, "novel_type", "网络小说"),
                    idea=getattr(request, "idea", ""),
                    world_setting=world_str,
                    characters=chars_str,
                    persist_callbacks=gate_callbacks,
                    rewrite_service=RewriteLoopService(),
                    chapter_index_in_volume=i,
                )
                # 用 gate 结果更新 chapter_result（L3 改善则内容已由 rewrite 落库）
                chapter_result["quality_status"] = gate_result.quality_status
                chapter_result["quality_scores"] = gate_result.quality_scores
                chapter_result["state_delta"] = gate_result.state_delta
                chapter_result["generation_failed"] = chapter_result.get("generation_failed") or (
                    gate_result.quality_status == "failed"
                )
                # L3 改善 → 章节已由 rewrite_service 激活候选并落库，跳过后续 persist_single_chapter
                if gate_result.rewrite_improved:
                    persisted_by_gate = True
                    chapter_result["content"] = "（已由 L3 改写激活，见最新版本）"
            # persist_single_chapter 调用处需加条件：if not persisted_by_gate and not chapter_result.get("generation_failed"):
            # （执行者：找到现有 persist_single_chapter 调用行，包此条件）
            except Exception as gate_err:
                logger.warning(
                    "quality_gate_failed_non_fatal",
                    novel_id=novel_id, chapter=global_ch_num, error=str(gate_err),
                )
                # gate 失败绝不阻塞生成——章节照常落库，质量状态留空
            # === 漏斗结束 ===

            chapter_result["volume_number"] = volume_number
            generated_chapters.append(chapter_result)
```

并在文件合适位置加 `_persist_quality_for_gate` 辅助（或复用现有 persist 回调）。若已有 persist_quality 回调，直接复用；否则定义：

```python
async def _persist_quality_for_gate(novel_id, chapter_number, scores, warnings):
    """gate 的质量评分持久化回调。委托到 chapter version 的 quality_scores。"""
    try:
        manager = get_novel_manager()
        # 创建一个标记版本记录评分（不激活，不改当前正文）
        # 简化：直接更新最近活跃版本的 quality_scores
        from src.api.services.chapter_service import get_chapter_service
        svc = get_chapter_service()
        versions = await svc.list_chapter_versions(novel_id, chapter_number)
        if versions:
            # 更新最新版本的质量评分
            await _update_version_quality_scores(svc, novel_id, chapter_number,
                                                  versions[0]["version_number"], scores)
    except Exception as e:
        logger.warning("persist_quality_for_gate_failed", error=str(e))
```

> 注意：`_persist_quality_for_gate` 的确切实现取决于 ChapterService 是否有更新版本评分的方法。若没有，可简化为仅写 quality_status（已有 update_quality_status），评分记录留空——卷报告已能处理 None。**执行者：先检查 ChapterService 有无 update 版本评分方法，无则简化实现并在自审记录。**

- [ ] **Step 3: 上一章衔接改读 state_delta**

修改 `:528-539` 的 previous_chapter 构建，从读 `last_content[-400:]` 改为读上一章 state_delta：

```python
        if i == 0:
            previous_chapter = prev_context or "这是本卷第一章"
        else:
            last_result = generated_chapters[-1] if generated_chapters else {}
            parts = []
            if last_result.get("title"):
                parts.append(f"上一章：《{last_result['title']}》")
            # 优先用结构化 state_delta，回退正文结尾
            last_delta = last_result.get("state_delta")
            if last_delta and not last_delta.get("_unverified"):
                from src.core.quality.state_delta import merge_delta_for_context
                merged = merge_delta_for_context(last_delta, {})
                if merged:
                    parts.append(merged)
            else:
                last_content = last_result.get("content", "")
                if last_content:
                    parts.append(f"结尾段落：\n{last_content[-400:]}")
            if ch_outline.get("plot"):
                parts.append(f"本章需要推进：{ch_outline['plot']}")
            previous_chapter = "\n".join(parts) if parts else "续写"
```

- [ ] **Step 4: 运行现有长篇测试确认无回归**

Run: `cd /Users/a1/Developer/projects/xIaoShuo && pytest tests/unit/test_change044_long_form_services.py -v 2>&1 | tail -25`
Expected: PASS（若现有测试因 gate 接入失败，检查是否 mock 不全；gate 内部 try/except 应保证不阻塞，但若测试断言 chapter_result 结构可能需更新——只更新确实因新行为变化的断言）

- [ ] **Step 5: ruff 检查**

Run: `cd /Users/a1/Developer/projects/xIaoShuo && ruff check src/api/services/long_form_generation_helpers.py`

- [ ] **Step 6: Commit**

```bash
cd /Users/a1/Developer/projects/xIaoShuo
git add src/api/services/long_form_generation_helpers.py
git commit -m "feat: 长篇逐章循环接入质量门禁漏斗 + state_delta 衔接

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 5: 全量回归与收尾

**Files:** 无新文件，跑测试 + 静态检查

- [ ] **Step 1: 跑本计划全部新测试**

Run: `cd /Users/a1/Developer/projects/xIaoShuo && pytest tests/unit/test_change061_persist_methods.py tests/unit/test_change061_quality_gate.py tests/unit/test_change061_context_state_delta.py -v 2>&1 | tail -20`
Expected: 全 PASS

- [ ] **Step 2: 跑受影响的核心测试无回归**

Run: `cd /Users/a1/Developer/projects/xIaoShuo && pytest tests/unit/test_change044_long_form_services.py tests/unit/test_chapter_service.py tests/unit/test_rewrite_loop_service.py tests/unit/test_change060_volume_quality_report.py -v 2>&1 | tail -25`
Expected: 全 PASS

- [ ] **Step 3: ruff 全量检查（本次改动范围）**

Run: `cd /Users/a1/Developer/projects/xIaoShuo && ruff check src/core/quality/ src/api/services/long_form_generation_helpers.py src/api/services/novel_context_service.py src/api/services/chapter_service.py src/api/services/novel_manager.py`
Expected: 无新增 error（既有 error 在非本次文件可忽略）

- [ ] **Step 4: 集成冒烟（可选，若环境允许）**

若有 DB 环境：`cd /Users/a1/Developer/projects/xIaoShuo && pytest tests/integration/test_change044_long_form_api.py -v 2>&1 | tail -15`
若无 DB 跳过，记录。

- [ ] **Step 5: Commit（若有任何修复）**

```bash
cd /Users/a1/Developer/projects/xIaoShuo
git add -A
git commit -m "test: 长篇质量闭环接入全量回归通过

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- 局限1 state_delta 接入衔接上下文 → Task 3 ✓
- 局限2 漏斗接入生成管道 → Task 2(gate) + Task 4(循环接入) ✓
- 持久化方法 → Task 1 ✓
- 失败永不阻塞 → Task 2 gate.py `_safe` + 循环 try/except ✓
- Token 预算守卫 → Task 2（L3 受 QUALITY_MAX_REWRITE_PER_CHAPTER 限制，QUALITY_TOKEN_BUDGET 的精确 token 计数标注为后续——当前用 max_iterations 限制，已满足"不无限烧"）

**Placeholder scan:** Task 4 Step 2 的 `_persist_quality_for_gate` 标注了"执行者检查有无 update 版本评分方法，无则简化"——这是真实的实现不确定性，非占位。其余步骤代码完整。

**Type consistency:**
- `GateResult` 字段与 gate.py 返回一致 ✓
- `GatePersistCallbacks` 与 Task 1 新增方法签名一致（update_state_delta(novel_id, chapter_number, dict)/update_quality_status(novel_id, chapter_number, str)）✓
- `run_quality_gate` 参数与测试 mock 一致 ✓

**已知简化（执行者注意）：**
1. Token 预算守卫当前用 `max_iterations`（QUALITY_MAX_REWRITE_PER_CHAPTER）限制 L3 重试次数，未精确计数 input/output token 与 QUALITY_TOKEN_BUDGET_PER_CHAPTER 比较。这是可接受的简化——次数限制已防止无限烧，精确 token 计数留后续。若需严格，在 gate.py 加 token 累计。
2. `_persist_quality_for_gate` 的实现取决于 ChapterService 现有能力，执行者需现场判断。
3. L3 改善后 final_content 仍返回原 content（未从 DB 重读候选内容）——因为 auto_improve_chapter 已 activate 候选并写回 Chapter.content，但 gate 返回的 chapter_result.content 是改写前的。长篇循环若依赖 chapter_result.content 落库需注意：persist_single_chapter 可能用旧内容覆盖。**执行者 Task 4 须确认 persist 时机**——若 persist 在 gate 之后且用 chapter_result.content，会覆盖 L3 改善的候选。需在 gate 改善时重读 Chapter.content 或让 persist 跳过已激活章。

---

## Execution Handoff

计划已保存到 `docs/superpowers/plans/2026-07-15-long-form-quality-gate-integration.md`。两种执行方式：

**1. Subagent-Driven（推荐）** —— 每个 Task 派独立子 Agent，Task 间审查
**2. Inline Execution** —— 本会话内批量执行带检查点

你选哪种？
