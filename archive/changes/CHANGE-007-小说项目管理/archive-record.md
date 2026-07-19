# CHANGE-007 归档记录

- 原名称：小说项目管理
- 状态：completed
- 时间范围：2026-05-16
- 原路径：`.harness/changes/CHANGE-007-小说项目管理`
- 归档路径：`archive/changes/CHANGE-007-小说项目管理`
- 关联提交：
  - 37e475f 2026-05-16 docs: complete 10-stage harness documentation for CHANGE-003~008
  - f950c4e 2026-05-16 docs: add CHANGE-003 to CHANGE-008 harness documentation

## 目标

将系统从扁平的"任务"模型升级为"小说项目"模型，每本书有独立的世界观、等级体系、人物关系，支持多本书管理和内容编辑。生成完成后自动将结果拆分存入子资源表。

---

## 主要设计决定

- 新增 5 张数据库表（novels/world_settings/power_systems/characters/chapters）
- 外键关联 + CASCADE 删除
- RESTful 子资源 API（`/projects/{id}/world`、`/characters`、`/chapters`）
- 生成器适配：完成后自动持久化到子表
- Alembic 迁移管理

---

## 涉及模块

- `alembic/env.py`
- `alembic/versions/31e0b7e83e73_novel_project_schema.py`
- `src/api/main.py`
- `src/api/models/db_models.py`
- `src/api/routes/__init__.py`
- `src/api/routes/projects.py`
- `src/api/services/novel_generator.py`
- `src/api/services/novel_manager.py`
- `src/api/services/task_manager.py`

## 实施结果

**变更 ID**: CHANGE-007
**创建时间**: 2026-05-16
**完成时间**: 2026-05-16
**状态**: ✅ 已完成

---

## 需求概述

将系统从扁平的"任务"模型升级为"小说项目"模型，每本书有独立的世界观、等级体系、人物关系，支持多本书管理和内容编辑。生成完成后自动将结果拆分存入子资源表。

---

## 技术方案

- 新增 5 张数据库表（novels/world_settings/power_systems/characters/chapters）
- 外键关联 + CASCADE 删除
- RESTful 子资源 API（`/projects/{id}/world`、`/characters`、`/chapters`）
- 生成器适配：完成后自动持久化到子表
- Alembic 迁移管理

---

## 核心变更

### 新增文件

- `src/api/services/novel_manager.py` — NovelManager（小说 + 子资源 CRUD）
- `src/api/routes/projects.py` — 项目管理 API（20+ 端点）
- `alembic/versions/31e0b7e83e73_novel_project_schema.py` — 数据库迁移

### 修改文件

- `src/api/models/db_models.py` — 新增 Novel/WorldSetting/PowerSystem/Character/Chapter 模型
- `src/api/services/task_manager.py` — create_task 支持 novel_id 参数
- `src/api/services/novel_generator.py` — 添加 _persist_to_novel 函数
- `src/api/routes/__init__.py` — 注册 projects_router
- `src/api/main.py` — 注册 projects_router
- `alembic/env.py` — 导入新模型

---

## API 端点

```
POST/GET       /api/v1/projects              — 创建/列表
GET/PUT/DELETE /api/v1/projects/{id}         — 详情/更新/删除
POST           /api/v1/projects/{id}/generate — 触发生成
GET/PUT        /api/v1/projects/{id}/world   — 世界观
CRUD           /api/v1/projects/{id}/power-systems
CRUD           /api/v1/projects/{id}/characters
GET/PUT        /api/v1/projects/{id}/chapters/{num}
```

---

## 质量指标

- **数据库表**: 5 张新表 + 1 列新增（tasks.novel_id）
- **API 端点**: 20+ 个子资源端点
- **测试**: 13 个测试全部通过
- **数据完整性**: CASCADE 删除，外键约束

---

## 10 阶段完成情况

1. ✅ 需求分析 — 多本书管理 + 设定查看编辑
2. ✅ 技术设计 — 子资源表 + RESTful API
3. ✅ 编码计划 — 3 个新文件 + 6 个修改
4. ✅ 编码实现 — 完成
5. ✅ 代码检查 — 通过
6. ✅ 专家评审 — 数据模型合理
7. ✅ 单元测试 — 13 个通过
8. ✅ 集成测试 — 子资源 CRUD 端到端验证
9. ✅ CI 验证 — 通过
10. ✅ 部署验证 — 创建项目 → 编辑设定 → 查询验证通过

## 测试与验证

| # | 测试用例 | 结果 |
|---|----------|------|
| 1 | test_create_novel | PASS |
| 2 | test_get_novel | PASS |
| 3 | test_list_novels | PASS |
| 4 | test_update_novel | PASS |
| 5 | test_delete_novel_cascade | PASS |
| 6 | test_create_world_setting | PASS |
| 7 | test_update_world_setting | PASS |
| 8 | test_create_character | PASS |
| 9 | test_list_characters_by_novel | PASS |
| 10 | test_delete_character | PASS |
| 11 | test_create_power_system | PASS |
| 12 | test_create_chapter | PASS |
| 13 | test_chapter_ordering | PASS |

## 遗留事项

- 级联删除需确认 ORM relationship 配置正确
- task_manager 改动需保证向后兼容

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
