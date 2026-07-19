# 变更总结: 数据隔离与健壮性修复

**变更 ID**: CHANGE-023  
**状态**: 完成  
**日期**: 2026-05-17

## 概述

修复 Codex Review 发现的 P1 数据隔离缺陷和健壮性问题，防止跨小说越权操作和异常状态。

## 修复内容

| # | 级别 | 问题 | 修复方式 |
|---|------|------|----------|
| 1 | P1 | 子资源 update/delete 不校验 novel_id | WHERE 追加 novel_id 条件 |
| 2 | P1 | send_message 先插入再验证 | 调整为先验证会话再插入 |
| 3 | P1 | AI 生成 novel 为 None 时 500 | 增加存在性检查，raise ValueError |
| 4 | P2 | 前端 AI 按钮 loading 卡死 | try/finally 包裹 |
| 5 | P2 | ruff 21 处 import 问题 | ruff --fix 自动修复 |

## 修改文件

- conversation_service.py
- storyline_service.py
- storylines.py (routes)
- StorylineManager.vue
- 多文件 ruff 自动修复

## 验证结果

- 13 个测试全部通过
- 前端构建成功
- ruff 检查通过
- 无回归问题
