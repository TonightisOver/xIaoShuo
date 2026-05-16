# xIaoShuo 项目规范

## Harness 体系

本项目使用 Harness 体系管理开发流程。每次接收新需求时，必须遵循以下规则：

1. 读取 `.harness/agents/application-owner.md` — Agent 角色定义和执行循环
2. 读取 `.harness/rules/开发流程规范.md` — 10 阶段流程 + Auto Mode 执行规范
3. 读取 `.harness/rules/工程结构.md` — 目录结构约束

其余 Rules 和 Skills 按需加载（见 application-owner.md 的配置索引）。

## Auto Mode 下的行为

- **批次 A**（阶段 1-2）连续执行，完成后暂停呈现架构方案，等待用户确认
- **批次 B**（阶段 3-10）连续执行，质量门禁失败自动修复重试，完成后暂停等待交付确认
- 只有两个人工门禁节点才暂停，其余阶段不打断用户

## 技术栈

- Python 3.11 · FastAPI · LangGraph · DeepSeek API
- PostgreSQL + SQLAlchemy · Redis · Celery
- pytest · ruff · mypy
