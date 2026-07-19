# CHANGE-035 归档记录

- 原名称：任务进度与图谱UX优化
- 状态：archived-completed
- 时间范围：2026-05-27
- 原路径：`.harness/changes/CHANGE-035-任务进度与图谱UX优化`
- 归档路径：`archive/changes/CHANGE-035-任务进度与图谱UX优化`
- 关联提交：
  - 413f7f0 2026-05-27 feat(CHANGE-050): 工程质量修复 — 层级边界修正与前端测试体系

## 目标

全面重构 StageIndicator 组件为网格卡片布局；TaskDetail 页面 UI 升级；RelationGraph 三层图谱交互优化；修复章节生成节点和质量检查节点的边界问题。

## 主要设计决定

全面重构 StageIndicator 组件为网格卡片布局；TaskDetail 页面 UI 升级；RelationGraph 三层图谱交互优化；修复章节生成节点和质量检查节点的边界问题。
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

## 涉及模块

- `frontend/src/App.vue`
- `frontend/src/components/StageIndicator.vue`
- `frontend/src/style.css`
- `frontend/src/views/RelationGraph.vue`
- `frontend/src/views/TaskDetail.vue`
- `src/api/services/novel_generator.py`
- `src/core/langgraph/nodes/chapter_generation.py`
- `src/core/langgraph/nodes/quality_check.py`
- `src/core/langgraph/state.py`

## 实施结果

全面重构 StageIndicator 组件为网格卡片布局；TaskDetail 页面 UI 升级；RelationGraph 三层图谱交互优化；修复章节生成节点和质量检查节点的边界问题。
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

## 测试与验证

全面重构 StageIndicator 组件为网格卡片布局；TaskDetail 页面 UI 升级；RelationGraph 三层图谱交互优化；修复章节生成节点和质量检查节点的边界问题。
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

## 遗留事项

原始资料未明确记录遗留事项。

## 原始文件清单

- `summary.md`
