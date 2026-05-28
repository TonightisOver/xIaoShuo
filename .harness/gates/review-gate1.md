# Gate 1 评审报告 — CHANGE-053 长篇小说章节规划显示修复

**评审类型**: plan_review（第 1 轮）
**评审时间**: 2026-05-28
**评审对象**: requirements.md + tasks.md（6 个任务）

---

## 一、代码验证结果

评审前对需求文档中的所有根因描述进行了代码核实。

### 根因 1 — 章节大纲未保存到 Outline 表（已确认）

`novel_generator.py` 第 941-963 行的卷循环中，`generate_volume_outline` 调用后直接进入 `generate_volume_chapters`，全程无任何 `upsert_volume_outline` 或 `upsert_chapter_outline` 调用。`OutlineService.upsert_volume_outline`（第 125 行）和 `upsert_chapter_outline`（第 146 行）方法均已存在且实现完整。`get_chapter_outlines` 查询 `level="chapter"` 的 Outline 记录，长篇流程不写入则前端显示 0 章。**根因描述准确。**

### 根因 2 — `auto_calc_chapters` 计算顺序错误（已确认）

`novel_generator.py` 第 861-865 行 `initialize_progress` 使用 `request.chapters_per_volume`，第 881-888 行 `update_novel` 使用 `request.chapters_per_volume`，第 899-921 行才执行 `auto_calc_chapters` 计算。当 `auto_calc_chapters=True` 时，进度追踪和小说元数据存储的是原始请求值而非计算值。**根因描述准确。**

### 根因 3 — `generate_master_outline` 传入错误章节数（已确认）

`long_form_generation_helpers.py` 第 62-68 行 prompt 格式化使用 `request.chapters_per_volume`，第 86-96 行 fallback 数据的 `chapter_types` 计算也使用 `request.chapters_per_volume`。函数签名无 `chapters_per_vol` 参数。**根因描述准确。**

### 根因 4 — `generate_chapter_outlines` max_tokens 不足（已确认）

`outline_service.py` 第 234 行 `generate_and_parse_json(client, prompt, max_tokens=4000, fallback=[])`，40 章 JSON 约需 6000-8000 token，4000 token 导致截断。**根因描述准确。**

---

## 二、完整性评审

### 需求覆盖情况

| 根本原因 | 对应需求 | 对应任务 | 覆盖状态 |
|---------|---------|---------|---------|
| 根因 1：大纲未持久化 | R1 | T3、T6 | 完整覆盖 |
| 根因 2：计算顺序错误 | R2 | T1、T5 | 完整覆盖 |
| 根因 3：master outline 章节数错误 | R3 | T2、T5 | 完整覆盖 |
| 根因 4：max_tokens 不足 | R4 | T4 | 完整覆盖 |

### 遗漏场景

**SHOULD FIX — S1**：T3 要求在 `vol_outline = await generate_volume_outline(...)` 之后、`generate_volume_chapters(...)` 之前插入持久化逻辑，但 `vol_outline` 的结构（`chapters` 字段的格式）在 tasks.md 中未说明。`generate_volume_outline` 的 fallback 数据（`long_form_generation_helpers.py` 第 181-193 行）中每章对象包含 `chapter` 字段作为章节编号，但 LLM 实际返回的章节对象是否保证包含 `chapter` 字段未在需求中明确。`upsert_chapter_outline` 的 `chapter_number` 参数需要从 `vol_outline["chapters"]` 中提取，若字段缺失会导致 `chapter_number=0` 或 KeyError。建议在 T3 中明确：从 `ch.get("chapter", idx)` 提取章节编号（idx 为枚举索引），与 `outline_service.py` 第 240 行现有模式保持一致。

**SHOULD FIX — S2**：T3 的持久化逻辑需要 `OutlineService` 实例，但 `generate_long_form_background` 函数当前未导入或实例化 `OutlineService`（`get_outline_service` 仅在第 515 行和第 702 行的其他函数中以局部 import 方式使用）。tasks.md 未说明如何获取 `OutlineService` 实例（局部 import + `get_outline_service()` 还是通过参数传入）。建议在 T3 中明确使用 `from src.api.services.outline_service import get_outline_service` 局部 import，与现有代码风格一致。

---

## 三、可行性评审

### T1 — 将 `auto_calc_chapters` 计算块移至函数顶部

**可行**。代码确认：计算块（第 899-921 行）与 `initialize_progress`（第 861 行）之间无数据依赖，`math` 模块已在文件顶层导入（第 6 行）。移动后 `initialize_progress` 和 `update_novel` 改用 `chapters_per_vol` 是直接替换，无架构冲突。

### T2 — 为 `generate_master_outline` 添加 `chapters_per_vol` 参数

**可行**。函数签名添加参数、内部替换引用、调用方传参均为直接修改，无依赖风险。需注意 fallback 数据中 `chapter_types` 的所有 `request.chapters_per_volume` 引用（第 86-96 行共 5 处）均需替换，tasks.md 描述"所有使用 `request.chapters_per_volume` 的地方"已覆盖，但实现者需注意 fallback 块中的 5 处引用不要遗漏。

**SHOULD FIX — S3**：T2 依赖 T1（tasks.md 已标注），但 T2 的验收标准未明确测试 fallback 路径中的 `chapter_types` 是否也使用了 `chapters_per_vol`。建议在 T5 的测试用例 `test_auto_calc_chapters_master_outline_uses_correct_value` 中增加对 fallback 数据 `chapter_types` 的断言，确保 5 处替换均被覆盖。

### T3 — 在卷循环中持久化卷纲和章纲到 Outline 表

**可行，有实现细节需明确（见 S1、S2）**。`upsert_volume_outline` 和 `upsert_chapter_outline` 均已实现且功能正确，try/except 包裹方案与现有卷级异常处理模式（第 991-1005 行）一致。

### T4 — 将 `generate_chapter_outlines` 的 max_tokens 从 4000 提升至 12000

