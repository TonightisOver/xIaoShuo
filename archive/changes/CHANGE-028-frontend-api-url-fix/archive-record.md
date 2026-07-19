# CHANGE-028 归档记录

- 原名称：frontend-api-url-fix
- 状态：completed
- 时间范围：2026-05-19
- 原路径：`.harness/changes/CHANGE-028-frontend-api-url-fix`
- 归档路径：`archive/changes/CHANGE-028-frontend-api-url-fix`
- 关联提交：
  - 0637259 2026-05-19 feat: improve chapter display and api robustness

## 目标

修复 `frontend/src/views/NovelDetail.vue` 中两条 API URL 前缀错误。

## 主要设计决定

## 修复方案

### 1. 预修复验证（NovelDetail.vue）

文件：`frontend/src/views/NovelDetail.vue`

已由外部预修复，实现阶段需逐行核对：

| 行号 | 当前值（预修复后） | 正确值 | 对应后端路由 | 状态 |
|------|-------------------|--------|-------------|------|
| 342 | `/api/v1/projects/${novelId}/relations` | `/api/v1/projects/${novelId}/relations` | `storylines.py` `GET /{novel_id}/relations` | 待验证 |
| 343 | `/api/v1/projects/${novelId}/outlines` | `/api/v1/projects/${novelId}/outlines` | `outlines.py` `GET /{novel_id}/outlines` | 待验证 |

验证方式：读取文件第 342-343 行，与上表正确值逐字符比对。

---

### 2. 全局 URL 扫描结果

已扫描 `frontend/src/**/*.vue` 中所有 `fetch(...)` 调用，结果如下：

#### 2.1 所有 .vue 文件 fetch URL 汇总

| 文件 | 行号 | URL 模式 | 对应后端路由 | 状态 |
|------|------|----------|-------------|------|
| `NovelDetail.vue` | 335 | `/api/v1/projects/${novelId}` | `projects.py GET /{novel_id}` | 正确 |
| `NovelDetail.vue` | 336 | `/api/v1/projects/${novelId}/world` | `projects.py GET /{novel_id}/world` | 正确 |
| `NovelDetail.vue` | 337 | `/api/v1/projects/${novelId}/characters` | `projects.py GET /{novel_id}/characters` | 正确 |
| `NovelDetail.vue` | 338 | `/api/v1/projects/${novelId}/chapters` | `projects.py GET /{novel_id}/chapters` | 正确 |
| `NovelDetail.vue` | 339 | `/api/v1/projects/${novelId}/conversations` | `projects.py GET /{novel_id}/conversations` | 正确 |
| `NovelDetail.vue` | 340 | `/api/v1/projects/${novelId}/volumes` | `projects.py GET /{novel_id}/volumes` | 正确 |
| `NovelDetail.vue` | 341 | `/api/v1/projects/${novelId}/power-systems` | `projects.py GET /{novel_id}/power-systems` | 正确 |
| `NovelDetail.vue` | 342 | `/api/v1/projects/${novelId}/relations` | `storylines.py GET /{novel_id}/relations` | 预修复，待验证 |
| `NovelDetail.vue` | 343 | `/api/v1/projects/${novelId}/outlines` | `outlines.py GET /{novel_id}/outlines` | 预修复，待验证 |
| `NovelDetail.vue` | 292 | `/api/v1/p

## 涉及模块

- `frontend/src/**/*.vue`
- `frontend/src/views/`
- `frontend/src/views/*.vue`
- `frontend/src/views/NovelDetail.vue`
- `src/api/routes/novels.py`
- `src/api/routes/outlines.py`
- `src/api/routes/projects.py`
- `src/api/routes/storylines.py`

## 实施结果

修复 `frontend/src/views/NovelDetail.vue` 中两条 API URL 前缀错误。

## 测试与验证

用户反馈「故事线关系图谱」页面不显示内容，「大纲」Tab 中的章节数据也不显示。
根因已由外部定位：`frontend/src/views/NovelDetail.vue` 的 `fetchAll()` 函数中，两条 API URL 使用了错误的路径前缀，导致请求 404，数据无法加载。
在本次 Harness 流程启动之前，已有人直接修改了 `NovelDetail.vue`，将这两行 URL 改为正确值。当前文件（第 342-343 行）已显示为：
```
fetch(`/api/v1/projects/${novelId}/relations`)
fetch(`/api/v1/projects/${novelId}/outlines`)
```
实现阶段需要验证该预修复是否正确、完整，并检查项目中是否还有其他同类 URL 错误。
---
1. **关系图谱数据加载**：`NovelDetail.vue` 的 `fetchAll()` 需正确调用 `/api/v1/projects/{novelId}/relations`
2. **大纲树数据加载**：`fetchAll()` 需正确调用 `/api/v1/projects/{novelId}/outlines`
3. **全局 URL 一致性**：项目所有前端 `.vue` 文件中的 fetch URL 必须与后端路由定义一致

## 遗留事项

| 风险 | 说明 |
|------|------|
| 预修复不完整 | 需逐行核对修复后的 URL 与后端路由是否完全匹配 |
| 同类问题遗漏 | 其他 .vue 文件可能存在相同模式的错误 URL |
| 回归风险 | 修改 fetchAll() 可能影响页面其他数据加载逻辑 |

---

## 原始文件清单

- `.gate1-approved`
- `01-需求分析.md`
- `02-技术设计.md`
- `03-编码计划.md`
- `04-编码报告-v1.md`
- `05-代码检查报告-v1.md`
