# CHANGE-050 任务清单

> 对应需求：`.harness/requirements.md` CHANGE-050
> 日期：2026-05-27

---

## 任务总览

| ID | 任务 | 优先级 | 依赖 | 文件范围 |
|----|------|--------|------|----------|
| T1 | 迁移 NovelContextBuilder 到 api/services 层 | P1 | — | `src/core/context/novel_context.py` → `src/api/services/novel_context_service.py` |
| T2 | 更新所有调用方 import | P1 | T1 | 6 个文件 |
| T3 | 修正 review-gate2.md 验收结论 | P1 | T1 | `.harness/gates/review-gate2.md` |
| T4 | 配置 Vitest 测试环境 | P1 | — | `frontend/package.json`、`frontend/vite.config.js` |
| T5 | 新建 useApi composable | P1 | T4 | `frontend/src/composables/useApi.js` |
| T6 | 编写 NovelDetail.vue 最小测试套件 | P1 | T4, T5 | `frontend/src/views/__tests__/NovelDetail.spec.js` |
| T7 | 拆分 NovelDetail.vue | P2 | T5, T6 | `frontend/src/composables/useNovelData.js`、`useNovelActions.js` |
| T8 | 拆分 ChapterEdit.vue | P2 | T5 | `frontend/src/composables/useChapterContent.js`、`useChapterRewrite.js`、`useChapterVersions.js` |
| T9 | 拆分 RelationGraph.vue | P2 | T5 | `frontend/src/composables/useRelationGraph.js`、`useKnowledgeGraph.js` |
| T10 | 提交遗留资料文件 | P2 | — | `.harness/changes/CHANGE-033~036/`、wiki、html |

---

## 详细任务

### T1 — 迁移 NovelContextBuilder 到 api/services 层

**目标**：消除 `src/core/context/novel_context.py` 对 `src.api.models.db_models` 的直接导入。

**操作步骤**：
1. 新建 `src/api/services/novel_context_service.py`，将 `novel_context.py` 的全部内容（4 个 dataclass + `NovelContextBuilder` 类）复制过来，保持代码不变。
2. 修改 `src/core/context/novel_context.py`：删除原有实现，改为从新位置 re-export：
   ```python
   # 向后兼容 re-export — 实现已迁移到 src/api/services/novel_context_service
   from src.api.services.novel_context_service import (
       BlueprintContext,
       GenerationContext,
       NovelContextBuilder,
       RewriteContext,
   )
   __all__ = ["BlueprintContext", "GenerationContext", "NovelContextBuilder", "RewriteContext"]
   ```
3. `src/core/context/__init__.py` 保持不变（仍从 `novel_context` re-export，链式兼容）。

**验收**：
- `grep -rn "from src.api" src/core/` 返回空
- `python -c "from src.core.context import NovelContextBuilder"` 无报错
- `python -c "from src.api.services.novel_context_service import NovelContextBuilder"` 无报错

---

### T2 — 更新所有调用方 import（可选优化）

**说明**：T1 的 re-export 方案已保证向后兼容，T2 为可选的清理步骤，将调用方 import 路径直接指向新位置，消除间接跳转。

**文件清单**：
1. `src/api/routes/projects.py`（第 639、855 行的 lazy import）
2. `src/api/services/blueprint_service.py`（第 12 行）
3. `src/api/services/long_form_generation_helpers.py`（第 21 行）
4. `src/api/services/novel_generator.py`（第 31 行）
5. `src/api/services/rewrite_loop_service.py`（第 9 行）

**变更**：将 `from src.core.context import NovelContextBuilder` 改为 `from src.api.services.novel_context_service import NovelContextBuilder`（及其他 dataclass）。

**验收**：
- `ruff check src/` 无新增 error
- `pytest tests/unit/ -q` 全部通过

---

### T3 — 修正 review-gate2.md 验收结论

**目标**：在 `.harness/gates/review-gate2.md` 的 CHANGE-049 章节中，如实记录 `core/context` 层级边界问题。

**操作**：在 CHANGE-049 章节的"约束验证"部分，将：
```
- [x] core/llm 和 core/langgraph/nodes 无反向依赖 services 层
```
修改为：
```
- [x] core/llm 和 core/langgraph/nodes 无反向依赖 services 层
- [ ] core/context 层级边界：novel_context.py 仍导入 src.api.models.db_models（遗留问题，由 CHANGE-050/T1 修正）
```

并在"结论"部分追加：
```
**补充说明（2026-05-27）**：Gate 2 审核时未覆盖 core/context 子模块，novel_context.py 存在 core→api 反向依赖，已在 CHANGE-050 中修正。
```

**验收**：文件内容包含上述补充说明。

---

### T4 — 配置 Vitest 测试环境

**目标**：在 `frontend/` 目录下建立可运行的 Vitest 测试环境。

