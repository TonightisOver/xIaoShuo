# 任务清单：全局架构优化 — 模块解耦与冗余消除

> 对应需求：`.harness/requirements.md` v1.0
> 日期：2026-05-26

---

## 优先级说明

- P0：影响面大、风险低（提取公共工具函数，不改变调用逻辑）
- P1：影响面中、风险中（重构调用关系，需要调整参数传递）
- P2：影响面大、风险较高（重构核心生成流程，需仔细验证）

---

## P0 — 提取公共模块（低风险，高收益）

### Task 1: 提取上下文构建公共模块

**文件**: 新建 `src/core/context/__init__.py` + `src/core/context/novel_context.py`

**变更内容**:
- 从 `novel_generator`、`chapter_rewriter`、`blueprint_service` 中提取重复的上下文构建逻辑
- 创建 `NovelContextBuilder` 类，提供以下方法：
  - `build_generation_context(novel_id) -> GenerationContext` — 返回 world_str, chars_str, storylines_str, style_instruction
  - `build_rewrite_context(novel_id, chapter_number) -> RewriteContext` — 返回改写所需的完整上下文
  - `build_blueprint_context(novel_id, chapter_number, chapter_outline) -> BlueprintContext` — 返回蓝图生成上下文
- 所有 DB 查询集中在此模块，core/llm 层不再直接访问 DB

**验收标准**:
- `novel_generator` 中 3 处上下文构建代码替换为调用 `NovelContextBuilder`
- `chapter_rewriter._build_rewrite_context` 替换为调用公共模块
- `blueprint_service._build_context` 替换为调用公共模块
- 所有现有测试通过
- ruff 检查通过

**依赖**: 无

---

### Task 2: 提取质量评估公共模块

**文件**: 新建 `src/core/quality/__init__.py` + `src/core/quality/evaluator.py`

**变更内容**:
- 将 `quality_check.node` 和 `rewrite_loop_service._evaluate_chapter_quality` 中重复的评估逻辑提取为：
  - `evaluate_chapter_quality(novel_id, chapter_number, content, context) -> QualityScores`
  - 统一 EVALUATION_PROMPT（只保留一份）
  - 统一 JSON 解析和 fallback 逻辑
- `quality_check.node` 和 `rewrite_loop_service` 都调用此公共函数

**验收标准**:
- `rewrite_loop_service.py` 中删除 EVALUATION_PROMPT 和 `_evaluate_chapter_quality` 函数
- `quality_check.py` 中删除 EVALUATION_PROMPT，改为调用公共模块
- 评估结果格式保持一致
- 所有现有测试通过

**依赖**: 无

---

### Task 3: 提取 LLM 调用辅助函数

**文件**: 修改 `src/core/llm/client.py`（或新建 `src/core/llm/helpers.py`）

**变更内容**:
- 提取通用的 `generate_and_parse_json(client, prompt, max_tokens, fallback) -> Any` 辅助函数
- 封装：调用 LLM → safe_json_parse → fallback 的标准流程
- 替换 `storyline_service`、`outline_service`、`blueprint_service`、`novel_generator` 中的重复调用模式

**验收标准**:
- 至少 8 处重复的 `client.generate() + safe_json_parse()` 调用替换为 `generate_and_parse_json()`
- 所有现有测试通过

**依赖**: 无

---

## P1 — 消除反向依赖（中风险）

### Task 4: chapter_generator 去除 DB 依赖

**文件**: 修改 `src/core/llm/chapter_generator.py`、`src/api/services/novel_generator.py`

**变更内容**:
- 将 `_generate_single_chapter_inner` 中的 StoryBible 查询逻辑移到调用方（service 层）
- 新增参数 `story_bible_context: str | None = None`，由调用方传入
- 将 BlueprintService 调用逻辑移到调用方，通过已有的 `blueprint: dict | None` 参数传入
- 删除函数末尾的 Chapter.chapter_type DB update（改为在调用方处理）
- 删除所有 `from src.api.*` 和 `from src.core.database` 的 import

**验收标准**:
- `src/core/llm/chapter_generator.py` 中无任何 `from src.api` 或 `from src.core.database` import
- `generate_single_chapter` 函数签名新增 `story_bible_context` 参数
- 所有调用方（novel_generator、chapter_generation node）更新传参
- 所有现有测试通过

**依赖**: Task 1（需要 NovelContextBuilder 提供上下文）

---

### Task 5: LangGraph 节点去除 service 层依赖

**文件**: 修改 `src/core/langgraph/nodes/chapter_generation.py`、`src/core/langgraph/nodes/quality_check.py`

**变更内容**:
- `chapter_generation.node`：
  - 移除 `from src.api.services.knowledge_graph_service` import
  - 移除 `from src.api.services.progress_event_bus` import
  - 改为通过 state 中的回调函数或 LangGraph config 注入这些依赖
  - kg_service 和 progress_callback 通过 state 字段传入
