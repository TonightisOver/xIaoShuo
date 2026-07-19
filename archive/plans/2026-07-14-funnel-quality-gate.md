# 分级漏斗式质量门禁 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复质量闭环中的两个 P0 断点(参数不匹配、固定假分数),并建立"规则做闸门、LLM 做裁判、风险决定成本"的分级漏斗式质量门禁,让百万字长篇的质量检查真实且廉价。

**Architecture:** 四级漏斗 —— L0 规则门禁(零 Token,每章必过)→ L1 风险分级(零~极低 Token,决定是否走 LLM)→ L2 LLM 裁判(中成本,仅高风险章全文评估)→ L3 候选改写择优(高成本,仅不达标章触发)。默认"均衡模式":全章 L0+L1,关键章必审 L2,普通章按风险触发 L2。失败一律标记 `unverified`,绝不伪造合格分。版本管理修复 `is_active` 真实语义,使候选版本可"先存不激活、择优再激活"。卷级任务区分 `completed / partially_completed / completed_with_unverified_quality / failed`。

**Tech Stack:** Python 3.11 · FastAPI · LangGraph · SQLAlchemy(async) · pytest · structlog · DeepSeek API(use_flash/pro 双档)

---

## 关键现状(执行者必读)

1. **建表机制**:无 alembic。`src/core/database.py:70 init_db()` 用 `Base.metadata.create_all` 建表。给 `Chapter` 加新列后,开发库需手动 `ALTER TABLE chapters ADD COLUMN ...` 或重建库。生产环境需在部署文档记录 SQL。
2. **`generate_chapter_stream` 真实签名**(`src/core/llm/chapter_generator.py:241`):接受 `client, chapter_outline, previous_chapter, characters_json, world_setting_json, on_token, on_complete, storylines_json="", style_instruction="", kg_service=None, novel_id=None, target_words=None, blueprint=None, story_bible_context=None`。**没有 `pause_checker` 参数**。这是 P0 bug 根因。
3. **`evaluate_chapter_quality`**(`src/core/quality/evaluator.py:105`):返回 `QualityResult`,有 `.scores / .overall / .feedback / .suggestions / .to_scores_dict()`。解析失败时返回 `default_score`(调用方传 0.5 或 0.8)。当前 `quality_check.py:201` 传 `default_score=0.8` —— 解析失败会返回 0.8 假分,需改为标记 unverified。
4. **`chapter_service.create_chapter_version`**(`src/api/services/chapter_service.py:145`):**`is_active` 参数名存实亡** —— 无论 True/False 都会把 `content` 写回 `Chapter.content`(第 204 行),且创建时不清零同章其它版本的 `is_active`。这是 L3 候选择优必须先修的根因。`activate_chapter_version`(`:285`)是唯一正确"清零其它+同步正文"的方法。
5. **`generate_volume_quality_report`**(`src/api/services/long_form_generation_helpers.py:625`):八个维度全写死 0.7。这是 P0 假分根因。
6. **`quality_check.py:40`**:只取 `chapters[-1]`,只评估最后一章。
7. **`graph.py:38` `_quality_loop_decision`**:只检查 `overall >= QUALITY_THRESHOLD`,不看一致性硬门禁。
8. **`novel_generator.py:1058`**:卷级 `except` 里 `continue` 到下一卷,但循环外仍 `complete_task` 标记整体完成 —— 卷失败仍标完成。
9. **配置**(`src/core/config.py`):`QUALITY_THRESHOLD=0.7`、`QUALITY_LOOP_ENABLED=True`、`MAX_REGENERATION_ATTEMPTS=2`、`KNOWLEDGE_GRAPH_ENABLED=True`、`KG_SUBAGENT_ENABLED=True`。**无任何成本/质量模式开关**,需新增 `QUALITY_MODE`。
10. **测试位置**:`tests/unit/`(单元)、`tests/integration/`(集成)。现有相关测试:`test_change044_long_form_services.py`、`test_rewrite_loop_service.py`、`test_chapter_service.py`、`test_change034_quality_eval.py`。用 `changeNNN_` 前缀命名新测试文件,延续项目惯例。
11. **`task_manager.complete_task`**(`src/api/services/task_manager.py:139`):硬编码 `task.status = "completed"`。需改造为接收 status 参数。
12. **灌水检测**(`filler_detection_service.py:85`):仅字数启发式,无语义重复检测。L0 会在其基础上增强。

---

## File Structure

| 文件 | 责任 | 动作 |
|------|------|------|
| `src/core/llm/chapter_generator.py` | 单章流式生成 | 修改:新增 `pause_checker` 参数(P0) |
| `src/api/services/long_form_generation_helpers.py` | 长篇卷级生成+质量报告 | 修改:真实卷级质量报告(P0) |
| `src/core/quality/__init__.py` | 质量维度常量 | 修改:确认 `QUALITY_DIMENSIONS` 导出 |
| `src/core/quality/gate.py` | **新增**:分级漏斗门禁编排 | 创建 |
| `src/core/quality/rules.py` | **新增**:L0 零 Token 规则检查 | 创建 |
| `src/core/quality/risk.py` | **新增**:L1 风险分级 | 创建 |
| `src/core/quality/state_delta.py` | **新增**:结构化状态增量抽取/读写 | 创建 |
| `src/core/config.py` | 配置 | 修改:新增 `QUALITY_MODE` 等 |
| `src/core/langgraph/nodes/quality_check.py` | 质量检查节点 | 修改:全章评估+unverified+硬门禁 |
| `src/core/langgraph/graph.py` | 图路由 | 修改:一致性硬门禁 |
| `src/api/services/chapter_service.py` | 章节版本服务 | 修改:修复 `is_active` 语义 |
| `src/api/services/rewrite_loop_service.py` | 改写闭环 | 修改:L3 候选择优 |
| `src/api/services/novel_generator.py` | 长篇生成编排 | 修改:卷级质量闭环+任务状态区分 |
| `src/api/services/filler_detection_service.py` | 灌水检测 | 修改:接入 L0 规则 |
| `src/api/models/db_models.py` | ORM 模型 | 修改:`Chapter.state_delta` JSON 列 |
| `src/api/services/task_manager.py` | 任务管理 | 修改:`complete_task` 接收 status |
| `frontend/src/components/NovelQualityTab.vue` | 前端质量面板 | 修改:诚实化展示 |
| `tests/unit/test_change060_quality_gate.py` 等 | 测试 | 创建 |

---

## Task 1: 修复 P0 —— `generate_chapter_stream` 接受 `pause_checker`

**Files:**
- Modify: `src/core/llm/chapter_generator.py:241` (外层包装) 与 `src/core/llm/chapter_generator.py:294` (`_generate_single_chapter_inner`)

- [ ] **Step 1: 写契约测试 —— 验证 `pause_checker` 被接受并在循环中调用**

```python
# tests/unit/test_change060_chapter_generator_pause.py
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock

from src.core.llm.chapter_generator import generate_chapter_stream


class _FakeStream:
    """模拟 client.stream_generate 的异步迭代器。"""
    def __init__(self, tokens):
        self._tokens = list(tokens)

    def __aiter__(self):
        async def _gen():
            for t in self._tokens:
                yield t
        return _gen()


@pytest.mark.asyncio
async def test_generate_chapter_stream_accepts_pause_checker():
    """长篇调用传入 pause_checker 时不应抛 unexpected keyword argument。"""
    client = MagicMock()
    client.stream_generate = MagicMock(return_value=_FakeStream(["段落一", "段落二"]))
    pause_checker = AsyncMock(return_value=False)

    on_token = AsyncMock()
    on_complete = AsyncMock()

    result = await generate_chapter_stream(
        client=client,
        chapter_outline={"chapter": 1, "title": "测试章", "plot": "测试"},
        previous_chapter="",
        characters_json="[]",
        world_setting_json="{}",
        on_token=on_token,
        on_complete=on_complete,
        target_words=100,
        pause_checker=pause_checker,
    )

    assert result.get("generation_failed") is not True
    assert "段落一" in result.get("content", "")
    # pause_checker 至少被调用一次（在生成开始或续写循环中）
    assert pause_checker.call_count >= 1


@pytest.mark.asyncio
async def test_generate_chapter_stream_pause_true_aborts():
    """当 pause_checker 返回 True 时应中止生成。"""
    client = MagicMock()
    client.stream_generate = MagicMock(return_value=_FakeStream(["段落一"] * 10))
    pause_checker = AsyncMock(return_value=True)

    result = await generate_chapter_stream(
        client=client,
        chapter_outline={"chapter": 1, "title": "测试章", "plot": "测试"},
        previous_chapter="",
        characters_json="[]",
        world_setting_json="{}",
        on_token=AsyncMock(),
        on_complete=AsyncMock(),
        target_words=100,
        pause_checker=pause_checker,
    )

    # 暂停时应标记失败或中止，不能正常完成
    assert result.get("generation_failed") is True or result.get("paused") is True
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_change060_chapter_generator_pause.py -v`
Expected: FAIL with `unexpected keyword argument 'pause_checker'`

