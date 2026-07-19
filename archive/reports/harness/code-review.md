# CHANGE-052 编码评审报告

**日期**: 2026-05-28
**评审者**: Reviewer Agent
**评审轮次**: 第 1 轮
**评审类型**: code_review

---

## 1. 需求符合性

### R1 — 修复卷纲生成 token 截断（P0）

| 验收标准 | 实现状态 |
|---|---|
| `generate_volume_outline` max_tokens 6000 → 12000 | 已实现（`long_form_generation_helpers.py` 第 200 行） |
| `generate_master_outline` max_tokens 6000 → 8000 | 已实现（第 108 行） |
| 章节数 < 80% 时重试最多 2 次 | 已实现（第 202-221 行，`for retry in range(2)`） |
| 重试后仍不足使用 fallback | 已实现（第 223-231 行） |

**问题 1（轻微）**：重试逻辑结构存在一个语义上的微妙问题。当前代码在 `for retry in range(2)` 循环内，先检查 `result` 是否满足，满足则 `break`，否则追加 prompt 并重新调用。这意味着：

- 初始调用（循环外）返回不足 → 进入循环 retry=0：追加 prompt，调用第 2 次
- retry=0 结果仍不足 → retry=1：追加 prompt（再次追加，prompt 变成两段警告），调用第 3 次
- retry=1 结果满足 → break

这是正确的行为（最多 3 次 LLM 调用 = 1 初始 + 2 重试），但 prompt 在第 2 次重试时会累积两段相同的警告文本，可能造成 prompt 冗余。这不影响正确性，但可以优化。

**问题 2（轻微）**：重试时 `retry_prompt` 是在原始 prompt 基础上追加，而非替换。第 2 次重试时 prompt 包含两段 `【重要】` 警告，虽然不影响功能，但略显冗余。

### R2 — 章节数量自动计算（P1）

| 验收标准 | 实现状态 |
|---|---|
| `LongFormNovelRequest` 新增 `auto_calc_chapters: bool = False` | 已实现 |
| `auto_calc_chapters=True` 时后端自动计算并夹紧 [20, 60] | 已实现（`novel_generator.py` 第 900-921 行） |
| 前端新增复选框，勾选后隐藏手动输入，显示预览 | 已实现 |
| 示例：1210000/5000/10 → 25 | 测试 `test_normal_range` 验证通过 |

**问题 3（需求偏差）**：需求 R2 明确要求将 `VOLUME_OUTLINE_PROMPT` 中的措辞从"本卷章节数：约 {chapters_count} 章"改为"建议 {chapters_count} 章（可在 ±30% 范围内根据情节节奏调整，但不得少于 {chapters_count_min} 章）"。

当前实现中 `prompts.py` 第 320 行仍为：
```
- 本卷章节数：约 {chapters_count} 章
```

该措辞变更未实现。需求文档将此作为 R2 的明确要求之一，且 `chapters_count_min` 变量也未引入。这是一个需求遗漏。

**问题 4（前端一致性）**：前端 `autoCalcChaptersPerVolume` 计算逻辑与后端一致（均使用 `Math.ceil` + clamp [20, 60]），但前端预览显示的是夹紧后的每卷章数，而总章数 `autoCalcTotalChapters` 未经夹紧。当 `autoCalcChaptersPerVolume` 被夹紧时（例如计算结果为 67 但显示 60），总章数预览（如 "预计约 334 章"）与实际生成章数（60 章/卷 × 卷数）不一致，可能误导用户。这是一个 UX 问题，不影响后端正确性。

### R3 — 字数约束强化（P1）

| 验收标准 | 实现状态 |
|---|---|
| 续写阈值 0.6 → 0.75 | 已实现（`chapter_generator.py` 第 54 行） |
| 续写最多 3 次（循环替代单次） | 已实现（第 322 行 `for attempt in range(MAX_CONTINUATION_ATTEMPTS)`） |
| 每次续写后重新计算字数 | 已实现（第 343 行） |
| `_continuation_generation` max_tokens 4000 → 6000 | 已实现（第 132 行） |
| 字数约束移至第 1 条，末尾加最终检查 | 已实现（`prompts.py` 第 193、202 行） |
| `VOLUME_OUTLINE_PROMPT` 增加强制要求措辞 | 已实现（第 331-333 行） |

---

## 2. 代码质量

**正面**：
- 重试逻辑清晰，日志记录完整（`volume_outline_insufficient_chapters`、`volume_outline_using_fallback`、`auto_calc_chapters_clamped` 等结构化日志）
- `MAX_CONTINUATION_ATTEMPTS` 提取为命名常量，可维护性好
- 前端 computed 属性逻辑简洁，与后端计算镜像一致
- `auto_calc_chapters` 字段有清晰的 Pydantic `description`