**操作步骤**：
1. 在 `frontend/` 目录执行：
   ```
   npm install --save-dev vitest@^2.0.0 @vue/test-utils@^2.4.0 jsdom@^24.0.0 @vitest/coverage-v8@^2.0.0
   ```
2. 修改 `frontend/vite.config.js`，添加 test 配置块：
   ```js
   import { defineConfig } from 'vite'
   import vue from '@vitejs/plugin-vue'

   export default defineConfig({
     plugins: [vue()],
     test: {
       environment: 'jsdom',
       globals: true,
     },
   })
   ```
3. 修改 `frontend/package.json`，在 `scripts` 中添加：
   ```json
   "test": "vitest run",
   "test:watch": "vitest"
   ```

**验收**：
- `cd frontend && npm test` 可执行（即使无测试文件也不报错，或报"no test files found"而非配置错误）
- `npm run build` 仍然成功

---

### T5 — 新建 useApi composable

**目标**：提供统一的 fetch 封装，替换 NovelDetail.vue 中散落的裸 fetch 调用和 alert 错误处理。

**文件**：`frontend/src/composables/useApi.js`

**接口设计**：
```js
export function useApi() {
  const error = ref(null)

  async function apiGet(url) { ... }        // GET，非 2xx 抛出 { detail }
  async function apiPost(url, body) { ... } // POST with JSON body
  async function apiPut(url, body) { ... }  // PUT with JSON body
  async function apiDelete(url) { ... }     // DELETE

  return { error, apiGet, apiPost, apiPut, apiDelete }
}
```

**错误处理规则**：
- 非 2xx 响应：尝试解析 JSON body 取 `detail` 字段，抛出 `Error(detail || '请求失败')`
- 网络错误：直接 rethrow
- 调用方负责 catch 并设置本地 errorMsg ref（不在 composable 内 alert）

**验收**：
- 文件存在且可被 import
- T6 的测试中可 mock 此 composable

---

### T6 — 编写 NovelDetail.vue 最小测试套件

**目标**：为 NovelDetail.vue 的核心交互路径建立自动化覆盖。

**文件**：`frontend/src/views/__tests__/NovelDetail.spec.js`

**测试用例**（≥6 个）：

1. **项目详情加载**
   - mock `fetch` 返回 9 个成功响应（novel、world、characters、chapters、volumes、conversations、powerSystems、relations、outlines）
   - mount NovelDetail，等待 `fetchAll` 完成
   - 断言 `novel.value` 被赋值，`loading.value` 为 false

2. **生成任务跳转**
   - mock `fetch('/api/v1/projects/:id/generate', POST)` 返回 `{ task_id: 'task-123' }`
   - 调用 `generate()`
   - 断言 `router.push` 被调用，参数为 `/task/task-123`

3. **章节删除（未分配章节）**
   - 预设 `chapters.value = [{ chapter_number: 1, ... }]`
   - mock DELETE 返回 200
   - 调用 `doDeleteUnassigned()`（先设置 `deleteTargetUnassigned`）
   - 断言 chapters 列表中不再包含 chapter_number=1 的项

4. **清理失败章节 — 用户确认**
   - mock `window.confirm` 返回 true
   - mock DELETE 返回 `{ deleted_count: 3 }`
   - 调用 `cleanupFailedChapters()`
   - 断言 confirm 被调用，fetch DELETE 被调用

5. **清理失败章节 — 用户取消**
   - mock `window.confirm` 返回 false
   - 调用 `cleanupFailedChapters()`
   - 断言 fetch 未被调用

6. **导出弹窗**
   - mount NovelDetail（mock fetchAll）
   - 找到导出按钮并触发 click
   - 断言 `showExportDialog.value` 为 true

7. **全功能生成 409 冲突**
   - mock POST 返回 409 `{ detail: '已有正在运行的任务' }`
   - mock `window.alert`
   - 调用 `fullGenerate()`
   - 断言 alert 被调用，包含"已有正在运行"

**验收**：
- `npm test` 输出 ≥6 PASS，0 FAIL
- 测试文件不依赖真实网络或数据库

---

### T7 — 拆分 NovelDetail.vue

**目标**：将 NovelDetail.vue 从 738 行减少到 ≤ 450 行，数据层和操作层抽入 composables。

**新建文件**：

`frontend/src/composables/useNovelData.js`
- 导出：`novel, world, characters, chapters, volumes, conversations, powerSystems, storylinesData, outlineTree, loading, fetchAll`
- 内部使用 `useApi` composable

`frontend/src/composables/useNovelActions.js`
- 导出：`generating, fullGenerating, generate, fullGenerate, startConversation, handleGenerateVolume, handleGenerateChapters, deleteTargetUnassigned, confirmDeleteUnassigned, doDeleteUnassigned, cleanupFailedChapters`
- 接收 `novelId` 和 `chapters` ref 作为参数（或通过 provide/inject）