- [ ] **Step 3: 修改外层 `generate_chapter_stream` 接受并透传 `pause_checker`**

在 `src/core/llm/chapter_generator.py:241` 的 `generate_chapter_stream` 签名末尾加参数,并透传给 `_generate_single_chapter_inner`:

```python
async def generate_chapter_stream(
    client: Any,
    chapter_outline: dict[str, Any],
    previous_chapter: str,
    characters_json: str,
    world_setting_json: str,
    on_token: Callable[[str, str], Awaitable[None]],
    on_complete: Callable[[str], Awaitable[None]],
    storylines_json: str = "",
    style_instruction: str = "",
    kg_service: Any | None = None,
    novel_id: str | None = None,
    target_words: int | None = None,
    blueprint: dict | None = None,
    story_bible_context: str | None = None,
    pause_checker: Callable[[], Awaitable[bool]] | None = None,
) -> dict[str, Any]:
    """Generate a single chapter using streaming for body text.

    Args:
        pause_checker: 可选的异步回调，返回 True 表示任务被暂停，应中止本章生成。
    """
    try:
        return await asyncio.wait_for(
            _generate_single_chapter_inner(
                client=client,
                chapter_outline=chapter_outline,
                previous_chapter=previous_chapter,
                characters_json=characters_json,
                world_setting_json=world_setting_json,
                storylines_json=storylines_json,
                style_instruction=style_instruction,
                kg_service=kg_service,
                novel_id=novel_id,
                target_words=target_words,
                blueprint=blueprint,
                story_bible_context=story_bible_context,
                on_token=on_token,
                on_complete=on_complete,
                pause_checker=pause_checker,
            ),
            timeout=CHAPTER_TIMEOUT_SECONDS,
        )
    except TimeoutError:
        chapter_num = chapter_outline.get("chapter", 0)
        logger.error(
            "chapter_generation_timeout",
            chapter=chapter_num,
            timeout=CHAPTER_TIMEOUT_SECONDS,
        )
        return {
            "chapter": chapter_num,
            "title": chapter_outline.get("title", f"Chapter {chapter_num}"),
            "content": f"[Chapter generation failed: timeout ({CHAPTER_TIMEOUT_SECONDS}s)]",
            "word_count": 0,
            "generation_failed": True,
        }
```

- [ ] **Step 4: 修改 `_generate_single_chapter_inner` 接受并在生成循环检查 `pause_checker`**

在 `src/core/llm/chapter_generator.py:294` 签名末尾加 `pause_checker` 参数。然后在正文生成前(约第 423 行 `if on_token:` 之前)插入暂停检查:

```python
async def _generate_single_chapter_inner(
    client: Any,
    chapter_outline: dict[str, Any],
    previous_chapter: str,
    characters_json: str,
    world_setting_json: str,
    storylines_json: str = "",
    style_instruction: str = "",
    kg_service: Any | None = None,
    novel_id: str | None = None,
    target_words: int | None = None,
    blueprint: dict | None = None,
    story_bible_context: str | None = None,
    on_token: Callable[[str, str], Awaitable[None]] | None = None,
    on_complete: Callable[[str], Awaitable[None]] | None = None,
    pause_checker: Callable[[], Awaitable[bool]] | None = None,
) -> dict[str, Any]:
    """生成单章内容。

    Args:
        target_words: Target word count for long-form mode (None for standard mode)
        blueprint: 预生成的章节蓝图（可选，传入则跳过蓝图生成/查询）
        pause_checker: 异步暂停检查，返回 True 则中止本章生成
    """
    # === 暂停检查（生成前）===
    chapter_num = chapter_outline.get("chapter", 0)
    if pause_checker is not None and await pause_checker():
        logger.info("chapter_generation_paused_before_start", chapter=chapter_num)
        return {
            "chapter": chapter_num,
            "title": chapter_outline.get("title", f"第{chapter_num}章"),
            "content": "",
            "word_count": 0,
            "generation_failed": True,
            "paused": True,
        }
    # ... 原有逻辑保持不变 ...
```

然后在正文流式生成循环(约第 423-427 行)中,每个 token 后插入暂停检查:

```python
    if on_token:
        content = ""
        async for token in client.stream_generate(prompt, use_flash=True):
            content += token
            await on_token(token, content)
            if pause_checker is not None and await pause_checker():
                logger.info("chapter_generation_paused_mid_stream", chapter=chapter_num)
                return {
                    "chapter": chapter_num,
                    "title": chapter_outline.get("title", f"第{chapter_num}章"),
                    "content": content,
                    "word_count": len(content),
                    "generation_failed": True,
                    "paused": True,
                }
    else:
        content = await client.generate(prompt, max_tokens=gen_max_tokens, use_flash=True)
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/unit/test_change060_chapter_generator_pause.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: 确认现有长篇调用已正确传入 `pause_checker`(已在 `long_form_generation_helpers.py:585` 传入,无需改)**

Run: `grep -n "pause_checker" src/api/services/long_form_generation_helpers.py`
Expected: 出现 `pause_checker=pause_checker` 在 `generate_chapter_stream` 调用处

- [ ] **Step 7: 跑现有相关测试确认无回归**

Run: `pytest tests/unit/test_change044_long_form_services.py tests/unit/test_change034_quality_eval.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add src/core/llm/chapter_generator.py tests/unit/test_change060_chapter_generator_pause.py
git commit -m "fix: generate_chapter_stream 接受 pause_checker 参数(P0)
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 2: 修复 P0 —— 卷级质量报告真实化(失败标记 unverified,不写假分)

**Files:**
- Modify: `src/api/services/long_form_generation_helpers.py:625` (`generate_volume_quality_report`)
- Create: `tests/unit/test_change060_volume_quality_report.py`

- [ ] **Step 1: 写失败测试 —— 失败章节应被标记为 unverified,告警非空**

```python
# tests/unit/test_change060_volume_quality_report.py
import pytest
from src.api.services.long_form_generation_helpers import generate_volume_quality_report


@pytest.mark.asyncio
async def test_failed_chapter_produces_warning_not_fake_score():
    """传入 generation_failed=True 的章节，报告不应给 0.7 假分，而应标记 unverified 并告警。"""
    chapters = [
        {
            "chapter": 1,
            "title": "第一章",
            "content": "正常内容，足够长，足够长，足够长，足够长，足够长，足够长，足够长。",
            "word_count": 30,
        },
        {
            "chapter": 2,
            "title": "第二章",
            "content": "[章节生成失败: timeout]",
            "word_count": 0,
            "generation_failed": True,
        },
    ]
    report = await generate_volume_quality_report(
        novel_id="novel-1", volume_number=1, chapters=chapters
    )

    # 不能再是固定 0.7
    assert report["avg_quality_score"] != 0.7 or report.get("has_unverified")
    # 失败章节必须出现在告警或 unverified 列表
    assert report["warnings"], "失败章节应产生告警"
    unverified = [c for c in report.get("unverified_chapters", [])]
    assert any(c.get("chapter") == 2 for c in unverified + report["warnings"])


@pytest.mark.asyncio
async def test_normal_chapters_no_false_alarm():
    """正常章节不应被误报为灌水或停滞。"""
    chapters = [
        {"chapter": i, "title": f"第{i}章", "content": "内容" * 500, "word_count": 1000}
        for i in range(1, 4)
    ]
    report = await generate_volume_quality_report(
        novel_id="novel-1", volume_number=1, chapters=chapters
    )
    assert report["chapter_count"] == 3
    assert not report.get("unverified_chapters")
    # 短章节不应被无脑标为灌水（1000 字不算灌水）
    assert not report["filler_chapters"] or all(
        c.get("chapter") not in [1, 2, 3] for c in report["filler_chapters"]
    )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest tests/unit/test_change060_volume_quality_report.py -v`
Expected: FAIL (当前实现返回固定 0.7 + 空 warnings)

- [ ] **Step 3: 重写 `generate_volume_quality_report` 为基于真实 L0 规则的报告**

替换 `src/api/services/long_form_generation_helpers.py:625-659` 整个函数:

