# CHANGE-053 需求文档

**日期**: 2026-05-28
**状态**: 待实现
**优先级**: P0（核心功能缺陷）

---

## 一、问题背景

用户生成 150 万字长篇小说后，前端"章节规划"页面显示的章节数量与实际要求严重不符：
- 显示 5-6 章或 0 章，而非预期的 40 章
- 章节数/字数与用户设定不一致

---

## 二、根本原因分析（基于代码审查）

### 根因 1 — 章节大纲未保存到 Outline 表（前端显示 0 章的直接原因）

`generate_long_form_background`（`novel_generator.py` 第 941-963 行）在生成每卷的 `vol_outline` 后，从不调用 `upsert_chapter_outline` 或 `upsert_volume_outline`，导致 `Outline` 表里没有任何章节大纲记录。

前端"章节规划"数量来自 `get_outline_tree` → `get_chapter_outlines`（查询 `Outline` 表 `level="chapter"` 的记录），因此显示为 0。

`OutlineService.upsert_chapter_outline` 和 `upsert_volume_outline` 方法已存在且功能正确，只是从未被长篇生成流程调用。

### 根因 2 — `auto_calc_chapters` 计算顺序错误（章节数与要求不一致的原因）

在 `novel_generator.py` 中：
- `initialize_progress`（第 861-865 行）使用 `request.chapters_per_volume`（默认 40）
- `update_novel`（第 881-888 行）使用 `request.chapters_per_volume`（默认 40）
- `auto_calc_chapters` 计算（第 899-921 行）在上述两个调用**之后**才执行

当 `auto_calc_chapters=True` 时，进度追踪和小说元数据存储的是原始 `request.chapters_per_volume`（40），而非自动计算值，导致数据不一致。

### 根因 3 — `generate_master_outline` 传入错误的章节数

`long_form_generation_helpers.py` 的 `generate_master_outline` 函数（第 62-68 行）在 prompt 中使用 `request.chapters_per_volume`，但当 `auto_calc_chapters=True` 时，实际每卷章节数已被重新计算为 `chapters_per_vol`。

函数签名目前没有 `chapters_per_vol` 参数，导致主大纲的章节分布规划与实际生成不一致。

### 根因 4 — `generate_chapter_outlines` token 不足（显示 5-6 章的直接原因）

`outline_service.py` 的 `generate_chapter_outlines` 函数（第 234 行）使用 `max_tokens=4000`。对 40 章来说，每章 JSON 约 150-200 token，40 章需要约 6000-8000 token，4000 token 的限制导致 JSON 截断，只能生成 5-6 章大纲。

---

## 三、需求规格

### 需求 R1：长篇生成流程中保存章节大纲到 Outline 表（P0）

**背景**：这是前端"章节规划"显示 0 章的直接原因，也是最高优先级修复。

**要求**：
- 在 `generate_long_form_background` 的每卷循环中，`generate_volume_outline` 调用成功后，立即将 `vol_outline` 保存到 `Outline` 表（调用 `OutlineService.upsert_volume_outline`）
- 同时将 `vol_outline["chapters"]` 中的每个章节大纲保存到 `Outline` 表（调用 `OutlineService.upsert_chapter_outline`）
- 保存操作失败不应中断章节生成流程（try/except 包裹，记录 warning 后继续）

**验收标准**：
- 长篇生成完成后，`Outline` 表中存在 `level="volume"` 的卷纲记录（每卷一条）
- `Outline` 表中存在 `level="chapter"` 的章纲记录（每章一条）
- 前端"章节规划"显示的章节数量与 `chapters_per_vol` 一致
- 保存失败时生成流程不中断，日志记录 warning

### 需求 R2：修复 `auto_calc_chapters` 计算顺序（P0）

**背景**：`chapters_per_vol` 的计算必须在 `initialize_progress` 和 `update_novel` 之前完成，否则存储的元数据与实际生成不一致。

