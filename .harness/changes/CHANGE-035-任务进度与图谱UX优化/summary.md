# CHANGE-035 任务进度与图谱 UX 优化

## 概述
全面重构 StageIndicator 组件为网格卡片布局；TaskDetail 页面 UI 升级；RelationGraph 三层图谱交互优化；修复章节生成节点和质量检查节点的边界问题。

## 变更文件

| 文件 | 变更类型 | 说明 |
|------|---------|------|
| `frontend/src/components/StageIndicator.vue` | 修改 | 从线性步骤条改为网格卡片布局，支持 done/active/failed/pending 四态样式 |
| `frontend/src/views/TaskDetail.vue` | 修改 | 任务详情页 UI 重构，章节进度展示优化，增加失败章节标记显示 |
| `frontend/src/views/RelationGraph.vue` | 修改 | 三层图谱交互优化，节点筛选、层级切换、缩放控制 |
| `frontend/src/App.vue` | 修改 | 全局导航样式调整 |
| `frontend/src/style.css` | 修改 | 补充卡片、徽章、动画样式 |
| `src/api/services/novel_generator.py` | 修改 | 进度事件增加 stage_label 字段 |
| `src/core/langgraph/nodes/chapter_generation.py` | 修改 | 修复边界：空章节大纲时不触发进度回调 |
| `src/core/langgraph/nodes/quality_check.py` | 修改 | 修复 JSON 解析失败时的降级处理 |
| `src/core/langgraph/state.py` | 修改 | 新增 stage_label 字段 |

## 核心实现

### StageIndicator 重构
- 旧版：水平线性步骤条，阶段多时挤压变形
- 新版：`grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5` 响应式网格
- 四态样式：done（绿色）/ active（紫色高亮+ring）/ failed（红色）/ pending（灰色）

### TaskDetail 优化
- 任务 ID 截断显示（前 8 位 + ...）
- 章节进度区分成功/失败数量
- 当前活动阶段描述文本展示

## 关联 Commits
- `0c13127` feat: improve task progress and graph UX
