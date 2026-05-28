# CHANGE-051 需求文档

**日期**: 2026-05-27
**状态**: 待实现
**优先级**: P0（核心功能缺陷）

---

## 一、问题背景

用户设计了一部 121 万字长篇小说，系统实际只生成了 60 章（10卷×6章），平均每章约 5000 字，远未达到目标。具体表现：

- 卷7 只有 1 章，卷8 没有章节——后面几卷被严重截断
- 总章节数 60 章 vs 应有约 242 章（121万÷5000字/章）
- 每章字数难以保证在目标范围内

---

## 二、根本原因分析（基于代码审查）

### 2.1 章节数量不足的根本原因

**原因 A：`generate_volume_outline` 的 `max_tokens=6000` 硬限制导致 JSON 截断**

`long_form_generation_helpers.py` 第 200 行：
```python
result = await generate_and_parse_json(client, prompt, max_tokens=6000, fallback=fallback_data)
```

当 `chapters_per_volume=40` 时，每章的 JSON 对象约 200-300 token，40 章需要约 8000-12000 token。6000 token 的限制导致 JSON 在中间被截断，`safe_json_parse` 的 `_extract_json_block` 正则只能匹配完整的 `{...}` 块，截断的 JSON 无法被修复，最终触发 fallback。

**fallback 的问题**：`fallback_data` 中的 `chapters` 列表是正确填充的（`chapters_per_volume` 个章节），但 `safe_json_parse` 在 JSON 截断时会尝试提取部分 JSON——如果提取到的是一个只有少数章节的不完整对象，就会返回那个不完整对象而非 fallback。这解释了为什么卷7只有1章而不是0章。

**原因 B：`generate_master_outline` 同样使用 `max_tokens=6000`**

`long_form_generation_helpers.py` 第 108 行：
```python
return await generate_and_parse_json(client, prompt, max_tokens=6000, fallback=fallback_data)
```

总纲 prompt 要求 LLM 为每卷输出 `chapter_types` 分布（含6个字段），10卷的总纲 JSON 也可能在 6000 token 内被截断，导致后面几卷的 `chapter_types` 丢失，进而影响卷纲生成时的章节类型分布计算。

**原因 C：前端 `chapters_per_volume` 默认值与实际行为不匹配**

`Create.vue` 第 190 行：前端默认 `chapters_per_volume: 40`，但用户截图显示每卷约 6 章。这说明用户可能手动改小了该值，或者 LLM 在 token 截断后只输出了少量章节。

### 2.2 字数约束弱的根本原因

**原因 D：续写只触发一次，且阈值过低**

`chapter_generator.py` 第 320-350 行：续写仅在 `word_count < target_words * 0.6`（60%阈值）时触发，且只触发一次。如果第一次续写后仍不足 80%，不会再次续写。

**原因 E：`CHAPTER_GENERATION_PROMPT_WITH_WORD_COUNT` 字数约束表述不够强**

当前 prompt 第 8 条规则：`【字数约束】本章目标字数为 {target_words} 字，允许浮动范围为 ±20%`。这是软性要求，LLM 经常不遵守。

**原因 F：`_continuation_generation` 的 `max_tokens=4000` 限制**

续写时 `max_tokens=4000`，如果需要补充 2000+ 字，可能仍然不足。

---

## 三、需求规格

### 需求 R1：修复卷纲生成 token 截断问题（P0）

**背景**：这是导致章节数量不足的直接原因。

**要求**：
- `generate_volume_outline` 的 `max_tokens` 从 6000 提升至 12000
- `generate_master_outline` 的 `max_tokens` 从 6000 提升至 8000
- 在 `generate_volume_outline` 中增加章节数量验证：若返回的 `chapters` 数量 < `chapters_per_volume * 0.8`，则触发重试（最多2次），重试时在 prompt 中明确要求"必须输出完整的 {chapters_per_volume} 章"
- 重试失败后使用 fallback（当前 fallback 逻辑正确，保留）

**验收标准**：
- 对于 `chapters_per_volume=40`，每卷生成的章节数 ≥ 32（80%）
- 对于 `chapters_per_volume=6`，每卷生成的章节数 = 6（100%）
- 10卷全部生成，无卷被跳过

### 需求 R2：章节数量自动计算与弹性分配（P1）

**背景**：用户希望根据目标字数自动推算章节数，而非手动计算。

**要求**：
- 在 `LongFormNovelRequest` 中新增字段 `auto_calc_chapters: bool = False`
- 当 `auto_calc_chapters=True` 时，后端自动计算 `total_chapters = target_words / words_per_chapter`，并将其均匀分配到各卷（`chapters_per_volume = total_chapters / volumes`，向上取整）
- `chapters_per_volume` 字段改为"建议值"语义：在 `VOLUME_OUTLINE_PROMPT` 中将"本卷章节数：约 {chapters_count} 章"的措辞改为"本卷章节数：建议 {chapters_count} 章（可在 ±30% 范围内根据情节节奏调整，但不得少于 {chapters_count_min} 章）"
- 前端在长篇模式下新增"自动计算章节数"复选框，勾选后隐藏"每卷章数"输入框并显示计算结果预览

**验收标准**：
- `target_words=1210000, words_per_chapter=5000, volumes=10` 时，`auto_calc_chapters=True` 自动计算出 `chapters_per_volume=25`（1210000/5000/10=24.2，向上取整）
- 前端显示"预计约 242 章，每卷约 25 章"
- 后端 API 接受 `auto_calc_chapters=true` 并正确覆盖 `chapters_per_volume`

### 需求 R3：字数约束强化（P1）

**背景**：每章实际生成字数难以保证在目标范围内。

**要求**：
- 将续写触发阈值从 60% 提升至 75%（即 `WORD_COUNT续写阈值 = 0.75`）
- 将续写最大次数从 1 次提升至 3 次，每次续写后重新检查字数
- 在 `CHAPTER_GENERATION_PROMPT_WITH_WORD_COUNT` 中强化字数约束措辞，在规则列表最前面（第1条）加入字数要求，并在 prompt 末尾重复强调
- 续写的 `max_tokens` 从 4000 提升至 6000

**验收标准**：
- 对于 `target_words=5000`，生成章节字数 ≥ 4000（80%）的比例 ≥ 90%
- 续写逻辑在字数不足时最多触发 3 次
- 单元测试覆盖：`_check_word_count` 和续写循环逻辑

---

## 四、方案评估

### 方案 A — 章节数量自动计算（对应 R2）

**可行性**：高。纯后端逻辑，不涉及 LLM 调用变更，只需在请求处理入口计算并覆盖 `chapters_per_volume`。

**推荐**：实现，但优先级低于 R1（R1 是根本原因修复）。

### 方案 B — 卷大纲生成 token 限制修复（对应 R1）

**可行性**：高。直接修改 `max_tokens` 参数，风险极低。增加重试逻辑也是标准模式。

**推荐**：优先实现，这是最直接的根本原因修复。

### 方案 C — 字数约束强化（对应 R3）

**可行性**：高。修改常量和 prompt 文本，增加循环逻辑。

**推荐**：实现，但注意续写次数增加会线性增加 API 调用成本，3次上限是合理的平衡点。

### 推荐实现顺序

1. **R1**（token 修复）— 最高优先级，直接解决用户反馈的核心问题
2. **R3**（字数强化）— 中优先级，改善生成质量
3. **R2**（自动计算）— 低优先级，改善用户体验

---

## 五、不在范围内

- 不修改 LangGraph 节点（标准小说生成流程）
- 不修改数据库 schema
- 不修改质量评估逻辑
- 不修改 KG/StoryBible 相关逻辑
