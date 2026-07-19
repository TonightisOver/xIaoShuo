# 变更总结: 自定义文风（LLM 生成）

**变更 ID**: CHANGE-014  
**创建时间**: 2026-05-16  
**完成时间**: 2026-05-16  
**状态**: ✅ 已完成

---

## 需求概述

在 CHANGE-010 的 8 种预设文风基础上，添加"自定义"选项。用户输入自然语言描述（如"江南的文风，带一点灰色幽默"），通过 LLM 生成具体的风格指令，注入到生成 prompt 中。

---

## 技术方案

- 新增 POST /api/v1/style/generate API，调用 LLM 将用户描述转化为风格指令
- novels 表新增 custom_style_description 和 writing_style_prompt 字段
- 新增 get_style_instruction() 统一风格获取逻辑（预设/自定义）
- 5 个 LLM 节点统一改用 get_style_instruction
- 前端选择"自定义"后展开输入框 + 生成按钮 + 可编辑预览

---

## 核心变更

### 新增文件
- `src/api/routes/style.py` — 风格生成 API
- `alembic/versions/0702fe33fe6c_add_custom_style_fields.py` — 数据库迁移

### 修改文件
- `src/core/validation.py` — 添加 get_style_instruction，validate_writing_style 支持"自定义"
- `src/api/models/db_models.py` — Novel 添加 2 个字段
- `src/api/models/requests.py` — CreateNovelRequest 添加 writing_style_prompt
- `src/core/langgraph/state.py` — 添加 writing_style_prompt
- `src/core/langgraph/nodes/*.py` — 5 个节点改用 get_style_instruction
- `src/api/services/novel_generator.py` — initial_state 传入 writing_style_prompt
- `src/api/services/novel_manager.py` — create_novel + _novel_to_dict 支持新字段
- `src/api/routes/projects.py` — Request 模型 + generate 传递
- `frontend/src/views/Create.vue` — 自定义 UI

---

## 质量指标

- **测试**: 13 个通过
- **前端构建**: 成功
- **数据库迁移**: 已应用
- **向后兼容**: 预设风格不受影响

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
