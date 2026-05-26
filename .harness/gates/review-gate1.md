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
