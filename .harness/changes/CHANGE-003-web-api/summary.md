# 变更总结: Web API (FastAPI)

**变更 ID**: CHANGE-003  
**创建时间**: 2026-05-16  
**完成时间**: 2026-05-16  
**状态**: ✅ 已完成

---

## 需求概述

为 xIaoShuo 平台提供 RESTful Web API，支持通过 HTTP 接口创建小说生成任务、查询任务状态、列出任务列表，并提供 Swagger 交互式文档。

---

## 技术方案

使用 FastAPI 框架构建异步 API，采用分层架构（routes → services → models），通过 BackgroundTasks 实现异步任务执行，Pydantic 模型做请求/响应验证。

---

## 核心变更

### 新增文件

- `src/api/__init__.py`
- `src/api/main.py` — FastAPI 应用入口，CORS 中间件，lifespan 管理
- `src/api/routes/__init__.py` — 路由注册
- `src/api/routes/health.py` — 健康检查端点
- `src/api/routes/novels.py` — 小说任务 CRUD 端点
- `src/api/models/__init__.py`
- `src/api/models/requests.py` — CreateNovelRequest（idea/novel_type/target_words）
- `src/api/models/responses.py` — TaskResponse/TaskDetailResponse/TaskListResponse
- `src/api/services/__init__.py`
- `src/api/services/task_manager.py` — 任务管理器（JSON 文件存储）
- `src/api/services/novel_generator.py` — 后台生成服务
- `src/core/validation.py` — 输入验证（创意长度、小说类型）
- `run_api.py` — 启动脚本
- `tests/api/__init__.py`
- `tests/api/test_routes.py` — 9 个 API 测试

---

## 质量指标

- **API 端点**: 4 个（health + novels CRUD）
- **测试用例**: 9 个，全部通过
- **输入验证**: 创意长度 10-1000 字，8 种小说类型
- **文档**: Swagger UI (`/docs`) + ReDoc (`/redoc`)

---

## 10 阶段完成情况

1. ✅ 需求分析 — 确定 RESTful API 设计
2. ✅ 技术设计 — FastAPI + 分层架构
3. ✅ 编码计划 — 文件清单和接口定义
4. ✅ 编码实现 — 15 个文件
5. ✅ 代码检查 — ruff 通过
6. ✅ 专家评审 — 架构合理
7. ✅ 单元测试 — 9 个用例通过
8. ✅ 集成测试 — API 端到端验证
9. ✅ CI 验证 — 全部通过
10. ✅ 部署验证 — 服务启动正常，端点可访问
