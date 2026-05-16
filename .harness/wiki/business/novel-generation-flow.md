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

### 6. 质量检查 (quality_check)

**输入**: 生成的章节内容  
**输出**: quality_scores（各维度评分）  
**条件路由**: 分数 ≥ 0.8 → 人工审核；< 0.8 → 重新生成

### 7. 人工审核 (human_review)

**输入**: 完整生成结果  
**输出**: approval_status  
**当前状态**: 占位实现（自动通过）

## 错误处理

每个节点都有 fallback 机制：
- LLM API 失败 → 使用预设的 mock 数据继续流程
- 确保流程不会因单次 API 失败而中断

## 进度推送

通过 WebSocket 实时推送：
- `stage_start` — 开始新阶段
- `stage_complete` — 阶段完成（含百分比）
- `chapter_progress` — 逐章进度
- `completed` — 全部完成
- `error` — 失败

## 结果持久化

生成完成后，`_persist_to_novel()` 自动将结果拆分存入：
- world_settings 表 ← world_setting
- characters 表 ← characters 列表
- chapters 表 ← chapters 列表
- novels.status ← "completed"
