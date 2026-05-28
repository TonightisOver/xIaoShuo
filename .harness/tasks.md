# CHANGE-051 任务清单

**日期**: 2026-05-27
**关联需求**: `.harness/requirements.md`
**总任务数**: 9

---

## 批次一：R1 — 修复卷纲生成 token 截断（P0）

### T1 — 提升 `generate_volume_outline` 的 max_tokens

**文件**: `src/api/services/long_form_generation_helpers.py`
**行号**: 第 200 行
**变更**:
```python
# 修改前
result = await generate_and_parse_json(client, prompt, max_tokens=6000, fallback=fallback_data)

# 修改后
result = await generate_and_parse_json(client, prompt, max_tokens=12000, fallback=fallback_data)
```
**依赖**: 无
**验收**: `max_tokens` 参数值为 12000

---

### T2 — 提升 `generate_master_outline` 的 max_tokens

**文件**: `src/api/services/long_form_generation_helpers.py`
**行号**: 第 108 行
**变更**:
```python
# 修改前
return await generate_and_parse_json(client, prompt, max_tokens=6000, fallback=fallback_data)

# 修改后
return await generate_and_parse_json(client, prompt, max_tokens=8000, fallback=fallback_data)
```
**依赖**: 无
**验收**: `max_tokens` 参数值为 8000

---

### T3 — 在 `generate_volume_outline` 中增加章节数量验证与重试

**文件**: `src/api/services/long_form_generation_helpers.py`
**位置**: `generate_volume_outline` 函数，在 `result = await generate_and_parse_json(...)` 之后

**逻辑**:
1. 检查 `result.get("chapters", [])` 的长度
2. 若长度 < `chapters_per_volume * 0.8`，在 prompt 末尾追加强制要求文本，重试最多 2 次
3. 重试 prompt 追加内容：`\n\n【重要】上次输出的章节数不足，请务必输出完整的 {chapters_per_volume} 章，不得少于 {min_chapters} 章。`
4. **重试次数耗尽后**才触发 fallback（fallback 不计入重试次数，已有 fallback 逻辑保持不变）

**依赖**: T1（先提升 token 上限再加重试，避免重试也被截断）
**验收**:
- 单元测试：mock LLM 返回少于 80% 章节数的 JSON，验证重试被触发
- 重试后章节数满足要求时，不再继续重试

---

### T4 — 修复 `VOLUME_OUTLINE_PROMPT` 中的章节数量措辞

**文件**: `src/core/llm/prompts.py`
**位置**: `VOLUME_OUTLINE_PROMPT` template，第 329 行附近

**变更**：将 prompt 中的章节数量要求从软性描述改为强制要求：

```
# 修改前（template 中）
请为本卷生成 {chapters_count} 章的详细章纲

# 修改后
请为本卷生成 {chapters_count} 章的详细章纲（必须严格输出 {chapters_count} 章，不得少于此数量）
```

同时在 `## 卷纲要求` 段落开头增加：
```
【强制要求】本卷必须输出 {chapters_count} 章，每章都需要完整的 JSON 对象。不得因为情节原因减少章节数。
```

**依赖**: 无
**验收**: prompt 文本包含"必须严格输出"和章节数量的强制要求

---

## 批次二：R3 — 字数约束强化（P1）

### T5 — 调整续写触发阈值和最大次数

**文件**: `src/core/llm/chapter_generator.py`

**变更 1**：修改常量（第 54 行附近）
```python
# 修改前
WORD_COUNT续写阈值 = 0.6  # Below 60% triggers continuation

# 修改后
WORD_COUNT续写阈值 = 0.75  # Below 75% triggers continuation
MAX_CONTINUATION_ATTEMPTS = 3  # 最多续写次数
```

