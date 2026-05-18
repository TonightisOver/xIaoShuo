# xIaoShuo 项目规范

## Harness 体系

本项目使用 Harness v2.0 多 Agent 协作体系管理开发流程。

入口: 使用 `/harness` 命令启动开发流程。

核心文件:
- `.harness/agents/orchestrator.md` — 主编排器，协调子 Agent 和门禁
- `.harness/rules/开发流程规范.md` — 10 阶段 + 2 Gate 流程规范
- `.harness/rules/工程结构.md` — 目录结构约束

其余 Rules 按需加载。

## Auto Mode 行为

- **批次 A**（Analyst: 阶段 1-2）连续执行，完成后在 **Gate 1** 暂停等待设计审批
- **批次 B**（Implementer → Tester → Deployer: 阶段 3-10）连续执行，完成后在 **Gate 2** 暂停等待交付审批
- 质量门禁失败自动修复重试（最多 3 次）
- 只有两个 Gate 暂停，其余阶段不打断用户

## 技术栈

- Python 3.11 · FastAPI · LangGraph · DeepSeek API
- PostgreSQL + SQLAlchemy · Redis · Celery
- pytest · ruff · mypy