**修改文件**：`frontend/src/views/NovelDetail.vue`
- `<script setup>` 中替换为 composable 调用
- 保留：computed（statusLabel、statusClass、unassignedChapters）、tabs 定义、onMounted

**验收**：
- `wc -l frontend/src/views/NovelDetail.vue` ≤ 450
- `npm run build` 成功
- `npm test` 仍然通过（T6 的测试需同步更新 mock 路径）

---

### T8 — 拆分 ChapterEdit.vue

**目标**：将 ChapterEdit.vue 从 854 行减少到 ≤ 450 行。

**新建文件**：

`frontend/src/composables/useChapterContent.js`
- 导出：`chapter, content, saving, saved, load, save, regenerate, deleteChapter`
- 接收 `novelId, chapterNumber` 参数

`frontend/src/composables/useChapterRewrite.js`
- 导出：`showRewriteModal, rewriteInstruction, rewriting, rewriteResult, rewriteError, selectionText, selectionStart, selectionEnd, openRewriteModal, closeRewriteModal, doRewrite, acceptRewrite`

`frontend/src/composables/useChapterVersions.js`
- 导出：`versions, showVersionHistory, previewVersionData, loadVersions, previewVersion, doRollback, doActivate`

**修改文件**：`frontend/src/views/ChapterEdit.vue`
- `<script setup>` 中替换为 composable 调用
- 保留：UI 状态（isReadMode、showSettings、fontSize、activeFont、activeTheme）、导航辅助函数（goToChapter、copyContent）

**验收**：
- `wc -l frontend/src/views/ChapterEdit.vue` ≤ 450
- `npm run build` 成功

---

### T9 — 拆分 RelationGraph.vue

**目标**：将 RelationGraph.vue 从 669 行减少到 ≤ 400 行。

**新建文件**：

`frontend/src/composables/useRelationGraph.js`
- 导出：`relations, loading, load, renderTree, transformToTree`
- 接收 `novelId` 参数

`frontend/src/composables/useKnowledgeGraph.js`
- 导出：`kgData, kgLoading, extracting, extractProgress, generatingStorylines, storylineGenError, loadThreeLayerGraph, reExtractKG, generateStorylines, renderKnowledgeGraph, getActiveGraphData`
- 接收 `novelId` 参数

**修改文件**：`frontend/src/views/RelationGraph.vue`
- `<script setup>` 中替换为 composable 调用
- 保留：activeTab、activeSubLayer、showAll、DOM ref（treeContainer、kgContainer）、changeSubLayer、toggleShowAll

**验收**：
- `wc -l frontend/src/views/RelationGraph.vue` ≤ 400
- `npm run build` 成功

---

### T10 — 提交遗留资料文件

**目标**：将 git untracked 的资料文件纳入版本控制。

**操作步骤**：
1. 确认 `.gitignore` 中无规则会排除这些路径（检查 `*.bundle` 规则是否已存在或需添加）
2. 若 `*.bundle` 未在 `.gitignore` 中，添加 `*.bundle` 规则
3. Stage 以下文件/目录：
   - `.harness/changes/CHANGE-033-任务大厅与质量评估/`
   - `.harness/changes/CHANGE-034-story-bible与三层图谱/`
   - `.harness/changes/CHANGE-035-任务进度与图谱UX优化/`
   - `.harness/changes/CHANGE-036-修复章节生成挂起与API调用/`
   - `.harness/wiki/business/story-bible.md`
   - `全流程使用指南.html`
4. 不 stage `xiaoshuo-*.bundle` 文件

**验收**：
- `git status` 中上述文件不再显示为 untracked
- `git status` 中 `xiaoshuo-*.bundle` 仍显示为 untracked 或被 .gitignore 忽略

---

## 执行顺序建议

```
T1 → T2 → T3   （后端层级修正，可独立执行）
T4 → T5 → T6   （前端测试体系，T4 是前置）
T7 → T8 → T9   （页面拆分，依赖 T5；T6 完成后执行 T7 以避免测试失效）
T10             （独立，随时可执行）
```

P1 任务（T1~T6）优先完成，P2 任务（T7~T10）在 P1 验收通过后执行。

---

## 验收检查清单

### P1 验收

- [ ] `grep -rn "from src.api" src/core/` 返回空
- [ ] `pytest tests/unit/ -q` 全部通过
- [ ] `ruff check src/` 无新增 error
- [ ] `review-gate2.md` 包含 core/context 遗留问题说明
- [ ] `cd frontend && npm test` ≥6 PASS，0 FAIL
- [ ] `npm run build` 成功

### P2 验收

- [ ] `wc -l frontend/src/views/NovelDetail.vue` ≤ 450
- [ ] `wc -l frontend/src/views/ChapterEdit.vue` ≤ 450
- [ ] `wc -l frontend/src/views/RelationGraph.vue` ≤ 400
- [ ] `npm run build` 成功（拆分后）
- [ ] `git status` 中 CHANGE-033~036 目录不再为 untracked
