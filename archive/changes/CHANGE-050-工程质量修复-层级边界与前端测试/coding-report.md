# CHANGE-050 编码报告 — 层级边界修正

**日期**: 2026-05-27
**分支**: feature/change-049-refactoring-decouple

---

## 任务完成情况

### T1：迁移 NovelContextBuilder 到 api/services 层

- 新建 `src/api/services/novel_context_service.py`，内容与原 `novel_context.py` 完全一致
- 将 `src/core/context/novel_context.py` 替换为向后兼容 re-export stub
- `src/core/context/__init__.py` 无需修改，仍从 `novel_context` 导出，链路完整

### T2：更新调用方 import

以下文件的 `from src.core.context import NovelContextBuilder` 已更新为
`from src.api.services.novel_context_service import NovelContextBuilder`：

| 文件 | 状态 |
|------|------|
| `src/api/services/blueprint_service.py` | 已更新 |
| `src/api/services/long_form_generation_helpers.py` | 已更新 |
| `src/api/services/rewrite_loop_service.py` | 已更新 |
| `src/api/services/novel_generator.py` | 已更新（原任务清单遗漏，实际存在该 import，循环依赖修复必须） |
| `src/api/routes/projects.py` | 无相关 import，跳过 |

**注**：`novel_generator.py` 未在原任务 T2 列表中，但其 `from src.core.context import NovelContextBuilder` 导致循环依赖（`api.services.__init__` → `novel_generator` → `core.context` → `api.services.novel_context_service` → `api.services.__init__`），必须一并修正。

### T3：修正 review-gate2.md 验收结论

- 在 CHANGE-049 约束验证部分追加了 `core/context` 层级边界遗留问题条目
- 在 APPROVED 结论后追加了补充说明

---

## 验收自检结果

| 检查项 | 结果 |
|--------|------|
| `from src.core.context import NovelContextBuilder` | re-export OK |
| `from src.api.services.novel_context_service import NovelContextBuilder` | new path OK |
| `ruff check src/ --select E,F --quiet` | 无新增 error（存量 E501 均为改动前已有） |
| `grep -rn "from src.api" src/core/` | 仅剩 re-export 行，无 `from src.api.models` |

---

## 架构约束状态

- core/context 层不再直接依赖 api/models
- 向后兼容 re-export 保证现有调用方无感知迁移
- 循环依赖已消除

---

## T10：提交遗留资料文件（git add）

**执行时间**: 2026-05-27

### 操作记录

1. **检查 `.gitignore`**：原文件无 `*.bundle` 规则，已在末尾追加：
   ```
   # Git bundles
   *.bundle
   ```

2. **执行 git add**（仅指定文件，未使用 `git add .`）：
   - `.harness/changes/CHANGE-033-任务大厅与质量评估/` — staged (new file: summary.md)
   - `.harness/changes/CHANGE-034-story-bible与三层图谱/` — staged (new file: summary.md)
   - `.harness/changes/CHANGE-035-任务进度与图谱UX优化/` — staged (new file: summary.md)
   - `.harness/changes/CHANGE-036-修复章节生成挂起与API调用/` — staged (new file: summary.md)
   - `.harness/wiki/business/story-bible.md` — staged (new file)
   - `全流程使用指南.html` — staged (new file)
   - `.gitignore` — staged (modified，新增 `*.bundle` 规则)

3. **验证结果**：
   - `git status` 确认上述 7 项均显示为 staged（`Changes to be committed`）
   - `xiaoshuo-*.bundle` 文件不再出现在 untracked 列表（已被 `.gitignore` 忽略）
   - 未执行 git commit，staging 完成，等待后续流程统一提交

---

## T4 + T5 + T6：前端测试体系

**执行时间**: 2026-05-27

### T4：配置 Vitest 测试环境

- 安装依赖：`vitest@^2.1.9`、`@vue/test-utils@^2.4.10`、`jsdom@^24.1.3`（已写入 devDependencies）
- `frontend/vite.config.js` 追加 `test: { environment: 'jsdom', globals: true }` 配置块
- `frontend/package.json` 新增 `"test": "vitest run"` 和 `"test:watch": "vitest"` 脚本

### T5：新建 useApi composable

- 新建 `frontend/src/composables/useApi.js`
- 导出 `useApi()` — 封装 `apiGet / apiPost / apiPut / apiDelete`，统一错误处理

