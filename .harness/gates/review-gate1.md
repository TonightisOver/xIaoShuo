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

# plan_review 评审报告 — CHANGE-050 工程质量收尾

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