**可行**。单行修改，无依赖风险。注意：`outline_service.py` 第 204 行的 `generate_volume_outlines` 函数也使用 `max_tokens=4000`，该函数用于短篇/标准流程的卷纲生成，需求文档未要求修改此处，评审不对此提出要求，但实现者应注意不要误改。

### T5 — 为 T1/T2 新增单元测试

**可行**。测试文件路径 `tests/test_novel_generator_auto_calc.py` 位于 `tests/` 根目录，与现有测试文件组织方式不一致（现有单元测试均在 `tests/unit/` 下，如 `tests/unit/test_change052_chapter_constraints.py`）。

**SHOULD FIX — S4**：建议将测试文件路径改为 `tests/unit/test_change053_auto_calc.py`，与项目现有测试目录结构保持一致。

### T6 — 为 T3 新增单元测试

**可行**。同 T5，测试文件路径 `tests/test_novel_generator_outline_persist.py` 位于 `tests/` 根目录，建议改为 `tests/unit/test_change053_outline_persist.py`（见 S4）。

---

## 四、粒度合理性评审

6 个任务的拆分合理。批次一（T1+T2+T3+T4）为实现任务，批次二（T5+T6）为测试任务，依赖关系标注清晰（T5 依赖 T1/T2，T6 依赖 T3）。T4 独立无依赖，可与 T1/T2/T3 并行执行，粒度适当。

---

## 五、验收标准评审

- **R1/T3**：验收标准"前端章节规划显示的章节数量与 `chapters_per_vol` 一致"是端到端验证，需要数据库和前端联调，单元测试无法覆盖。T6 的单元测试覆盖了持久化逻辑本身，端到端验证可作为手动验收项，当前描述可接受。
- **R2/T1**：验收标准明确了 `auto_calc_chapters=True` 和 `False` 两种路径，可验证。
- **R3/T2**：验收标准未明确 fallback 路径的覆盖（见 S3）。
- **R4/T4**：验收标准为"max_tokens 修改后单测通过"，可验证。

---

## 六、风险识别

| 风险 | 级别 | 说明 |
|-----|-----|-----|
| T3 章节编号提取字段不确定 | 中 | LLM 返回的章节对象若缺少 `chapter` 字段，持久化会写入错误的 chapter_number（见 S1） |
| T4 max_tokens 提升至 12000，API 调用成本增加 | 低 | `generate_chapter_outlines` 仅在用户手动触发时调用，非长篇自动流程，影响有限 |
| T1 移动计算块后 `words_per_chapter` 变量赋值顺序 | 低 | 第 897 行 `words_per_chapter = request.words_per_chapter` 在计算块之前，移动后需确认 `words_per_chapter` 不被 `auto_calc_chapters` 块引用（经确认：计算块只引用 `request.words_per_chapter`，无问题） |

---

## 七、评审结论

### MUST FIX 项（阻塞流程）

无。

### SHOULD FIX 项（不阻塞，建议修复）

- **S1**（T3）：明确从 `ch.get("chapter", idx)` 提取章节编号，与 `outline_service.py` 第 240 行现有模式保持一致，避免 KeyError 或写入 `chapter_number=0`
- **S2**（T3）：明确使用 `from src.api.services.outline_service import get_outline_service` 局部 import 获取服务实例，与现有代码风格一致
- **S3**（T5）：`test_auto_calc_chapters_master_outline_uses_correct_value` 测试用例增加对 fallback 数据 `chapter_types` 的断言，确保 `generate_master_outline` 中 5 处 `request.chapters_per_volume` 引用均被替换
- **S4**（T5/T6）：测试文件路径改为 `tests/unit/test_change053_*.py`，与项目现有测试目录结构一致

---

## 结论

**APPROVED**

需求文档对 4 个根因的分析经代码验证全部准确，任务拆分合理，依赖关系清晰，无 MUST FIX 项。4 个 SHOULD FIX 项均为实现细节建议，不阻塞进入实现阶段。建议实现者在 T3 中参考 `outline_service.py` 第 239-242 行的现有章节编号提取模式，确保持久化逻辑的健壮性。

---

# Gate 1 评审报告 — CHANGE-052 长篇小说章节数量与字数约束修复

**评审类型**: plan_review（第 1 轮）
**评审时间**: 2026-05-27
**评审对象**: requirements.md + tasks.md（9 个任务）

---

## 一、完整性评审

### 覆盖情况

| 根本原因 | 对应任务 | 覆盖状态 |
|---------|---------|---------|
| R1 JSON 截断（max_tokens 不足） | T1、T2、T3、T4 | 完整覆盖 |
| R2 auto_calc_chapters 自动计算 | T8、T9 | 完整覆盖 |
| R3 续写阈值与次数不足 | T5、T6、T7 | 完整覆盖 |

### 遗漏场景

**SHOULD FIX — S1**：T3 增加了章节数量验证与重试逻辑，但 fallback_data 路径（`generate_and_parse_json` 解析失败时直接使用 fallback）不会触发重试。tasks.md 未说明重试是在 `generate_and_parse_json` 内部实现还是在 `generate_volume_outline` 外层包装。若在外层包装，需明确 fallback 路径是否也计入重试次数，否则 fallback 会绕过验证静默返回错误数据。建议在 tasks.md 中补充一句说明。

**SHOULD FIX — S2**：T8 的 `auto_calc_chapters` 自动计算公式未在 tasks.md 中给出。`target_words / volumes / words_per_chapter` 是最直接的公式，但需要明确取整方式（floor/round）以及边界约束（结果是否需要 clamp 到 `chapters_per_volume` 字段的 `ge=20, le=60` 范围）。缺少公式定义会导致实现者自行决定，可能产生越界值。

---

## 二、可行性评审

### T1：generate_volume_outline max_tokens 6000→12000

