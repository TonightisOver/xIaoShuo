# 变更总结: PostgreSQL 数据库持久化

**变更 ID**: CHANGE-004  
**创建时间**: 2026-05-16  
**完成时间**: 2026-05-16  
**状态**: ✅ 已完成

---

## 需求概述

将任务存储从 JSON 文件迁移到 PostgreSQL 数据库，支持并发访问、事务、索引查询，使用 SQLAlchemy 2.0 async ORM 和 Alembic 数据库迁移管理。

---

## 技术方案

- SQLAlchemy 2.0 + asyncpg 异步驱动
- 连接池管理（pool_size=5, max_overflow=10, pool_pre_ping=True）
- Alembic 版本化迁移
- 单表设计（Task），JSONB 存储嵌套数据（progress/result/errors）
- 测试使用独立 xiaoshuo_test 数据库 + NullPool

---

## 核心变更

### 新增文件

- `src/core/database.py` — 数据库连接管理（engine/session/init/close）
- `src/api/models/db_models.py` — Task SQLAlchemy 模型
- `alembic.ini` — Alembic 配置
- `alembic/env.py` — 迁移环境（动态 URL，模型注册）
- `alembic/versions/e45b29ed4fe6_initial_schema.py` — 初始迁移
- `scripts/migrate_json_to_db.py` — JSON → PostgreSQL 数据迁移脚本
- `tests/conftest.py` — 测试数据库配置（NullPool）
- `DATABASE_SETUP.md` — 数据库设置指南

### 修改文件

- `pyproject.toml` — 添加 sqlalchemy/alembic/psycopg2-binary 依赖
- `src/core/config.py` — 添加 DATABASE_URL 等配置
- `src/api/services/task_manager.py` — 重写为 SQLAlchemy 查询
- `src/api/main.py` — lifespan 管理 init_db/close_db
- `.env` — 添加数据库连接字符串

---

## 质量指标

- **迁移数据**: 5 个任务从 JSON 成功迁移
- **测试用例**: 9 个 API 测试全部通过
- **索引**: task_id（唯一）、status、created_at DESC
- **连接池**: pool_pre_ping 保证连接有效性

---

## 10 阶段完成情况

1. ✅ 需求分析 — PostgreSQL + ORM + 迁移
2. ✅ 技术设计 — 单表 + JSONB + 连接池
3. ✅ 编码计划 — 8 个新文件 + 5 个修改
4. ✅ 编码实现 — 完成所有文件
5. ✅ 代码检查 — 通过
6. ✅ 专家评审 — 架构合理
7. ✅ 单元测试 — 9 个用例通过（NullPool 解决事件循环问题）
8. ✅ 集成测试 — API + 数据库端到端
9. ✅ CI 验证 — 通过
10. ✅ 部署验证 — 数据库连接正常，CRUD 操作验证通过
