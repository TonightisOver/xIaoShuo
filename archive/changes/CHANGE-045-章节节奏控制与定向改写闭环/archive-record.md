# CHANGE-045 归档记录

- 原名称：章节节奏控制与定向改写闭环
- 状态：completed
- 时间范围：2026-05-26
- 原路径：`.harness/changes/CHANGE-045-章节节奏控制与定向改写闭环`
- 归档路径：`archive/changes/CHANGE-045-章节节奏控制与定向改写闭环`
- 关联提交：
  - 76a9dab 2026-05-26 feat(CHANGE-045): 章节节奏控制与定向改写闭环

## 目标

### T1: ChapterBlueprint 数据模型
- 文件: `src/api/models/db_models.py`
- 在文件末尾新增 `ChapterBlueprint` model
- 包含字段: novel_id, chapter_number, chapter_type, plot_goal, hook_design, foreshadow_actions, cliffhanger, pacing_target, key_characters, word_target, rewrite_actions, is_active, created_at, updated_at
- 约束: UniqueConstraint(novel_id, chapter_number, is_active), Index(novel_id, chapter_number)
- 验证: import 成功，`__tablename__` = "chapter_blueprints"

### T2: Prompt 模板
- 文件: `src/core/llm/prompts.py`
- 新增 `BLUEPRINT_GENERATION_PROMPT` (PromptTemplate)
  - 输入变量: chapter_outline, previous_chapter, story_bible, kg_context, volume_context
  - 输出: 严格 JSON，含 chapter_type/plot_goal/hook_design/foreshadow_actions/cliffhanger/pacing_target/key_characters/word_target
- 新增 `TARGETED_REWRITE_PROMPTS` (dict[str, str])
  - 8 种改写类型: compress_pacing, enhance_hook, fix_character, trim_filler, enhance_plot, add_foreshadow, fix_world, enhance_trope
  - 每个模板使用 f-string 占位符: {full_content}, {instruction}, {context}, {characters}, {world_setting}
- 验证: import 成功，变量和 key 列表正确

### T10: Alembic Migration
- 文件: `alembic/versions/20260525_add_chapter_blueprint.py`
- revision: `20260525_blueprint`, down_revision: `20260525_long_form`
- 创建 chapter_blueprints 表，含所有字段、索引和唯一约束
- downgrade 完整回滚
- 验证: AST 语法检查通过

## 主要设计决定

1. **蓝图降级路径**: 当 BlueprintService 不可用时，自动降级到原有 CHAPTER_PLANNING_PROMPT
2. **独立质量评估**: rewrite_loop_service 内置独立的 LLM 质量评估，不依赖 LangGraph pipeline
3. **版本管理复用**: 所有改写操作复用 ChapterVersion (source="ai_rewrite")
4. **批量改写链式执行**: batch_targeted_rewrite 按优先级顺序链式执行，每步输出作为下步输入

## 涉及模块

- `alembic/versions/20260525_add_chapter_blueprint.py`
- `src/api/models/db_models.py`
- `src/api/routes/projects.py`
- `src/api/services/blueprint_service.py`
- `src/api/services/quality_action_service.py`
- `src/api/services/rewrite_loop_service.py`
- `src/core/llm/chapter_generator.py`
- `src/core/llm/chapter_rewriter.py`
- `src/core/llm/prompts.py`

## 实施结果

- 文件: `src/api/models/db_models.py`
- 在文件末尾新增 `ChapterBlueprint` model
- 包含字段: novel_id, chapter_number, chapter_type, plot_goal, hook_design, foreshadow_actions, cliffhanger, pacing_target, key_characters, word_target, rewrite_actions, is_active, created_at, updated_at
- 约束: UniqueConstraint(novel_id, chapter_number, is_active), Index(novel_id, chapter_number)
- 验证: import 成功，`__tablename__` = "chapter_blueprints"
- 文件: `src/core/llm/prompts.py`
- 新增 `BLUEPRINT_GENERATION_PROMPT` (PromptTemplate)
  - 输入变量: chapter_outline, previous_chapter, story_bible, kg_context, volume_context
  - 输出: 严格 JSON，含 chapter_type/plot_goal/hook_design/foreshadow_actions/cliffhanger/pacing_target/key_characters/word_target
- 新增 `TARGETED_REWRITE_PROMPTS` (dict[str, str])
  - 8 种改写类型: compress_pacing, enhance_hook, fix_character, trim_filler, enhance_plot, add_foreshadow, fix_world, enhance_trope
  - 每个模板使用 f-string 占位符: {full_content}, {instruction}, {context}, {characters}, {world_setting}

## 测试与验证

- `from src.api.models.db_models import ChapterBlueprint` — OK
- `from src.core.llm.prompts import BLUEPRINT_GENERATION_PROMPT, TARGETED_REWRITE_PROMPTS` — OK
- Migration 文件语法检查 — OK

## 遗留事项

原始资料未明确记录遗留事项。

## 原始文件清单

- `coding-report-phase1.md`
- `coding-report.md`