- `quality_check.node`：
  - 移除 `from src.api.services.story_bible_service` import
  - 移除 `from src.api.services.knowledge_graph_service` import
  - 改为通过 state 中预计算的 `story_bible_context` 和 `kg_conflicts` 传入
  - 或者将一致性检查逻辑移到 service 层，节点只做 LLM 评估

**验收标准**:
- `src/core/langgraph/nodes/` 下所有文件无 `from src.api` import
- LangGraph 节点只依赖 `src.core.*`
- 所有现有测试通过

**依赖**: Task 4

---

### Task 6: 拆分 novel_generator 职责

**文件**: 修改 `src/api/services/novel_generator.py`，新建 `src/api/services/chapter_persistence_service.py`

**变更内容**:
- 提取 `_persist_to_novel` 为独立的 `ChapterPersistenceService`：
  - `persist_langgraph_result(novel_id, result)` — 持久化 LangGraph 结果
  - `persist_generated_chapters(novel_id, chapters, volume_number)` — 持久化生成的章节
  - `create_chapter_versions(novel_id, chapters)` — 批量创建版本记录
- 提取进度推送逻辑为内部辅助函数，减少重复
- `generate_volume_background` 和 `generate_chapters_background` 中的持久化代码替换为调用 `ChapterPersistenceService`

**验收标准**:
- `novel_generator.py` 行数从 ~1500 降至 ~800
- 持久化逻辑集中在 `chapter_persistence_service.py`
- 所有现有测试通过

**依赖**: Task 1

---

## P2 — 职责边界重划（较高风险）

### Task 7: storyline_service AI 生成逻辑分离

**文件**: 修改 `src/api/services/storyline_service.py`，新建 `src/api/services/ai_generation_service.py`

**变更内容**:
- 将 `generate_storylines_ai`、`generate_power_systems_ai`、`generate_arcs_ai`、`generate_scenes_ai` 移到新的 `AIGenerationService`
- `StorylineService` 只保留 CRUD 操作
- `AIGenerationService` 负责所有"基于设定 AI 生成新内容"的逻辑
- 利用 Task 1 的 `NovelContextBuilder` 和 Task 3 的 `generate_and_parse_json` 简化代码

**验收标准**:
- `storyline_service.py` 只包含 CRUD 方法（list/create/update/delete）
- `ai_generation_service.py` 包含所有 AI 生成方法
- `novel_generator._run_sub_feature` 中的调用更新为新 service
- 所有现有测试通过

**依赖**: Task 1, Task 3

---

### Task 8: chapter_rewriter 上下文构建统一

**文件**: 修改 `src/core/llm/chapter_rewriter.py`

**变更内容**:
- 删除 `_build_rewrite_context` 函数（它直接访问 DB，违反 core 层原则）
- 改为接收已构建好的 context dict 作为参数
- 调用方（route 或 service 层）负责通过 `NovelContextBuilder` 构建上下文后传入
- 更新 `rewrite_chapter_segment` 和 `targeted_rewrite` 的函数签名

**验收标准**:
- `chapter_rewriter.py` 中无 `from src.api` 或 `from src.core.database` import
- 所有改写功能正常工作
- 所有现有测试通过

**依赖**: Task 1

---

### Task 9: 清理 novel_generator 中的重复章节生成逻辑

**文件**: 修改 `src/api/services/novel_generator.py`

**变更内容**:
- `generate_volume_background` 和 `generate_chapters_background` 中有大量重复的章节生成循环逻辑
- 提取为统一的 `_generate_chapters_batch(client, chapter_outlines, context, ...) -> list[dict]`
- 统一进度推送逻辑
- 统一错误处理和 fallback 逻辑

**验收标准**:
- 章节生成循环逻辑只存在一份
- `generate_volume_background` 和 `generate_chapters_background` 调用统一的批量生成函数
- 所有现有测试通过

**依赖**: Task 1, Task 4, Task 6

---

### Task 10: 验证与回归测试

**文件**: 运行全量测试套件

**变更内容**:
- 运行 `pytest tests/` 确保所有测试通过
- 运行 `ruff check src/` 确保代码风格一致
- 运行 `mypy src/` 确保类型检查通过
- 验证无循环 import（可通过 `python -c "import src.api.main"` 验证）
- 检查依赖方向：core 层文件中不应有 `from src.api` import

**验收标准**:
- pytest 全部通过
- ruff 无 error
- mypy 无新增 error
- 无循环 import
- `grep -r "from src.api" src/core/` 返回空

**依赖**: Task 1-9 全部完成

---

## 执行顺序建议

```
Phase 1 (P0, 并行):  Task 1 + Task 2 + Task 3
Phase 2 (P1, 串行):  Task 4 → Task 5 → Task 6
Phase 3 (P2, 串行):  Task 7 → Task 8 → Task 9
Phase 4 (验证):      Task 10
```

预计总工作量：~2000 行代码变更（新增 ~400 行公共模块，删除 ~600 行重复代码，修改 ~1000 行调用关系）。
