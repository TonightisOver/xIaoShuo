# 人机交互对话系统

## 概述

对话系统让用户与 AI 讨论小说设定和情节，讨论结果可直接"确定"为设定，并驱动大纲生成。

## 核心流程

```
创建对话 → 多轮讨论 → 确定设定 → 结束对话 → 生成总纲→卷纲
```

## 对话中的操作

### 发送消息
- 用户发送消息后，AI 基于小说上下文（世界观/人物）回复
- 上下文包含：世界观 4 维度 + 人物详情（前 5 个）
- 最近 20 轮对话作为 LLM 上下文

### 确定设定（CHANGE-020）
每条 AI 回复可标记为"确定"：
- **确定为世界观** → 直接写入 world_settings
- **确定为人物** → 创建新 character
- **确定为故事线** → 创建新 storyline

确定后消息标记 `confirmed_as` 字段，按钮变灰。

### 结束对话
结束后可执行：
- **应用到设定** — 逐条建议手动应用
- **从对话生成故事线** — LLM 提取故事线结构
- **生成总纲→卷纲** — LLM 整理对话为总纲，自动生成卷纲

## API 端点

```
POST   /projects/{id}/conversations              — 创建对话
GET    /projects/{id}/conversations              — 列表
GET    /projects/{id}/conversations/{conv_id}    — 详情（含消息）
POST   /projects/{id}/conversations/{conv_id}/messages — 发送消息
POST   /projects/{id}/conversations/{conv_id}/conclude — 结束对话
POST   /projects/{id}/conversations/{conv_id}/messages/{msg_id}/confirm — 确定设定
POST   /projects/{id}/conversations/{conv_id}/generate-outline — 生成总纲+卷纲
POST   /projects/{id}/conversations/{conv_id}/apply-suggestion — 应用建议
```

## 数据安全

- send_message 先验证会话存在再插入消息（CHANGE-023）
- **novel_id 隔离（CHANGE-024）**：所有对话操作均按 `conv_id + novel_id` 双键查询，跨小说访问返回 404
  - `get_conversation(conv_id, novel_id)` — WHERE 双键，不可跨小说读取
  - `send_message(conv_id, content, novel_id)` — 传入 novel_id 校验归属
  - `conclude_conversation(conv_id, novel_id)` — 传入 novel_id 校验归属
  - `confirm_message` — JOIN Conversation 三元组校验（msg_id + conv_id + novel_id），防止跨小说误写设定
