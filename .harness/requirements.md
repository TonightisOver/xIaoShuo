# CHANGE-050 需求文档

**日期**: 2026-05-27
**分支**: feature/change-049-refactoring-decouple（在此分支继续）
**优先级**: P1 × 2，P2 × 2

---

## 背景

CHANGE-049 完成了全局架构优化，但遗留了以下工程质量问题：
1. `src/core/context/novel_context.py` 仍直接导入 `src.api.models.db_models`，违反 core 层不依赖 api 层的架构约束，且 Gate 2 验收结论未如实反映此问题。
2. 前端缺乏测试体系，`NovelDetail.vue`（738 行）承载九类数据加载与多项危险操作（生成、删除、清理），完全无自动化覆盖。
3. 三个超大 Vue 文件（ChapterEdit 854 行、NovelDetail 738 行、RelationGraph 669 行）混合了展示、数据请求、危险操作和状态流转，可维护性差。
4. 多个已完成 CHANGE 的资料文件（CHANGE-033~036 目录、story-bible.md、全流程使用指南.html）未提交到仓库。

---

## 需求详情

### FR-1 [P1] 修正 core/context 层级边界违规

**问题**：`src/core/context/novel_context.py` 第 16 行直接导入 `src.api.models.db_models`，违反架构约束"core 层不能依赖 api 层"。

**解决方案**：将 `NovelContextBuilder` 及其三个 dataclass（`GenerationContext`、`RewriteContext`、`BlueprintContext`）迁移到 `src/api/services/novel_context_service.py`。

**迁移后的导入路径**：
- 新文件：`src/api/services/novel_context_service.py`
- 旧包 `src/core/context/` 改为从新位置 re-export，维持向后兼容（调用方无需修改）
- 或直接更新所有调用方 import，删除 `src/core/context/` 包

**调用方清单**（需同步更新 import）：
- `src/api/routes/projects.py`（2 处）
- `src/api/services/blueprint_service.py`
- `src/api/services/long_form_generation_helpers.py`
- `src/api/services/novel_generator.py`
- `src/api/services/rewrite_loop_service.py`

**Gate 2 修正**：在 `.harness/gates/review-gate2.md` 的 CHANGE-049 章节中，补充说明 `core/context` 层级边界问题未被覆盖，并记录 CHANGE-050 将修正此问题。

**验收标准**：
- `grep -r "from src.api" src/core/` 返回空（core 层无 api 层导入）
- 所有现有测试通过（`pytest tests/unit/ -q`）
- `ruff check src/` 无新增 error

---

### FR-2 [P1] 前端引入最小测试体系

**问题**：`frontend/package.json` 无 `test` 命令，`NovelDetail.vue` 承载九类数据加载与多项危险操作（生成、删除、清理），完全无自动化覆盖。

**子需求**：

#### FR-2a 引入 Vitest + @vue/test-utils

- 安装 `vitest@^2.0.0`、`@vue/test-utils@^2.4.0`、`jsdom@^24.0.0`
- 在 `frontend/vite.config.js`（或新建 `vitest.config.js`）中配置 `test.environment: 'jsdom'`
- 在 `package.json` 中添加 `"test": "vitest run"` 和 `"test:watch": "vitest"`

#### FR-2b 抽出统一请求/错误处理 composable

新建 `frontend/src/composables/useApi.js`，提供：
- `apiGet(url)` — 封装 fetch GET，非 2xx 时抛出含 `detail` 的错误
- `apiPost(url, body)` — 封装 fetch POST
- `apiDelete(url)` — 封装 fetch DELETE
- `apiPut(url, body)` — 封装 fetch PUT
- 统一错误处理：替换散落的 `alert()` 为响应式 `errorMsg ref`；危险操作的 `confirm()` 保留但封装为 `useConfirm` 辅助函数

#### FR-2c 为 NovelDetail.vue 补最小测试

