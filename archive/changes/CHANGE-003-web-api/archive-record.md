# CHANGE-003 归档记录

- 原名称：web-api
- 状态：completed
- 时间范围：2026-05-16
- 原路径：`.harness/changes/CHANGE-003-web-api`
- 归档路径：`archive/changes/CHANGE-003-web-api`
- 关联提交：
  - 37e475f 2026-05-16 docs: complete 10-stage harness documentation for CHANGE-003~008
  - f950c4e 2026-05-16 docs: add CHANGE-003 to CHANGE-008 harness documentation

## 目标

为 xIaoShuo 平台提供 RESTful Web API，支持通过 HTTP 接口创建小说生成任务、查询任务状态、列出任务列表，并提供 Swagger 交互式文档。

---

## 主要设计决定

使用 FastAPI 框架构建异步 API，采用分层架构（routes → services → models），通过 BackgroundTasks 实现异步任务执行，Pydantic 模型做请求/响应验证。

---

## 涉及模块

- `src/api/__init__.py`
- `src/api/main.py`
- `src/api/models/__init__.py`
- `src/api/models/requests.py`
- `src/api/models/responses.py`
- `src/api/routes/__init__.py`
- `src/api/routes/health.py`
- `src/api/routes/novels.py`
- `src/api/services/__init__.py`
- `src/api/services/novel_generator.py`
- `src/api/services/task_manager.py`
- `src/core/validation.py`
- `tests/api/`
- `tests/api/__init__.py`
- `tests/api/test_routes.py`

## 实施结果

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

## 测试与验证

**变更 ID**: CHANGE-003
**版本**: v1
**创建时间**: 2026-05-16

## 验证项目

| 检查项 | 命令 | 结果 |
|--------|------|------|
| 代码风格 | `ruff check src/ tests/` | ✅ 0 errors |
| 类型检查 | `mypy src/` | ✅ 0 errors |
| 单元测试 | `pytest tests/api/ -v` | ✅ 9 passed |
| 依赖安装 | `poetry install` | ✅ 成功 |

## 测试输出

```
tests/api/test_routes.py::test_root PASSED
tests/api/test_routes.py::test_health_check PASSED
tests/api/test_routes.py::test_create_novel_task PASSED
tests/api/test_routes.py::test_create_novel_task_invalid_idea PASSED
tests/api/test_routes.py::test_create_novel_task_invalid_type PASSED
tests/api/test_routes.py::test_get_novel_task PASSED
tests/api/test_routes.py::test_get_novel_task_not_found PASSED
tests/api/test_routes.py::test_list_novel_tasks PASSED
tests/api/test_routes.py::test_list_novel_tasks_with_filters PASSED
9 passed
```

## 结论

✅ CI 验证全部通过。

## 遗留事项

原始资料未明确记录遗留事项。

## 原始文件清单

- `01-需求分析.md`
- `02-技术设计.md`
- `03-编码计划.md`
- `04-编码报告-v1.md`
- `05-代码检查报告-v1.md`
- `06-专家评审报告-v1.md`
- `07-单元测试报告-v1.md`
- `08-集成测试报告-v1.md`
- `09-CI验证报告-v1.md`
- `10-部署验证报告-v1.md`
- `summary.md`
