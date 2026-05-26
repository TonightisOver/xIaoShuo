# 需求评审报告 - CHANGE-048

## 评审结论: APPROVED

## 评审要点

### 1. 完整性 (Completeness)

需求文档定义了 5 个功能需求 (FR-1 ~ FR-5)，任务清单的 7 个 Task 完整覆盖：

| 功能需求 | 对应任务 | 覆盖情况 |
|---------|---------|---------|
| FR-1 读者人设定义 | Task-3 (READER_PERSONAS 常量) | 完整 |
| FR-2 模拟执行 | Task-3 (Service 层) | 完整 |
| FR-3 结果存储 | Task-1 + Task-2 (模型 + 迁移) | 完整 |
| FR-4 历史对比 | Task-4 (GET 列表/详情 API) | 完整 |
| FR-5 前端交互 | Task-6 + Task-7 (面板 + 集成) | 完整 |

### 2. 可行性 (Feasibility)

- LLM 调用模式与现有 `outline_sync_service.py` 一致 -- 使用 `get_llm_client()` + `safe_json_parse()` + structlog，技术路径已验证。
- `asyncio.gather` 并行执行在项目中已有使用先例，可行。
- FastAPI BackgroundTasks 模式在 `novels.py` 和 `projects.py` 中已大量使用，模式成熟。
- 数据模型 `novel_id` 使用 `String(100) FK` 关联 `novels.novel_id`，与现有 Chapter、Outline 等模型一致。
- 前端 polling GET 接口是合理的简化方案，无需引入 WebSocket。

### 3. 一致性 (Consistency)

- 数据模型字段与 API 响应结构完全对齐。
- 前端卡片内容（engagement 分数、情感反应、节奏评价、爽点/痛点、总评）与 LLM 输出 JSON 结构一一对应。
- 路由注册遵循现有 `__init__.py` 导出 + `main.py` include_router 模式。
- 测试命名 `test_change048_reader_simulation.py` 遵循项目既有规范。

### 4. 范围 (Scope)

7 个任务，预估复杂度"中"，合理。核心工作量集中在 Task-3（Service 层 prompt 设计 + 并行调用 + 错误处理）和 Task-6（前端面板），其余为胶水代码。对单人开发者而言 1-2 天可完成。

### 5. 风险评估 (Risk)

| 风险项 | 等级 | 缓解措施 |
|--------|------|---------|
| LLM 输出 JSON 不稳定 | 中 | 已规划使用 `safe_json_parse` 容错解析，单人设失败不阻塞整体 |
| 4 路并行 LLM 调用可能触发 rate limit | 低 | DeepSeek API 并发限制较宽松；`get_llm_client()` 已内置 retry |
| 前端轮询频率未明确 | 低 | 建议实现时设定 3s 间隔 + 最大轮询次数 |
| 上下文截断策略（前8000+后2000字）可能丢失关键信息 | 低 | 对网文章节（通常 2000-5000 字）影响极小 |

## 问题与建议

### 建议项（不阻塞）

1. **ReaderFeedbackCard.vue 未单独列为任务**：需求文档前端设计部分提到了独立的 `ReaderFeedbackCard.vue` 组件，但任务清单中未单独列出。建议在 Task-6 中明确说明卡片是内联实现还是抽取为子组件。当前不阻塞，因为 Task-6 描述已包含卡片内容。

2. **轮询终止条件建议明确**：Task-6 描述"轮询或 polling 获取结果"，建议实现时确定：轮询间隔 3 秒，最大等待 90 秒，终止条件为 status=completed 或 failed。

3. **novel_id FK 类型**：Task-1 描述 `novel_id(FK)` 但未指定类型为 `String(100)`。实现时需确保与现有模型一致（`String(100), ForeignKey("novels.novel_id", ondelete="CASCADE")`）。

4. **status 字段枚举**：需求文档定义了 4 种状态（pending/running/completed/failed），建议 Task-1 中添加 CheckConstraint 或在 Service 层使用 Enum 常量，与项目中其他模型保持一致。

## 总结

需求文档和任务分解质量良好。功能边界清晰，技术方案与项目现有模式高度一致，依赖关系合理，无阻塞性问题。建议项均为实现细节层面的补充，可在编码阶段自然解决。批准进入实现阶段。
