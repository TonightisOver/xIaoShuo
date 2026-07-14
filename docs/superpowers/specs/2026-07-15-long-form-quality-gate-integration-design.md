# 长篇质量闭环接入设计

> 把已建好的 L0/L1/L2/L3 分级漏斗 + state_delta 结构化记忆接入长篇逐章生成管道，让质量闭环真正运行起来。

## 背景与目标

前一轮（feat/funnel-quality-gate）已建成分级漏斗的各组件：L0 规则门禁（Task3）、L1 风险分级（Task4）、state_delta 抽取（Task5）、quality_check unverified+硬门禁（Task6）、is_active 候选择优（Task7）。但这些组件**未接入生成管道**——`extract_state_delta` 无任何调用点，`Chapter.state_delta` 列恒空，L0 预筛只收集不拦截，长篇衔接上下文仍用 `content[:300]` 截取正文。

本轮目标：**让漏斗跑起来，让记忆生效**。接入后达成：
- 每章生成后跑 L0 规则 + 抽取 state_delta，结构化状态增量替代正文截取作为下一章衔接上下文（改善几十万字连贯性）
- 高风险章触发 L2 全文评审，不达标触发 L3 候选择优（质量闭环闭合）
- 成本由风险决定：低风险章零 LLM 评审，仅高风险章走 L2/L3

## 范围边界

**仅接入长篇主路径**：`long_form_generation_helpers.generate_volume_chapters` 逐章循环 + `novel_context_service`。标准模式（`chapter_generation` 节点）保持现状（它已有 quality_check 节点）。

**不含**（后续独立工作）：
- P2 模型分层路由（use_flash 按章节类型分层）
- rewrite_loop 孤儿候选版本清理
- 标准模式接入漏斗

## 架构

长篇逐章生成循环（`generate_volume_chapters`）里，每章生成后接入完整漏斗：

```
每章生成完成
  ↓
① 抽取 state_delta（flash，必做）→ 持久化 Chapter.state_delta
  ↓
② L0 规则门禁（零 Token）→ violations + filler/stalled 标记
  ↓
③ L1 风险分级（基于 L0 + state_delta + chapter_type）
   ├─ 低风险：直接通过，不调 LLM
   ├─ 中风险：按抽检比例 → 可能走 L2
   └─ 高风险：必走 L2
  ↓
④ L2 LLM 全文评审（仅高风险/抽检章）→ 8维评分 + 一致性检查
   ├─ 达标 or unverified：通过
   └─ 不达标且非 unverified：触发 L3
  ↓
⑤ L3 候选改写择优（仅 L2 不达标）→ 基线 vs 候选，改善才激活
  ↓
⑥ 更新衔接上下文：下一章用 state_delta（merge_delta_for_context）替代 content[:300]
```

**关键顺序**：state_delta 抽取在 L0 之前——L1 分级和 L2 评审都可用 state_delta 作为低成本输入。L0 失败章（generation_failed）直接跳到落库标记 failed，不走 L1/L2。

## 组件分解

### 1. 质量门禁编排器（新增）

**`src/core/quality/gate.py`**

核心函数：
```python
async def run_quality_gate(
    *,
    novel_id: str,
    chapter_number: int,
    chapter_result: dict,        # 生成结果（含 content/word_count/chapter_type/generation_failed）
    chapter_outline: dict | None,
    novel_type: str,
    idea: str,
    world_setting: str,
    characters: str,
    persist_callbacks: GatePersistCallbacks,  # 写 state_delta/quality_status/scores 的回调
    rewrite_service: RewriteLoopService | None = None,  # L3，可选
    chapter_index_in_volume: int = 0,
) -> GateResult:
```

返回 `GateResult`：
```python
@dataclass
class GateResult:
    final_content: str           # 最终章节内容（L3 改善则用候选，否则原内容）
    quality_status: str          # verified / unverified / consistency_blocked / failed
    quality_scores: dict         # 8维 + overall（低风险章未走 L2 时各维度为 None；卷报告汇总时跳过 None 维度，Task2 已处理）
    state_delta: dict            # 抽取的状态增量（失败则带 _unverified）
    l0_result: dict              # L0 规则结果
    risk_level: RiskLevel        # L1 分级
    l2_evaluated: bool           # 是否走了 L2
    rewrite_attempted: bool      # 是否走了 L3
    rewrite_improved: bool | None
    tokens_used: int             # 单章累计 Token
    warnings: list[dict]
```