**问题 5（代码质量）**：`novel_generator.py` 中 `auto_calc_chapters` 的计算逻辑与前端 `autoCalcChaptersPerVolume` 的计算逻辑是重复的（两处都实现了 `ceil(target/wpc/vol)` + clamp）。测试文件 `test_change052_chapter_constraints.py` 中的 `_calc` 辅助方法也是第三份镜像。这三处逻辑目前一致，但未来若修改夹紧范围，需要同步三处。建议后端将此逻辑提取为独立函数，但这属于优化建议，不阻塞合并。

---

## 3. 安全性

无安全问题。新增字段均有类型约束（`bool`），`words_per_chapter` 上限放宽至 8000 有合理的业务依据（支持 5000 字/章场景），不引入安全风险。

---

## 4. 性能

**问题 6（性能影响，已知权衡）**：
- `max_tokens` 从 6000 提升至 12000（卷纲）和 8000（总纲），加上最多 2 次重试，最坏情况下单卷纲生成需要 3 次 LLM 调用，token 消耗约为原来的 6 倍。这是需求明确要求的权衡，需求文档已评估为合理。
- 续写最多 3 次，每次 max_tokens=6000，最坏情况下单章生成需要 4 次 LLM 调用（1 初始 + 3 续写）。需求文档已评估为合理的平衡点。

以上均为已知且被需求接受的性能权衡，不构成阻塞问题。

---

## 5. 兼容性

- `auto_calc_chapters` 字段默认值为 `False`，现有调用方不传该字段时行为不变，向后兼容。
- `words_per_chapter` 上限从 4000 放宽至 8000，现有数据（≤4000）仍在合法范围内，向后兼容。
- 前端两处 payload 构建（`submit` 和 `fullGenerate`）均已加入 `auto_calc_chapters`，一致性良好。

---

## 6. 规范遵循

- ruff check 通过，无新增 lint 问题。
- 结构化日志使用 `structlog` 风格，与项目规范一致。
- Pydantic 字段使用 `Field(default=..., description=...)` 风格，与现有字段一致。

---

## 7. 测试覆盖

16 个新增单元测试覆盖了三个核心逻辑路径：

- **T3（重试逻辑）**：4 个测试，覆盖无重试、1 次重试成功、2 次重试后 fallback、重试 prompt 内容验证。覆盖充分。
- **T5（续写循环）**：5 个测试，覆盖无续写、最大次数、提前停止、字数更新、异常中断。覆盖充分。
- **T8（自动计算）**：7 个测试，覆盖正常范围、上限夹紧、下限夹紧、边界值、字段接受。覆盖充分。

**问题 7（测试覆盖缺口）**：`CHAPTER_GENERATION_PROMPT_WITH_WORD_COUNT` 中新增的 `target_words_min` 和 `target_words_max` 变量没有对应的单元测试验证 prompt 格式化是否正确（即这两个变量是否被正确传入并渲染）。虽然代码逻辑（`chapter_generator.py` 第 258-267 行）看起来正确，但缺少测试保护。这是一个轻微的覆盖缺口，不阻塞合并。

---

## 8. 问题汇总

| # | 严重程度 | 类型 | 描述 |
|---|---|---|---|
| 1 | 轻微 | 代码质量 | 重试时 prompt 累积两段警告文本（第 2 次重试） |
| 2 | 轻微 | 代码质量 | 同上，与问题 1 相关 |
| 3 | **中等** | **需求偏差** | **R2 要求的 `VOLUME_OUTLINE_PROMPT` 措辞变更（"建议"+"不得少于"）未实现** |
| 4 | 轻微 | UX | 前端预览总章数在夹紧场景下与实际生成章数不一致 |
| 5 | 轻微 | 代码质量 | 自动计算逻辑在后端、前端、测试中三处重复 |
| 6 | 信息 | 性能 | token 消耗增加为已知权衡，需求已接受 |
| 7 | 轻微 | 测试覆盖 | prompt 变量渲染缺少单元测试 |

---

## 结论

**REVISION_REQUIRED**

核心阻塞问题：**问题 3**。需求 R2 明确要求将 `VOLUME_OUTLINE_PROMPT` 中的章节数措辞改为"建议"语义并引入 `chapters_count_min` 变量，该变更未实现。这是需求文档中明确列出的功能点，不是可选优化。

其余问题（1、2、4、5、7）均为轻微问题，不单独阻塞合并，但建议在修复问题 3 时一并处理问题 4（前端预览一致性）。