**可行**。代码确认：`long_form_generation_helpers.py` 第 200 行 `generate_and_parse_json(client, prompt, max_tokens=6000, fallback=fallback_data)`，修改点明确。12000 tokens 对于 20-60 章的卷纲 JSON 是合理上限。

### T2：generate_master_outline max_tokens 6000→8000

**可行**。代码确认：`long_form_generation_helpers.py` 第 108 行 `generate_and_parse_json(client, prompt, max_tokens=6000, fallback=fallback_data)`，修改点明确。总纲结构比卷纲简单，8000 足够。

### T3：generate_volume_outline 章节数量验证与重试

**可行，但需注意实现位置**。`generate_volume_outline` 当前直接调用 `generate_and_parse_json` 并返回结果，重试逻辑需要在该函数内部、`generate_and_parse_json` 调用之后、`return result` 之前插入。实现位置清晰，无架构冲突。

### T4：VOLUME_OUTLINE_PROMPT 章节数量措辞改为强制要求

**可行**。Prompt 第 329 行已有 `请为本卷生成 {chapters_count} 章的详细章纲`，措辞已是命令式，但缺少"必须恰好"等强制性表述。修改为强制措辞是纯文本变更，无代码风险。

### T5：续写阈值 0.6→0.75，MAX_CONTINUATION_ATTEMPTS=3，单次改循环

**可行，有一个实现细节需确认**。代码确认：`chapter_generator.py` 第 54 行 `WORD_COUNT续写阈值 = 0.6`（注意：变量名混用中英文，是现有代码风格，不是新问题）。当前第 321-350 行是单次调用 `_continuation_generation`。改为循环时，每次循环后需更新 `current_words`（即用新的 `word_count = len(content)` 作为下一次的 `current_words` 入参），tasks.md 未明确说明这一点。

**SHOULD FIX — S3**：建议在 T5 验收标准中补充"每次续写后重新计算字数，以新字数判断是否继续"，避免实现者用初始字数做循环判断导致无限续写或提前退出。

### T6：_continuation_generation max_tokens 4000→6000

**可行**。代码确认：`chapter_generator.py` 第 131 行 `max_tokens=4000`，修改点明确，无依赖风险。

### T7：CHAPTER_GENERATION_PROMPT_WITH_WORD_COUNT 字数约束移至第 1 条

**可行**。代码确认：`prompts.py` 第 200 行，字数约束当前在第 8 条（最后一条）。移至第 1 条是纯文本重排，无变量或格式风险。末尾加最终检查也是纯文本追加。

注意：`CHAPTER_GENERATION_PROMPT_WITH_WORD_COUNT` 的 `input_variables` 列表（第 178-184 行）中缺少 `target_words_min` 和 `target_words_max`，但模板第 200 行已使用这两个变量，且调用方（`chapter_generator.py` 第 259-267 行）已正确传入。这是现有代码的轻微不一致，T7 不需要修复，但实现者应注意不要因为重排而破坏这两个变量的引用。

### T8：LongFormNovelRequest 新增 auto_calc_chapters 字段

**可行，但存在 MUST FIX 问题**。`requests.py` 结构清晰，新增 `bool` 字段是标准 Pydantic 操作。`novel_generator.py` 中读取该字段并覆盖 `chapters_per_volume` 的逻辑也是直接赋值，无架构冲突。

**MUST FIX — M1**：`chapters_per_volume` 字段有 `ge=20, le=60` 的验证约束（`requests.py` 第 74-79 行）。若 `auto_calc_chapters=True` 时自动计算的结果超出此范围，Pydantic 不会报错（因为是在业务逻辑中赋值，不是在模型初始化时），但后续逻辑可能产生异常行为（如生成 0 章或 200 章的卷纲）。tasks.md 必须明确：自动计算后是否需要 clamp 到 [20, 60]，或者放宽约束，或者在计算结果越界时抛出用户友好的错误。

### T9：Create.vue 新增"自动计算章节数"复选框和预览

**可行**。前端变更独立，不影响后端逻辑。

---

## 三、粒度合理性评审

9 个任务的拆分合理，批次划分（P0 先行、P1 跟进）符合优先级。批次三（T8/T9）前后端各一个任务，粒度适当。

**SHOULD FIX — S4**：T8 和 T9 存在隐式依赖（前端预览需要知道后端计算公式），但 tasks.md 未标注依赖关系。建议在 T9 中注明"依赖 T8 确定的计算公式"，避免前端实现与后端不一致。

---

## 四、验收标准评审

- T1/T2：验收标准为"max_tokens 修改后单测通过"，可验证。
- T3：验收标准需补充 fallback 路径的处理说明（见 S1）。
- T5：验收标准需补充循环字数更新逻辑（见 S3）。
- T8：验收标准需补充越界处理（见 M1）。
- T9：验收标准为"UI 可见、预览正确"，可验证。

---

## 五、风险识别

| 风险 | 级别 | 说明 |
|-----|-----|-----|
| T1 将 max_tokens 提升至 12000，单次 API 调用成本翻倍 | 低 | 每卷只调用一次，可接受 |
| T5 续写循环最多 3 次，每章最多额外 3 次 LLM 调用 | 中 | 高并发场景下需关注 API 限流，建议在 T5 验收标准中注明已有 `CHAPTER_TIMEOUT_SECONDS=600` 兜底 |
| T8 auto_calc_chapters 越界未处理 | 高 | 见 M1，必须修复 |

---

## 六、评审结论

### MUST FIX 项（阻塞流程）

**M1**（T8）：`auto_calc_chapters` 自动计算结果可能超出 `chapters_per_volume` 的 [20, 60] 约束范围，tasks.md 未定义越界处理策略。需在 tasks.md 中明确：计算结果 clamp 到合法范围、或放宽约束、或越界时返回错误。

### SHOULD FIX 项（不阻塞，建议修复）