**变更 2**：将 `_generate_single_chapter_inner` 中的单次续写改为循环（第 319-350 行附近）
```python
# 修改前：单次续写
min_threshold = int(target_words * WORD_COUNT续写阈值)
if word_count < min_threshold:
    content = await _continuation_generation(...)
    word_count = len(content)

# 修改后：循环续写，最多 MAX_CONTINUATION_ATTEMPTS 次
min_threshold = int(target_words * WORD_COUNT续写阈值)
for attempt in range(MAX_CONTINUATION_ATTEMPTS):
    if word_count >= min_threshold:
        break
    logger.info("chapter_continuation_attempt", chapter=..., attempt=attempt+1, word_count=word_count)
    try:
        content = await _continuation_generation(
            ...,
            current_words=word_count,
        )
        word_count = len(content)  # 每次续写后重新计算实际字数
    except Exception as e:
        logger.warning("continuation_failed", ...)
        break
```

**依赖**: 无
**验收**:
- `WORD_COUNT续写阈值` 常量值为 0.75
- `MAX_CONTINUATION_ATTEMPTS` 常量值为 3
- 单元测试：mock `_continuation_generation`，验证在字数不足时最多调用 3 次

---

### T6 — 提升续写的 max_tokens

**文件**: `src/core/llm/chapter_generator.py`
**位置**: `_continuation_generation` 函数，第 131 行

**变更**:
```python
# 修改前
continued = await client.generate(continuation_prompt, max_tokens=4000, use_flash=True)

# 修改后
continued = await client.generate(continuation_prompt, max_tokens=6000, use_flash=True)
```

**依赖**: 无
**验收**: `max_tokens` 参数值为 6000

---

### T7 — 强化 `CHAPTER_GENERATION_PROMPT_WITH_WORD_COUNT` 字数约束

**文件**: `src/core/llm/prompts.py`
**位置**: `CHAPTER_GENERATION_PROMPT_WITH_WORD_COUNT` template（第 177 行附近）

**变更**：将字数约束从第 8 条规则移至第 1 条，并在 prompt 末尾重复强调：

```
# 修改前（规则第 8 条）
8. 【字数约束】本章目标字数为 {target_words} 字，允许浮动范围为 ±20%（即 {target_words_min} ~ {target_words_max} 字）。请务必控制在此范围内，避免过短或过长。

# 修改后（规则第 1 条，其余规则顺延）
1. 【字数硬性要求】本章必须写满 {target_words_min} ~ {target_words_max} 字（目标 {target_words} 字，±20% 浮动）。字数不足视为生成失败，请在结束前检查字数并补充内容直到达标。
```

在 prompt 末尾（"请直接输出章节内容"之前）增加：
```
【最终检查】在输出前，请确认本章字数已达到 {target_words_min} 字以上。如果不足，请继续补充情节、对话或描写，直到达标。
```

**依赖**: 无
**验收**: prompt 中字数约束出现在规则第 1 条，且 prompt 末尾有最终检查提示

---

## 批次三：R2 — 章节数量自动计算（P1）

### T8 — 后端支持 `auto_calc_chapters` 参数

**文件 1**: `src/api/models/requests.py`

在 `LongFormNovelRequest` 中新增字段：
```python
auto_calc_chapters: bool = Field(
    default=False,
    description="是否根据 target_words/words_per_chapter 自动计算每卷章节数",
)
```

**文件 2**: `src/api/services/novel_generator.py`

在 `generate_long_form_background` 函数中，`chapters_per_vol = request.chapters_per_volume` 这行之前（第 897 行附近）插入：
```python
# 自动计算每卷章节数
if request.auto_calc_chapters:
    import math
    total_chapters = math.ceil(request.target_words / request.words_per_chapter)
    # 公式：chapters_per_vol = clamp(ceil(total_chapters / volumes), 20, 60)
    computed_chapters_per_vol = math.ceil(total_chapters / request.volumes)
    chapters_per_vol = max(20, min(60, computed_chapters_per_vol))
    if chapters_per_vol != computed_chapters_per_vol:
        logger.warning(
            "auto_calc_chapters_clamped",
            computed=computed_chapters_per_vol,
            clamped=chapters_per_vol,
            target_words=request.target_words,
            words_per_chapter=request.words_per_chapter,
            volumes=request.volumes,
        )
    logger.info(
        "auto_calc_chapters",
        target_words=request.target_words,
        words_per_chapter=request.words_per_chapter,
        total_chapters=total_chapters,
        chapters_per_vol=chapters_per_vol,
    )
else:
    chapters_per_vol = request.chapters_per_volume
```