**修复要求**：
1. 在 `VOLUME_OUTLINE_PROMPT` 中将"本卷章节数：约 {chapters_count} 章"改为"本卷章节数：建议 {chapters_count} 章（可在 ±30% 范围内根据情节节奏调整，但不得少于 {chapters_count_min} 章）"，并在 `long_form_generation_helpers.py` 的 prompt 格式化调用中传入 `chapters_count_min = int(chapters_per_volume * 0.7)`（即 ±30% 下限）。
2. （建议）修复前端预览：当 `autoCalcChaptersPerVolume` 被夹紧时，`autoCalcTotalChapters` 应显示为 `autoCalcChaptersPerVolume * form.value.volumes` 而非原始计算值，以保持预览与实际生成一致。

---

# CHANGE-052 编码评审报告（第 2 轮）

**日期**: 2026-05-28
**评审者**: Reviewer Agent
**评审轮次**: 第 2 轮（针对修复后代码）
**评审类型**: code_review

---

## 上轮 REVISION_REQUIRED 修复验证

### 问题 3（需求偏差）— 修复验证结果：通过

**验证内容**：

| 修复项 | 预期 | 实际（代码确认） |
|---|---|---|
| `VOLUME_OUTLINE_PROMPT.input_variables` 新增 `"chapters_count_min"` | 已新增 | 已确认（`prompts.py` 第 309 行） |
| 第 321 行措辞改为"建议 {chapters_count} 章（可在 ±30% 范围内…但不得少于 {chapters_count_min} 章）" | 已改为建议语义 | 已确认（`prompts.py` 第 321 行） |
| `long_form_generation_helpers.py` 格式化调用新增 `chapters_count_min=int(chapters_per_volume * 0.7)` | 已新增 | 已确认（第 168 行） |
| `Create.vue` 语法错误（`const router = useRouter() = [...]`）已修复 | 两行独立声明 | 已确认（第 185-187 行） |

所有上轮 MUST FIX 项均已正确实现。

---

## 修复引入的新问题分析

### 语义矛盾评估（"建议" vs "强制要求"）

当前 prompt 中存在两段措辞：

- **"当前卷信息"段**（第 321 行）：`建议 {chapters_count} 章（可在 ±30% 范围内根据情节节奏调整，但不得少于 {chapters_count_min} 章）`
- **"卷纲要求"段**（第 332-334 行）：`【强制要求】本卷必须输出 {chapters_count} 章…不得因为情节原因减少章节数`

**评估结论：可接受的设计，不构成 MUST FIX。**

理由：
1. 两段服务不同目的。"当前卷信息"段是给 LLM 的上下文描述，提供弹性空间以允许情节驱动的章节数微调；"卷纲要求"段是输出格式约束，防止 LLM 因 token 截断或懒惰而少输出 JSON 对象。这是 prompt 工程中常见的"软约束 + 硬约束"双层设计。
2. 从实际效果看，`chapters_count_min`（= `chapters_per_volume * 0.7`）与后端重试逻辑的 `min_chapters`（= `chapters_per_volume * 0.8`）形成梯度：prompt 层允许最低 70%，代码层要求最低 80%，代码层更严格，不会因 prompt 弹性而导致实际章节数不足。
3. 若将两段统一为同一措辞，反而会削弱 prompt 的表达层次，降低 LLM 对"情节弹性"与"输出完整性"的区分理解。

**建议（非阻塞）**：可在"卷纲要求"段补充一句说明，例如"（情节弹性在章节内容中体现，JSON 对象数量必须完整）"，以消除人类读者的困惑，但这不影响 LLM 行为，不要求修复。

### 新增代码质量检查

**`chapters_count_min` 计算值一致性**：

- `prompts.py` 中 `chapters_count_min` 的语义是"不得少于此数量"（±30% 下限 = 70%）
- `long_form_generation_helpers.py` 第 168 行：`int(chapters_per_volume * 0.7)` — 与语义一致
- 后端重试逻辑 `min_chapters = int(chapters_per_volume * 0.8)`（第 204 行）— 代码层阈值更严格，两者不冲突

无新引入的逻辑错误。

**`Create.vue` 语法修复验证**：

- 第 182 行：`import { ref, computed } from 'vue'`
- 第 183 行：`import { useRouter } from 'vue-router'`
- 第 185 行：`const router = useRouter()`
- 第 187 行：`const novelTypes = ['玄幻', ...]`

修复正确，`router` 与 `novelTypes` 为独立声明，无语法问题。

**上轮问题 4（前端预览一致性）— 未修复，状态确认**：

`autoCalcTotalChapters`（第 214-216 行）仍为 `Math.ceil(target_words / words_per_chapter)`，未改为 `autoCalcChaptersPerVolume * volumes`。上轮将此标记为"建议"而非 MUST FIX，本轮维持该评估：此为 UX 轻微问题，不阻塞合并。

---

## 本轮问题汇总

