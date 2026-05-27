# CHANGE-051 需求文档

**日期**: 2026-05-27  
**优先级**: P1 × 2，P2 × 1

---

## 1. 背景与目标

当前 LLM 客户端（`src/core/llm/client.py`）使用单一全局模型配置，无 token 用量追踪，也不支持按场景切换模型或在前端动态配置 API 参数。本次需求在不破坏现有接口的前提下，为系统增加三项能力：

1. **Token 监控** — 记录每次 LLM 调用的 prompt/completion/total tokens，并提供查询接口
2. **双模型策略** — 章节生成使用 `v4-flash`（快速/低成本），重要决策（规划、蓝图、质量评估等）使用 `v4-pro`（高质量）
3. **前端可配置模型** — 用户可在前端界面自定义 base_url、api_key、模型名称，并持久化到数据库

---

## 2. 功能需求

### 2.1 Token 监控机制（P1）

**涉及文件**: `src/core/llm/client.py`、新增 `src/core/llm/token_tracker.py`、新增路由合并至 `src/api/routes/llm_config.py`

**行为描述**:
- `LLMClient.generate()` 调用成功后，从 `AIMessage.response_metadata` 中提取 `token_usage`（langchain-openai 标准字段：`prompt_tokens`、`completion_tokens`、`total_tokens`）
- 将每次调用记录写入内存聚合器（`TokenTracker` 单例），包含：时间戳、模型名、prompt_tokens、completion_tokens、total_tokens
- 提供 REST 查询接口 `GET /api/v1/llm/token-stats`，返回：总调用次数、累计各类 token 数、按模型分组统计、最近 50 条调用记录

**约束**:
- token 记录仅保存在内存中（进程重启后清零），不写数据库，避免引入额外 schema 变更
- 若 API 响应中不含 token 信息（如某些兼容接口），静默跳过，不报错；`TokenTracker` 内部维护 `records_skipped` 计数器记录跳过次数，`GET /token-stats` 响应中暴露该字段
- `TokenTracker` 最多保留最近 1000 条记录（循环覆盖），防止内存无限增长

### 2.2 双模型策略（P1）

**涉及文件**: `src/core/config.py`、`src/core/llm/client.py`、`src/core/llm/chapter_generator.py`

**行为描述**:
- 在 `Settings` 中新增两个模型配置字段：
  - `DEEPSEEK_MODEL_FLASH: str = "deepseek-v4-flash"` — 用于章节正文生成
  - `DEEPSEEK_MODEL_PRO: str = "deepseek-v4-pro"` — 用于规划/蓝图/质量评估等决策场景
- `LLMClient` 初始化时创建两个 `ChatOpenAI` 实例：`self.llm_flash` 和 `self.llm_pro`
- `generate()` 方法新增 `use_flash: bool = False` 参数，`True` 时使用 flash 模型，默认使用 pro 模型
- `chapter_generator.py` 中章节正文生成调用（步骤 5 的 `client.generate(prompt, max_tokens=8000)` 和续写调用 `_continuation_generation`）传入 `use_flash=True`；规划/蓝图调用（步骤 3 的 `client.generate(planning_prompt, max_tokens=3000)`）保持默认（pro）

**约束**:
- 两个模型实例共享同一 `base_url` 和 `api_key`（来自 Settings 或激活的数据库配置）
- `use_flash` 为可选参数，默认 `False`，向后兼容所有现有调用方
- 现有 `DEEPSEEK_MODEL` 字段保留，不变（向后兼容 .env 配置）；`DEEPSEEK_MODEL_FLASH` 和 `DEEPSEEK_MODEL_PRO` 是独立的新增字段，与 `DEEPSEEK_MODEL` 并列存在，不存在别名或继承关系

### 2.3 前端可配置模型（P2）

**涉及文件**: `src/api/models/db_models.py`、新增 `src/api/routes/llm_config.py`、新增 `frontend/src/views/LLMSettings.vue`、`frontend/src/router/index.js`（或 `.ts`）、主导航组件

**后端行为**:
- 新增 `LLMConfig` 数据库模型，字段：
  - `id` (PK, Integer, autoincrement)
  - `name: str(100)` — 配置名称（如"我的 DeepSeek"）
  - `base_url: str(500)` — API base URL
  - `api_key: str(500)` — API Key（存储明文，响应时脱敏显示 `****` + 末4位）
  - `model_flash: str(100)` — 快速模型名
  - `model_pro: str(100)` — 高质量模型名
  - `is_active: bool` — 是否为当前激活配置（同一时刻最多一条为 True）
  - `created_at`, `updated_at`
- 新增路由文件 `src/api/routes/llm_config.py`，前缀 `/api/v1/llm`：
  - `GET /configs` — 列出所有配置（api_key 脱敏）
  - `POST /configs` — 创建新配置
  - `PUT /configs/{config_id}` — 更新配置
  - `DELETE /configs/{config_id}` — 删除配置
  - `POST /configs/{config_id}/activate` — 激活指定配置（同时将其他配置设为非激活）
  - `GET /token-stats` — token 统计查询（与 2.1 合并到同一路由文件）
- `LLMClient` 初始化时，优先使用传入的 `LLMConfig` 对象参数；若无则回退到 `Settings` 中的环境变量。应用启动时（`src/api/main.py` 的 lifespan），查询数据库中激活的 `LLMConfig`，调用 `LLMClient(llm_config=active_config)` 初始化全局单例；无激活配置时以 Settings 初始化。`get_llm_client()` 保持同步，返回已初始化的全局单例，所有调用点（包括 `chapter_generator.py`、`chapter_rewriter.py`、`helpers.py` 等）均通过该单例获取客户端，数据库激活配置对所有生成行为生效

**前端行为**:
- 新增 `frontend/src/views/LLMSettings.vue` — LLM 配置管理页面
  - 展示配置列表（名称、base_url、模型名、激活状态）
  - 支持新增、编辑、删除、激活操作
  - 展示 token 统计面板（总调用次数、累计 tokens、按模型分组）
- 在路由文件中注册 `/settings/llm`
- 在主导航中添加入口（位置：现有导航栏末尾）

---

## 3. 非功能需求

- **向后兼容**: 所有现有 API 接口和调用方不受影响
- **无破坏性迁移**: 新增数据库表通过 `init_db()` 的 `create_all` 自动创建，无需手动迁移脚本
- **安全**: api_key 在所有 GET 响应中脱敏（仅显示 `****xxxx` 末4位）
- **测试**: 每个新模块需有对应单元测试

---

## 4. 不在范围内

- Redis/Celery 层面的 token 持久化
- 多用户权限隔离（当前系统无用户体系）
- LLM 调用的流式（streaming）支持
- 对 `chapter_rewriter.py`、`helpers.py` 等其他 LLM 调用点的 flash/pro 切换（仅处理 `chapter_generator.py`）
- api_key 加密存储

---

## 5. 依赖关系

- 需求 2.3（前端配置）依赖需求 2.2（双模型字段）中的 `model_flash`/`model_pro` 概念
- 需求 2.1（token 统计路由）与需求 2.3（llm_config 路由）合并到同一路由文件
- 数据库模型变更（2.3）需在路由实现（2.3）之前完成
- `LLMClient` 的数据库读取（2.3）需在 token 监控（2.1）和双模型（2.2）之后实现
