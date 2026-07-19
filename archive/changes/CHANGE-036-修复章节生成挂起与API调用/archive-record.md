# CHANGE-036 归档记录

- 原名称：修复章节生成挂起与API调用
- 状态：archived-completed
- 时间范围：2026-05-27
- 原路径：`.harness/changes/CHANGE-036-修复章节生成挂起与API调用`
- 归档路径：`archive/changes/CHANGE-036-修复章节生成挂起与API调用`
- 关联提交：
  - 413f7f0 2026-05-27 feat(CHANGE-050): 工程质量修复 — 层级边界修正与前端测试体系

## 目标

修复章节生成任务卡死（无限挂起）问题；修复 API Key 为占位符时静默 fallback 导致进度虚高问题；改进错误处理和重试逻辑；新增启动时 API Key 有效性检查。

## 主要设计决定

修复章节生成任务卡死（无限挂起）问题；修复 API Key 为占位符时静默 fallback 导致进度虚高问题；改进错误处理和重试逻辑；新增启动时 API Key 有效性检查。
1. `chapter_generator.py` 无超时保护，单章生成可无限等待
2. `.env` 中 `DEEPSEEK_API_KEY=dummy_key_for_compilation` 为无效占位符，触发 fallback 返回硬编码武侠文本，进度计数器仍递增
3. `_should_retry` 不识别 `openai.APIConnectionError`，连接错误不重试直接失败
| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/core/llm/chapter_generator.py` | 修改 | 新增 `asyncio.wait_for` 300s 超时保护；超时返回增加 `generation_failed: True` |
| `src/core/langgraph/nodes/chapter_generation.py` | 修改 | try/except 移入 for 循环内，逐章捕获；失败章节打标记不再 fallback 硬编码内容 |
| `src/core/llm/client.py` | 修改 | `_should_retry` 增加 `openai.APIConnectionError \| openai.APITimeoutError` 识别 |
| `src/api/services/novel_generator.py` | 修改 | 进度回调增加 `successful_chapters` / `failed_chapters` 字段 |
| `src/api/main.py` | 修改 | lifespan 启动时检查 API Key 是否为占位符，打印 WARNING |
| `src/api/routes/health.py` | 修改 | `/health` 端点增加 `api_key_configured: bool` 字段 |

## 涉及模块

- `src/api/main.py`
- `src/api/models/responses.py`
- `src/api/routes/health.py`
- `src/api/routes/ws.py`
- `src/api/services/novel_generator.py`
- `src/core/config.py`
- `src/core/database.py`
- `src/core/langgraph/graph.py`
- `src/core/langgraph/nodes/chapter_generation.py`
- `src/core/langgraph/state.py`
- `src/core/llm/chapter_generator.py`
- `src/core/llm/client.py`
- `tests/unit/test_change036_retry_and_chapter_resilience.py`

## 实施结果

修复章节生成任务卡死（无限挂起）问题；修复 API Key 为占位符时静默 fallback 导致进度虚高问题；改进错误处理和重试逻辑；新增启动时 API Key 有效性检查。
1. `chapter_generator.py` 无超时保护，单章生成可无限等待
2. `.env` 中 `DEEPSEEK_API_KEY=dummy_key_for_compilation` 为无效占位符，触发 fallback 返回硬编码武侠文本，进度计数器仍递增
3. `_should_retry` 不识别 `openai.APIConnectionError`，连接错误不重试直接失败
| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/core/llm/chapter_generator.py` | 修改 | 新增 `asyncio.wait_for` 300s 超时保护；超时返回增加 `generation_failed: True` |
| `src/core/langgraph/nodes/chapter_generation.py` | 修改 | try/except 移入 for 循环内，逐章捕获；失败章节打标记不再 fallback 硬编码内容 |
| `src/core/llm/client.py` | 修改 | `_should_retry` 增加 `openai.APIConnectionError \| openai.APITimeoutError` 识别 |
| `src/api/services/novel_generator.py` | 修改 | 进度回调增加 `successful_chapters` / `failed_chapters` 字段 |
| `src/api/main.py` | 修改 | lifespan 启动时检查 API Key 是否为占位符，打印 WARNING |
| `src/api/routes/health.py` | 修改 | `/health` 端点增加 `api_key_configured: bool` 字段 |

## 测试与验证

修复章节生成任务卡死（无限挂起）问题；修复 API Key 为占位符时静默 fallback 导致进度虚高问题；改进错误处理和重试逻辑；新增启动时 API Key 有效性检查。
1. `chapter_generator.py` 无超时保护，单章生成可无限等待
2. `.env` 中 `DEEPSEEK_API_KEY=dummy_key_for_compilation` 为无效占位符，触发 fallback 返回硬编码武侠文本，进度计数器仍递增
3. `_should_retry` 不识别 `openai.APIConnectionError`，连接错误不重试直接失败
| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `src/core/llm/chapter_generator.py` | 修改 | 新增 `asyncio.wait_for` 300s 超时保护；超时返回增加 `generation_failed: True` |
| `src/core/langgraph/nodes/chapter_generation.py` | 修改 | try/except 移入 for 循环内，逐章捕获；失败章节打标记不再 fallback 硬编码内容 |
| `src/core/llm/client.py` | 修改 | `_should_retry` 增加 `openai.APIConnectionError \| openai.APITimeoutError` 识别 |
| `src/api/services/novel_generator.py` | 修改 | 进度回调增加 `successful_chapters` / `failed_chapters` 字段 |
| `src/api/main.py` | 修改 | lifespan 启动时检查 API Key 是否为占位符，打印 WARNING |
| `src/api/routes/health.py` | 修改 | `/health` 端点增加 `api_key_configured: bool` 字段 |

## 遗留事项

原始资料未明确记录遗留事项。

## 原始文件清单

- `summary.md`
