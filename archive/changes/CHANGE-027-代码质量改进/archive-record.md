# CHANGE-027 归档记录

- 原名称：代码质量改进
- 状态：completed
- 时间范围：2026-05-19
- 原路径：`.harness/changes/CHANGE-027-代码质量改进`
- 归档路径：`archive/changes/CHANGE-027-代码质量改进`
- 关联提交：
  - 0637259 2026-05-19 feat: improve chapter display and api robustness

## 目标

本次变更是一次纯代码质量改进，不涉及新业务功能。目标是消除已识别的 8 类技术债务，提升系统的可靠性、可观测性和可维护性。所有改动均在现有架构内完成，不引入新的外部依赖（结构化日志除外）。

---

## 主要设计决定

**变更编号**: CHANGE-027
**日期**: 2026-05-19
**设计人**: Analyst Agent v2.0

---

## 1. 总体策略

本次改动分为 5 个独立模块，互不依赖，可并行实施：

| 模块 | 涉及文件 | 复杂度 |
|------|---------|--------|
| A. 重试逻辑 | `src/core/llm/client.py` | 中 |
| B. CORS 配置 | `src/api/main.py` | 低 |
| C. 数据库索引 + Migration | `src/api/models/db_models.py`、新增 migration 文件 | 低 |
| D. 内存泄漏修复 | `src/api/services/novel_generator.py` | 低 |
| E. 结构化日志 | `src/core/logging_config.py`、`src/core/llm/client.py`、`src/api/services/novel_generator.py` | 中 |
| F. response_model | `src/api/routes/projects.py`、`src/api/models/responses.py` | 中 |
| G. 测试补充 | `tests/unit/` 下新增文件 | 中 |

---

## 2. 模块 A：重试逻辑

### 2.1 问题根因

`@retry` 装饰器在类定义时求值，无法访问实例属性 `self.max_retries`。同时 `retry_if_exception_type` 只覆盖网络层异常，不覆盖 HTTP 状态码异常。

### 2.2 设计方案

**方案选择**: 将 `@retry` 装饰器移除，改为在方法体内使用 `tenacity.AsyncRetrying` 上下文管理器，在 `__init__` 时读取 `max_retries`。

**HTTP 状态码异常处理**: `langchain_openai` 底层使用 `httpx`，HTTP 错误会抛出 `httpx.HTTPStatusError`。需要自定义 `retry_if_exception` 谓词，检查状态码是否为 429 或 5xx。

### 2.3 改动点：`src/core/llm/client.py`

```
改动说明：
1. 移除顶层 @retry 装饰器及其导入（stop_after_attempt, retry_if_exception_type）
2. 新增导入：tenacity.AsyncRetrying, tenacity.retry_if_exception, httpx
3. __init__ 中保存 self.max_retries（已有）
4. generate() 方法改为：
   - 用 AsyncRetrying(stop=stop_after_attempt(self.max_retries), ...) 包裹 ainvoke 调用
   - retry 谓词：lambda e: isinstance(e, (TimeoutError, ConnectionError))
                  or (isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (429, 500, 502, 503))
   - wait: wait_exponential(multiplier=1, min=2, max=30)，429 时等待更长
   - reraise=True
5. 日志中记录重试次数（结合模块 E）
```

**关键设计决策**:
- 401 不重试（认证失败重试无意义，会消耗配额）
- 429 重试时 wait 上限设为 30s（DeepSeek 限流通常在 10-20s 内恢复）
- 5xx 重试（服务端临时故障）

---

## 3. 模块 B：CORS 配置

### 3.1 设计方案

**文件**: `src/api/main.py`

当前

## 涉及模块

- `alembic/versions/`
- `alembic/versions/20260519_add_status_indexes.py`
- `src/api/main.py`
- `src/api/models/db_models.py`
- `src/api/models/responses.py`
- `src/api/routes/`
- `src/api/routes/projects.py`
- `src/api/services/novel_generator.py`
- `src/api/services/novel_manager.py`
- `src/api/services/progress_event_bus.py`
- `src/core/config.py`
- `src/core/llm/client.py`
- `src/core/logging_config.py`
- `tests/unit/`
- `tests/unit/test_llm/test_client.py`
- `tests/unit/test_novel_generator.py`
- `tests/unit/test_progress_event_bus.py`

## 实施结果

- ruff: **0 新增错误**，修复 1 个预存 F541
- mypy: **0 新增错误**（structlog import-not-found 为预期，安装依赖后消除）
- 质量门禁: **通过**（本次变更文件无新增 lint 错误）

