# plan_review 评审报告

**评审轮次**: 第 1 轮
**评审对象**: 章节节奏控制与定向改写闭环 (requirements.md + tasks.md)
**日期**: 2026-05-25

## 评审结论
**结果**：APPROVED

---

## 评审发现

### MUST FIX（必须修复）

无。

### SHOULD FIX（建议修复）

1. **Blueprint 替代现有 CHAPTER_PLANNING_PROMPT 需保留降级路径**
   - 位置：requirements.md FR-1 "替代现有 CHAPTER_PLANNING_PROMPT"；tasks.md T5
   - 问题：当前 `chapter_generator.py` 的双级联流程（先调用 CHAPTER_PLANNING_PROMPT 生成规划单，再注入正文生成）是核心生成逻辑。需求说"替代"，但 Blueprint 是结构化 JSON 字段，而现有规划单是自由文本 Markdown。T5 任务描述过于简略，未说明如何兼容已有小说（已生成章节无 Blueprint 的情况）。
   - 建议：T5 描述中补充：(a) 对无 Blueprint 的章节保留现有 CHAPTER_PLANNING_PROMPT 降级路径；(b) 明确 Blueprint JSON 如何转化为注入正文 Prompt 的约束文本。

2. **定向改写 API 与现有 rewrite 端点的定位区分未说明**
   - 位置：requirements.md FR-3
   - 问题：现有 `POST /{novel_id}/chapters/{chapter_number}/rewrite` 是"选中文本片段改写"（需传入 selected_text），新增的 `targeted-rewrite` 是"按维度整章改写"。两者功能有重叠但粒度不同，需求文档未说明两者的定位区分和是否共存。
   - 建议：补充一句说明：现有 rewrite 端点保留用于用户手动选段改写，新增 targeted-rewrite 用于系统自动按质量维度改写，两者共存互不影响。

3. **T4 依赖标注不完整**
   - 位置：tasks.md T4 "依赖: T1"
   - 问题：T4 "Quality-to-Action 映射逻辑" 需要读取八维评分结果的数据结构（来自 `quality_check.py` 的 scores dict），但依赖仅标注了 T1（数据模型）。实现者需要了解评分输出格式才能正确映射。
   - 建议：在 T4 描述中补充"参考 `src/core/langgraph/nodes/quality_check.py` 的评分输出格式（8 维度 key: advancement/conflict/character_consistency/world_consistency/foreshadowing/pacing/readability/trope_alignment）"。

4. **Blueprint.chapter_type 与 Chapter.chapter_type 字段重复**
   - 位置：requirements.md FR-1 蓝图字段
   - 问题：现有 `Chapter` model 已有 `chapter_type` 字段（String(30)）。Blueprint 中也定义了 `chapter_type`。需明确两者关系：Blueprint 的 chapter_type 是规划阶段的预设值，生成后是否同步写入 Chapter.chapter_type？
   - 建议：在 T1 或 FR-1 中补充说明数据流向：Blueprint.chapter_type 为规划值，章节生成完成后自动同步到 Chapter.chapter_type。

5. **auto-improve 闭环的终止条件需精确定义**
   - 位置：requirements.md FR-4
   - 问题：FR-4 说"最多迭代 N 轮（默认 3 轮）"，但未定义"达标"的具体条件。是所有维度 >= 0.5？还是 overall >= 某阈值？还是所有之前低分维度都提升了？提前终止的条件不明确。
   - 建议：补充达标条件定义，例如"当所有维度评分 >= 阈值（默认 0.5）或本轮改写后无维度提升时终止循环"。

6. **T10 Alembic Migration 执行顺序建议提前**
   - 位置：tasks.md T10
   - 问题：T10 依赖 T1 是正确的，但 T3/T4/T5 等 service 层任务在开发时需要数据库表已存在才能做集成测试。当前任务编号暗示 T10 在 T9 之后执行。
   - 建议：调整实际执行顺序为 T1 -> T10 -> T2 -> T3/T4/T5/T6 并行 -> T7/T8/T9 -> T11，确保 service 开发时 DB schema 已就绪。

### INFO（信息提示）

1. **ChapterVersion.source 约束无需扩展**：当前 CHECK 约束已包含 `'ai_rewrite'`，定向改写产生的版本可直接复用此值，无需新增枚举。设计合理。

2. **Prompt 模板文件膨胀预警**：`prompts.py` 当前已 414 行，T2 将新增蓝图生成和 8 种改写类型的模板。建议实现时考虑按功能拆分为子模块（如 `prompts/blueprint.py`、`prompts/rewrite.py`），但不阻塞当前需求。

3. **性能约束可行**："单章蓝图生成 < 15s" 和 "单次定向改写 < 60s" 与现有 LLM 调用超时设置（chapter_rewriter: 120s, chapter_generator: 600s）兼容，DeepSeek API 响应时间在此范围内可行。

4. **Novel relationship 建议**：新增 ChapterBlueprint 建议通过 novel_id + chapter_number 直接查询，无需在 Novel model 中添加 relationship，避免 Novel model 过度膨胀（当前已有 7 个 relationship）。

5. **现有 rewrite 上下文构建可复用**：`chapter_rewriter.py` 中的 `_build_rewrite_context()` 函数已实现从 DB 读取世界观、大纲、人物卡、StoryBible 等上下文，定向改写引擎（T6）可直接复用此函数，减少重复代码。

---

## 总结

需求设计完整，技术方案与现有架构兼容性良好，复用了 ChapterVersion、八维质量评估、LLM client 等现有基础设施。任务拆分粒度合理（11 个任务），依赖关系基本正确。核心关注点是：(1) Blueprint 替代现有规划流程时需保留降级路径以兼容存量数据；(2) 新旧改写 API 的定位需在文档中明确区分；(3) auto-improve 的终止条件需精确定义以避免实现歧义。以上均为 SHOULD FIX 级别建议，不阻塞进入实现阶段。

**结论：APPROVED**
