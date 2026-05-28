# CHANGE-053 任务清单

**日期**: 2026-05-28
**关联需求**: `.harness/requirements.md`
**总任务数**: 6

---

## 批次一：R2 + R3 — 修复 auto_calc_chapters 计算顺序与 master outline 参数（P0）

### T1 — 将 `auto_calc_chapters` 计算块移至函数顶部

**文件**: `src/api/services/novel_generator.py`
**位置**: `generate_long_form_background` 函数，第 855 行起

**变更**：将当前第 899-921 行的 `auto_calc_chapters` 计算块整体移至 `initialize_progress` 调用（第 861 行）**之前**，并将 `initialize_progress` 和 `update_novel` 中的 `request.chapters_per_volume` 替换为 `chapters_per_vol`。

```python
# 修改后的顺序（伪代码）：

# 1. 先计算 chapters_per_vol（移至最前）
if request.auto_calc_chapters:
    total_chapters = math.ceil(request.target_words / request.words_per_chapter)
    computed_chapters_per_vol = math.ceil(total_chapters / request.volumes)
    chapters_per_vol = max(20, min(60, computed_chapters_per_vol))
    # ... logging ...
else:
    chapters_per_vol = request.chapters_per_volume

# 2. initialize_progress 使用 chapters_per_vol（而非 request.chapters_per_volume）
await progress_service.initialize_progress(
    novel_id=novel_id,
    total_volumes=request.volumes,
    chapters_per_volume=chapters_per_vol,  # ← 修改
)

# 3. generate_master_outline 传入 chapters_per_vol（见 T2）

# 4. update_novel 使用 chapters_per_vol（而非 request.chapters_per_volume）
await novel_manager.update_novel(
    novel_id,
    master_outline=master_outline,
    total_volumes=request.volumes,
    chapters_per_volume=chapters_per_vol,  # ← 修改
    words_per_chapter=request.words_per_chapter,
    is_long_form=True,
)
```

**依赖**: 无
**验收**:
- `auto_calc_chapters=True, target_words=1500000, words_per_chapter=3000, volumes=10` 时，`initialize_progress` 和 `update_novel` 均使用 `chapters_per_vol=50`
- `auto_calc_chapters=False` 时行为与修改前完全一致
- 单元测试：验证 `chapters_per_vol` 在 `initialize_progress` 调用前已被正确计算

---

### T2 — 为 `generate_master_outline` 添加 `chapters_per_vol` 参数

**文件 1**: `src/api/services/long_form_generation_helpers.py`

在 `generate_master_outline` 函数签名中添加 `chapters_per_vol: int` 参数，并在函数内部将所有使用 `request.chapters_per_volume` 的地方替换为 `chapters_per_vol`：

```python
# 修改前
async def generate_master_outline(
    novel_id: str,
    request: Any,
) -> dict[str, Any]:
    ...
    prompt = MASTER_OUTLINE_PROMPT.format(
        ...
        chapters_per_volume=request.chapters_per_volume,
        ...
    )
    # fallback 中也使用 request.chapters_per_volume

# 修改后
async def generate_master_outline(
    novel_id: str,
    request: Any,
    chapters_per_vol: int,
) -> dict[str, Any]:
    ...
    prompt = MASTER_OUTLINE_PROMPT.format(
        ...
        chapters_per_volume=chapters_per_vol,  # ← 修改
        ...
    )
    # fallback 中也改用 chapters_per_vol
```

**文件 2**: `src/api/services/novel_generator.py`

在调用 `generate_master_outline` 时传入 `chapters_per_vol`（此时 T1 已确保 `chapters_per_vol` 已被计算）：

```python
master_outline = await generate_master_outline(
    novel_id=novel_id,
    request=request,
    chapters_per_vol=chapters_per_vol,  # ← 新增
)
```

**依赖**: T1（需要 `chapters_per_vol` 在调用前已计算）
**验收**:
- `auto_calc_chapters=True` 时，`generate_master_outline` 的 prompt 中 `chapters_per_volume` 字段值等于自动计算的 `chapters_per_vol`
- `auto_calc_chapters=False` 时，`chapters_per_vol = request.chapters_per_volume`，行为与修改前一致

---

## 批次二：R1 — 保存章节大纲到 Outline 表（P0）

### T3 — 在卷循环中持久化卷纲和章纲到 Outline 表

**文件**: `src/api/services/novel_generator.py`
**位置**: `generate_long_form_background` 函数，`generate_volume_outline` 调用之后（第 943-950 行附近）

**变更**：在 `vol_outline = await generate_volume_outline(...)` 之后，`generate_volume_chapters(...)` 之前，插入大纲持久化逻辑：

