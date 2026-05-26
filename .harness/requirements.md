# 需求文档：读者视角模拟 (CHANGE-048)

> 版本：v1.0 · 日期：2026-05-26

---

## 需求概述

模拟不同类型读者（核心粉丝、路人读者、专业评论家、网文老白）阅读章节后的反馈，帮助作者在发布前预判读者反应，发现潜在问题（节奏拖沓、人物OOC、爽点不足等）。

核心思路：用 LLM 扮演不同读者人设，对章节内容进行角色化评价，输出结构化反馈。

## 核心设计原则

- **人设驱动**：每种读者有明确的阅读偏好和评价标准，LLM prompt 中注入人设
- **结构化输出**：反馈结果为 JSON 结构，便于前端展示和历史对比
- **异步执行**：多个读者视角并行调用 LLM，通过 asyncio.gather 加速
- **最小侵入**：新增独立 service + route，不修改现有章节生成逻辑

---

## 功能需求

### FR-1: 读者人设定义

系统内置 4 种读者人设：

| 人设 ID | 名称 | 阅读偏好 | 评价侧重 |
|---------|------|----------|----------|
| `hardcore_fan` | 核心粉丝 | 追更型，关注剧情连贯性和人物成长 | 人物OOC检测、伏笔回收、情感共鸣 |
| `casual_reader` | 路人读者 | 碎片化阅读，注重即时爽感 | 开头吸引力、节奏紧凑度、是否想继续读 |
| `critic` | 专业评论家 | 文学性审美，关注叙事技巧 | 文笔质量、叙事结构、主题深度 |
| `veteran_reader` | 网文老白 | 阅文无数，对套路敏感 | 套路新鲜度、爽点密度、金手指合理性 |

人设数据以代码常量形式存储（`READER_PERSONAS` dict），不入库。后续可扩展为用户自定义人设。

### FR-2: 章节读者模拟执行

对指定章节触发读者模拟：
1. 获取章节内容 + 上下文（前 1-2 章摘要、人物设定、大纲）
2. 对选定的读者人设（默认全部 4 种），并行调用 LLM
3. 每个 LLM 调用注入对应人设 prompt，要求输出结构化 JSON 反馈
4. 解析 LLM 返回，存入数据库

LLM 输出结构（每个人设）：
```json
{
  "engagement_score": 0.0-1.0,
  "would_continue_reading": true/false,
  "emotional_response": "简短情感描述",
  "pacing_assessment": "too_slow|good|too_fast",
  "character_consistency": "consistent|minor_issues|ooc",
  "satisfaction_points": ["爽点1", "爽点2"],
  "pain_points": ["问题1", "问题2"],
  "overall_comment": "一段话总评（以该读者口吻）"
}
```

### FR-3: 模拟结果存储

新增 `reader_simulations` 表存储模拟结果：
- 每次模拟生成一条主记录（simulation）
- 每个人设的反馈作为 JSON 数组存储在主记录中

### FR-4: 历史对比

- 同一章节可多次执行模拟（修改后重新评估）
- 前端可查看历史模拟记录列表
- 支持查看单次模拟的详细结果

### FR-5: 前端交互

- 在章节编辑页面增加"读者模拟"入口按钮
- 点击后弹出模拟面板，可选择人设（默认全选）
- 执行中显示 loading 状态
- 结果以卡片形式展示每个读者的反馈
- 支持查看历史模拟记录

---

## 数据模型

### 新增表：`reader_simulations`

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer PK | 自增主键 |
| novel_id | String(100) FK | 关联小说 |
| chapter_number | Integer | 章节编号 |
| personas_used | JSON | 使用的人设 ID 列表 |
| results | JSON | 各人设反馈结果数组 |
| summary | Text | LLM 生成的综合摘要（可选） |
| status | String(20) | pending/running/completed/failed |
| duration_ms | Integer | 执行耗时 |
| created_at | DateTime | 创建时间 |

索引：`novel_id` + `chapter_number` 联合索引

---

## API 设计

### POST `/api/v1/projects/{novel_id}/chapters/{chapter_number}/reader-simulation`

触发读者模拟。

Request Body:
```json
{
  "personas": ["hardcore_fan", "casual_reader", "critic", "veteran_reader"]
}
```
`personas` 可选，默认全部 4 种。

Response (202):
```json
{
  "simulation_id": 1,
  "status": "running",
  "message": "读者模拟已启动"
}
```

### GET `/api/v1/projects/{novel_id}/chapters/{chapter_number}/reader-simulations`

获取该章节的模拟历史列表。

Response (200):
```json
{
  "simulations": [
    {
      "id": 1,
      "chapter_number": 5,
      "personas_used": ["hardcore_fan", "casual_reader", "critic", "veteran_reader"],
      "status": "completed",
      "duration_ms": 12500,
      "created_at": "2026-05-26T10:00:00Z"
    }
  ]
}
```

### GET `/api/v1/projects/{novel_id}/reader-simulations/{simulation_id}`

获取单次模拟的详细结果。

Response (200):
```json
{
  "id": 1,
  "novel_id": "novel_abc",
  "chapter_number": 5,
  "personas_used": ["hardcore_fan", "casual_reader", "critic", "veteran_reader"],
  "status": "completed",
  "results": [
    {
      "persona_id": "hardcore_fan",
      "persona_name": "核心粉丝",
      "engagement_score": 0.85,
      "would_continue_reading": true,
      "emotional_response": "看到主角终于突破了，有点激动",
      "pacing_assessment": "good",
      "character_consistency": "consistent",
      "satisfaction_points": ["突破情节设计合理", "师徒对话有感情"],
      "pain_points": ["中间修炼描写略长"],
      "overall_comment": "这章整体不错，突破戏份写得有张力..."
    }
  ],
  "summary": "综合来看，本章在核心粉丝和老白群体中反响较好...",
  "duration_ms": 12500,
  "created_at": "2026-05-26T10:00:00Z"
}
```

---

## 前端设计

### 入口位置
章节编辑页面（`ChapterEdit.vue`）右侧工具栏或底部操作区，新增"读者模拟"按钮。

### 模拟面板（ReaderSimPanel.vue）
- 人设选择：4 个 checkbox，默认全选
- 执行按钮："开始模拟"
- Loading 状态：显示进度提示
- 结果展示：每个人设一张卡片，包含评分雷达/数值 + 文字评价
- 历史记录：底部折叠区域，可展开查看历史模拟

### 结果卡片（ReaderFeedbackCard.vue）
- 头部：人设名称 + 头像图标 + engagement 分数
- 中部：情感反应、节奏评价、人物一致性（标签形式）
- 爽点/痛点：绿色/红色列表
- 底部：总评文字（以读者口吻）

---

## 非功能需求

### 性能
- 4 个人设并行调用 LLM，总耗时应 < 30s（单次 LLM 调用 timeout=30s）
- 使用 `asyncio.gather` 并行执行，单个失败不影响其他

### 错误处理
- 单个人设 LLM 调用失败：该人设结果标记为 error，其余正常返回
- 章节内容为空：返回 400 错误
- 模拟执行中重复触发：返回 409 或允许新建（当前设计允许多次执行）

### 上下文窗口管理
- 章节内容 + 上下文（前章摘要、人设）需控制在 LLM 上下文窗口内
- 如章节过长，截取前 8000 字 + 后 2000 字

### 日志
- 使用 structlog 记录模拟触发、LLM 调用、结果解析等关键节点