- **S1**（T3）：补充说明 fallback 路径是否触发重试
- **S2**（T8）：明确 auto_calc_chapters 的计算公式和取整方式
- **S3**（T5）：验收标准补充"每次续写后重新计算字数"
- **S4**（T9）：标注对 T8 计算公式的依赖

---

## 结论

**REVISION_REQUIRED**

存在 1 个 MUST FIX 项（M1），需在 tasks.md 中补充 `auto_calc_chapters` 越界处理策略后方可进入实现阶段。

---

# Plan Review 评审报告 — 全局架构优化：模块解耦与冗余消除

**评审对象**: `.harness/requirements.md` + `.harness/tasks.md`
**评审轮次**: 第 1 轮
**评审日期**: 2026-05-26

---

## 评审结论

**结果**: APPROVED

---

## 代码验证结果

### 1. chapter_generator 反向依赖 — 已确认

`src/core/llm/chapter_generator.py` 第 223-239 行：
- `from src.api.models.db_models import StoryBible`
- `from src.api.services.story_bible_service import extract_relevant_constraints`
- `from src.core.database import get_db_session`

第 252 行：
- `from src.api.services.blueprint_service import BlueprintService`

第 389-392 行：
- `from src.api.models.db_models import Chapter`
- `from src.core.database import get_db_session`（写入 chapter_type）

**结论**: 需求文档描述准确，core/llm 层确实反向依赖 api/services 层和 database 层。

### 2. LangGraph 节点 import service 层 — 已确认

`src/core/langgraph/nodes/chapter_generation.py` 第 34 行：
- `from src.api.services.knowledge_graph_service import get_knowledge_graph_service`

第 97 行：
- `from src.api.services.progress_event_bus import get_progress_callback`

`src/core/langgraph/nodes/quality_check.py` 第 17-19 行：
- `from src.api.models.db_models import ChapterVersion`
- `from src.core.database import get_db_session`

第 157 行：
- `from src.api.services.knowledge_graph_service import get_knowledge_graph_service`

第 177 行：
- `from src.api.services.story_bible_service import detect_bible_conflicts`

**结论**: 需求文档描述准确。

### 3. novel_generator 行数与职责混合 — 已确认

实际行数：**1521 行**（需求文档说 850+，实际远超此数）。包含：
- 4 个后台生成入口函数（generate_novel_background, generate_novel_full_background, generate_volume_background, generate_long_form_background）
- 编排逻辑（_run_langgraph_pipeline, _run_sub_feature）
- DB 持久化（_persist_to_novel）
- 进度推送（大量 event_bus.publish 调用）
- 长篇生成全流程（_generate_master_outline, _generate_volume_outline, _generate_volume_chapters, _generate_volume_quality_report）

**结论**: 问题比需求文档描述的更严重。

### 4. storyline_service AI 生成逻辑混合 — 已确认

`src/api/services/storyline_service.py`（511 行）包含：
- CRUD 方法（list/create/update/delete storylines, arcs, scenes）
- AI 生成方法：`generate_storylines_ai`, `generate_power_systems_ai`, `generate_arcs_ai`, `generate_scenes_ai`, `generate_from_conversation`

每个 AI 生成方法都包含重复的模式：获取上下文 -> 构建 prompt -> 调用 LLM -> parse JSON -> 持久化。

**结论**: 需求文档描述准确。

### 5. 质量评估 Prompt 重复 — 已确认

`quality_check.py` 第 44-103 行的 `EVALUATION_PROMPT` 与 `rewrite_loop_service.py` 第 26-70 行的 `EVALUATION_PROMPT` 高度重复（核心评估维度和输出格式完全相同，仅 rewrite_loop 版本略简化了输出格式要求）。

**结论**: 需求文档描述准确。

### 6. chapter_rewriter 反向依赖 — 已确认

`src/core/llm/chapter_rewriter.py` 第 77-78 行：
- `from src.api.models.db_models import Chapter, Novel, Outline, StoryBible`
- `from src.core.database import get_db_session`

**结论**: 需求文档中提到的 chapter_rewriter 上下文构建问题确实存在。

---

## 评审发现

### MUST FIX（必须修复）

无。

### SHOULD FIX（建议修复）

1. **novel_generator 行数描述不准确**
   - 位置：requirements.md 1.1 表格
   - 问题：文档描述 "850+ 行"，实际为 1521 行。这不影响重构方向，但低估了拆分工作量。
   - 建议：更新为实际行数 ~1500 行，并在 Task 6 中调整目标（从 "降至 ~800" 调整为 "降至 ~600-700"，因为长篇生成相关函数也应考虑拆分）。

2. **Task 6 拆分范围可能不够**
   - 位置：tasks.md Task 6
   - 问题：novel_generator 中 `generate_long_form_background` 及其辅助函数（_generate_master_outline, _generate_volume_outline, _generate_volume_chapters, _generate_volume_quality_report）占约 500 行，Task 6 只提到拆分 `_persist_to_novel` 和进度推送逻辑，可能不足以将文件降至 ~800 行。
   - 建议：考虑将长篇生成逻辑也拆分为独立的 `long_form_generation_service.py`，或在 Task 9 中一并处理。当前不阻塞，可在实施阶段视情况调整。

3. **Task 5 的依赖注入方案需要明确**
   - 位置：tasks.md Task 5
   - 问题：文档提到 "通过 state 中的回调函数或 LangGraph config 注入这些依赖"，但未明确选择哪种方案。两种方案各有利弊：state 注入简单但污染 state 类型定义；config 注入更干净但需要修改 graph 创建逻辑。
   - 建议：在实施时优先选择 LangGraph config 注入（通过 `configurable` 字段传入 service 实例），保持 state 类型定义的纯净性。

4. **Task 4 遗漏了 chapter_rewriter 的同类问题**
   - 位置：tasks.md Task 4
   - 问题：Task 4 只处理 chapter_generator 的 DB 依赖，但 chapter_rewriter.py 存在完全相同的问题（直接 import db_models 和 get_db_session）。Task 8 虽然覆盖了 chapter_rewriter，但 Task 8 依赖 Task 1 而非 Task 4，两者的解耦模式应保持一致。
   - 建议：在 Task 8 描述中明确参考 Task 4 的解耦模式，确保 core/llm 下两个文件的重构方式一致。