**编排逻辑**（gate.py 内部）：
1. 若 `generation_failed`/`paused` → 直接返回 `quality_status=failed`，不跑后续
2. 抽取 state_delta（调 `extract_state_delta`，flash）→ 持久化（回调）
3. L0 规则（`run_l0_rules`）
4. L1 分级（`classify_risk`）
5. 若 `should_invoke_l2`（基于风险+索引）→ L2 评审（`evaluate_chapter_quality`）
   - **一致性判定**：复用 evaluate_chapter_quality 返回的 `character_consistency` / `world_consistency` 维度分数，低于 0.4 视为 block（不重新调 KG 服务，避免过重）。可选叠加 `detect_bible_conflicts` 回调（若注入）做 StoryBible 硬冲突检测。
   - 一致性 block → `quality_status=consistency_blocked`，不再 L3
   - 评分达标（overall >= QUALITY_THRESHOLD）→ `verified`
   - 评分不达标且 L3 可用 → L3
   - L2 异常 → `unverified`
6. L3 改写（`rewrite_service.auto_improve_chapter`，受 `QUALITY_MAX_REWRITE_PER_CHAPTER` 和 `QUALITY_TOKEN_BUDGET_PER_CHAPTER` 守卫）→ 改善则用候选内容，未改善保留基线 `unverified`
7. 持久化 quality_status + scores（回调）

**Token 守卫**：gate.py 维护单章累计 Token（L2 评审 + L3 改写的 input/output token），达 `QUALITY_TOKEN_BUDGET_PER_CHAPTER`（20000）即停止 L3 重试，转 `unverified`。

**关键不变量**：gate.py 任何环节失败都返回可用的 `GateResult`（最坏 `quality_status=unverified`，`final_content`=原内容），**永不抛异常阻塞调用方**。

### 2. 落库回调接口

gate.py 不直接碰 DB，通过注入的回调持久化：

```python
@dataclass
class GatePersistCallbacks:
    update_state_delta: Callable[[str, int, dict], Awaitable[None]]      # novel_id, ch_num, delta
    update_quality_status: Callable[[str, int, str], Awaitable[None]]    # novel_id, ch_num, status
    persist_quality_scores: Callable[[str, int, dict, list], Awaitable[None]]  # 沿用现有 persist_quality
    detect_bible_conflicts: Callable | None = None                        # 一致性检查（可选）
```

这些回调由 `novel_generator`/`long_form_generation_helpers` 在调用 gate 时注入，复用已有的持久化路径（`persist_quality`、`_sync_chapter_type_to_db` 等）。`update_state_delta` / `update_quality_status` 需在 `ChapterService`/`NovelManager` 新增对应方法。

### 3. 衔接上下文改造

**`src/api/services/novel_context_service.py`**

`build_rewrite_context` 的 `prev_chapter_summary` / `next_chapter_summary`：
- 优先读 `Chapter.state_delta`，用 `merge_delta_for_context` 转文本
- `state_delta` 为 None（历史章未抽取）时回退 `content[:300]`（兼容）
- 同样改造 `build_generation_context` 中上一章衔接（`get_chapter_tail` 路径）

**`src/api/services/long_form_generation_helpers.py`**

逐章循环（:518 起）：
- 生成后调 `run_quality_gate`，用返回的 `final_content` 替换 chapter_result 的 content（L3 改善生效）
- 上一章衔接（:536 `last_content[-400:]`）改为读上一章 `state_delta`
- gate 返回的 quality_status/quality_scores 写入 chapter_result 供卷报告（Task2 已消费）

### 4. 持久化方法（新增）

`ChapterService` + `NovelManager` 新增：
```python
async def update_state_delta(self, novel_id, chapter_number, state_delta: dict) -> None
async def update_quality_status(self, novel_id, chapter_number, status: str) -> None
```

简单 UPDATE，不创建新版本（state_delta/quality_status 是 Chapter 表字段，非版本字段）。

## 数据流

### 正常流（低风险章）
```
生成章 → 抽取state_delta(flash) → 持久化state_delta → L0 → L1=LOW → 直接通过
→ 质量评分=None(未评审) → quality_status=verified(规则通过) → 落库
→ 下一章衔接用本章state_delta
```
成本：1次生成 + 1次flash抽取。不调 L2。

### 高风险章（L2 达标）
```
生成章 → 抽取state_delta → L0 → L1=HIGH → L2全文评审 → 达标
→ 持久化评分+state_delta+quality_status=verified → 落库
```

### 高风险章（L2 不达标，L3 改善）
```
... → L2不达标 → L3: 候选版本(is_active=False) → 评分比较 → 改善
→ activate候选 → 用候选内容 → quality_status=verified → 落库
```

### 高风险章（L3 未改善 / Token 超限）
```
... → L3未改善 or Token超限 → 保留基线 → quality_status=unverified → 落库(基线内容)
→ 卷报告has_unverified=True(Task2已消费) → 任务状态completed_with_unverified_quality(Task8已消费)
```