**依赖**: 无
**验收**:
- `auto_calc_chapters=True, target_words=1210000, words_per_chapter=5000, volumes=10` → `chapters_per_vol=25`（计算值 25，在范围内，无 warning）
- `auto_calc_chapters=True, target_words=1000000, words_per_chapter=3000, volumes=5` → `chapters_per_vol=60`（计算值 67，夹紧为 60，记录 warning）
- `auto_calc_chapters=False` 时行为与修改前完全一致
- 单元测试覆盖三种分支：正常范围、超上限夹紧、`auto_calc_chapters=False`

---

### T9 — 前端新增"自动计算章节数"选项

**文件**: `frontend/src/views/Create.vue`

**变更 1**：在 `form` 初始值中新增字段（第 190 行附近）：
```javascript
auto_calc_chapters: false,
```

**变更 2**：在"每卷章数"输入框所在的 `<div>` 外层包裹条件渲染，并在其上方增加复选框：
```html
<!-- 在长篇结构设定 grid 之前 -->
<label class="flex items-center gap-2 cursor-pointer">
  <input type="checkbox" v-model="form.auto_calc_chapters" class="accent-accent-600 w-3.5 h-3.5 rounded" />
  <span class="text-xs text-neutral-600">自动计算章节数（根据目标字数÷每章字数）</span>
</label>

<!-- 自动计算时显示预览，隐藏手动输入 -->
<div v-if="form.auto_calc_chapters" class="text-xs text-accent-700 bg-accent-50 px-3 py-2 rounded">
  预计约 {{ autoCalcTotalChapters }} 章，每卷约 {{ autoCalcChaptersPerVolume }} 章
</div>
<div v-else class="space-y-1">
  <label class="block text-xs text-neutral-500">每卷章数</label>
  <input type="number" v-model.number="form.chapters_per_volume" min="20" max="60" class="input text-sm text-center" />
  <span class="text-[10px] text-neutral-400">20 ~ 60 章</span>
</div>
```

**变更 3**：在 `<script setup>` 中新增计算属性：
```javascript
const autoCalcTotalChapters = computed(() =>
  Math.ceil(form.value.target_words / form.value.words_per_chapter)
)
const autoCalcChaptersPerVolume = computed(() => {
  const raw = Math.ceil(autoCalcTotalChapters.value / form.value.volumes)
  return Math.max(20, Math.min(60, raw))  // 与后端保持一致，夹紧到 [20, 60]
})
```

**变更 4**：在 `submit` 和 `fullGenerate` 的 payload 中加入 `auto_calc_chapters: form.value.auto_calc_chapters`

**依赖**: T8
**验收**:
- 勾选"自动计算"后，"每卷章数"输入框隐藏，显示预览文字
- 预览文字随目标字数/每章字数/卷数实时更新
- 预览值与后端计算结果一致（含夹紧逻辑，上限 60、下限 20）
- 提交时 payload 包含 `auto_calc_chapters: true`

---

## 任务依赖关系

```
T1 (max_tokens 12000) ──→ T3 (重试逻辑)
T2 (max_tokens 8000)  ──→ 独立
T4 (prompt 措辞)      ──→ 独立
T5 (续写阈值/次数)    ──→ 独立
T6 (续写 max_tokens)  ──→ 独立
T7 (prompt 字数约束)  ──→ 独立
T8 (后端 auto_calc)   ──→ T9 (前端 auto_calc)
```

## 实现顺序建议

**阶段 1（P0，立即修复）**: T1 → T2 → T3 → T4
**阶段 2（P1，质量提升）**: T5 → T6 → T7
**阶段 3（P1，体验优化）**: T8 → T9

## 测试要求

每个任务完成后需运行：
```bash
cd E:/platform/xiaoshuo_review
python -m pytest tests/ -x -q
ruff check src/
mypy src/ --ignore-missing-imports
```

T3、T5、T8 需要新增单元测试文件（若对应测试文件不存在则创建）。