```python
async def generate_volume_quality_report(
    novel_id: str,
    volume_number: int,
    chapters: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate quality report for a volume based on real L0 rule checks.

    不再返回固定 0.7 假分。失败/异常章节标记为 unverified，告警非空。
    真实的多维 LLM 评分由 quality_check 节点逐章持久化，此处汇总已存评分 +
    对每章跑 L0 规则门禁。
    """
    from src.core.quality.rules import run_l0_rules
    from src.api.services.novel_manager import get_novel_manager

    manager = get_novel_manager()
    total_word_count = sum(ch.get("word_count", 0) for ch in chapters)
    chapter_count = len(chapters)

    warnings: list[dict[str, Any]] = []
    unverified_chapters: list[dict[str, Any]] = []
    filler_chapters: list[dict[str, Any]] = []
    stalled_chapters: list[dict[str, Any]] = []

    # 计算本卷平均字数用于灌水判断
    avg_word = (total_word_count / chapter_count) if chapter_count else 0

    # 收集已持久化的逐章评分（若存在）
    persisted_scores: dict[int, dict[str, float]] = {}
    try:
        for ch in chapters:
            ch_num = ch.get("chapter")
            if not ch_num:
                continue
            # quality_check 节点会把评分写入 ChapterVersion.quality_score 或专门表
            # 这里先尝试从 manager 获取最新评分（若接口存在），不存在则跳过
            scores = await _get_persisted_chapter_scores(manager, novel_id, ch_num)
            if scores:
                persisted_scores[ch_num] = scores
    except Exception:
        # 评分获取失败不应阻断报告生成
        pass

    dimension_keys = [
        "advancement", "character_consistency", "world_consistency",
        "pacing", "conflict", "foreshadowing", "dialogue_quality",
        "emotional_impact",
    ]

    for ch in chapters:
        ch_num = ch.get("chapter")
        content = ch.get("content", "") or ""
        word_count = ch.get("word_count", 0) or len(content)
        title = ch.get("title", f"第{ch_num}章")

        # 1. 失败章 → unverified + 告警
        if ch.get("generation_failed") or ch.get("paused"):
            unverified_chapters.append({"chapter": ch_num, "title": title, "reason": "generation_failed"})
            warnings.append({
                "chapter": ch_num, "title": title,
                "severity": "error", "type": "generation_failed",
                "message": f"第{ch_num}章生成失败，质量未评估",
            })
            continue

        # 2. L0 规则门禁
        l0 = run_l0_rules(
            content=content,
            word_count=word_count,
            avg_word_count=avg_word,
            chapter_outline=ch.get("outline") or ch.get("plot"),
            chapter_number=ch_num,
        )
        for v in l0.get("violations", []):
            warnings.append({
                "chapter": ch_num, "title": title,
                "severity": v.get("severity", "warning"),
                "type": v.get("type"),
                "message": v.get("message"),
            })
        if l0.get("filler_flag"):
            filler_chapters.append({"chapter": ch_num, "title": title, "score": l0.get("filler_score", 0)})
        if l0.get("stalled_flag"):
            stalled_chapters.append({"chapter": ch_num, "title": title})

    # 汇总分数：仅基于已持久化的真实评分，未评估的维度不伪造
    has_unverified = bool(unverified_chapters)
    if persisted_scores:
        dim_sums: dict[str, list[float]] = {k: [] for k in dimension_keys}
        for sc in persisted_scores.values():
            for k in dimension_keys:
                v = sc.get(k)
                if isinstance(v, (int, float)):
                    dim_sums[k].append(float(v))
        avg_scores = {
            k: round(sum(v) / len(v), 4) if v else None
            for k, v in dim_sums.items()
        }
        evaluated = [v for v in avg_scores.values() if v is not None]
        avg_quality_score = round(sum(evaluated) / len(evaluated), 4) if evaluated else None
    else:
        # 没有任何真实评分时，分数为 None（未评估），绝不写 0.7
        avg_scores = {k: None for k in dimension_keys}
        avg_quality_score = None

    return {
        "volume_number": volume_number,
        "chapter_count": chapter_count,
        "total_word_count": total_word_count,
        "avg_scores": avg_scores,
        "avg_quality_score": avg_quality_score,
        "has_unverified": has_unverified,
        "unverified_chapters": unverified_chapters,
        "warnings": warnings,
        "filler_chapters": filler_chapters,
        "stalled_chapters": stalled_chapters,
    }


async def _get_persisted_chapter_scores(
    manager, novel_id: str, chapter_number: int
) -> dict[str, float] | None:
    """从持久层获取单章已存评分。若接口不存在或无评分，返回 None。

    这里尝试调用 ChapterService 暴露的评分查询；若尚未实现逐章评分持久化，
    返回 None 以触发"未评估"语义，而非伪造 0.7。
    """
    try:
        # 优先用 version 上的 quality_score（单值），后续可扩展为多维度
        versions = await manager.list_chapter_versions(novel_id, chapter_number)
        for v in versions:
            qs = v.get("quality_score")
            if isinstance(qs, (int, float)):
                return {"overall": float(qs)}
        return None
    except Exception:
        return None
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_change060_volume_quality_report.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/api/services/long_form_generation_helpers.py tests/unit/test_change060_volume_quality_report.py
git commit -m "fix: 卷级质量报告改用真实 L0 规则，失败章标记 unverified(P0)
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 3: L0 规则门禁模块 —— 零 Token 规则检查

**Files:**
- Create: `src/core/quality/rules.py`
- Create: `tests/unit/test_change060_l0_rules.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/unit/test_change060_l0_rules.py
from src.core.quality.rules import run_l0_rules


def test_failed_generation_flagged():
    result = run_l0_rules(content="", word_count=0, avg_word_count=2000, chapter_outline="x", chapter_number=1)
    types = [v["type"] for v in result["violations"]]
    assert "too_short" in types


def test_repetitive_paragraphs_detected():
    # 同一段落重复三次
    para = "他走进了房间，环顾四周，什么也没说。" * 1
    content = "\n\n".join([para] * 6)
    result = run_l0_rules(content=content, word_count=len(content), avg_word_count=1000, chapter_outline="x", chapter_number=1)
    types = [v["type"] for v in result["violations"]]
    assert "repetitive_paragraphs" in types


def test_outline_coverage_checked():
    outline = "林炎挑战陈安"
    content = "林炎和陈安完全不相关的故事，没有任何挑战情节。" * 10
    result = run_l0_rules(content=content, word_count=len(content), avg_word_count=1000, chapter_outline=outline, chapter_number=1)
    types = [v["type"] for v in result["violations"]]
    assert "low_outline_coverage" in types


def test_normal_chapter_clean():
    content = "这是一段全新的原创正文内容，情节推进明显，没有重复。" * 30
    result = run_l0_rules(content=content, word_count=len(content), avg_word_count=len(content), chapter_outline="原创", chapter_number=1)
    assert result["filler_flag"] is False
    assert result["stalled_flag"] is False


def test_filler_flagged_for_very_short():
    result = run_l0_rules(content="短", word_count=1, avg_word_count=2000, chapter_outline="x", chapter_number=1)
    assert result["filler_flag"] is True
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/unit/test_change060_l0_rules.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: 实现 `rules.py`**

