# CHANGE-021 归档记录

- 原名称：章节管理与UI优化
- 状态：completed
- 时间范围：2026-05-17
- 原路径：`.harness/changes/CHANGE-021-章节管理与UI优化`
- 归档路径：`archive/changes/CHANGE-021-章节管理与UI优化`
- 关联提交：
  - 5e8121e 2026-05-17 feat(CHANGE-021): chapter management, AI storyline generation, UI improvements

## 目标

修复章节大纲分组Bug，新增章节管理操作按钮，新增故事线AI生成功能，优化UI交互动效。

## 主要设计决定

**变更 ID**: CHANGE-021
**创建时间**: 2026-05-17

## 1. 章节管理修复

### ChapterEdit.vue 添加操作按钮

```
┌─────────────────────────────────────────┐
│ 第3章：初露锋芒          [重新生成] [删除] [保存] │
│ 5000字                                   │
├─────────────────────────────────────────┤
│                                         │
│ [章节内容编辑区]                          │
│                                         │
└─────────────────────────────────────────┘
```

- "重新生成"：调用 POST /generate-chapters {chapter_start: N, chapter_end: N}
- "删除"：调用 DELETE /chapters/{num}，确认后跳回详情页

### 章节列表添加操作

NovelDetail 章节 Tab 中每章添加删除图标（×）。

### OutlineEditor 添加生成入口

每卷章纲下方添加"生成本卷章节"按钮：
- 调用 POST /generate-volume {volume_number: N}
- 跳转到任务详情页查看进度

## 2. UI 优化方案

### 2.1 书架卡片渐变

按小说类型分配渐变色：
```css
玄幻: from-indigo-500/10 to-purple-500/10
仙侠: from-cyan-500/10 to-blue-500/10
都市: from-amber-500/10 to-orange-500/10
科幻: from-emerald-500/10 to-teal-500/10
历史: from-yellow-500/10 to-red-500/10
武侠: from-red-500/10 to-rose-500/10
言情: from-pink-500/10 to-fuchsia-500/10
悬疑: from-gray-500/10 to-slate-500/10
```

### 2.2 小说详情页 Banner

顶部添加渐变 banner 区域，显示标题、类型、字数、状态。

### 2.3 对话气泡优化

- AI 消息：左侧添加机器人图标（SVG）
- 用户消息：右侧添加用户图标
- 气泡添加微阴影

### 2.4 全局动效

- 按钮 hover: scale(1.02) + shadow 过渡
- 卡片 hover: translateY(-2px) + shadow-lg
- Tab 下划线: transition-all duration-300
- 进度条: 添加 shimmer 动画

## 3. 修改文件

| 文件 | 修改 |
|------|------|
| `frontend/src/views/ChapterEdit.vue` | 添加"重新生成"+"删除"按钮 |
| `frontend/src/views/NovelDetail.vue` | 章节列表添加删除图标 |
| `frontend/src/views/OutlineEditor.vue` | 卷章纲下添加"生成章节"按钮 |
| `frontend/src/views/Home.vue` | 卡片渐变背景 |
| `frontend/src/views/Conversation.vue` | 气泡样式优化 |
| `frontend/src/style.css` | 全局动效、渐变、阴影优化 |
| `frontend/src/App.vue` | header 微调 |

## 涉及模块

- `frontend/src/App.vue`
- `frontend/src/style.css`
- `frontend/src/views/ChapterEdit.vue`
- `frontend/src/views/Conversation.vue`
- `frontend/src/views/Home.vue`
- `frontend/src/views/NovelDetail.vue`
- `frontend/src/views/OutlineEditor.vue`
- `frontend/src/views/StorylineManager.vue`
- `src/api/routes/storylines.py`
- `src/api/services/storyline_service.py`

## 实施结果

修复章节大纲分组Bug，新增章节管理操作按钮，新增故事线AI生成功能，优化UI交互动效。

## 测试与验证

| 阶段 | 状态 |
|------|------|
| 代码检查 | PASS |
| 专家评审 | PASS |
| 单元测试 (13/13) | PASS |
| 集成测试 | PASS |
| CI验证 | PASS |
| 部署验证 | PASS |

## 遗留事项

### 问题 1: 删除章节不可用 + 无法重新生成单章
**现象**: 前端没有删除章节按钮，也没有"重新生成本章"按钮
**修复**:
- 章节编辑页添加"删除本章"按钮
- 章节编辑页添加"重新生成本章"按钮（调用 generate-chapters API，range=当前章）
- 章节列表中每章添加删除图标

### 问题 2: 大纲/卷纲/章纲生成后应能直接生成章节
**现象**: 大纲编辑器中生成了章纲后，没有"开始生成章节"的入口
**修复**:
- OutlineEditor 中每卷的章纲生成后，显示"生成本卷章节"按钮
- 点击后调用 POST /projects/{id}/generate-volume
- 总纲确认后显示"一键生成所有章节"按钮

### 问题 3: UI 设计太素
**现象**: 整体界面过于简洁，缺乏视觉层次和品质感
**修复**:
- 书架页：卡片添加渐变背景色（按类型区分）
- 小说详情页：添加顶部 banner/封面区域
- 章节编辑器：添加工具栏（字数统计、保存状态）
- 对话页面：气泡样式优化，添加头像图标
- 全局：按钮添加微动效，卡片添加悬浮阴影过渡
- 进度条：添加动画效果
- Tab 切换：添加下划线动画

### 问题 4: 故事线管理内容太死板
**现象**: 故事线/弧光/场景全靠手动输入，没有 LLM 辅助
**修复**:
- 添加故事线时可输入简单描述，LLM 自动补全（名称/类型/关键事件）
- 人物弧光基于已有人物+大纲，LLM 自动生成阶段轨迹
- 场景基于世界观+大纲，LLM 自动生成
- 新增 API: POST /projects/{id}/storylines/generate-ai
- 新增 API: POST /projects/{id}/character-arcs/generate-ai
- 新增 API: POST /projects/{id}/scenes/generate-ai
- 前端 StorylineManager 添加"AI 生成"按钮

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