### T6：NovelDetail.vue 最小测试套件

- 新建 `frontend/src/views/__tests__/NovelDetail.spec.js`
- 基于 NovelDetail.vue 实际代码结构编写，关键发现：
  - 数据加载函数：`fetchAll()`，并行 9 个 fetch
  - 生成函数：`generate()` / `fullGenerate()`
  - 删除函数：`doDeleteUnassigned()` / `cleanupFailedChapters()`
  - 导出弹窗：`showExportDialog` ref，ExportDialog 组件在 chapters tab 内渲染
  - 409 处理：`fullGenerate` 检查 `detail` 包含 `已有正在运行` 时直接 `alert(msg)`

### 验收自检结果

| 检查项 | 结果 |
|--------|------|
| `npm test` | 7 PASS，0 FAIL |
| `npm run build` | 成功，619 modules transformed |

### 测试用例清单

| # | 用例 | 状态 |
|---|------|------|
| 1 | fetchAll 成功后 novel ref 被赋值 | PASS |
| 2 | generate() 成功后跳转到 /task/:id | PASS |
| 3 | doDeleteUnassigned 调用 DELETE 并从章节列表移除 | PASS |
| 4 | cleanupFailedChapters — confirm=true 时调用 DELETE cleanup | PASS |
| 5 | cleanupFailedChapters — confirm=false 时不调用 DELETE | PASS |
| 6 | 点击导出按钮后 showExportDialog 变为 true | PASS |
| 7 | fullGenerate 收到 409 "已有正在运行" 时调用 alert | PASS |

---

## T7 + T8 + T9：大型 Vue 页面拆分 — Composables 解耦

**执行时间**: 2026-05-27

### 目标

将三个超大 Vue 页面拆分为 composables + 子组件，使每个视图文件行数达标。

### 新建 Composables

| 文件 | 职责 |
|------|------|
| `frontend/src/composables/useNovelData.js` | novel/world/characters/chapters/volumes/conversations/powerSystems/storylinesData/outlineTree 数据加载 |
| `frontend/src/composables/useNovelActions.js` | generate/fullGenerate/startConversation/handleGenerateVolume/handleGenerateChapters/confirmDeleteUnassigned/doDeleteUnassigned/cleanupFailedChapters |
| `frontend/src/composables/useChapterContent.js` | chapter/content 加载、保存、重新生成、删除 |
| `frontend/src/composables/useChapterRewrite.js` | AI 改写弹窗状态与逻辑（openRewriteModal/doRewrite/acceptRewrite） |
| `frontend/src/composables/useChapterVersions.js` | 版本历史加载、预览、回滚、激活 |
| `frontend/src/composables/useChapterNavigation.js` | 章节列表/分卷/上下章导航 |
| `frontend/src/composables/useRelationGraph.js` | 关系树数据加载与 D3 树形渲染 |
| `frontend/src/composables/useKnowledgeGraph.js` | 三层知识图谱数据加载、KG 抽取、故事线生成、D3 力导向图渲染 |

### 新建子组件

| 文件 | 职责 |
|------|------|
| `frontend/src/components/NovelChaptersTab.vue` | NovelDetail 章节 Tab 内容（VolumeList + 未分卷章节 + 弹窗） |
| `frontend/src/components/NovelStorylinesTab.vue` | NovelDetail 故事线 Tab 内容（故事线/弧光/场景展示） |
| `frontend/src/components/ChapterModals.vue` | ChapterEdit AI 改写弹窗 + 版本预览弹窗 |
| `frontend/src/components/ChapterReadMode.vue` | ChapterEdit 沉浸阅读模式全屏面板 |

### 行数验收

| 文件 | 目标 | 实际 | 状态 |
|------|------|------|------|
| `src/views/NovelDetail.vue` | ≤ 450 | 415 | PASS |
| `src/views/ChapterEdit.vue` | ≤ 450 | 394 | PASS |
| `src/views/RelationGraph.vue` | ≤ 400 | 286 | PASS |

### 构建验收

| 检查项 | 结果 |
|--------|------|
| `npm run build` | 成功，631 modules transformed，2.62s |
| 构建产物 | NovelDetail-*.js / ChapterEdit-*.js / RelationGraph-*.js 均正常输出 |