| # | 严重程度 | 类型 | 描述 | 状态 |
|---|---|---|---|---|
| 上轮问题 3 | — | 需求偏差 | `VOLUME_OUTLINE_PROMPT` 措辞变更 + `chapters_count_min` | **已修复** |
| 上轮问题 4 | 轻微 | UX | 前端预览总章数在夹紧场景下不一致 | 未修复（建议项，不阻塞） |
| 新问题 A | 信息 | Prompt 设计 | "建议"与"强制要求"语义并存 | 可接受设计，不需修复 |

无新引入的 MUST FIX 问题。

---

## 结论

**APPROVED**

上轮唯一阻塞问题（问题 3）已正确修复：`VOLUME_OUTLINE_PROMPT` 措辞已改为建议语义，`chapters_count_min` 变量已正确引入并传值，`Create.vue` 语法错误已修复。修复本身未引入新的正确性或需求偏差问题。

prompt 中"建议"与"强制要求"并存的语义设计经评估为合理的双层约束，不构成缺陷。

剩余轻微问题（前端预览一致性）为已知 UX 优化项，可在后续迭代中处理，不阻塞本次合并。

---

# CHANGE-053 编码评审报告

**日期**: 2026-05-28
**评审者**: Reviewer Agent
**评审轮次**: 第 1 轮
**评审类型**: code_review

---

## 1. 需求符合性

| 需求 | 实现状态 | 说明 |
|---|---|---|
| R1 — 保存章节大纲到 Outline 表 | 已实现 | `novel_generator.py` 卷循环中，`generate_volume_outline` 后立即调用 `upsert_volume_outline` + `upsert_chapter_outline`，try/except 包裹，失败记录 warning 后继续 |
| R2 — 修复 `auto_calc_chapters` 计算顺序 | 已实现 | 计算块移至函数顶部，`initialize_progress` 和 `update_novel` 均改用 `chapters_per_vol` |
| R3 — `generate_master_outline` 接受正确章节数 | 已实现 | 新增 `chapters_per_vol: int` 参数，prompt 格式化和 fallback 数据均使用该值 |
| R4 — 提升 `generate_chapter_outlines` max_tokens | 已实现 | `outline_service.py` 第 234 行从 4000 改为 12000 |

所有 4 个需求均已覆盖，无遗漏。

---

## 2. 代码质量

**命名与结构**：变量命名清晰（`chapters_per_vol`、`computed_chapters_per_vol`），注释标注了 T1/T2/T3 与需求对应关系，可读性良好。

**日志**：结构化日志字段完整，`auto_calc_chapters_clamped` 和 `volume_outline_persisted` / `volume_outline_persist_failed` 均有足够上下文。

**fallback 逻辑**：T3 的 `ch_num = ch.get("chapter", idx + 1)` 使用卷内相对章号（从 1 开始），与 `upsert_chapter_outline(novel_id, volume_number, chapter_number, content)` 的语义一致，正确。

---

## 3. 安全性

无安全隐患。T3 的 `except Exception as persist_error` 仅记录 `str(persist_error)`，不向外暴露内部信息。

---

## 4. 性能

**SHOULD FIX（不阻塞）**：T3 的章节大纲持久化在卷循环内逐章串行 `await upsert_chapter_outline`。对 40-60 章/卷、10 卷的场景，每卷最多 60 次数据库写入，总计最多 600 次。每次写入是独立的 upsert，无批量接口可用（现有 `OutlineService` 未提供批量方法）。在当前架构下可接受，但若后续出现性能瓶颈，可考虑为 `OutlineService` 添加批量 upsert 方法。

---

## 5. 兼容性

- `auto_calc_chapters=False` 时，`chapters_per_vol = request.chapters_per_volume`，行为与修改前完全一致，向后兼容。
- `generate_master_outline` 新增必填参数 `chapters_per_vol`，唯一调用方 `novel_generator.py` 已同步更新，无其他调用方。
- `max_tokens=12000` 提升不影响现有接口契约，仅影响 LLM 调用成本，可接受。

---

## 6. 规范遵循

- 代码风格与项目一致（async/await、structlog、from-import 延迟导入）。
- 延迟导入 `from src.api.services.outline_service import get_outline_service` 在循环内每次执行，但 Python 模块缓存保证无性能损耗。
- 无新增外部依赖。

---

## 7. 问题汇总

| # | 严重程度 | 类型 | 描述 |
|---|---|---|---|
| 1 | 轻微 | 性能 | T3 逐章串行写入，最坏情况 600 次 DB upsert；当前可接受，建议后续批量化 |

无 MUST FIX 项。

---

## 结论

**APPROVED**

4 个需求均已正确实现，无 MUST FIX 项。代码质量、安全性、兼容性均达标，可进入下一阶段。