```python
# src/core/quality/rules.py
"""L0 规则门禁 —— 零 Token 的章节质量预筛。

所有检查基于正则/字数/哈希，不调用 LLM。用于：
- 每章生成后立即跑，作为分级漏斗的第一道闸门
- 卷级质量报告的真实数据来源（替代固定 0.7 假分）
"""

import re
from typing import Any

from src.core.config import get_settings

# 阈值
MIN_WORD_COUNT = 800
SHORT_FRACTION_OF_AVG = 0.4   # < 平均字数 40% → 灌水候选
REPETITION_THRESHOLD = 0.5    # 段落重复率超过此值 → 重复告警
OUTLINE_COVERAGE_MIN = 0.2    # 大纲关键词命中率低于此 → 覆盖率告警
SENTENCE_PREFIX_LEN = 8       # 句首 N 字用于句式复用检测


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
        if prefix_repeat >= 0.4:
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
    """计算正文对大纲关键词的命中率（0-1）。"""
    if not outline:
        return 1.0  # 无大纲时不报覆盖率问题
    if isinstance(outline, dict):
        text = " ".join(str(v) for v in outline.values())
    else:
        text = str(outline)
    # 提取 2 字以上的关键词（简化：取所有长度>=2 的连续中文片段）
    keywords = re.findall(r"[一-龥]{2,}", text)
    keywords = list(dict.fromkeys(keywords))  # 去重保序
    if not keywords:
        return 1.0
    hit = sum(1 for kw in keywords if kw in content)
    return hit / len(keywords)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_change060_l0_rules.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/core/quality/rules.py tests/unit/test_change060_l0_rules.py
git commit -m "feat: L0 零 Token 规则门禁(字数/重复/句式/大纲覆盖率)
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 4: L1 风险分级模块 —— 决定是否走 LLM

**Files:**
- Create: `src/core/quality/risk.py`
- Modify: `src/core/config.py` (新增 `QUALITY_MODE`)
- Create: `tests/unit/test_change060_risk.py`

- [ ] **Step 1: 在 config.py 新增 `QUALITY_MODE` 配置**

在 `src/core/config.py` 的 `Settings` 类中(约第 64 行 `MAX_REGENERATION_ATTEMPTS` 之后)加:

```python
    # 质量门禁成本模式：economy(成本优先) / balanced(均衡) / high(质量优先)
    QUALITY_MODE: str = "balanced"
    # 普通章(非关键章)的 L2 LLM 评审抽检比例(0-1)，economy 模式下更低
    QUALITY_SAMPLE_RATIO: float = 0.2
    # 单章最大 L3 改写次数（避免无限循环）
    QUALITY_MAX_REWRITE_PER_CHAPTER: int = 2
    # 单章评审 Token 预算上限（达到即转人工）
    QUALITY_TOKEN_BUDGET_PER_CHAPTER: int = 20000
    # 关键章节类型（开篇/高潮/反转/卷末/结局）必审 L2
    QUALITY_CRITICAL_CHAPTER_TYPES: tuple[str, ...] = (
        "opening", "climax", "twist", "volume_end", "ending", "key_milestone",
    )
```

- [ ] **Step 2: 写失败测试**

```python
# tests/unit/test_change060_risk.py
from src.core.quality.risk import classify_risk, RiskLevel


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
```

- [ ] **Step 3: 运行确认失败**

Run: `pytest tests/unit/test_change060_risk.py -v`
Expected: FAIL (module not found)

- [ ] **Step 4: 实现 `risk.py`**

```python
# src/core/quality/risk.py
"""L1 风险分级 —— 基于 L0 规则结果决定是否调用 LLM 评审。

规则做闸门：正常章节只走 L0+L1，几乎不烧 Token；
只有高风险章触发 L2 LLM 全文评估，仅不达标章触发 L3 改写。
"""

from enum import Enum
from typing import Any

from src.core.config import get_settings


class RiskLevel(str, Enum):
    LOW = "low"       # 直接通过，不调 LLM
    MEDIUM = "medium"  # 按抽检比例决定是否调 LLM
    HIGH = "high"     # 必调 LLM 全文评审


def classify_risk(
    *,
    l0_rules: dict[str, Any],
    chapter_type: str | None = None,
    is_failed: bool = False,
) -> RiskLevel:
    """根据 L0 规则结果与章节类型分级。

    高风险条件（任一满足）：
      - 生成失败
      - 章节类型属于关键章节（开篇/高潮/反转/卷末/结局）
      - L0 出现 error 级违规
      - filler_flag 或 stalled_flag 为 True

    中风险：
      - L0 出现 warning 级违规

    低风险：
      - L0 干净且非关键章节
    """
    settings = get_settings()
    critical_types = set(getattr(settings, "QUALITY_CRITICAL_CHAPTER_TYPES", ()))

    if is_failed:
        return RiskLevel.HIGH

    if chapter_type and chapter_type in critical_types:
        return RiskLevel.HIGH

    violations = l0_rules.get("violations", [])
    if any(v.get("severity") == "error" for v in violations):
        return RiskLevel.HIGH
    if l0_rules.get("filler_flag") or l0_rules.get("stalled_flag"):
        return RiskLevel.HIGH
    if any(v.get("severity") == "warning" for v in violations):
        return RiskLevel.MEDIUM

    return RiskLevel.LOW


def should_invoke_l2(
    risk: RiskLevel,
    chapter_index_in_volume: int,
) -> bool:
    """决定是否对该章调用 L2 LLM 评审。

    - HIGH：必调
    - MEDIUM：按抽检比例（每 N 章抽 1 章）
    - LOW：在 balanced/high 模式下也做低频抽检，economy 模式不抽检
    """
    settings = get_settings()
    mode = getattr(settings, "QUALITY_MODE", "balanced")

    if risk == RiskLevel.HIGH:
        return True
    if risk == RiskLevel.MEDIUM:
        # 每 3 章抽 1 章
        return chapter_index_in_volume % 3 == 0
    # LOW
    if mode == "high":
        return chapter_index_in_volume % 5 == 0  # 低频抽检
    if mode == "balanced":
        return chapter_index_in_volume % 5 == 0
    return False  # economy: 不抽检低风险
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/unit/test_change060_risk.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add src/core/quality/risk.py src/core/config.py tests/unit/test_change060_risk.py
git commit -m "feat: L1 风险分级 + QUALITY_MODE 配置(均衡/成本/质量)
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 5: 结构化状态增量 —— Chapter 表 JSON 列 + 抽取模块

**Files:**
- Modify: `src/api/models/db_models.py:281` (`Chapter` 加 `state_delta`)
- Create: `src/core/quality/state_delta.py`
- Create: `tests/unit/test_change060_state_delta.py`

- [ ] **Step 1: 在 `Chapter` 模型加 `state_delta` JSON 列**

在 `src/api/models/db_models.py` 的 `Chapter` 类中(第 302 行 `updated_at` 之后、`novel` relationship 之前)加:

```python
    # 结构化状态增量：本章关键事件/人物变化/伏笔/时间线/未解决冲突
    # 替代"正文前 300 字截取"作为长期记忆，供 L1 风险分级与卷级检查使用
    state_delta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    # 本章是否通过质量门禁及评估状态：verified / unverified / failed
    quality_status: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
```

确保文件顶部已导入 `JSON`(检查 `from sqlalchemy import ... JSON`)。

- [ ] **Step 2: 手动给已有开发库加列(无 alembic)**

Run: `python -c "import asyncio; from src.core.database import engine; from sqlalchemy import text; asyncio.run(lambda: engine.begin().sync_exec(lambda c: c.execute(text('ALTER TABLE chapters ADD COLUMN IF NOT EXISTS state_delta JSON, ADD COLUMN IF NOT quality_status VARCHAR(20)'))))" 2>&1 || echo "如库不存在将自动 create_all，可忽略"`

> 说明：`init_db()` 的 `create_all` 对新库会自动建这两列；对已有库需上述 ALTER。开发环境通常重建库即可。

- [ ] **Step 3: 写 `state_delta` 抽取模块的失败测试**

```python
# tests/unit/test_change060_state_delta.py
import pytest
from unittest.mock import AsyncMock, patch

from src.core.quality.state_delta import extract_state_delta, DEFAULT_DELTA_SCHEMA


def test_default_schema_has_required_keys():
    for k in ["key_events", "character_changes", "timeline_delta",
              "foreshadows_planted", "foreshadows_resolved",
              "unresolved_conflicts", "next_chapter_must_carry"]:
        assert k in DEFAULT_DELTA_SCHEMA


@pytest.mark.asyncio
async def test_extract_state_delta_parses_llm_json():
    fake_llm_json = '''```json
    {
      "key_events": ["陈安击败林炎"],
      "character_changes": {"陈安": {"位置": "万剑门", "情绪": "隐忍"}},
      "timeline_delta": {"推进": "3天"},
      "foreshadows_planted": ["残卷古文"],
      "foreshadows_resolved": [],
      "unresolved_conflicts": ["林炎师姐未现"],
      "next_chapter_must_carry": ["藏匿残卷"]
    }
    ```'''
    with patch("src.core.quality.state_delta.get_llm_client") as mock_get:
        client = AsyncMock()
        client.generate = AsyncMock(return_value=fake_llm_json)
        mock_get.return_value = client
        delta = await extract_state_delta(
            chapter_content="正文内容...", chapter_number=5,
            novel_type="玄幻", world_setting="修真世界", characters="陈安/林炎",
        )
    assert delta["key_events"] == ["陈安击败林炎"]
    assert delta["character_changes"]["陈安"]["位置"] == "万剑门"
    assert delta["next_chapter_must_carry"] == ["藏匿残卷"]


@pytest.mark.asyncio
async def test_extract_state_delta_fallback_on_parse_failure():
    with patch("src.core.quality.state_delta.get_llm_client") as mock_get:
        client = AsyncMock()
        client.generate = AsyncMock(return_value="not json at all")
        mock_get.return_value = client
        delta = await extract_state_delta(
            chapter_content="正文", chapter_number=5,
            novel_type="玄幻", world_setting="w", characters="c",
        )
    # 解析失败应返回 schema 占位 + _unverified 标记，不能抛异常
    assert delta.get("_unverified") is True
    assert delta["key_events"] == []
```

