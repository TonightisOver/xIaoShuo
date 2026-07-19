# 后端测试基线恢复设计

> 在不扩展业务功能、不处理安全配置、不改变外部 API 的前提下，修复重构后遗留的测试契约漂移，并移除 `src/core` 对 `src.api` 的反向依赖。

## 背景

项目历史归档已经完成，但后端无数据库单元测试仍有 15 个存量失败。新鲜复现结果显示：13 个失败来自测试仍使用重构前的 patch 路径、调用签名、默认语义或不完整 Mock；另外 2 个失败来自同一处真实架构回归——`src/core/langgraph/nodes/quality_check.py` 在函数内部导入两个 `src.api.services` 模块。

这些失败均与归档文件移动无关。相关重构分别来自：

- `2c56a9a`：长篇入口迁入 `long_form_generation_helpers.py`。
- `9f83bf3`：`generate_single_chapter` 收敛为 `ChapterGenContext` 参数。
- `5653747`：质量节点接入公共 gate 时引入 Core → API 反向依赖。
- 章节版本语义已经明确为 `is_active=False` 只创建候选快照。
- 真实 ORM 章节对象的 `state_delta` 默认值为 `None`。

## 目标

1. 恢复 `tests/unit` 为零失败基线。
2. 让测试 patch 实际定义和查找协作者的模块，而不是兼容 re-export 模块。
3. 让测试使用当前公开调用契约和当前业务语义。
4. 移除 `src/core/**` 对 `src.api/**` 的全部导入。
5. 保持短篇质量 gate 的持久化和自动改写能力由 API 编排层注入。
6. 保持归档内容、登录/密钥/管理员配置、数据库模型、HTTP 接口和前端行为不变。

## 非目标

- 不恢复已经废弃的散列参数接口。
- 不在 `novel_generator.py` 增加无法影响函数 globals 的虚假兼容 shim。
- 不改变 `ChapterService.create_chapter_version()` 的 `is_active=False` 默认语义。
- 不为 `MagicMock` 在生产代码中增加特殊分支。
- 不调整质量阈值、gate 评分口径、改写算法或任务状态机。
- 不处理安全收口、真实 PostgreSQL 连接、Git 暂存、提交或推送。
- 不顺带执行后端分包、前端模块化或任务队列改造。

## 方案比较

### 方案一：在旧模块增加兼容符号

可以让部分 patch 不再抛 `AttributeError`，但迁移后的函数仍在 `long_form_generation_helpers` 的 globals 中查找协作者，旧模块 patch 不会真正生效。该方案制造假兼容且可能误调用真实 LLM，不采用。

### 方案二：只修改生产代码迁就旧测试

需要恢复旧调用签名、旧章节激活语义，并为 `MagicMock` 添加生产分支，会逆转已经完成的重构并污染业务代码，不采用。

### 方案三：测试契约对齐 + Core 依赖注入（采用）

过期测试跟随当前真实接口；唯一真实架构问题通过已有 LangGraph `configurable` 注入机制解决。改动范围小，能同时恢复测试可信度和层级边界。

## 详细设计

### 1. 长篇生成测试 patch 路径

测试仍可从 `src.api.services.novel_generator` 导入兼容入口 `generate_long_form_background`，以验证路由层兼容面。但该函数的协作者必须 patch 到其定义模块：

```text
src.api.services.long_form_generation_helpers
```

需要迁移的符号包括：

- `get_task_manager`
- `get_long_form_progress_service`
- `generate_master_outline`
- `generate_volume_outline`
- `generate_volume_chapters`
- `generate_volume_quality_report`
- `_emit_progress`

函数内部懒加载的 `get_novel_manager` 和 `get_outline_service` 继续 patch 原服务模块。

### 2. 章节版本与章节生成契约

- 期望同步更新 `Chapter.content` 的测试显式传入 `is_active=True`。
- 现有 `test_change060_is_active_semantics.py` 继续证明 inactive 候选不会覆盖正文，不重复新增同义测试。
- 超时测试构造 `ChapterGenContext` 后调用 `generate_single_chapter(ctx)`，不恢复旧关键字参数。

### 3. ORM Mock 真实性

两个改写上下文测试中的前后章节 Mock 显式设置：

```python
chapter.state_delta = None
```

这与 `Chapter.state_delta` 的真实数据库默认状态一致，使被测逻辑走正文摘要回退路径。生产代码不识别测试框架类型。

### 4. 空章节质量语义

空章节没有可评分正文时保持：

```text
overall = None
status = "unverified"
consistency_blocked = False
```

旧测试改为验证该语义，不再要求伪造正分。

### 5. Quality Check 依赖注入

`quality_check.node()` 只从 `config["configurable"]` 获取 API 能力：

- `persist_quality`：未注入时使用异步 no-op。
- `rewrite_service`：未注入时为 `None`，由 `run_quality_gate` 按现有逻辑优雅降级为不执行 L3。

`novel_generator._run_langgraph_pipeline()` 在 API 层注入：

```python
{
    "persist_quality": _persist_quality_to_version,
    "rewrite_service": RewriteLoopService(),
}
```

`resume_pipeline()` 同样携带这两个依赖。当前图在 `human_review` 后直接进入
`END`，不会再次执行质量节点；这里保持完整配置是防御性约束，避免未来调整中断点
或恢复拓扑时静默丢失持久化和 L3 能力。

Core 层保留对 `src.core.quality.gate` 的依赖，因为 gate 本身通过回调隔离数据库和 API 服务。

## 测试策略

1. 先保留并运行当前 15 个失败，确认红灯原因。
2. 逐组更新测试契约，每组立即运行对应测试。
3. 增加节点注入契约测试：传入 sentinel `rewrite_service`，断言节点原样交给 `run_quality_gate`。
4. 捕获初始 pipeline 与 resume 的 `astream` 配置，断言 API 层均提供持久化和改写依赖。
5. 运行两个层级边界测试，证明 Core 中不存在 API import。
6. 运行全部相关质量 gate、长篇生成、章节服务和上下文测试。
7. 运行完整 `tests/unit`、Ruff、FastAPI 导入、前端测试与前端构建。
8. 数据库集成测试仍记录为环境未验证，不用无数据库结果替代真实 PostgreSQL 结论。

## 验收标准

- 原 15 个失败全部消失，`tests/unit` 零失败。
- `test_core_has_no_api_imports` 与 `test_core_langgraph_nodes_do_not_import_api_services` 通过。
- `quality_check.py` 的 AST 中不存在 `src.api` import。
- 长篇测试不会触发真实 LLM、数据库或进度服务。
- inactive 版本语义测试继续通过。
- 前端 47 个测试与构建保持通过。
- 归档 manifest、索引和原始历史文件不被改动。
- 未执行任何 Git 暂存、提交或推送。

## 风险与控制

- **patch 到错误命名空间：** 定向运行 8 个长篇测试，确认 mock 调用断言生效且无真实外部调用。
- **移除 fallback 后 L3 丢失：** 对初始执行和 resume 配置都注入 `RewriteLoopService`，并增加节点注入契约测试。
- **误改业务语义：** 生产代码只调整依赖来源，不修改 gate 分支、评分或持久化参数。
- **工作区已有大量归档移动：** 只编辑本设计列出的源码和测试文件，不触碰 `.claude/worktrees/*` 与其他用户改动。