### INFO（信息提示）

1. **quality_check.node 中的 `_persist_quality_to_version` 也是反向依赖**
   - quality_check.py 第 12-41 行定义了 `_persist_quality_to_version`，直接操作 DB。Task 5 的描述中未明确提到这个函数的处理方式。实施时需要将此持久化逻辑移到 service 层或通过回调处理。

2. **Phase 2 串行依赖链较长**
   - Task 4 -> Task 5 -> Task 6 形成串行链，如果 Task 4 遇到问题会阻塞后续。但考虑到 Task 4 的变更范围明确（参数化 + 删除 import），风险可控。

3. **测试覆盖率未知**
   - Task 10 要求 "所有现有测试通过"，但未评估现有测试是否覆盖了被重构的代码路径。建议在实施前先运行一次测试，确认基线状态。

---

## 总结

需求文档对架构问题的分析准确且全面，经代码验证所有描述的耦合点和重复模式均真实存在。任务拆分粒度合理，Phase 分层和依赖关系设计正确，优先级排序（先提取公共模块、再消除反向依赖、最后重划职责边界）符合重构最佳实践。SHOULD FIX 项主要是行数描述偏差和实施细节建议，不影响整体方案的可行性和正确性。

**结论: APPROVED**

---

# plan_review 评审报告 — CHANGE-051 LLM 增强三件套

**评审对象**: `.harness/requirements.md` + `.harness/tasks.md`  
**评审轮次**: 第 1 轮  
**评审日期**: 2026-05-27

---

## 评审结论

**结果**: REVISION_REQUIRED

---

## 代码验证结果

### 1. 现有 LLMClient 结构 — 已确认

`src/core/llm/client.py` 当前为单模型实例（`self.llm`），`generate()` 无 `use_flash` 参数，无 token 提取逻辑。全局工厂 `get_llm_client()` 为同步函数，返回懒加载单例。

### 2. chapter_generator.py 调用点 — 已确认

- 步骤 3（规划）：第 246 行 `await client.generate(planning_prompt, max_tokens=3000)` — 对应 T4 保持默认 pro
- 步骤 5（正文）：第 293 行 `await client.generate(prompt, max_tokens=8000)` — 对应 T4 传入 `use_flash=True`
- 续写：第 131 行 `await client.generate(continuation_prompt, max_tokens=4000)` — 对应 T4 传入 `use_flash=True`

三处调用点与任务描述完全一致，T4 实施路径清晰。

### 3. 现有测试路径 — 已确认

现有 LLM 客户端测试位于 `tests/unit/test_llm/test_client.py`，项目无 `tests/core/` 目录。tasks.md 中 T1/T3/T4 的测试路径写为 `tests/core/llm/test_*.py`，与实际目录结构不符。

### 4. 数据库模型与 init_db — 已确认

`src/core/database.py` 的 `init_db()` 使用 `Base.metadata.create_all`，新增模型只需继承 `Base` 即可自动建表，无需手动迁移脚本。T5 方案可行。

### 5. 路由注册模式 — 已确认

现有路由文件均在文件内定义完整前缀（如 `prefix="/api/v1/novels"`），`__init__.py` 统一导出，`main.py` 直接 `include_router`。T6/T7 的设计与此一致。

---

## 评审发现

### MUST FIX（必须修复）

#### M1: T8 双工厂设计导致数据库配置对核心生成逻辑实际无效

需求 2.3 声明"LLMClient 初始化时，优先从数据库读取激活的 LLMConfig"，但 T8 的实现方案是引入 `async def get_llm_client_async()` 异步工厂供路由层使用，同时保留同步 `get_llm_client()` 回退到 Settings。

问题：`chapter_generator.py`、`chapter_rewriter.py`、`helpers.py` 等核心生成逻辑均通过同步工厂 `get_llm_client()` 获取客户端，T8 完成后这些调用点将永远使用 Settings 配置，数据库激活配置对实际生成行为无效。这与需求描述存在语义落差——用户在前端激活了新配置，但章节生成仍使用旧的环境变量配置。

**修复建议**（二选一）：
- 方案 A：在需求/任务文档中明确界定"数据库配置仅对 API 路由层的直接 LLM 调用生效，核心生成流程（chapter_generator 等）始终使用 Settings"，并在前端 UI 上给出相应说明，避免用户误解。
- 方案 B：改为在应用启动时（lifespan）统一查询激活配置并初始化全局单例，消除双工厂，使数据库配置对所有调用点生效。

#### M2: T3 的 token 提取路径缺乏验证保障，静默失效无法感知

需求和任务均指定从 `response.response_metadata.get("token_usage", {})` 提取 token 数据。约束要求"若字段不存在则静默跳过"，但若字段路径本身因 langchain-openai 版本差异而不同（如某些版本将 token 信息放在 `response.usage_metadata` 而非 `response_metadata["token_usage"]`），token 监控功能将永远静默失效，且无任何可观测信号。

**修复建议**：在 T1 的 `TokenTracker` 中增加 `records_skipped` 计数器，并在 `GET /token-stats` 响应中暴露该字段。同时在 T3 验收标准中增加：使用带有 `response_metadata` 的 mock 响应验证提取路径正确性（现有 `test_client.py` 中的 mock 响应未设置 `response_metadata`，需补充）。

---

### SHOULD FIX（建议修复）

#### S1: T5 的 `is_active` 缺少数据库级唯一性保障

需求要求"同一时刻最多一条为 True"，T5 仅在 `is_active` 上加普通索引。T6 的激活接口通过事务保证互斥，但在高并发场景下（两个请求同时激活不同配置），若数据库事务隔离级别为 READ COMMITTED，仍可能出现两条 `is_active=True`。

