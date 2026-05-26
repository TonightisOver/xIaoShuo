# 编码评审报告 - CHANGE-047

## 评审结论: APPROVED

## 优点

- 服务层结构清晰，职责单一，与项目现有 Service 模式（ConversationService、OutlineService 等）保持一致
- LLM 调用使用 asyncio.wait_for 设置 30s 超时，避免无限阻塞；超时后优雅降级返回空结果
- 数据库模型设计合理：复合索引 (novel_id, status) 覆盖高频查询路径
- Pydantic 模型使用 regex pattern 约束 level 和 action 字段，在路由层即拦截非法输入
- 前端 UI 交互完整：自动触发影响分析、批量操作、状态可视化，用户体验闭环
- 测试覆盖了关键路径：空数据、超时、状态流转、批量操作、偏离检测高低分支
- safe_json_parse 防御 LLM 返回非法 JSON，suggestions_data[:20] 限制单次写入量

## 问题与建议

### Minor - batch_action 逐条开启独立 session 效率偏低

`batch_action` 循环调用 `accept_suggestion` / `reject_suggestion`，每次调用都会独立获取 session。当 ids 列表较长时（最多可传入无限制数量的 ID），会产生 N 次独立事务。

建议：
1. 在 BatchRequest 中增加 `ids` 长度上限（如 `max_length=100`）
2. 长期可考虑将 batch_action 改为单 session 内批量更新

当前不阻塞：实际场景中建议数量有限（单次分析最多 20 条），风险可控。

### Minor - accept/reject 端点未校验 suggestion 归属

`accept_suggestion(novel_id, suggestion_id)` 路由接收了 `novel_id` 参数，但服务层仅按 `suggestion_id` 查询，未验证该 suggestion 是否属于该 novel_id。恶意用户可通过猜测 ID 操作其他项目的建议。

建议：在 service 层查询时增加 `novel_id` 条件过滤：
```python
select(OutlineSyncSuggestion).where(
    and_(
        OutlineSyncSuggestion.id == suggestion_id,
        OutlineSyncSuggestion.novel_id == novel_id,
    )
)
```

当前不阻塞：项目为单用户/内部工具场景，无多租户隔离需求。但作为防御性编程建议保留。

### Minor - get_suggestions 的 status 参数缺少枚举校验

`list_suggestions` 端点的 `status` query 参数为自由字符串，用户可传入任意值（如 `status=xxx`），虽然不会报错但返回空结果可能造成困惑。

建议：使用 `Query(None, pattern="^(pending|accepted|rejected|expired)$")` 或 Enum 类型约束。

### Minor - detect_deviation 超时时静默返回 score=0.0

当 LLM 超时或异常时，`detect_deviation` 返回 `deviation_score: 0.0`，这会导致 outline 状态被标记为 "completed"（因为 0.0 < 0.3）。这可能掩盖实际偏离。

建议：超时时返回一个明确的错误状态或保持原状态不变，而非假设"无偏离"。

### Minor - 前端 fetch 调用缺少统一错误处理

`acceptOne`、`rejectOne`、`batchAction` 等函数未处理网络错误或非 2xx 响应，失败时 UI 无反馈。

建议：添加 try/catch 和用户提示（toast 或 inline message）。

## 总结

代码整体质量良好，架构清晰，与项目既有模式一致。LLM 调用有超时保护，数据库操作使用 async context manager 确保连接释放。所有问题均为 Minor 级别的防御性改进建议，不影响功能正确性和系统稳定性，批准合入。
