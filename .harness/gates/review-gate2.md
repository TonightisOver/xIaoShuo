# Gate 2 交付审批 — CHANGE-051

**日期**: 2026-05-27
**分支**: feature/change-051-llm-enhancement

## 需求摘要

LLM 增强三件套：Token 监控、双模型策略、前端可配置模型

## 代码变更清单

| 文件 | 类型 | 说明 |
|------|------|------|
| src/core/llm/token_tracker.py | 新增 | TokenTracker 内存聚合器 |
| src/core/llm/client.py | 修改 | 双模型 + token 追踪 + llm_config 参数 |
| src/core/llm/chapter_generator.py | 修改 | 正文/续写用 flash，规划用 pro |
| src/core/config.py | 修改 | 新增 DEEPSEEK_MODEL_FLASH/PRO 字段 |
| src/api/models/db_models.py | 修改 | 新增 LLMConfig 模型 |
| src/api/routes/llm_config.py | 新增 | CRUD + token-stats 路由 |
| src/api/routes/__init__.py | 修改 | 导出 llm_config_router |
| src/api/main.py | 修改 | lifespan 单例初始化 + 路由注册 |
| frontend/src/views/LLMSettings.vue | 新增 | 配置管理 + token 统计页面 |
| frontend/src/router/index.js | 修改 | 注册 /settings/llm 路由 |
| frontend/src/App.vue | 修改 | 导航栏添加"模型配置"入口 |
| tests/unit/test_llm/test_token_tracker.py | 新增 | TokenTracker 单元测试 |
| tests/unit/test_llm/test_client.py | 修改 | 补充双模型 + token 追踪测试 |
| tests/unit/test_llm/test_client_db_config.py | 新增 | DB 配置初始化测试 |
| tests/api/routes/test_llm_config.py | 新增 | llm_config 路由集成测试 |

变更统计: 25 文件，+2337 行，-567 行

## 测试结果

- 单元测试: 414/414 通过
- 新增测试: 47 个
- WebSocket 测试: 修复预存竞态问题（与本次变更无关）

## 评审结论汇总

| 阶段 | 结论 |
|------|------|
| 需求评审（第1轮） | REVISION_REQUIRED |
| 需求评审（第2轮） | APPROVED |
| 编码评审 | APPROVED |
| 测试评审 | APPROVED |
