# 变更总结: 画风/文风风格选择

**变更 ID**: CHANGE-010  
**创建时间**: 2026-05-16  
**完成时间**: 2026-05-16  
**状态**: 已完成

---

## 需求概述

创建小说时可选择写作风格（8 种预设文风），影响所有 LLM 生成节点的输出风格。

---

## 技术方案

- novels 表新增 `writing_style VARCHAR(50) DEFAULT '现代白话'`
- 风格定义为代码常量（WRITING_STYLES 字典），每种风格对应一段 prompt 指令
- 风格指令前置拼接到 5 个 LLM 节点的 prompt 中
- 前端按钮组选择，与类型选择 UI 风格一致

---

## 核心变更

### 新增文件
- `alembic/versions/ad3a0f8b7114_add_writing_style.py` — 数据库迁移

### 修改文件
- `src/core/validation.py` — 添加 WRITING_STYLES 常量 + validate_writing_style
- `src/api/models/db_models.py` — Novel 添加 writing_style 字段
- `src/api/models/requests.py` — CreateNovelRequest 添加 writing_style
- `src/core/langgraph/state.py` — NovelState 添加 writing_style
- `src/core/langgraph/nodes/idea_expansion.py` — prompt 注入风格
- `src/core/langgraph/nodes/world_building.py` — prompt 注入风格
- `src/core/langgraph/nodes/character_design.py` — prompt 注入风格
- `src/core/langgraph/nodes/outline_generation.py` — prompt 注入风格
- `src/core/langgraph/nodes/chapter_generation.py` — prompt 注入风格
- `src/api/services/novel_generator.py` — initial_state 传入 writing_style
- `src/api/services/novel_manager.py` — create_novel + _novel_to_dict 支持
- `src/api/routes/projects.py` — API 路由支持 writing_style
- `frontend/src/views/Create.vue` — 风格选择 UI（8 按钮组）

---

## 质量指标

- **单元测试**: 13/13 通过
- **集成测试**: 8/8 通过
- **CI 验证**: 全部通过（ruff + mypy + pytest + vite build）
- **代码检查**: ruff (通过), mypy (通过)

---

## 风险和问题

无阻塞性问题。非阻塞建议：
1. 各节点 prompt 注入逻辑可抽取公共函数减少重复
2. 风格定义可考虑配置化以便后续扩展

---

## 10 阶段完成情况

1. 需求分析 — 8 种预设文风，影响全部生成节点
2. 技术设计 — DB 字段 + State 传递 + Prompt 前置拼接
3. 编码计划 — 14 个文件修改
4. 编码实现 — 完成
5. 代码检查 — ruff/mypy 通过，无问题
6. 专家评审 — 架构合理，通过
7. 单元测试 — 13/13 通过
8. 集成测试 — 8/8 通过，全链路验证
9. CI 验证 — 全部通过
10. 部署验证 — 部署成功，功能正常，向后兼容

---

**更新时间**: 2026-05-16