建议在 `LLMConfig` 模型的 `__table_args__` 中添加部分唯一索引（PostgreSQL 支持 `WHERE is_active = TRUE`），或在任务文档中明确说明并发场景依赖应用层事务保证，当前系统单 worker 场景下风险可接受。

#### S2: tasks.md 执行顺序图与依赖列表不一致

执行顺序图中 T8 的箭头来自 `T6 ──► T7 ──► T8`，但 T8 的依赖列表写的是 `T3, T5`。T8 实际上不依赖 T7（路由注册），只依赖 T3 和 T5。依赖图应修正为 T8 从 T3 和 T5 直接引出，与 T7 并行执行。

#### S3: T9 前端 API 调用方式描述不准确

T9 要求"使用项目现有 fetch/axios 封装"，但项目前端（`App.vue`、各 View 文件）使用原生 `fetch`，无 axios 依赖，也无统一 API 封装层。建议将描述修正为"使用原生 fetch，参考 Home.vue 或 NovelDetail.vue 的调用模式"，避免实现者引入 axios 新依赖。

#### S4: T2 验收标准未覆盖 `DEEPSEEK_MODEL` 别名关系

需求 2.2 要求保留 `DEEPSEEK_MODEL` 作为 `DEEPSEEK_MODEL_PRO` 的别名，但 T2 验收标准只验证了 `DEEPSEEK_MODEL_FLASH`。建议补充验证：`assert s.DEEPSEEK_MODEL_PRO == "deepseek-v4-pro"` 以及说明 `DEEPSEEK_MODEL` 字段保留不变（而非真正的别名——两者是独立字段，需求描述"别名"用词不准确）。

---

### INFO（信息提示）

#### I1: 测试文件路径与项目目录结构不符

tasks.md 中 T1、T3、T4 的测试路径写为 `tests/core/llm/test_*.py`，但项目实际测试目录为 `tests/unit/test_llm/`（已有 `test_client.py`），项目无 `tests/core/` 目录。建议统一修正为 `tests/unit/test_llm/test_*.py`，T6 的测试路径 `tests/api/routes/test_llm_config.py` 与现有 `tests/api/` 目录一致，无需修改。

#### I2: `chapter_rewriter.py` 和 `helpers.py` 的 flash/pro 切换已明确排除

需求第 4 节已明确排除这两个文件，评审不对此提出要求。建议在 T4 任务描述末尾补充一句"不修改 chapter_rewriter.py 和 helpers.py"，避免实现者误操作。

#### I3: api_key 明文存储已在需求范围外说明

需求第 4 节明确"api_key 加密存储"不在范围内，T5/T6 的明文存储+脱敏显示方案与此一致，无问题。

---

## 总结

需求整体设计合理，三项功能边界清晰，向后兼容策略明确，任务拆分粒度适当。主要问题集中在两点：T8 的双工厂架构导致数据库配置对核心生成逻辑实际无效，与需求描述存在语义落差（M1）；T3 的 token 提取路径缺乏验证保障，静默失效无可观测信号（M2）。建议修复 M1 和 M2 后重新提交评审。

**结论: REVISION_REQUIRED**


**评审对象**: `.harness/requirements.md` + `.harness/tasks.md`
**评审轮次**: 第 1 轮
**评审日期**: 2026-05-27

---

## 评审结论

**结果**: APPROVED

---

## 代码验证结果

### 1. core/context 层级边界违规 — 已确认

`src/core/context/novel_context.py` 第 16 行：
- `from src.api.models.db_models import (Chapter, Character, Novel, Outline, StoryBible, Storyline, WorldSetting)`

`src/core/context/__init__.py` 当前从 `novel_context` re-export，链式依赖存在。

`src/api/services/novel_context_service.py` 尚不存在（Glob 返回空），需由 T1 新建。

**结论**: 需求描述准确，问题真实存在，T1 方案（迁移 + re-export）可行。

### 2. 调用方 import 路径 — 已确认

6 处调用方均通过 `from src.core.context import NovelContextBuilder` 导入，T1 的 re-export 方案可保证向后兼容，T2 为可选清理。

**额外发现**：`tests/unit/test_change049_refactoring.py` 第 24 行直接从 `src.core.context.novel_context` 导入 `NovelContextBuilder`；`tests/unit/test_change037_chapter_editor.py` 第 344、397 行 mock 路径为 `src.core.context.NovelContextBuilder`。T1 的 re-export 方案可维持这些测试路径有效，但 T2 若直接删除 `src/core/context/novel_context.py` 的实现（而非保留 re-export）将导致测试失败。tasks.md T1 步骤 2 已明确保留 re-export，风险可控。

### 3. 前端测试体系缺失 — 已确认

`frontend/package.json` 无 `test` 命令，`devDependencies` 中无 vitest/test-utils。三个 Vue 文件行数经实测：NovelDetail.vue 738 行、ChapterEdit.vue 854 行、RelationGraph.vue 669 行，与需求描述完全一致。

### 4. 遗留资料文件 — 已确认

`git status` 显示 CHANGE-033~036 目录、`story-bible.md`、`全流程使用指南.html` 均为 untracked，与需求描述一致。

---

## 评审发现

### MUST FIX（必须修复）

无。

### SHOULD FIX（建议修复）

1. **T1 验收标准与测试文件存在潜在冲突**
   - 位置：tasks.md T1 验收标准第 1 条
   - 问题：`grep -rn "from src.api" src/core/` 返回空 是 T1 的核心验收标准，但 T1 步骤 2 将 `novel_context.py` 改为 re-export 后，该文件本身会包含 `from src.api.services.novel_context_service import ...`，导致 grep 仍有输出，验收标准自相矛盾。
   - 建议：将验收标准修正为 `grep -rn "from src.api.models" src/core/` 返回空（只检查对 db_models 的直接依赖，允许 re-export 中的 services 层引用），或在 T1 步骤 2 中明确 re-export 行不计入违规。