**要求**：
- 将 `auto_calc_chapters` 的计算逻辑（当前第 899-921 行）移至 `initialize_progress` 调用（第 861 行）**之前**
- `initialize_progress` 和 `update_novel` 均改用计算后的 `chapters_per_vol`

**验收标准**：
- `auto_calc_chapters=True, target_words=1500000, words_per_chapter=3000, volumes=10` 时，`initialize_progress` 和 `update_novel` 均使用 `chapters_per_vol=50`（1500000/3000/10=50）
- `auto_calc_chapters=False` 时行为与修改前完全一致

### 需求 R3：`generate_master_outline` 接受并使用正确的章节数（P1）

**背景**：主大纲的章节分布规划应与实际生成的每卷章节数一致。

**要求**：
- 为 `generate_master_outline` 函数添加 `chapters_per_vol: int` 参数
- 函数内部 prompt 格式化和 fallback 数据均使用 `chapters_per_vol` 而非 `request.chapters_per_volume`
- 调用方（`novel_generator.py`）在计算出 `chapters_per_vol` 后再调用 `generate_master_outline`，并传入该值

**验收标准**：
- `auto_calc_chapters=True` 时，`generate_master_outline` 的 prompt 中 `chapters_per_volume` 字段值等于自动计算的 `chapters_per_vol`
- `auto_calc_chapters=False` 时，行为与修改前一致（`chapters_per_vol = request.chapters_per_volume`）

### 需求 R4：提升 `generate_chapter_outlines` 的 max_tokens（P1）

**背景**：`outline_service.py` 的 `generate_chapter_outlines` 使用 `max_tokens=4000`，对 40 章来说远远不够，导致只能生成 5-6 章大纲。

**要求**：
- 将 `generate_chapter_outlines` 中的 `max_tokens=4000` 提升至 `max_tokens=12000`

**验收标准**：
- `max_tokens` 参数值为 12000
- 对 40 章的卷纲，`generate_chapter_outlines` 能返回完整的 40 章大纲列表

---

## 四、方案评估

### 方案 A — 保存大纲到 Outline 表（对应 R1）

**可行性**：高。`OutlineService` 的 `upsert_volume_outline` 和 `upsert_chapter_outline` 方法已存在且功能正确，只需在长篇生成流程中调用。需要在 `long_form_generation_helpers.py` 中引入 `OutlineService`，或在 `novel_generator.py` 的循环中调用。

**推荐**：在 `novel_generator.py` 的卷循环中，`generate_volume_outline` 调用后立即持久化，保持关注点分离。

### 方案 B — 修复计算顺序（对应 R2）

**可行性**：高。纯代码重排，将 `auto_calc_chapters` 计算块移至函数顶部，风险极低。

**推荐**：优先实现，是最简单的修复。

### 方案 C — `generate_master_outline` 参数修复（对应 R3）

**可行性**：高。添加一个参数，修改调用方传参，风险低。需要确保调用顺序：先计算 `chapters_per_vol`，再调用 `generate_master_outline`。

**推荐**：与 R2 一起实现，因为两者都涉及 `chapters_per_vol` 的计算顺序。

### 方案 D — 提升 token 上限（对应 R4）

**可行性**：高。单行修改，风险极低。

**推荐**：立即实现。

### 推荐实现顺序

1. **R2**（计算顺序）— 最先修复，为 R3 提供正确的 `chapters_per_vol`
2. **R3**（master outline 参数）— 依赖 R2 的计算顺序修复
3. **R1**（保存大纲）— 核心功能修复，解决前端显示 0 章问题
4. **R4**（token 上限）— 解决前端显示 5-6 章问题

---

## 五、不在范围内

- 不修改 LangGraph 节点（标准小说生成流程）
- 不修改数据库 schema
- 不修改质量评估逻辑
- 不修改 KG/StoryBible 相关逻辑
- 不修改 CHANGE-051 已完成的 token 修复（`generate_volume_outline` max_tokens=12000 已正确）
