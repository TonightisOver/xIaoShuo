# 小说生成流程

## 工作流阶段

LangGraph 编排的 7 阶段顺序流程：

```
创意扩展 → 世界观构建 → 人物设计 → 大纲生成 → 章节生成 → 质量检查 → 人工审核
```

### 1. 创意扩展 (idea_expansion)

**输入**: 用户创意（10-1000 字）  
**输出**: 扩展后的详细故事概念  
**LLM 调用**: 1 次

### 2. 世界观构建 (world_building)

**输入**: 扩展后的创意  
**输出**: world_setting（背景、地理、文化、规则）  
**LLM 调用**: 1 次

### 3. 人物设计 (character_design)

**输入**: 创意 + 世界观  
**输出**: characters（角色列表）+ relationships（关系图）  
**LLM 调用**: 1 次

### 4. 大纲生成 (outline_generation)

**输入**: 创意 + 世界观 + 人物  
**输出**: outline（总纲）+ chapter_outlines（章节大纲列表）  
**LLM 调用**: 1 次

### 5. 章节生成 (chapter_generation)

**输入**: 章节大纲 + 人物 + 世界观 + 上一章内容  
**输出**: chapters（逐章生成，每章 ~8000 tokens）  
**LLM 调用**: N 次（每章 1 次）  
**进度回调**: 每章完成后推送 chapter_progress 事件

## 质量检查 8 维度评估（CHANGE-033）

`quality_check` 节点使用 AI 对每章进行多维度评分（0.0-1.0）：

| 维度 | 说明 |
|------|------|
| advancement | 主线推进度 |
| conflict | 冲突与悬念度 |
| character_consistency | 角色一致性 |
| world_consistency | 世界观一致性 |
| foreshadowing | 伏笔与回收 |
| pacing | 叙事节奏控制 |
| readability | 表达精炼度 |
| trope_alignment | 网络爽点题材契合度 |

AI 返回 JSON 格式，包含每维度评分、反馈意见和修改建议。overall_score ≥ 0.8 → 通过；< 0.8 → 重新生成。



### 7. 人工审核 (human_review)

**输入**: 完整生成结果  
**输出**: approval_status  
**当前状态**: 占位实现（自动通过）

## 错误处理（CHANGE-036 更新）

- LLM API 失败 → 失败章节打 `generation_failed: True` 标记，内容显示 `[章节生成失败：{error}]`，不再 fallback 硬编码内容
- 单章失败不影响其他章节继续生成（try/except 在 for 循环内逐章捕获）
- 章节生成超时（300s）→ 返回 `[生成超时，请重试]` + `generation_failed: True`
- 连接错误自动重试最多 3 次（识别 `openai.APIConnectionError`）
- 进度回调包含 `successful_chapters` / `failed_chapters` 字段，前端可区分真实生成数

## 进度推送

通过 WebSocket 实时推送：
- `stage_start` — 开始新阶段
- `stage_complete` — 阶段完成（含百分比）
- `chapter_progress` — 逐章进度
- `completed` — 全部完成
- `error` — 失败

## 13 阶段全功能生成（CHANGE-026）

在基础 7 阶段流程完成后，继续执行 6 个附加阶段：

```
基础 7 阶段 → 力量体系 → 大纲持久化 → 故事线 → 人物弧光 → 场景 → 自动对话
```

### 设计原则
- Wrapper 模式：`generate_novel_full_background()` 封装全流程，不修改原始 7 阶段逻辑
- 独立容错：每个附加阶段独立 try-catch，失败不阻断后续步骤

## 章节生成上下文（重要）

章节生成时必须注入完整上下文，否则 LLM 会产出与小说无关的内容：

### LangGraph 流程中的章节生成
`chapter_generation` 节点从 state 中读取 `characters` 和 `world_setting`，正确传入 prompt。

### 独立卷生成（generate_volume_background）
- 从数据库获取人物、世界观、故事线
- 若 volumes 表中无数据，回退到 outlines 表查找
- 上下文以 JSON 格式注入 prompt + 文风指令

### 按范围生成（generate_chapters_background）
- 同样从数据库获取完整上下文
- 与卷生成共享相同的上下文构建逻辑

## 结果持久化

生成完成后，`_persist_to_novel()` 自动将结果拆分存入：
- world_settings 表 ← world_setting
- characters 表 ← characters 列表
- volumes 表 ← volumes 结构
- chapters 表 ← chapters 列表
- novels.status ← "completed"

全功能流程额外持久化：
- power_systems 表 ← 力量体系（generate_power_systems_ai）
- outlines 表（三级） ← 大纲（persist_outlines_from_result）
- storylines 表 ← 故事线
- character_arcs 表 ← 人物弧光
- scenes_table 表 ← 场景
- conversations + messages 表 ← 自动创作总结