- [ ] **Step 4: 运行确认失败**

Run: `pytest tests/unit/test_change060_state_delta.py -v`
Expected: FAIL (module not found)

- [ ] **Step 5: 实现 `state_delta.py`**

```python
# src/core/quality/state_delta.py
"""结构化状态增量 —— 每章生成后抽取，替代"正文前 N 字截取"作为长期记忆。

用于：
- L1 风险分级（比对状态增量而非全文）
- 连续章/卷级检查（只传增量，不传正文，降 Token）
- 下一章生成的衔接上下文
"""

import json
from typing import Any

import structlog

from src.core.json_utils import safe_json_parse
from src.core.llm.client import get_llm_client

logger = structlog.get_logger(__name__)

DEFAULT_DELTA_SCHEMA: dict[str, Any] = {
    "key_events": [],
    "causes": [],
    "character_changes": {},
    "timeline_delta": {},
    "foreshadows_planted": [],
    "foreshadows_resolved": [],
    "unresolved_conflicts": [],
    "next_chapter_must_carry": [],
}

EXTRACT_PROMPT = """你是小说连续性编辑器。请从本章正文中抽取结构化状态增量，供下一章生成与长期一致性检查使用。

【小说背景】
- 类型：{novel_type}
- 世界观：{world_setting}
- 人物：{characters}

【本章正文】
---
{chapter_content}
---

请抽取并仅输出一个 JSON 对象，字段如下：
{{
  "key_events": ["本章关键事件1", ...],
  "causes": ["导致这些事件的因果1", ...],
  "character_changes": {{ "人物名": {{"位置": "...", "情绪": "...", "能力": "...", "新物品": [...], "关系变化": "..."}}, ... }},
  "timeline_delta": {{ "推进": "N天/N月", "now": "主线时间锚点" }},
  "foreshadows_planted": ["新埋伏笔1", ...],
  "foreshadows_resolved": ["本章回收的伏笔1", ...],
  "unresolved_conflicts": ["未解决的冲突1", ...],
  "next_chapter_must_carry": ["下一章必须承接的状态1", ...]
}}

只输出 JSON，不要任何解释或闲聊。
"""


async def extract_state_delta(
    *,
    chapter_content: str,
    chapter_number: int,
    novel_type: str = "网络小说",
    world_setting: str = "",
    characters: str = "",
    content_limit: int = 6000,
) -> dict[str, Any]:
    """调用 LLM 抽取本章状态增量。失败时返回 schema 占位 + _unverified 标记。"""
    prompt = EXTRACT_PROMPT.format(
        novel_type=novel_type,
        world_setting=world_setting or "未设定",
        characters=characters or "未设定",
        chapter_content=chapter_content[:content_limit],
        chapter_number=chapter_number,
    )
    try:
        client = get_llm_client()
        raw = await client.generate(prompt, max_tokens=1500)
        parsed = safe_json_parse(raw, fallback=None)
        if isinstance(parsed, dict):
            # 合并 schema，补全缺失字段
            delta = {k: parsed.get(k, v) for k, v in DEFAULT_DELTA_SCHEMA.items()}
            return delta
    except Exception as e:
        logger.warning("state_delta_extract_failed", chapter=chapter_number, error=str(e))

    # 解析失败 —— 返回占位 + unverified 标记（绝不抛异常阻断主流程）
    fallback = dict(DEFAULT_DELTA_SCHEMA)
    fallback["_unverified"] = True
    return fallback


def merge_delta_for_context(prev_delta: dict[str, Any] | None, cur_delta: dict[str, Any]) -> str:
    """把多章状态增量合并为供下一章生成用的衔接上下文文本。"""
    if not prev_delta and not cur_delta:
        return ""
    parts: list[str] = []
    if prev_delta:
        carry = prev_delta.get("next_chapter_must_carry") or []
        if carry:
            parts.append("上一章要求承接：" + "；".join(carry))
        evts = prev_delta.get("key_events") or []
        if evts:
            parts.append("上一章关键事件：" + "；".join(evts[-3:]))
    if cur_delta:
        ch = cur_delta.get("character_changes") or {}
        if ch:
            parts.append("人物当前状态：" + json.dumps(ch, ensure_ascii=False))
    return "\n".join(parts)
```

- [ ] **Step 6: 运行测试确认通过**

Run: `pytest tests/unit/test_change060_state_delta.py -v`
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add src/api/models/db_models.py src/core/quality/state_delta.py tests/unit/test_change060_state_delta.py
git commit -m "feat: 结构化状态增量(Chapter.state_delta)替代正文截取
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 6: L2 诚实化 —— quality_check 节点失败标记 unverified + 全章评估 + 硬门禁

**Files:**
- Modify: `src/core/langgraph/nodes/quality_check.py` (全章评估 + unverified + 硬门禁)
- Modify: `src/core/langgraph/graph.py:20` (`_quality_loop_decision` 加一致性硬门禁)
- Create: `tests/unit/test_change060_quality_check_unverified.py`

- [ ] **Step 1: 写失败测试 —— 评估失败应标记 unverified 而非返回 0.8 假分**

```python
# tests/unit/test_change060_quality_check_unverified.py
import pytest
from unittest.mock import AsyncMock, patch

from src.core.langgraph.nodes import quality_check


@pytest.mark.asyncio
async def test_eval_failure_marks_unverified_not_fake_score():
    """evaluate_chapter_quality 抛异常时，节点应标记 unverified，overall=None，绝不返回 0.82 兜底。"""
    state = {
        "chapters": [{"chapter": 1, "title": "测试", "content": "正文内容", "word_count": 4}],
        "novel_type": "玄幻",
        "idea": "测试",
        "world_setting": None,
        "characters": [],
        "novel_id": "novel-1",
    }
    config = {"configurable": {}}

    with patch("src.core.langgraph.nodes.quality_check.evaluate_chapter_quality",
               new=AsyncMock(side_effect=Exception("LLM 挂了"))):
        result = await quality_check.node(state, config)

    scores = result["quality_scores"]
    assert scores.get("overall") is None, "评估失败不应给假分，应为 None(unverified)"
    assert scores.get("status") == "unverified"


@pytest.mark.asyncio
async def test_consistency_block_blocks_pass_regardless_of_overall():
    """一致性被判定 block 时，无论 overall 多高，路由都应判定不通过。"""
    from src.core.langgraph.graph import _quality_loop_decision
    state = {
        "quality_scores": {"overall": 0.95, "consistency": 0.3, "consistency_blocked": True},
        "_regeneration_count": 0,
    }
    # overall 0.95 >> 阈值 0.7，但一致性 block → 应走 regenerate
    decision = _quality_loop_decision(state, "human_review")
    assert decision == "regenerate"
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/unit/test_change060_quality_check_unverified.py -v`
Expected: FAIL

- [ ] **Step 3: 修改 `quality_check.py` —— 失败标记 unverified + 全章评估**

在 `src/core/langgraph/nodes/quality_check.py` 中:

**(a) 全章评估**：把第 42 行 `last_chapter = chapters[-1] if chapters else None` 改为循环评估所有未评估章节。但为控制 Token，只对 L1 判定需要 L2 的章节全文评估，其余走 L0。简化实现：评估 `chapters[-1]`(保持向后兼容)但额外把 L0 结果对所有章节写入 state。

替换第 58-65 行 `if not last_chapter:` 分支后的逻辑，在 `try` 块前加入 L0 全章预筛，并把默认分改为 unverified 语义：

修改 `default_scores`(第 44-56 行)为:

```python
    # 评估失败的兜底：标记为 unverified，overall=None，绝不伪造合格分
    unverified_scores = {
        "overall": None,
        "advancement": None,
        "conflict": None,
        "character_consistency": None,
        "world_consistency": None,
        "foreshadowing": None,
        "pacing": None,
        "readability": None,
        "trope_alignment": None,
        "consistency": 1.0,
        "status": "unverified",
    }
```

把所有 `default_scores` 引用替换为 `unverified_scores`(第 60、245、256、258 行)。

**(b) L0 全章预筛 + 一致性硬门禁**：在第 67 行 `chapter_content = ...` 之后、第 71 行 KG 检查之前插入:

