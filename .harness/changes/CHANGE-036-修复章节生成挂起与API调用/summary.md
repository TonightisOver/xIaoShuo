# CHANGE-036 修复章节生成挂起与 API 调用问题

## 概述
修复章节生成任务卡死（无限挂起）问题；修复 API Key 为占位符时静默 fallback 导致进度虚高问题；改进错误处理和重试逻辑；新增启动时 API Key 有效性检查。

## 根本原因
1. `chapter_generator.py` 无超时保护，单章生成可无限等待
2. `.env` 中 `DEEPSEEK_API_KEY=dummy_key_for_compilation` 为无效占位符，触发 fallback 返回硬编码武侠文本，进度计数器仍递增
3. `_should_retry` 不识别 `openai.APIConnectionError`，连接错误不重试直接失败

## 变更文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/core/llm/chapter_generator.py` | 修改 | 新增 `asyncio.wait_for` 300s 超时保护；超时返回增加 `generation_failed: True` |
| `src/core/langgraph/nodes/chapter_generation.py` | 修改 | try/except 移入 for 循环内，逐章捕获；失败章节打标记不再 fallback 硬编码内容 |
| `src/core/llm/client.py` | 修改 | `_should_retry` 增加 `openai.APIConnectionError \| openai.APITimeoutError` 识别 |
| `src/api/services/novel_generator.py` | 修改 | 进度回调增加 `successful_chapters` / `failed_chapters` 字段 |
| `src/api/main.py` | 修改 | lifespan 启动时检查 API Key 是否为占位符，打印 WARNING |
| `src/api/routes/health.py` | 修改 | `/health` 端点增加 `api_key_configured: bool` 字段 |
| `src/api/models/responses.py` | 修改 | HealthResponse 增加 `api_key_configured` 字段 |
| `src/api/routes/ws.py` | 修改 | WebSocket 进度事件透传 `failed_chapters` 字段 |
| `src/core/langgraph/graph.py` | 修改 | 图节点超时异常向上传播，不再静默吞掉 |
| `src/core/langgraph/state.py` | 修改 | 新增 `generation_failed` 状态字段 |
| `src/core/config.py` | 修改 | 新增 `CHAPTER_TIMEOUT_SECONDS` 配置项 |
| `src/core/database.py` | 修改 | 连接池参数调整，避免长任务占用连接 |
| `tests/unit/test_change036_retry_and_chapter_resilience.py` | 新增 | 32 个测试：重试逻辑、逐章捕获、超时标记、进度字段、health 端点 |

## 修复效果
- 章节生成最长等待 300s 后超时，任务不再无限挂起
- API Key 无效时章节内容显示 `[章节生成失败：...]`，不再是硬编码武侠文本
- 连接错误触发最多 3 次重试
- `/health` 返回 `api_key_configured: false` 可快速诊断配置问题

## 关联 Commits
- `878aacf` fix: resolve chapter generation stuck in running state
- `4abf692` fix: prevent chapter generation from hanging indefinitely
- 本次 harness-flow 修复（API Key 配置 + 代码层修复）
