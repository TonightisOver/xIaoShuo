# CHANGE-013 归档记录

- 原名称：人机交互问答生成
- 状态：completed
- 时间范围：2026-05-16
- 原路径：`.harness/changes/CHANGE-013-人机交互问答生成`
- 归档路径：`archive/changes/CHANGE-013-人机交互问答生成`
- 关联提交：
  - ec35bfa 2026-05-16 feat(CHANGE-013): add interactive conversation for novel creation

## 目标

为小说创作平台新增"创作对话"功能，允许用户与 AI 进行多轮对话讨论小说设定和情节，对话结束后自动提取结构化建议。

## 主要设计决定

**变更 ID**: CHANGE-013
**创建时间**: 2026-05-16

## 1. 设计概述

在小说项目中添加"创作对话"功能。用户发送消息后，后端将小说上下文（世界观/人物/已有章节摘要）+ 对话历史拼接为 prompt，调用 DeepSeek API 生成回复。对话结束后可提取结论应用到设定。

## 2. 系统架构

```
前端聊天 UI
    ↓ POST /conversations/{id}/messages
API Route
    ↓
ConversationService
    ├── 读取小说上下文（world_setting/characters/outline）
    ├── 拼接对话历史为 messages 数组
    ├── 调用 DeepSeek API
    ├── 保存 AI 回复到 messages 表
    └── 返回 AI 回复
```

## 3. 数据库设计

```sql
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    novel_id VARCHAR(100) REFERENCES novels(novel_id) ON DELETE CASCADE,
    topic VARCHAR(100) NOT NULL,
    status VARCHAR(20) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    concluded_at TIMESTAMPTZ
);
CREATE INDEX ix_conversations_novel_id ON conversations(novel_id);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX ix_messages_conversation_id ON messages(conversation_id);
```

## 4. Prompt 构建策略

发送消息时，构建如下 prompt：

```
System: 你是一位资深小说创作顾问。当前正在协助用户创作一部{novel_type}小说。

已有设定：
- 世界观：{world_setting_summary}
- 主要人物：{characters_summary}
- 大纲：{outline_summary}

讨论主题：{topic}

请基于以上设定，与用户讨论并提供专业建议。回复简洁有针对性。

[对话历史]
User: ...
Assistant: ...
User: [最新消息]
```

## 5. API 详细设计

### POST /conversations/{id}/messages

**Request**:
```json
{"content": "我想让主角有隐藏身份"}
```

**Response**:
```json
{
  "id": 5,
  "role": "assistant",
  "content": "好的，隐藏身份可以有几种类型...",
  "created_at": "..."
}
```

### POST /conversations/{id}/conclude

**Response**:
```json
{
  "status": "concluded",
  "suggestions": [
    {"type": "character", "content": "主角隐藏身份：远古血脉后裔"},
    {"type": "world", "content": "新增设定：血脉觉醒机制"}

## 涉及模块

- `alembic/versions/a9962b0d350c_add_conversations.py`
- `alembic/versions/xxx.py`
- `frontend/src/`
- `frontend/src/router/index.js`
- `frontend/src/views/Conversation.vue`
- `frontend/src/views/NovelDetail.vue`
- `src/api/`
- `src/api/main.py`
- `src/api/models/db_models.py`
- `src/api/routes/__init__.py`
- `src/api/routes/conversations.py`
- `src/api/services/conversation_service.py`

## 实施结果

为小说创作平台新增"创作对话"功能，允许用户与 AI 进行多轮对话讨论小说设定和情节，对话结束后自动提取结构化建议。

## 测试与验证

| 阶段 | 结果 |
|------|------|
| 代码检查 | 通过，无安全隐患 |
| 专家评审 | 通过，架构合理 |
| 单元测试 | 13/13 通过 |
| 集成测试 | 全部通过 |
| CI 验证 | 全部通过 |
| 部署验证 | 全部通过 |

## 遗留事项

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| LLM 响应慢导致用户等待 | 低 | 前端有 loading 状态提示 |
| Token 消耗过高 | 低 | 20 轮上下文限制 |
| 结论提取格式不稳定 | 低 | JSON 解析失败有兜底处理 |

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
