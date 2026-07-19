# CHANGE-023 归档记录

- 原名称：数据隔离与健壮性修复
- 状态：completed
- 时间范围：2026-05-17
- 原路径：`.harness/changes/CHANGE-023-数据隔离与健壮性修复`
- 归档路径：`archive/changes/CHANGE-023-数据隔离与健壮性修复`
- 关联提交：
  - f5e8c3e 2026-05-17 fix(CHANGE-023): data isolation, robustness, and lint fixes

## 目标

修复 Codex Review 发现的 P1 数据隔离缺陷和健壮性问题，防止跨小说越权操作和异常状态。

## 主要设计决定

### 数据隔离修复
所有 service 方法的 update/delete 改为 WHERE id = ? AND novel_id = ?

### 错误处理修复
- send_message: 先查会话再插入
- AI 生成: 先检查 novel 存在
- 前端: AI 生成按钮添加 try/finally

### 代码质量
- ruff --fix 自动修复
- 关键函数补类型注解

## 涉及模块

- 未在原始文档中识别出明确模块路径

## 实施结果

| # | 文件 | 状态 | 说明 |
|---|------|------|------|
| 1 | storyline_service.py | ✅ 完成 | storyline/arc/scene 的 update/delete 增加 novel_id 校验 |
| 2 | storylines.py | ✅ 完成 | 路由层提取 novel_id 并传递给 service |
| 3 | conversation_service.py | ✅ 完成 | send_message 先验证会话存在再插入消息 |
| 4 | storyline_service.py | ✅ 完成 | AI 生成方法增加 novel 存在性检查，不存在 raise ValueError |
| 5 | StorylineManager.vue | ✅ 完成 | AI 按钮操作用 try/finally 包裹 |
| 6 | 多文件 | ✅ 完成 | ruff --fix 修复 21 处 import 问题 |

## 测试与验证

- 13 个测试全部通过
- 前端构建成功
- ruff 检查通过
- 无回归问题

## 遗留事项

### P1-1: 跨小说数据隔离不足
所有子资源接口 URL 带 novel_id，但服务层只按自增 id 查数据，不校验资源是否属于该小说。

**影响范围**:
- conversations: get_conversation(conv_id) 不校验 novel_id
- confirm_message: 只按 msg_id 查消息
- storylines: update/delete 只按 id
- character_arcs: update/delete 只按 id
- scenes: update/delete 只按 id
- power_systems: update/delete 只按 id

### P1-2: send_message 先插入再验证
conversation_service.send_message() 先创建 Message 再查会话，无效 conv_id 会 500。

### P1-3: AI 生成接口缺存在性保护
storyline_service 的 AI 生成方法中 novel 可能为 None，直接 .get() 会 500。

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