```python
vol_outline = await generate_volume_outline(
    novel_id=novel_id,
    master_outline=master_outline,
    volume_number=vol_num,
    chapters_per_volume=chapters_per_vol,
    words_per_chapter=words_per_chapter,
    request=request,
)

# ← 新增：持久化卷纲和章纲到 Outline 表
try:
    from src.api.services.outline_service import OutlineService
    outline_svc = OutlineService()
    await outline_svc.upsert_volume_outline(novel_id, vol_num, vol_outline)
    for ch in vol_outline.get("chapters", []):
        ch_num = ch.get("chapter")
        if ch_num:
            await outline_svc.upsert_chapter_outline(
                novel_id, vol_num, ch_num, ch
            )
    logger.info(
        "volume_outline_persisted",
        novel_id=novel_id,
        volume_number=vol_num,
        chapter_count=len(vol_outline.get("chapters", [])),
    )
except Exception as persist_error:
    logger.warning(
        "volume_outline_persist_failed",
        novel_id=novel_id,
        volume_number=vol_num,
        error=str(persist_error),
    )
    # 持久化失败不中断生成流程

# 继续原有的 generate_volume_chapters 调用
chapter_end = global_chapter_start + chapters_per_vol - 1
vol_chapters = await generate_volume_chapters(...)
```

**依赖**: 无（`OutlineService` 已存在）
**验收**:
- 长篇生成完成后，`Outline` 表中存在 `level="volume"` 的卷纲记录（每卷一条）
- `Outline` 表中存在 `level="chapter"` 的章纲记录（每章一条）
- 前端"章节规划"显示的章节数量与 `chapters_per_vol` 一致
- 持久化失败时生成流程不中断，日志记录 warning
- 单元测试：mock `OutlineService`，验证 `upsert_volume_outline` 和 `upsert_chapter_outline` 被正确调用

---

## 批次三：R4 — 提升 `generate_chapter_outlines` 的 max_tokens（P1）

### T4 — 将 `generate_chapter_outlines` 的 max_tokens 从 4000 提升至 12000

**文件**: `src/api/services/outline_service.py`
**行号**: 第 234 行

**变更**:
```python
# 修改前
chapters = await generate_and_parse_json(client, prompt, max_tokens=4000, fallback=[])

# 修改后
chapters = await generate_and_parse_json(client, prompt, max_tokens=12000, fallback=[])
```

**依赖**: 无
**验收**: `max_tokens` 参数值为 12000

---

## 批次四：测试覆盖

### T5 — 为 T1/T2 新增单元测试

**文件**: `tests/test_novel_generator_auto_calc.py`（若不存在则创建）

**测试用例**：
1. `test_auto_calc_chapters_before_initialize_progress`：验证 `auto_calc_chapters=True` 时，`initialize_progress` 收到的 `chapters_per_volume` 等于自动计算值（非 `request.chapters_per_volume`）
2. `test_auto_calc_chapters_master_outline_uses_correct_value`：验证 `generate_master_outline` 被调用时传入的 `chapters_per_vol` 等于自动计算值
3. `test_auto_calc_false_uses_request_value`：验证 `auto_calc_chapters=False` 时，`chapters_per_vol = request.chapters_per_volume`

**依赖**: T1, T2
**验收**: 3 个测试用例全部通过

---

### T6 — 为 T3 新增单元测试

**文件**: `tests/test_novel_generator_outline_persist.py`（若不存在则创建）

**测试用例**：
1. `test_volume_outline_persisted_after_generation`：mock `OutlineService`，验证每卷生成后 `upsert_volume_outline` 被调用一次
2. `test_chapter_outlines_persisted_after_generation`：mock `OutlineService`，验证每章大纲 `upsert_chapter_outline` 被调用
3. `test_persist_failure_does_not_interrupt_generation`：mock `upsert_volume_outline` 抛出异常，验证章节生成流程继续执行

**依赖**: T3
**验收**: 3 个测试用例全部通过

---

## 任务依赖关系

```
T1 (auto_calc 计算顺序) ──→ T2 (master outline 参数)
T1 ──→ T5 (测试)
T2 ──→ T5 (测试)
T3 (持久化大纲) ──→ T6 (测试)
T4 (token 上限) ──→ 独立
```

## 实现顺序建议

**阶段 1（P0，立即修复）**: T1 → T2 → T3
**阶段 2（P1，质量提升）**: T4
**阶段 3（测试覆盖）**: T5 → T6

## 测试要求

每个任务完成后需运行：
```bash
cd E:/platform/xiaoshuo_review
python -m pytest tests/ -x -q
ruff check src/
mypy src/ --ignore-missing-imports
```

T5、T6 需要新增单元测试文件（若对应测试文件不存在则创建）。