2. **T6 测试用例 7（409 冲突）与需求描述不一致**
   - 位置：tasks.md T6 测试用例 7 vs requirements.md FR-2c 第 6 条
   - 问题：tasks.md 描述"409 时触发 alert"，requirements.md 描述"409 时触发 confirm 弹窗"。两者语义不同（alert 是通知，confirm 是确认）。
   - 建议：统一为 alert（通知用户冲突），因为 409 是服务端拒绝，不需要用户二次确认。在 tasks.md T6 中明确使用 `window.alert`。

3. **T7 完成后 T6 测试需同步更新，但依赖关系未显式标注**
   - 位置：tasks.md 任务总览依赖列
   - 问题：T7 拆分 NovelDetail.vue 后，T6 的测试 mock 路径（composable 位置）可能需要更新。tasks.md 在 T7 验收中提到"T6 的测试需同步更新 mock 路径"，但任务总览的依赖列中 T7 未标注对 T6 的反向影响。
   - 建议：在 T7 描述中明确列出需要同步修改的测试文件，避免实施时遗漏。

### INFO（信息提示）

1. **FR-3 目标行数与 T7~T9 验收标准不一致**
   - requirements.md FR-3 目标：NovelDetail ≤450、ChapterEdit ≤450、RelationGraph ≤400
   - tasks.md T8 验收：ChapterEdit ≤450（一致）；T9 验收：RelationGraph ≤400（一致）；T7 验收：NovelDetail ≤450（一致）
   - 实际一致，无问题，仅确认。

2. **T10 未检查 .gitignore 中 *.bundle 规则**
   - tasks.md T10 步骤 1 要求检查 `.gitignore`，当前 git status 显示 `xiaoshuo-*.bundle` 为 untracked（而非 ignored），说明 `.gitignore` 中可能尚无 `*.bundle` 规则。实施时需先添加规则再 stage 其他文件，否则 bundle 文件可能被意外 stage。

3. **FR-2b 中 useConfirm 辅助函数在 tasks.md 中未体现**
   - requirements.md FR-2b 提到"危险操作的 confirm() 保留但封装为 useConfirm 辅助函数"，但 tasks.md T5 的接口设计中未包含 useConfirm。这是范围缩减，可接受，但实施时应明确不强制要求 useConfirm。

---

## 总结

需求文档对四个遗留问题的描述准确，经代码验证全部属实。任务拆分粒度合理，P1/P2 优先级划分清晰，执行顺序设计合理（后端修正独立于前端测试体系，互不阻塞）。SHOULD FIX 项中 T1 验收标准的 grep 命令存在自相矛盾的逻辑问题，建议在实施前修正，但不阻塞整体方案。

**结论: APPROVED**

---

# plan_review 评审报告 — CHANGE-051 LLM 增强三件套

**评审对象**: `.harness/requirements.md` + `.harness/tasks.md`
**评审轮次**: 第 2 轮（针对修订后文档）
**评审日期**: 2026-05-27

---

## 上轮 MUST FIX 修复验证

### M1（双工厂问题）— 修复确认

修订后的 requirements.md 第 2.3 节明确：`get_llm_client()` 保持同步，返回已初始化的全局单例，所有调用点（包括 `chapter_generator.py`、`chapter_rewriter.py`、`helpers.py` 等）均通过该单例获取客户端，数据库激活配置对所有生成行为生效。

tasks.md T8 整体重写为 lifespan 单例方案：在 `src/api/main.py` 的 lifespan startup 阶段查询激活配置并初始化全局单例，`get_llm_client()` 保持同步返回单例，不引入异步工厂。涉及文件增加 `src/api/main.py`，消除了双工厂设计。

**结论**: M1 修复完整，方案语义一致，无遗留问题。

### M2（token 提取路径验证）— 修复确认

T1 验收标准新增 `get_stats()` 返回值包含 `records_skipped` 字段。T3 验收标准新增两条 mock 验证：带 `response_metadata={"token_usage": {...}}` 的 mock 验证提取路径正确性；不含 `response_metadata` 的 mock 验证 `records_skipped` 增加 1 且不抛出异常。`GET /token-stats` 响应中暴露 `records_skipped` 字段。

**结论**: M2 修复完整，可观测性已建立。

---

## 评审结论

**结果**: APPROVED

---

## 评审发现

### MUST FIX（必须修复）

无。

### SHOULD FIX（建议修复）

#### S1（延续上轮 S2）: 执行顺序图依赖关系已修正，但图与文字说明存在细微不一致

tasks.md 执行顺序图已修正为 T8 独立分支（依赖 T3、T5），与 T7 并行，符合实际依赖关系。但图下方的文字说明列表中 T6 的依赖写为 `T1, T5`，而图中 T6 箭头来自 T5（T1 未显式连线到 T6）。T6 确实需要 T1（调用 `get_token_tracker()`），文字说明是正确的，图的表达略有遗漏。不阻塞实施，实现者按文字说明执行即可。

#### S2（延续上轮 S1）: T5 `is_active` 唯一性说明已补充，可接受

tasks.md T5 已补充"当前系统为单 worker 场景，并发风险可接受，不添加数据库级部分唯一索引"。说明清晰，决策有据，无需进一步修改。

### INFO（信息提示）

#### I1: T8 测试文件 `test_client_db_config.py` 的测试范围建议

T8 验收标准包含"激活数据库配置后重启应用，新的 LLM 调用使用数据库中的 base_url 和模型名"，这是集成级验证，难以在单元测试中覆盖。建议 `test_client_db_config.py` 聚焦于：(a) `LLMClient(llm_config=mock_config)` 正确从 `llm_config` 对象读取参数；(b) `LLMClient()` 无参数时回退到 Settings。lifespan 集成行为可在 T7 的路由测试中通过 `TestClient` 覆盖，或标注为手动验收项。