```python
    # L0 规则门禁：对所有章节跑零 Token 预筛
    from src.core.quality.rules import run_l0_rules
    from src.core.quality.risk import classify_risk, should_invoke_l2

    l0_all: list[dict] = []
    avg_wc = sum(len(c.get("content", "")) for c in chapters) / max(len(chapters), 1)
    for idx, ch in enumerate(chapters):
        l0 = run_l0_rules(
            content=ch.get("content", ""),
            word_count=ch.get("word_count"),
            avg_word_count=avg_wc,
            chapter_outline=ch.get("plot") or ch.get("outline"),
            chapter_number=ch.get("chapter", idx + 1),
        )
        l0_all.append(l0)
```

**(c) 一致性 block → 硬门禁标记**：在第 112 行 `consistency_score = 0.3` 旁边加:

```python
                    if verdict == "block":
                        consistency_score = 0.3
                        consistency_blocked = True  # 硬门禁：无论 overall 多少都不通过
                    elif verdict == "warn":
                        consistency_score = 0.8
                        consistency_blocked = False
                    else:
                        consistency_score = 1.0
                        consistency_blocked = False
```

(在函数顶部 `consistency_score = 1.0` 旁初始化 `consistency_blocked = False`)

**(d) 成功路径加 consistency_blocked**：在第 206 行 `quality_scores["consistency"] = consistency_score` 后加:

```python
        quality_scores["consistency"] = consistency_score
        if consistency_blocked:
            quality_scores["consistency_blocked"] = True
            quality_scores["status"] = "consistency_blocked"
```

**(e) 兜底返回也带 consistency_blocked**：第 256 行 return 块加:

```python
    return {
        **state,
        "quality_scores": {**unverified_scores, "consistency_blocked": consistency_blocked},
        "consistency_warnings": consistency_warnings,
        "current_stage": "quality_check_completed",
        "kg_continuity_report": kg_continuity_report,
    }
```

- [ ] **Step 4: 修改 `graph.py` `_quality_loop_decision` 加一致性硬门禁**

替换 `src/core/langgraph/graph.py:20-45`:

```python
def _quality_loop_decision(state: NovelState, pass_target: str) -> str:
    """质量循环条件路由的统一实现。

    - QUALITY_LOOP_ENABLED=False：直接通过到 pass_target（跳过重生成）
    - 一致性硬门禁：consistency_blocked 为 True 时，无论 overall 多少都必须 regenerate
    - 否则：overall >= QUALITY_THRESHOLD 或重试次数 >= MAX_REGENERATION_ATTEMPTS 时通过，
      否则回 regenerate

    Args:
        state: 当前状态
        pass_target: 质量达标时应进入的节点名（如 "human_review" / "review"）

    Returns:
        pass_target 或 "regenerate"
    """
    settings = get_settings()
    if not getattr(settings, "QUALITY_LOOP_ENABLED", True):
        return pass_target

    quality_scores = state.get("quality_scores", {})
    # 硬门禁：一致性严重冲突，无论综合分多少都不通过
    if quality_scores.get("consistency_blocked"):
        if state.get("_regeneration_count", 0) >= getattr(settings, "MAX_REGENERATION_ATTEMPTS", 2):
            # 达到重试上限也过不去 → 放行到 pass_target 但标记 unverified（不伪造通过）
            return pass_target
        return "regenerate"

    # 未评估状态不应伪装通过
    if quality_scores.get("status") == "unverified":
        if state.get("_regeneration_count", 0) >= getattr(settings, "MAX_REGENERATION_ATTEMPTS", 2):
            return pass_target
        return "regenerate"

    quality_score = quality_scores.get("overall", 0)
    if quality_score is None:
        return pass_target  # 无分（unverified 且达重试上限）→ 放行，不阻塞流程

    regeneration_count = state.get("_regeneration_count", 0)
    threshold = getattr(settings, "QUALITY_THRESHOLD", 0.8)
    max_attempts = getattr(settings, "MAX_REGENERATION_ATTEMPTS", 2)

    if quality_score >= threshold or regeneration_count >= max_attempts:
        return pass_target
    return "regenerate"
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest tests/unit/test_change060_quality_check_unverified.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: 跑现有质量测试确认无回归**

Run: `pytest tests/unit/test_change034_quality_eval.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add src/core/langgraph/nodes/quality_check.py src/core/langgraph/graph.py tests/unit/test_change060_quality_check_unverified.py
git commit -m "fix: 质量检查失败标记 unverified + 一致性硬门禁(P0/P1)
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 7: L3 候选择优 —— 修复 is_active 语义 + 改写不改善则回滚

**Files:**
- Modify: `src/api/services/chapter_service.py:145` (`create_chapter_version` 修复 is_active)
- Modify: `src/api/services/rewrite_loop_service.py:195` (候选择优)
- Create: `tests/unit/test_change060_is_active_semantics.py`
- Create: `tests/unit/test_change060_rewrite_rollback.py`

- [ ] **Step 1: 写 is_active 语义失败测试**

```python
# tests/unit/test_change060_is_active_semantics.py
import pytest
from unittest.mock import AsyncMock, patch

from src.api.services.chapter_service import ChapterService


@pytest.mark.asyncio
async def test_create_version_inactive_does_not_overwrite_chapter_content():
    """is_active=False 时，Chapter.content 不应被候选版本覆盖。"""
    svc = ChapterService()
    with patch("src.api.services.chapter_service.get_db_session") as mock_session:
        # 模拟 session 上下文
        session = AsyncMock()
        ch = type("Ch", (), {"content": "原正文", "word_count": 3, "updated_at": None})()
        session.execute = AsyncMock(side_effect=[
            AsyncMock(scalar_one_or_none=AsyncMock(return_value=ch)),  # chapter 查询
            AsyncMock(scalar_one_or_none=AsyncMock(return_value=0)),   # max version
        ])
        session.add = AsyncMock()
        session.flush = AsyncMock()
        mock_session.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_session.return_value.__aexit__ = AsyncMock(return_value=None)

        await svc.create_chapter_version(
            novel_id="n1", chapter_number=1, content="候选正文",
            source="ai_rewrite", is_active=False,
        )

    # is_active=False → 原正文不应被覆盖
    assert ch.content == "原正文", "is_active=False 时不应覆盖 Chapter.content"
```

- [ ] **Step 2: 运行确认失败**

Run: `pytest tests/unit/test_change060_is_active_semantics.py -v`
Expected: FAIL (当前实现无条件覆盖)

- [ ] **Step 3: 修复 `create_chapter_version` 的 is_active 语义**

在 `src/api/services/chapter_service.py:145` 中，修改第 185-206 行。关键改动：`is_active=False` 时只创建版本快照，不写回 `Chapter.content`；`is_active=True` 时清零同章其它版本再写回。

替换 `version = ChapterVersion(...)` 到 `ch.content = ...` 这段:

```python
            version = ChapterVersion(
                novel_id=novel_id,
                chapter_number=chapter_number,
                version_number=new_version,
                content=content,
                word_count=word_count,
                source=source,
                rewrite_instruction=rewrite_instruction,
                quality_score=quality_score,
                model_name=model_name,
                prompt_summary=prompt_summary,
                diff_from_previous=diff_from_previous,
                kg_conflicts=kg_conflicts,
                user_notes=user_notes,
                is_active=is_active,
                created_at=datetime.now(UTC),
            )
            session.add(version)

            # is_active=True：清零同章其它版本，并把候选正文写回 Chapter
            # is_active=False：只创建快照，不污染当前正文（供候选择优比较后再决定激活）
            if is_active:
                await session.execute(
                    ChapterVersion.__table__.update()
                    .where(
                        ChapterVersion.novel_id == novel_id,
                        ChapterVersion.chapter_number == chapter_number,
                        ChapterVersion.version_number != new_version,
                    )
                    .values(is_active=False)
                )
                ch.content = content
                ch.word_count = word_count
                ch.updated_at = datetime.now(UTC)

            await session.flush()
            return new_version
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest tests/unit/test_change060_is_active_semantics.py -v`
Expected: PASS

- [ ] **Step 5: 跑现有 chapter_service 测试确认无回归**

Run: `pytest tests/unit/test_chapter_service.py -v`
Expected: PASS（如有因 is_active 语义变化的失败，需相应更新测试断言——但不应破坏"激活版本同步正文"的正常路径）

- [ ] **Step 6: 写改写择优失败测试**

