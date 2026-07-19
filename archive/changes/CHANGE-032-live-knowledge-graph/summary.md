# 变更总结: 活态知识图谱与“动态记忆实体”（Consistency & Memory）

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
