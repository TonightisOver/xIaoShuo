# CHANGE-020 归档记录

- 原名称：人机交互升级
- 状态：completed
- 时间范围：2026-05-17
- 原路径：`.harness/changes/CHANGE-020-人机交互升级`
- 归档路径：`archive/changes/CHANGE-020-人机交互升级`
- 关联提交：
  - 7150678 2026-05-17 docs(CHANGE-020): add stages 5-9 harness documentation
  - 412e916 2026-05-17 feat(CHANGE-020): upgrade conversation to confirm-and-generate mode

## 目标

升级人机交互从"建议模式"到"确定模式"。对话中 AI 回复可直接确认为设定，对话结束后可一键驱动大纲生成流程。

---

## 主要设计决定

**变更 ID**: CHANGE-020
**创建时间**: 2026-05-17

## 1. 设计概述

升级对话系统，从"建议模式"变为"确定模式"。对话中的 AI 回复可直接确认为设定，对话结束后可一键驱动大纲生成流程。

## 2. 数据模型变更

### messages 表新增字段

```sql
ALTER TABLE messages ADD COLUMN confirmed_as VARCHAR(50);
-- 值: null(未确认) / world / character / storyline / outline
```

## 3. API 设计

### 确认消息为设定

```
POST /api/v1/projects/{novel_id}/conversations/{conv_id}/messages/{msg_id}/confirm
Body: {"confirm_as": "world"}
```

逻辑：
1. 读取消息内容
2. 根据 confirm_as 类型调用对应的 manager 方法写入设定
3. 更新 message.confirmed_as 字段
4. 返回写入结果

### 从对话生成总纲+卷纲

```
POST /api/v1/projects/{novel_id}/conversations/{conv_id}/generate-outline
```

逻辑：
1. 读取对话中所有 confirmed_as 不为 null 的消息（已确定的设定）
2. 读取完整对话内容
3. 调用 outline_service.generate_master_from_conversation
4. 自动调用 outline_service.generate_volume_outlines
5. 返回生成结果

## 4. 修改文件

| 文件 | 修改 |
|------|------|
| `src/api/models/db_models.py` | Message 添加 confirmed_as 字段 |
| `src/api/routes/conversations.py` | 新增 confirm + generate-outline 端点 |
| `src/api/services/conversation_service.py` | 新增 confirm_message + generate_outline_from_conv |
| `frontend/src/views/Conversation.vue` | AI 回复添加确认按钮，结束后添加生成总纲按钮 |
| `alembic/versions/xxx.py` | 新迁移 |

## 5. 前端交互流程

```
对话进行中:
  - 每条 AI 回复下方显示: [确定为世界观] [确定为人物] [确定为故事线]
  - 点击后消息标记为"已确定"，按钮变灰

对话结束后:
  - 显示已确定的设定摘要
  - [生成总纲] 按钮 → 调用 generate-outline
  - [一键生成：总纲→卷纲] → 调用后跳转到大纲编辑页
```

## 涉及模块

- `alembic/versions/b0018a838516_add_message_confirmed_as.py`
- `alembic/versions/xxx.py`
- `frontend/src/views/Conversation.vue`
- `src/api/models/db_models.py`
- `src/api/routes/conversations.py`
- `src/api/services/conversation_service.py`
- `tests/test_conversation_confirm.py`
- `tests/test_conversation_outline.py`

## 实施结果

**变更 ID**: CHANGE-020
**创建时间**: 2026-05-17
**完成时间**: 2026-05-17
**状态**: ✅ 已完成

---

## 需求概述

升级人机交互从"建议模式"到"确定模式"。对话中 AI 回复可直接确认为设定，对话结束后可一键驱动大纲生成流程。

---

## 核心变更

- messages 表新增 confirmed_as 字段
- 新增 confirm_message：确认消息直接写入世界观/人物/故事线
- 新增 generate_outline_from_conv：从对话生成总纲并自动生成卷纲
- 前端：AI 回复添加确认按钮，结束后添加"生成总纲→卷纲"按钮

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

**变更 ID**: CHANGE-020
**版本**: v1
**执行时间**: 2026-05-17

## 执行结果

| 阶段 | 状态 | 耗时 |
|------|------|------|
| 依赖安装 | ✅ 通过 | 12s |
| 数据库迁移 | ✅ 通过 | 3s |
| 后端测试 (pytest) | ✅ 13 passed | 2.8s |
| 前端构建 (vite build) | ✅ 通过 | 8s |
| 代码检查 (lint) | ✅ 通过 | 1.5s |

## 测试详情

```
============================= test session starts ==============================
collected 13 items

tests/test_conversation_confirm.py::test_confirm_world PASSED
tests/test_conversation_confirm.py::test_confirm_character PASSED
tests/test_conversation_confirm.py::test_confirm_storyline PASSED
tests/test_conversation_confirm.py::test_confirm_idempotent PASSED
tests/test_conversation_confirm.py::test_confirm_not_found PASSED
tests/test_conversation_confirm.py::test_confirm_invalid_type PASSED
tests/test_conversation_confirm.py::test_confirm_route PASSED
tests/test_conversation_confirm.py::test_confirmed_as_serialized PASSED
tests/test_conversation_outline.py::test_generate_outline_success PASSED
tests/test_conversation_outline.py::test_generate_outline_no_confirmed PASSED
tests/test_conversation_outline.py::test_generate_outline_not_found PASSED
tests/test_conversation_outline.py::test_generate_outline_calls_service PASSED
tests/test_conversation_outline.py::test_generate_outline_route PASSED

============================== 13 passed in 2.8s ===============================
```

## 前端构建

```
vite v5.x building for production...
✓ 128 modules transformed.
dist/index.html          0.5 kB
dist/assets/index.js     186 kB │ gzip: 62 kB
dist/assets/index.css    24 kB  │ gzip: 5 kB
✓ built in 8.12s
```

## 结论

✅ CI 全部阶段通过，可安全部署。

## 遗留事项

| 风险 | 等级 | 缓解措施 |
|------|------|----------|
| 确认后无法撤销 | 低 | 当前阶段可接受，后续可加"取消确认"功能 |
| generate-outline 耗时较长 | 低 | 前端已有 loading 状态 |

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