```python
# tests/unit/test_change060_rewrite_rollback.py
import pytest
from unittest.mock import AsyncMock, patch

from src.api.services.rewrite_loop_service import RewriteLoopService


@pytest.mark.asyncio
async def test_rewrite_reverts_when_score_drops():
    """改写后总分下降时，不应激活候选版本，应回滚到基线。"""
    svc = RewriteLoopService()

    # 基线分 0.7，候选分 0.5（下降）→ 不应激活候选
    eval_seq = [
        {"overall": 0.7, "advancement": 0.7, "character_consistency": 0.8, "world_consistency": 0.8,
         "conflict": 0.7, "foreshadowing": 0.7, "pacing": 0.7, "readability": 0.7, "trope_alignment": 0.7},  # 基线
        {"overall": 0.5, "advancement": 0.5, "character_consistency": 0.8, "world_consistency": 0.8,
         "conflict": 0.5, "foreshadowing": 0.5, "pacing": 0.5, "readability": 0.5, "trope_alignment": 0.5},  # 候选(下降)
    ]
    eval_mock = AsyncMock(side_effect=eval_seq)

    manager = AsyncMock()
    manager.get_chapter = AsyncMock(return_value={"content": "基线正文", "chapter": 1})
    # 候选版本号 2
    manager.create_chapter_version = AsyncMock(return_value=2)
    manager.activate_chapter_version = AsyncMock(return_value=True)
    manager.list_chapter_versions = AsyncMock(return_value=[{"version_number": 1, "is_active": True}])

    action_svc = AsyncMock()
    action_svc.generate_rewrite_actions = AsyncMock(return_value=[{"action_type": "enhance", "dimension": "pacing"}])

    with patch("src.api.services.rewrite_loop_service._evaluate_chapter_quality_for_novel", eval_mock), \
         patch("src.api.services.rewrite_loop_service.get_novel_manager", return_value=manager), \
         patch("src.api.services.rewrite_loop_service.QualityActionService", return_value=action_svc), \
         patch("src.api.services.rewrite_loop_service.batch_targeted_rewrite", AsyncMock(return_value="候选正文")), \
         patch("src.api.services.rewrite_loop_service.get_db_session") as mock_db:
        mock_db.return_value.__aenter__ = AsyncMock(return_value=AsyncMock())
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)
        result = await svc.auto_improve_chapter("n1", 1, max_iterations=1, target_score=0.9)

    # 候选版本号 2 不应被激活（分数下降）
    activate_calls = manager.activate_chapter_version.call_args_list
    activated_versions = [c.kwargs.get("version_number") for c in activate_calls]
    assert 2 not in activated_versions, "分数下降的候选版本不应被激活"
```

- [ ] **Step 7: 运行确认失败**

Run: `pytest tests/unit/test_change060_rewrite_rollback.py -v`
Expected: FAIL (当前实现先激活再评分)

- [ ] **Step 8: 重写 `rewrite_loop_service.py` 改写循环为候选择优**

替换 `src/api/services/rewrite_loop_service.py:195-244` 的"创建新版本→评估→判断达标"段为:

```python
            # 7. 创建候选版本（is_active=False，不污染当前正文）
            action_types = [a.get("action_type", "") for a in actions]
            candidate_version = await manager.create_chapter_version(
                novel_id=novel_id,
                chapter_number=chapter_number,
                content=new_content,
                source="ai_rewrite",
                rewrite_instruction=(
                    f"auto_improve_iter{iteration}:"
                    f" {','.join(action_types)}"
                ),
                is_active=False,  # 关键：先不激活
            )

            # 8. 评估候选版本分数
            scores_after = await _evaluate_chapter_quality_for_novel(
                novel_id, chapter_number, new_content
            )

            # 9. 候选择优：只有总分上升且保护维度不下降，才激活候选
            PROTECTED_DIMS = ["character_consistency", "world_consistency"]
            overall_up = scores_after.get("overall", 0) > scores_before.get("overall", 0)
            protected_ok = all(
                scores_after.get(dim, 0) >= scores_before.get(dim, 0) - 0.05  # 允许 0.05 容差
                for dim in PROTECTED_DIMS
            )

            improvement_history.append({
                "iteration": iteration,
                "scores_before": scores_before,
                "scores_after": scores_after,
                "actions_taken": action_types,
                "candidate_version": candidate_version,
                "activated": overall_up and protected_ok,
                "word_count": len(new_content),
            })

            logger.info(
                "auto_improve_iteration_done",
                novel_id=novel_id,
                chapter_number=chapter_number,
                iteration=iteration,
                overall_before=scores_before.get("overall"),
                overall_after=scores_after.get("overall"),
                activated=overall_up and protected_ok,
            )

            if overall_up and protected_ok:
                # 改善 → 激活候选版本
                await manager.activate_chapter_version(
                    novel_id=novel_id,
                    chapter_number=chapter_number,
                    version_number=candidate_version,
                )
                final_scores = scores_after
                all_pass_after = all(
                    scores_after.get(dim, 0) >= target_score for dim in target_dims
                )
                if all_pass_after:
                    break
            else:
                # 未改善 → 不激活候选，保留基线，记录失败
                logger.info(
                    "auto_improve_candidate_rejected",
                    novel_id=novel_id,
                    chapter_number=chapter_number,
                    candidate_version=candidate_version,
                    overall_before=scores_before.get("overall"),
                    overall_after=scores_after.get("overall"),
                )
                final_scores = scores_before  # 维持基线分
```

- [ ] **Step 9: 运行测试确认通过**

Run: `pytest tests/unit/test_change060_rewrite_rollback.py tests/unit/test_rewrite_loop_service.py -v`
Expected: PASS

- [ ] **Step 10: Commit**

```bash
git add src/api/services/chapter_service.py src/api/services/rewrite_loop_service.py tests/unit/test_change060_is_active_semantics.py tests/unit/test_change060_rewrite_rollback.py
git commit -m "fix: is_active 真实语义 + L3 候选择优(不改善则不激活)(P1)
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 8: 卷级任务状态区分 —— 卷失败/未验证不再伪完成

**Files:**
- Modify: `src/api/services/task_manager.py:139` (`complete_task` 接收 status)
- Modify: `src/api/services/novel_generator.py:1058-1079` (卷循环统计 + 区分状态)
- Create: `tests/unit/test_change060_task_status.py`

- [ ] **Step 1: 改 `complete_task` 接收 status 参数**

替换 `src/api/services/task_manager.py:139-167`:

```python
    async def complete_task(
        self,
        task_id: str,
        result: dict[str, Any],
        status: str = "completed",
    ) -> None:
        """完成任务

        Args:
            task_id: 任务 ID
            result: 任务结果
            status: completed / partially_completed / completed_with_unverified_quality / failed
        """
        async with get_db_session() as session:
            db_result = await session.execute(
                select(Task).where(Task.task_id == task_id)
            )
            task = db_result.scalar_one_or_none()

            if not task:
                logger.warning(f"Task {task_id} not found")
                return

            task.status = status
            task.completed_at = datetime.now()
            task.result = result
            task.progress = {
                "current_stage": result.get("current_stage", status),
                "completed_chapters": len(result.get("chapters", [])),
                "total_chapters": len(result.get("chapters", [])),
                "percentage": 100 if status == "completed" else result.get("completion_percentage", 100),
            }

            await session.commit()
            logger.info(f"Completed task {task_id} with status {status}")
```

- [ ] **Step 2: 写失败测试**

```python
# tests/unit/test_change060_task_status.py
import pytest
from unittest.mock import AsyncMock, patch

from src.api.services.task_manager import TaskManager


@pytest.mark.asyncio
async def test_complete_task_accepts_status():
    tm = TaskManager()
    with patch("src.api.services.task_manager.get_db_session") as mock_db:
        session = AsyncMock()
        task = type("T", (), {"status": None, "completed_at": None, "result": None, "progress": None})()
        session.execute = AsyncMock(return_value=AsyncMock(scalar_one_or_none=AsyncMock(return_value=task)))
        session.commit = AsyncMock()
        mock_db.return_value.__aenter__ = AsyncMock(return_value=session)
        mock_db.return_value.__aexit__ = AsyncMock(return_value=None)

        await tm.complete_task("t1", {"chapters": []}, status="partially_completed")

    assert task.status == "partially_completed"
```

- [ ] **Step 3: 运行确认通过**

Run: `pytest tests/unit/test_change060_task_status.py -v`
Expected: PASS

- [ ] **Step 4: 修改 `novel_generator.py` 卷循环统计 + 状态区分**

在 `src/api/services/novel_generator.py` 卷循环 `for` 之前(约第 990 行)初始化统计变量:

```python
        failed_volumes: list[int] = []
        unverified_volumes: list[int] = []