## 测试与验证

**变更编号**: CHANGE-027
**日期**: 2026-05-19
**分析人**: Analyst Agent v2.0
---
本次变更是一次纯代码质量改进，不涉及新业务功能。目标是消除已识别的 8 类技术债务，提升系统的可靠性、可观测性和可维护性。所有改动均在现有架构内完成，不引入新的外部依赖（结构化日志除外）。
---
**文件**: `src/core/llm/client.py`
**现状**:
- `@retry` 装饰器使用 `stop_after_attempt(3)` 字面量，与 `self.max_retries = settings.DEEPSEEK_MAX_RETRIES` 完全脱节——修改配置不生效。
- `retry_if_exception_type((TimeoutError, ConnectionError))` 只捕获网络层异常，不捕获 HTTP 429（限流）和 401（认证失败）。DeepSeek API 在高并发时会返回 429，当前实现会直接抛出而不重试。
**影响**: 配置项 `DEEPSEEK_MAX_RETRIES` 形同虚设；429 错误不重试导致任务失败率偏高。
**约束**: `@retry` 装饰器是静态的，不能直接读取实例属性。需要改为在 `__init__` 中动态构建重试逻辑，或使用 `tenacity.Retrying` 上下文管理器。

## 遗留事项

### 问题 1：重试逻辑硬编码且异常覆盖不足

**文件**: `src/core/llm/client.py`

**现状**:
- `@retry` 装饰器使用 `stop_after_attempt(3)` 字面量，与 `self.max_retries = settings.DEEPSEEK_MAX_RETRIES` 完全脱节——修改配置不生效。
- `retry_if_exception_type((TimeoutError, ConnectionError))` 只捕获网络层异常，不捕获 HTTP 429（限流）和 401（认证失败）。DeepSeek API 在高并发时会返回 429，当前实现会直接抛出而不重试。

**影响**: 配置项 `DEEPSEEK_MAX_RETRIES` 形同虚设；429 错误不重试导致任务失败率偏高。

**约束**: `@retry` 装饰器是静态的，不能直接读取实例属性。需要改为在 `__init__` 中动态构建重试逻辑，或使用 `tenacity.Retrying` 上下文管理器。

---

### 问题 2：CORS 配置违反规范

**文件**: `src/api/main.py`

**现状**:
```python
allow_origins=["*"],
allow_credentials=True,
```

**影响**: 浏览器会拒绝此配置。CORS 规范明确禁止同时使用通配符 origin 和 `credentials: true`——浏览器会抛出 CORS 错误，导致前端无法携带 Cookie 或 Authorization header 发起跨域请求。

**约束**: 修复方案有两种：
1. 去掉 `allow_credentials=True`（适合纯 token 认证，无 Cookie）
2. 将 `allow_origins` 改为明确的域名列表（适合生产环境）

当前项目为开发阶段，前端通过 Vite dev server 访问，推荐方案 1（去掉 credentials），同时保留通配符 origin，并在配置中预留生产环境 origins 的扩展点。

---

### 问题 3：数据库索引缺失

**文件**: `src/api/models/db_models.py`

**现状**（经代码核查）:
- `Novel.status`：已有 `index=True` ✅
- `Task.status`：已有 `index=True` ✅
- `Chapter.status`：`mapped_column(String(20), default="draft")` — **无索引** ❌
- `Volume.status`：`mapped_column(String(20), default="draft")` — **无索引** ❌
- `Conversation.status`：`mapped_column(String(20), default="active")` — **无索引** ❌
- `Storyline.status`：`mapped_column(String(20), default="active")` — **无索引** ❌
- `Outline.status`：`mapped_column(String(20), default="draft")` — **无索引** ❌

**影响**: 按 status 过滤的查询（如"获取所有 generating 状态的章节"）会全表扫描。随着数据量增长，性能会线性下降。

**约束**: 需要同步生成 Alembic migration，否则索引只在新建数据库时生效。

---

### 问题 4：进度回调内存泄漏

**文件**: `src/api/services/progress_event_bus.py`

**现状**:
```python
_progress_callbacks: dict[str, Any] = {}
```
`register_progress_callback` 在任务开始时注册，但 `novel_generator.py` 的异常路径（

## 原始文件清单

- `.gate1-approved`
- `01-需求分析.md`
- `02-技术设计.md`
- `03-编码计划.md`
- `04-编码报告-v1.md`
- `05-代码检查报告-v1.md`
- `06-专家评审报告-v1.md`