新建 `frontend/src/views/__tests__/NovelDetail.spec.js`，覆盖：
1. 项目详情加载（`fetchAll` 成功路径，mock 9 个 fetch 调用，验证 novel/chapters 等 ref 被赋值）
2. 生成任务跳转（`generate()` 成功后 router.push 到 `/task/:id`）
3. 章节删除（`doDeleteUnassigned()` 调用 DELETE API 并从 chapters 列表移除）
4. 清理失败章节（`cleanupFailedChapters()` 调用 DELETE API，验证 confirm 被调用）
5. 导出弹窗（点击导出按钮后 `showExportDialog` 变为 true）
6. 全功能生成冲突处理（`fullGenerate()` 收到 409 时触发 confirm 弹窗）

**验收标准**：
- `cd frontend && npm test` 执行通过，≥6 个测试用例全部 PASS
- `npm run build` 仍然成功

---

### FR-3 [P2] 拆分三个过大页面

**目标**：将展示逻辑、数据请求、危险操作、状态流转分离到 composables 和子组件，每个 Vue 文件控制在 450 行以内。

#### FR-3a 拆分 NovelDetail.vue（738 行）

抽出以下 composables：
- `frontend/src/composables/useNovelData.js` — 封装 `fetchAll`、9 个数据 ref（novel/world/characters/chapters/volumes/conversations/powerSystems/storylinesData/outlineTree）、loading 状态
- `frontend/src/composables/useNovelActions.js` — 封装 generate、fullGenerate、startConversation、handleGenerateVolume、handleGenerateChapters、deleteChapter、cleanupFailedChapters

#### FR-3b 拆分 ChapterEdit.vue（854 行）

抽出以下 composables：
- `frontend/src/composables/useChapterContent.js` — 封装 load、save、regenerate、deleteChapter、content ref、saving/saved 状态
- `frontend/src/composables/useChapterRewrite.js` — 封装 doRewrite、acceptRewrite、rewriteResult、rewriteError、showRewriteModal 状态
- `frontend/src/composables/useChapterVersions.js` — 封装 loadVersions、previewVersion、doRollback、doActivate、versions ref

#### FR-3c 拆分 RelationGraph.vue（669 行）

抽出以下 composables：
- `frontend/src/composables/useRelationGraph.js` — 封装 load、renderTree、relations ref、loading 状态
- `frontend/src/composables/useKnowledgeGraph.js` — 封装 loadThreeLayerGraph、reExtractKG、renderKnowledgeGraph、kgData ref、extracting 状态

**验收标准**：
- 三个 Vue 文件行数均 ≤ 450 行
- `npm run build` 成功
- 现有功能不回归

---

### FR-4 [P2] 提交遗留资料文件

将以下已确认无敏感信息的文件提交到仓库：
- `.harness/changes/CHANGE-033-任务大厅与质量评估/`（目录）
- `.harness/changes/CHANGE-034-story-bible与三层图谱/`（目录）
- `.harness/changes/CHANGE-035-任务进度与图谱UX优化/`（目录）
- `.harness/changes/CHANGE-036-修复章节生成挂起与API调用/`（目录）
- `.harness/wiki/business/story-bible.md`
- `全流程使用指南.html`

**不提交**：`xiaoshuo-*.bundle` 文件（二进制包，体积大，不入库）

**验收标准**：
- `git status` 中上述文件不再显示为 untracked
- `xiaoshuo-*.bundle` 未被 stage

---

## 非功能需求

- 所有 Python 变更通过 `ruff check` 和 `mypy`（现有配置）
- 所有 Python 变更不破坏现有 pytest 测试套件
- 前端变更通过 `npm run build`
- 不引入新的 core → api 反向依赖

## 范围边界

- **不在范围内**：修改数据库 schema、修改 API 接口合约、引入新的后端服务
- **不在范围内**：为 ChapterEdit.vue 和 RelationGraph.vue 补充测试（FR-2 仅覆盖 NovelDetail.vue）
- **不在范围内**：完全消除前端 `alert`/`confirm`（FR-2b 仅封装，不强制替换所有调用点）