```

在 `except Exception as vol_error:` 块(第 1058 行)的 `continue` 前加:

```python
            except Exception as vol_error:
                logger.error(
                    "volume_generation_failed",
                    novel_id=novel_id,
                    volume_number=vol_num,
                    error=str(vol_error),
                )
                failed_volumes.append(vol_num)
                await progress_service.update_volume_status(
                    novel_id=novel_id,
                    volume_number=vol_num,
                    status="failed",
                    errors=[str(vol_error)],
                )
                continue
```

在卷循环正常完成块(第 1034-1048 行)中，质量报告生成后检查 `has_unverified`:

```python
                # Generate quality report for this volume
                quality_report = await generate_volume_quality_report(
                    novel_id=novel_id,
                    volume_number=vol_num,
                    chapters=vol_chapters,
                )
                if quality_report.get("has_unverified"):
                    unverified_volumes.append(vol_num)
```

替换循环后的 `complete_task` 调用(第 1075-1079 行):

```python
        # 根据卷级结果区分任务状态：不再把失败/未验证伪装成 completed
        if failed_volumes and not all_chapters_generated:
            final_status = "failed"
        elif failed_volumes:
            final_status = "partially_completed"
        elif unverified_volumes:
            final_status = "completed_with_unverified_quality"
        else:
            final_status = "completed"

        await task_manager.complete_task(
            task_id,
            {
                "novel_id": novel_id,
                "total_volumes": total_volumes,
                "total_chapters": len(all_chapters_generated),
                "failed_volumes": failed_volumes,
                "unverified_volumes": unverified_volumes,
                "completion_percentage": int(
                    len(all_chapters_generated) / max(
                        getattr(request, "volumes", 1) * max(chapter_end - chapter_start + 1, 1), 1
                    ) * 100
                ) if all_chapters_generated else 0,
            },
            status=final_status,
        )
```

- [ ] **Step 5: 跑长篇服务测试确认无回归**

Run: `pytest tests/unit/test_change044_long_form_services.py -v`
Expected: PASS（若有断言依赖 `completed` 状态，需相应更新为接受状态枚举）

- [ ] **Step 6: Commit**

```bash
git add src/api/services/task_manager.py src/api/services/novel_generator.py tests/unit/test_change060_task_status.py
git commit -m "fix: 卷级任务区分 completed/partially/unverified/failed(P1)
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 9: 前端质量面板诚实化

**Files:**
- Modify: `frontend/src/components/NovelQualityTab.vue:42` (无数据时显示"未评估")

- [ ] **Step 1: 读取当前 `NovelQualityTab.vue` 第 38-50 行与 197 行附近**

Run: `sed -n '35,50p;190,210p' frontend/src/components/NovelQualityTab.vue`

- [ ] **Step 2: 修改"状态极佳"文案为诚实展示**

找到第 42 行附近:

```vue
      <div v-if="allWarnings.length === 0" class="...">
        ✅ 暂无严重质量告警，全书逻辑及推进节奏状态极佳。
      </div>
```

替换为:

```vue
      <div v-if="allWarnings.length === 0 && !hasUnverified" class="...">
        ✅ 暂无严重质量告警，全书逻辑及推进节奏状态良好。
      </div>
      <div v-else-if="hasUnverified" class="quality-tab__unverified">
        ⚠️ 部分章节质量未评估（生成失败或评审异常），以下数据不完整。
      </div>
```

并在 `<script setup>` 的计算属性中新增 `hasUnverified`:

```javascript
const hasUnverified = computed(() => {
  return (qualityReport.value?.volumes || []).some(
    v => v.quality_report?.has_unverified || (v.quality_report?.unverified_chapters || []).length > 0
  )
})
```

- [ ] **Step 3: 前端构建验证**

Run: `cd frontend && npm run build 2>&1 | tail -20`
Expected: 构建成功无报错

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/NovelQualityTab.vue
git commit -m "fix: 质量面板未评估时显示诚实提示而非状态极佳(P0)
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 10: 灌水检测接入 L0 规则 + 全量回归

**Files:**
- Modify: `src/api/services/filler_detection_service.py:85` (`_calculate_filler_score` 复用 L0)
- Run: 全量相关测试

- [ ] **Step 1: 让 `filler_detection_service` 复用 L0 规则**

在 `src/api/services/filler_detection_service.py` 顶部加导入:

```python
from src.core.quality.rules import run_l0_rules
```

替换 `_calculate_filler_score`(第 85-126 行)为:

```python
    def _calculate_filler_score(
        self, chapter: Chapter, avg_word_count: float
    ) -> float:
        """Calculate filler score. 复用 L0 规则门禁的重复/句式/字数检测。"""
        content = chapter.content or ""
        l0 = run_l0_rules(
            content=content,
            word_count=chapter.word_count,
            avg_word_count=avg_word_count,
            chapter_outline=None,
            chapter_number=chapter.chapter_number,
        )
        # L0 的 filler_score 综合了字数、段落重复、句式；取其值
        return l0.get("filler_score", 0.0)
```

- [ ] **Step 2: 全量回归测试**

Run: `pytest tests/unit/test_change044_long_form_services.py tests/unit/test_rewrite_loop_service.py tests/unit/test_chapter_service.py tests/unit/test_change034_quality_eval.py tests/unit/test_change060_*.py -v`
Expected: 全部 PASS

- [ ] **Step 3: 跑 ruff/mypy 静态检查**

Run: `ruff check src/core/quality/ src/api/services/long_form_generation_helpers.py src/api/services/chapter_service.py src/api/services/rewrite_loop_service.py 2>&1 | tail -20`
Expected: 无 error

Run: `mypy src/core/quality/ 2>&1 | tail -20`
Expected: 无新增 error

- [ ] **Step 4: Commit**

```bash
git add src/api/services/filler_detection_service.py
git commit -m "refactor: 灌水检测复用 L0 规则(段落重复/句式/字数)
Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- P0 参数不匹配 → Task 1 ✓
- P0 固定假分数 → Task 2 ✓ (+ Task 9 前端诚实化 ✓)
- P1 质量检查只查最后一章 → Task 6 L0 全章预筛 ✓ (L2 全文评估仍只评末章以控 Token,但 unverified 硬门禁确保不伪通过)
- P1 失败默认通过 → Task 6 unverified + Task 8 状态区分 ✓
- P1 卷级不闭环 → Task 8 ✓
- P1 改写越改越差 → Task 7 候选择优 ✓
- P1 上下文薄弱 → Task 5 state_delta ✓ (接入下一章生成的衔接由 Task 5 的 `merge_delta_for_context` 提供,但需在后续 task 接入 `novel_context_service` —— 见下方已知局限)
- P2 正文固定 flash / 模型分层路由 → 未在本计划内(用户选 P0+L0/L1 范围)
- 成本控制(均衡模式) → Task 4 QUALITY_MODE + risk.py ✓

**Placeholder scan:** 无 TBD/TODO/占位。所有代码步骤含完整代码。

**Type consistency:**
- `run_l0_rules` 返回 `{violations, filler_flag, filler_score, stalled_flag, outline_coverage}` —— Task 2/4/6/10 使用一致 ✓
- `classify_risk` 返回 `RiskLevel` 枚举 —— Task 4/6 一致 ✓
- `extract_state_delta` 返回 dict 含 `DEFAULT_DELTA_SCHEMA` 字段 —— Task 5 一致 ✓
- `create_chapter_version(is_active=False)` 语义 —— Task 7 修复后 Task 2 不受影响(Task 2 用的是 `list_chapter_versions` 读) ✓
- `complete_task(status=...)` —— Task 8 一致 ✓

**已知局限(需后续 task 接入,不属本次范围):**
1. `state_delta` 已抽取并存入 `Chapter.state_delta`,但 `novel_context_service.build_rewrite_context` 仍用 `content[:300]`。把 `prev_chapter_summary` 改读 `Chapter.state_delta`(用 `merge_delta_for_context`)应在下一轮做。本次仅建好基础设施 + 抽取持久化。
2. L0 全章预筛结果目前只写入 state 供报告,尚未驱动 `should_invoke_l2` 实际拦截章节生成 —— 这是分级漏斗的运行时编排,建议作为下一轮 Task(接入 `chapter_generation` 节点)。本计划聚焦"让数据真实",运行时编排为后续。
3. P2 模型分层路由(use_flash 分层)未做。
4. 读者模拟 A/B、设定锁定、一键改写前端闭环未做。

---

## Execution Handoff

计划已保存到 `docs/superpowers/plans/2026-07-14-funnel-quality-gate.md`。两种执行方式:

**1. Subagent-Driven(推荐)** —— 我为每个 Task 派发独立子 Agent 实现,Task 间审查,快速迭代。

**2. Inline Execution** —— 在本会话内按 executing-plans 批量执行,带检查点审查。

你选哪种?
