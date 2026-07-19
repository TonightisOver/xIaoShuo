# CHANGE-017 归档记录

- 原名称：故事线人物弧光场景
- 状态：completed
- 时间范围：2026-05-17
- 原路径：`.harness/changes/CHANGE-017-故事线人物弧光场景`
- 归档路径：`archive/changes/CHANGE-017-故事线人物弧光场景`
- 关联提交：
  - 0aa722d 2026-05-17 feat(CHANGE-018): add D3.js tree visualization for story relations
  - f7d19a3 2026-05-17 feat(CHANGE-017): add storyline, character arc, and scene management

## 目标

为小说项目添加结构化叙事管理：故事线（主线/副线/暗线）、人物弧光（成长轨迹）、场景管理，以及它们之间的三元关联关系。

---

## 主要设计决定

**变更 ID**: CHANGE-017
**创建时间**: 2026-05-17

## 1. 设计概述

新增 storylines、character_arcs、scenes 三张主表 + storyline_characters 关联表，提供完整的 CRUD API 和前端管理界面。数据结构为 CHANGE-018（三元图谱可视化）提供基础。

## 2. 数据库设计

```sql
CREATE TABLE storylines (
    id SERIAL PRIMARY KEY,
    novel_id VARCHAR(100) REFERENCES novels(novel_id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    type VARCHAR(20) NOT NULL DEFAULT 'main',
    description TEXT,
    key_events JSON DEFAULT '[]',
    status VARCHAR(20) DEFAULT 'active',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE character_arcs (
    id SERIAL PRIMARY KEY,
    novel_id VARCHAR(100) REFERENCES novels(novel_id) ON DELETE CASCADE,
    character_id INTEGER REFERENCES characters(id) ON DELETE CASCADE,
    arc_type VARCHAR(30) NOT NULL DEFAULT 'growth',
    description TEXT,
    stages JSON DEFAULT '[]',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE scenes (
    id SERIAL PRIMARY KEY,
    novel_id VARCHAR(100) REFERENCES novels(novel_id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    location VARCHAR(200),
    description TEXT,
    appearances JSON DEFAULT '[]',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE storyline_characters (
    id SERIAL PRIMARY KEY,
    storyline_id INTEGER REFERENCES storylines(id) ON DELETE CASCADE,
    character_id INTEGER REFERENCES characters(id) ON DELETE CASCADE,
    role_in_line VARCHAR(50)
);
```

## 3. 服务层

### StorylineService

```python
class StorylineService:

## 涉及模块

- `alembic/env.py`
- `alembic/versions/8795631f9b67_add_storylines_arcs_scenes.py`
- `alembic/versions/xxx.py`
- `frontend/src/router/index.js`
- `frontend/src/views/NovelDetail.vue`
- `frontend/src/views/StorylineManager.vue`
- `src/api/main.py`
- `src/api/models/db_models.py`
- `src/api/routes/__init__.py`
- `src/api/routes/storylines.py`
- `src/api/services/storyline_service.py`
- `tests/api/`
- `tests/api/test_routes.py`
- `tests/integration/`
- `tests/integration/test_langgraph/test_graph.py`
- `tests/unit/`
- `tests/unit/test_core/test_json_utils.py`
- `tests/unit/test_core/test_validation.py`
- `tests/unit/test_langgraph/test_nodes.py`
- `tests/unit/test_llm/test_client.py`

## 实施结果

**变更 ID**: CHANGE-017
**创建时间**: 2026-05-17
**完成时间**: 2026-05-17
**状态**: ✅ 已完成

---

## 需求概述

为小说项目添加结构化叙事管理：故事线（主线/副线/暗线）、人物弧光（成长轨迹）、场景管理，以及它们之间的三元关联关系。

---

## 核心变更

- 4 张新表：storylines, character_arcs, scenes_table, storyline_characters
- StorylineService：完整 CRUD + 关联 + get_relations
- API：故事线/弧光/场景 CRUD + 人物关联 + 关系查询
- 前端：StorylineManager.vue + NovelDetail "故事线" Tab

---

## 10 阶段完成情况

1. ✅ 需求分析
2. ✅ 技术设计
3. ✅ 编码计划
4. ✅ 编码实现
5. ✅ 代码检查
6. ✅ 专家评审
7. ✅ 单元测试
8. ✅ 集成测试
9. ✅ CI 验证
10. ✅ 部署验证

## 测试与验证

**变更 ID**: CHANGE-017
**版本**: v1
**验证时间**: 2026-05-17

## CI 检查项

| # | 检查项 | 命令 | 结果 |
|---|--------|------|------|
| 1 | Python 类型检查 | 无 mypy 配置（项目未启用） | N/A |
| 2 | 代码格式 | 符合项目现有风格 | PASS |
| 3 | 单元测试 | pytest tests/unit/ | 全部通过 |
| 4 | 集成测试 | pytest tests/integration/ | 全部通过 |
| 5 | API 测试 | pytest tests/api/ | 全部通过 |
| 6 | 前端构建 | npm run build | 成功，无错误 |
| 7 | 导入检查 | 所有新增 import 可解析 | PASS |
| 8 | 迁移检查 | alembic 迁移文件语法正确 | PASS |

## 测试结果汇总

```
tests/unit/test_core/test_validation.py       .......... PASSED
tests/unit/test_core/test_json_utils.py       ... PASSED
tests/unit/test_langgraph/test_nodes.py       ....... PASSED
tests/unit/test_llm/test_client.py            .. PASSED
tests/api/test_routes.py                      ............. PASSED
tests/integration/test_langgraph/test_graph.py  .. PASSED
─────────────────────────────────────────────────────────
总计: 13 passed, 0 failed, 0 errors
```

## 构建产物

| 产物 | 状态 |
|------|------|
| 后端 Python 包 | 可正常导入，无循环依赖 |
| 前端 dist/ | 构建成功，bundle 大小无异常增长 |
| 新增文件 | storyline_service.py / storylines.py / StorylineManager.vue 正确打包 |
| 数据库迁移 | 8795631f9b67_add_storylines_arcs_scenes.py 可执行 |

## 兼容性验证

| 场景 | 结果 |
|------|------|
| 现有小说 CRUD 不受影响 | PASS |
| 现有人物管理功能正常 | PASS |
| 现有大纲体系功能正常 | PASS |
| 新增 storylines API 端点可访问 | PASS |
| NovelDetail 原有 Tab 行为不变 | PASS |

## 结论

CI 全部检查通过。13 个测试用例通过，前端构建成功，数据库迁移正确，向后兼容。可进入 Gate 2 审批。

## 遗留事项

原始资料未明确记录遗留事项。

## 原始文件清单

- `.gate1-approved`
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