## 失败处理矩阵

| 情况 | 处理 | quality_status | 阻塞生成 |
|------|------|---------------|---------|
| 生成失败 | 跳过漏斗 | failed | 否(已有占位) |
| state_delta抽取失败 | 返回_unverified占位 | 不影响后续 | 否 |
| L0严重违规(一致性block) | 标记 | consistency_blocked | 否,记入卷报告 |
| L2评审异常 | 标记 | unverified | 否 |
| L3改写未改善 | 保留基线 | unverified | 否 |
| L3 Token超限 | 停止重试 | unverified | 否 |

**核心不变量**：漏斗任何环节失败都不阻塞章节落库和下一章生成。最坏 quality_status=unverified，章节内容仍是可用基线。保证百万字生成不因单章评审卡死。

## 测试策略

gate.py 是编排器，依赖的各组件（L0/L1/L2/state_delta/L3）已有各自测试。gate.py 测试聚焦**编排流程与失败矩阵**，用 mock 各组件：

`tests/unit/test_change061_quality_gate.py`：
- `test_failed_chapter_skips_funnel`：generation_failed 直接返回 failed，不调抽取/L0/L2
- `test_low_risk_skips_l2`：L1=LOW 时不调 evaluate_chapter_quality
- `test_high_risk_invokes_l2`：L1=HIGH 时调 L2，达标返回 verified
- `test_l2_failure_marks_unverified`：L2 抛异常 → unverified，不阻塞
- `test_l2_below_threshold_triggers_l3`：L2 不达标 → 调 rewrite_service
- `test_l3_no_improvement_keeps_baseline`：L3 未改善 → final_content=原内容，unverified
- `test_consistency_block_marks_blocked`：L2 一致性 block → consistency_blocked，不调 L3
- `test_token_budget_exhausted_stops_rewrite`：Token 超限 → 停止 L3，unverified
- `test_state_delta_persisted`：抽取后调 update_state_delta 回调
- `test_paused_chapter_skips_funnel`：paused 直接返回，不跑漏斗

衔接上下文改造测试：
- `test_build_rewrite_context_uses_state_delta`：有 state_delta 时用 merge_delta_for_context
- `test_build_rewrite_context_fallback_to_content`：state_delta=None 回退 content[:300]

持久化方法测试：
- `test_update_state_delta` / `test_update_quality_status`：UPDATE 正确

集成测试（不跑全量，仅长篇服务）：
- `test_change061_long_form_gate_integration`：mock LLM，验证 generate_volume_chapters 调 gate 且卷报告消费 quality_status

## 依赖与复用

全部复用前一轮已建并测试通过的组件：
- `src/core/quality/rules.run_l0_rules`（Task3）
- `src/core/quality/risk.classify_risk` / `should_invoke_l2`（Task4）
- `src/core/quality/state_delta.extract_state_delta` / `merge_delta_for_context`（Task5）
- `src/core/quality/evaluator.evaluate_chapter_quality`（已有）
- `src/api/services/rewrite_loop_service.RewriteLoopService.auto_improve_chapter`（Task7）
- 配置：`QUALITY_MODE` / `QUALITY_MAX_REWRITE_PER_CHAPTER` / `QUALITY_TOKEN_BUDGET_PER_CHAPTER` / `QUALITY_CRITICAL_CHAPTER_TYPES`（Task4 已配）

## 文件清单

**新增**：
- `src/core/quality/gate.py` — 漏斗编排器
- `tests/unit/test_change061_quality_gate.py` — 编排测试

**修改**：
- `src/api/services/novel_context_service.py` — 衔接上下文读 state_delta
- `src/api/services/long_form_generation_helpers.py` — 逐章循环调 gate + 衔接读 state_delta
- `src/api/services/chapter_service.py` — 新增 update_state_delta / update_quality_status
- `src/api/services/novel_manager.py` — 代理上述两方法
- `tests/unit/test_change044_long_form_services.py` 或新文件 — 衔接上下文 + 持久化方法测试

## 风险与缓解

- **每章 +1 次 flash 抽取的成本**：state_delta 抽取用 flash 模型（低成本），且它替代了原本"截取300字正文"这种低质上下文，净收益为正（长期连贯性显著改善）。若需进一步降本，后续可加"低风险章跳过抽取"的配置开关。
- **L3 同步改写拖慢生成**：L3 仅在 L2 不达标的高风险章触发（少数），且有 Token 预算守卫。可接受。
- **state_delta 抽取失败导致记忆断档**：返回 _unverified 占位，下一章衔接回退 content 截取（兼容），不阻断。
- **历史章无 state_delta**：衔接上下文回退 content[:300]，逐步过渡，无需迁移历史数据。