#### I2: T9 前端 API 调用描述已修正

上轮 S3 建议已采纳，T9 描述改为"使用原生 fetch，参考 Home.vue 或 NovelDetail.vue 的调用模式"，准确反映项目实际技术栈。

#### I3: T2 验收标准已补充 `DEEPSEEK_MODEL_PRO` 断言

上轮 S4 建议已采纳，T2 验收标准新增 `assert s.DEEPSEEK_MODEL_PRO == 'deepseek-v4-pro'` 和原字段存在性断言，三个字段独立并列关系表述清晰。

---

## 总结

两项 MUST FIX 均已完整修复：T8 的双工厂问题通过 lifespan 单例方案彻底消除，数据库配置对所有调用点生效；T3 的 token 提取路径通过 mock 验证和 `records_skipped` 计数器建立了可观测性。上轮 SHOULD FIX 中的 S2（执行顺序图）、S3（前端 fetch 描述）、S4（T2 验收标准）均已采纳修正。当前文档无 MUST FIX 项，方案完整、一致、可实施。

**结论: APPROVED**

---

# plan_review 评审报告 — CHANGE-051 长篇小说章节数量与字数约束修复

**评审对象**: `.harness/requirements.md` + `.harness/tasks.md`
**评审轮次**: 第 2 轮（针对修订后文档）
**评审日期**: 2026-05-27

---

## 上轮 MUST FIX 修复验证

### M1（T8 auto_calc_chapters 越界处理）— 修复确认

tasks.md T8 现已包含完整的 clamp 逻辑：
```python
chapters_per_vol = max(20, min(60, computed_chapters_per_vol))
if chapters_per_vol != computed_chapters_per_vol:
    logger.warning("auto_calc_chapters_clamped", ...)
```
公式明确为 `clamp(ceil(total_chapters / volumes), 20, 60)`，越界时记录 warning，验收标准覆盖超上限夹紧场景。**修复完整。**

## 上轮 SHOULD FIX 修复验证

### S1（T3 fallback 与重试关系）— 修复确认

tasks.md T3 步骤 4 明确："重试次数耗尽后才触发 fallback（fallback 不计入重试次数，已有 fallback 逻辑保持不变）"。语义清晰，无歧义。**修复完整。**

### S2（T8 计算公式明确）— 修复确认

tasks.md T8 现有完整公式注释：`# 公式：chapters_per_vol = clamp(ceil(total_chapters / volumes), 20, 60)`，取整方式（ceil）和边界约束均已明确。**修复完整。**

### S3（T5 续写后重新计算字数）— 修复确认

tasks.md T5 循环体内已有 `word_count = len(content)  # 每次续写后重新计算实际字数`，且 `_continuation_generation` 调用传入 `current_words=word_count` 使用更新后的值。**修复完整。**

### S4（T9 依赖 T8 已标注）— 修复确认

tasks.md T9 `**依赖**: T8`，依赖关系图也已标注 `T8 (后端 auto_calc) ──→ T9 (前端 auto_calc)`。**修复完整。**

---

## 本轮新发现

### SHOULD FIX — S5：T8 验收标准使用了超出字段约束的测试值

**位置**：tasks.md T8 验收标准第 1 条；requirements.md 第 91 行

**问题**：`words_per_chapter` 字段在 `LongFormNovelRequest` 中定义为 `ge=2000, le=4000`（`requests.py` 第 80-84 行）。但 T8 验收标准的主要测试用例使用 `words_per_chapter=5000`，该值会被 Pydantic 在模型初始化时直接拒绝（422 Validation Error），auto_calc 逻辑根本不会执行。

requirements.md 问题背景（第 11-14 行）明确描述用户的实际场景是"每章约 5000 字"，说明 5000 字/章是真实需求，而非文档笔误。

**影响**：若实现者按验收标准编写单元测试，测试将因 Pydantic 验证失败而报错，而非测试 auto_calc 逻辑本身。若实现者直接调用 API，请求会被拒绝。

**修复建议**（二选一）：
- 方案 A：将 `words_per_chapter` 的 `le` 约束从 4000 放宽至 10000（或更合理的上限），以覆盖用户实际使用场景，并在 T8 中增加对应的字段变更说明。
- 方案 B：将 T8 验收标准的测试用例改为使用合法值（如 `words_per_chapter=4000`），并在 requirements.md 中说明 5000 字/章的场景需要先放宽字段约束（作为后续任务）。

### SHOULD FIX — S6：T8 代码片段中 `import math` 位于函数体内

**位置**：tasks.md T8 代码片段第 2 行

**问题**：`import math` 写在 `generate_long_form_background` 函数体内的 `if` 块中。查看 `novel_generator.py` 的现有 import 区（第 1-32 行），`math` 模块未被导入，但项目代码风格统一使用顶层 import。函数内 import 虽然功能上正确，但违反项目代码风格，且 ruff 的 `PLC0415` 规则会对此发出警告，可能导致 `ruff check src/` 检查失败。

**修复建议**：在 T8 代码片段中将 `import math` 移至文件顶层 import 区，与现有 import 语句并列。

---

## 评审结论

### MUST FIX 项

无。

### SHOULD FIX 项

- **S5**（T8）：验收标准使用 `words_per_chapter=5000` 超出字段 `le=4000` 约束，测试用例无法执行。需明确是放宽字段约束还是修改测试用例。
- **S6**（T8）：`import math` 位于函数体内，违反项目代码风格，可能触发 ruff 警告。

---

## 总结

上轮全部 1 个 MUST FIX（M1）和 4 个 SHOULD FIX（S1-S4）均已完整修复，文档质量显著提升。本轮新发现 2 个 SHOULD FIX：T8 验收标准使用了超出字段约束的测试值（S5），以及 `import math` 的位置问题（S6）。两项均不阻塞实施，但 S5 若不处理会导致单元测试无法按预期运行。

**结论: APPROVED**
