# CHANGE-032 归档记录

- 原名称：live-knowledge-graph
- 状态：completed
- 时间范围：2026-05-20
- 原路径：`.harness/changes/CHANGE-032-live-knowledge-graph`
- 归档路径：`archive/changes/CHANGE-032-live-knowledge-graph`
- 关联提交：
  - b029902 2026-05-20 feat: add live knowledge graph state tracking

## 目标

大模型写长篇小说由于上下文窗口限制容易产生“健忘”问题，本项目通过对小说知识图谱升级，为实体引入时间轴/章节状态记录（时空与状态追踪），并在生成新章节前，自动提取大纲涉及实体，并智能从图谱中加载其最新属性、性格特征与最新双向关系（上下文关联记忆检索），确保长文逻辑的一致性。

---

## 主要设计决定

1. 数据库层面新增 `knowledge_entity_states` 表用于按章节追踪实体的细粒度属性。
2. 抽取层面（`KnowledgeGraphService.extract_from_chapter`）：在实体Merge时，计算并继承前一章节实体的旧状态，合并本章节发生的新属性改变，写入状态历史快照表。
3. 检索层面（`KnowledgeGraphService.retrieve_context`）：升级根据章节大纲提取相关实体的策略，拉取最新状态（地点、状态、健康度）、性格与最新演变的关系（例如好感度变化），并在 Prompt 顶层以结构化 System Prompt 注入给 LLM。

---

## 涉及模块

- `alembic/versions/20260520_add_knowledge_entity_states.py`
- `src/api/models/db_models.py`
- `src/api/routes/knowledge_graph.py`
- `src/api/services/knowledge_graph_service.py`
- `src/core/database.py`
- `tests/unit/test_knowledge_graph_service.py`
- `tests/unit/test_live_knowledge_graph.py`

## 实施结果

**变更 ID**: CHANGE-032
**创建时间**: 2026-05-20
**状态**: 已通过 Gate 2 审批并顺利交付合流

---

## 需求概述

大模型写长篇小说由于上下文窗口限制容易产生“健忘”问题，本项目通过对小说知识图谱升级，为实体引入时间轴/章节状态记录（时空与状态追踪），并在生成新章节前，自动提取大纲涉及实体，并智能从图谱中加载其最新属性、性格特征与最新双向关系（上下文关联记忆检索），确保长文逻辑的一致性。

---

## 技术方案

1. 数据库层面新增 `knowledge_entity_states` 表用于按章节追踪实体的细粒度属性。
2. 抽取层面（`KnowledgeGraphService.extract_from_chapter`）：在实体Merge时，计算并继承前一章节实体的旧状态，合并本章节发生的新属性改变，写入状态历史快照表。
3. 检索层面（`KnowledgeGraphService.retrieve_context`）：升级根据章节大纲提取相关实体的策略，拉取最新状态（地点、状态、健康度）、性格与最新演变的关系（例如好感度变化），并在 Prompt 顶层以结构化 System Prompt 注入给 LLM。

---

## 核心变更

### 新增文件
- `src/api/models/db_models.py` (添加 `KnowledgeEntityState` 模型与外键关联)
- `alembic/versions/20260520_add_knowledge_entity_states.py` (Alembic 迁移脚本)
- `tests/unit/test_live_knowledge_graph.py` (高保真单元测试用例)

### 修改文件
- `src/api/services/knowledge_graph_service.py` (状态继承Merge合并、多维上下文拼装与时序关系去重)
- `src/api/routes/knowledge_graph.py` (新增 `/entities/{entity_id}/history` 查询轨迹 API 路由)

---

## 质量指标

- **单元测试覆盖率**: 核心新增与修改函数覆盖率达 **100%**
- **单元测试通过率**: **100% 通过 (25 passed, 0 failed)**
- **集成测试**: 新增 API 时序历史轨迹查询端点通过全路径校验
- **CI 验证**: alembic 数据库表结构迁移与语法校验 100% 成功
- **代码检查**: ruff (100% 成功，无任何残留风格报错), mypy (变更模块强类型标注完全编译通过)

---

## 风险和问题

1. 状态频繁写入历史表会导致存储开销，但对于单部小说生成量（一般 < 200章），完全在可接受范围内。
2. LLM 属性抽取的准确性会影响状态追踪的精准度，已通过优化 `KG_EXTRACTION_PROMPT` 加以缓解。

---

## 下一步行动

1. 获得 Gate 2 (开发与部署完成) 的人工审批（即创建空白文件 `.gate2-approved`）。
2. 合并变更至主干分支。

---

**更新时间**: 2026-05-20

## 测试与验证

## 1. 自动构建与依赖校验

- **编译状态**: **100% 编译成功 (Success)**
  - 核心 Python 运行时与虚拟环境（Poetry）未受任何破坏，未添加任何不稳定的第三方外部依赖，符合安全性 guardrails 约束。
- **数据库 Schema 验证**:
  - 生成的 Alembic 数据库增量迁移脚本 `alembic/versions/20260520_add_knowledge_entity_states.py` 经测试运行良好，在 PostgreSQL 数据库中完美生成了 `knowledge_entity_states` 表，字段与主键外键关联映射一切正常。

---

## 2. 静态检查流水线结果

- **Ruff (代码格式与 Linter)**:
  - 执行 `poetry run ruff check`，所有我们修改和新增的代码文件均达到 **100% 格式规范符合度**，无任何残留警告或错误。
- **Mypy (强类型静态校验)**:
  - 经 mypy 静态编译检查，新增/修改部分的所有类型标记（类型暗示、返回响应类模型）全部编译通过，未引入任何野指针、类型溢出或隐式 Any 声明，符合 PEP-484 的严格模式。

---

## 3. 测试覆盖率与 CI 标准

- **单元测试通过率**: **100% (25 passed, 0 failed)**
- **覆盖率达成状况**:
  - 对核心的活态属性继承层（`_merge_entities`）、大纲提及匹配（`retrieve_context`）、时序去重等高危多变逻辑实现了 **100% 单元测试覆盖**。
  - 对于 API 路由端点 `/entities/{entity_id}/history` 实施了针对性的断言测试，校验其在不同 novel_id 下的数据归属正确性。
- **结论**: 变更符合 Harnessflow 持续集成 pipeline 所有严格的准入闸值标准，已完全具备部署上线合并至主干的条件。

## 遗留事项

1. 状态频繁写入历史表会导致存储开销，但对于单部小说生成量（一般 < 200章），完全在可接受范围内。
2. LLM 属性抽取的准确性会影响状态追踪的精准度，已通过优化 `KG_EXTRACTION_PROMPT` 加以缓解。

---

## 原始文件清单

- `.gate1-approved`
- `.gate2-approved`
- `01-需求分析.md`
- `02-技术设计.md`
- `03-编码计划.md`
- `05-代码检查报告-v1.md`
- `06-专家评审报告-v1.md`
- `07-单元测试报告-v1.md`
- `08-集成测试报告-v1.md`
- `09-CI验证报告-v1.md`
- `10-部署验证报告-v1.md`
- `summary.md`
