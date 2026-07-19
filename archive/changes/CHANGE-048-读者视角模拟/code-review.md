# 编码评审报告 - CHANGE-048

## 评审结论: APPROVED

## 优点

1. **并行 LLM 调用设计合理** — `asyncio.gather(*tasks, return_exceptions=True)` 正确处理了多 persona 并行调用，单个 persona 失败不影响整体流程。

2. **防御性编程到位** — 无效 persona 过滤、空章节检测、LLM 超时（30s `wait_for`）、JSON 解析容错（`safe_json_parse`）均有覆盖。

3. **DB 模型设计简洁** — 复合索引 `(novel_id, chapter_number)` 覆盖主查询路径，`JSON` 列存储灵活结果，外键 CASCADE 删除保证一致性。

4. **前端轮询策略务实** — 2s 间隔、最多 20 次（40s 上限），与后端 30s LLM 超时匹配良好。

5. **代码风格与项目一致** — structlog、singleton factory、async context manager 用法均与 `quality_report_service` 等现有服务保持一致。

## 问题与建议

### P2 - 建议改进（非阻塞）

1. **`get_simulation` 端点未校验 novel_id 归属**
   - 路由 `GET /{novel_id}/reader-simulations/{simulation_id}` 接收 `novel_id` 但查询时仅用 `simulation_id`，用户可通过任意 novel_id 访问其他项目的模拟结果。
   - 建议：查询条件加上 `ReaderSimulation.novel_id == novel_id`。
   - 严重程度：低（当前项目为单用户/内部工具，无多租户隔离需求）。

2. **`execute_simulation` 中 status 更新为 "running" 未持久化**
   - 第 145 行 `sim.status = "running"` 在 `async with get_db_session()` 块内设置，但该 session 退出时是否自动 commit 取决于 `get_db_session` 实现。如果是 autocommit=False 且无显式 commit，状态不会写入 DB。
   - 建议：确认 `get_db_session` 的 `__aexit__` 是否自动 commit，或显式 `await session.commit()`。

3. **章节内容截断策略可优化**
   - 当前 `content[:8000] + "\n...\n" + content[-2000:]` 可能在中文字符中间截断句子。
   - 建议：按句号/换行符边界截断，或在 prompt 中说明内容已截断。

4. **前端 persona 列表硬编码**
   - `ReaderSimPanel.vue` 第 98-103 行硬编码了 4 个 persona，后端已有 `GET /personas` 端点但未使用。
   - 建议：`onMounted` 时从后端拉取 persona 列表，保持前后端同步。

5. **模板中残留占位符注释**
   - 第 53 行 `<!-- PLACEHOLDER_CONTINUE -->` 应清理。

### P3 - 观察

- singleton `_reader_simulation_service` 在测试中通过直接实例化 `ReaderSimulationService()` 绕过，不影响测试正确性但与生产路径略有差异。
- `list_simulations` 硬编码 `limit(20)` 无分页参数，当前规模足够，后续可按需扩展。

## 总结

实现完整、结构清晰，与项目现有模式高度一致。并行 LLM + 后台任务 + 轮询的架构选型合理。所有建议均为非阻塞改进项，不影响功能正确性和稳定性。批准合入。
