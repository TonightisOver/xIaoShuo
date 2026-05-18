# 大纲体系

## 概述

三级大纲结构：总纲 → 卷纲 → 章纲。支持 LLM 自动生成和手动编辑，支持从人机交互对话中提取。

## 三级结构

```
总纲 (master)
├── 核心前提 (premise)
├── 主要冲突 (main_conflict)
├── 情节线 (plot_arcs)
├── 结局走向 (ending)
└── 主题 (themes)

卷纲 (volume)
├── 卷标题 (title)
├── 概要 (summary)
├── 阶段目标 (goal)
├── 本卷高潮 (climax)
└── 章节列表 (chapters)

章纲 (chapter)
├── 章标题 (title)
├── 场景列表 (scenes: [{location, characters, event}])
├── 转折点 (turning_point)
├── 情感节奏 (emotional_beat)
└── 字数目标 (word_target)
```

## 生成流程

```
人机对话 → 确定总纲 → LLM 生成卷纲 → LLM 生成章纲 → 生成章节内容
```

### 自动分卷逻辑
- 10 万字 → 2-3 卷
- 30 万字 → 5-8 卷
- 50 万字+ → 8-15 卷

## API 端点

```
GET    /projects/{id}/outlines              — 获取完整树形大纲
GET    /projects/{id}/outlines/master       — 获取总纲
PUT    /projects/{id}/outlines/master       — 编辑总纲
POST   /projects/{id}/outlines/generate-volumes — 基于总纲生成卷纲
POST   /projects/{id}/outlines/generate-chapters/{vol} — 基于卷纲生成章纲
PUT    /projects/{id}/outlines/volume/{num} — 编辑卷纲
PUT    /projects/{id}/outlines/chapter/{num} — 编辑章纲
POST   /projects/{id}/outlines/from-conversation/{conv_id} — 从对话生成总纲
```

## 与生成的关系

- 大纲编辑器中每卷有"生成章纲"按钮 → 调用 `POST /outlines/generate-chapters/{vol}` 生成章纲到 outlines 表
- 大纲编辑器中每卷有"生成本卷章节"按钮 → 调用 `POST /projects/{id}/generate-volume` 生成章节内容到 chapters 表
- 章节生成时使用对应章纲作为 prompt 输入，同时注入人物/世界观/故事线上下文
- 生成完成后章节存入 chapters 表

### 跨表 Fallback（CHANGE-026 v2）

卷纲存在两个表中：
- `volumes` 表 — LangGraph 流程生成（outline JSONB 字段含 chapters）
- `outlines` 表 — OutlineEditor 手动/LLM 生成（level="volume"）

"生成本卷章节"按钮调用 `generate_volume_background()`，该函数按以下优先级查找：
1. 先查 `volumes` 表（`novel_manager.get_volume()`）
2. 若不存在，回退到 `outlines` 表（`outline_service.get_volume_outlines()` + `get_chapter_outlines()`）
3. 两表都没有则报 404

此修复解决了"只有第一卷能生成本卷章节，第二卷第三卷不行"的问题。
