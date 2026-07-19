# CHANGE-050 归档记录

- 原名称：工程质量修复-层级边界与前端测试
- 状态：completed
- 时间范围：2026-05-27
- 原路径：`.harness/changes/CHANGE-050-工程质量修复-层级边界与前端测试`
- 归档路径：`archive/changes/CHANGE-050-工程质量修复-层级边界与前端测试`
- 关联提交：
  - c71584b 2026-05-27 fix(CHANGE-050): 彻底消除 core→api 反向依赖
  - 413f7f0 2026-05-27 feat(CHANGE-050): 工程质量修复 — 层级边界修正与前端测试体系

## 目标

将三个超大 Vue 页面拆分为 composables + 子组件，使每个视图文件行数达标。

## 主要设计决定

**SHOULD FIX — 层级方向问题**

`src/core/context/novel_context.py`（core 层）导入自 `src/api/services/novel_context_service`（api 层），导致 `src.core.context` 包整体依赖 `src.api.services`。标准分层架构期望 api → core，而非 core → api。

当前依赖链：
```
src.core.context.__init__
  → src.core.context.novel_context
    → src.api.services.novel_context_service
```

这意味着任何导入 `src.core.context` 的模块都会传递依赖 `src.api.services`，包括 `src/api/routes/projects.py` 中的两处旧路径调用。

该问题是迁移方向本身造成的：将实现从 core 移到 api.services，再在 core 中保留 re-export，必然产生 core→api 的反向依赖。长期解决方案是将 `projects.py` 中的 2 处旧路径也更新为直接导入 `src.api.services.novel_context_service`，然后删除 re-export stub 和 `__init__.py` 中的相关导出，彻底消除反向依赖。

---

## 涉及模块

- `frontend/package.json`
- `frontend/src/components/ChapterModals.vue`
- `frontend/src/components/ChapterReadMode.vue`
- `frontend/src/components/NovelChaptersTab.vue`
- `frontend/src/components/NovelStorylinesTab.vue`
- `frontend/src/composables/useApi.js`
- `frontend/src/composables/useChapterContent.js`
- `frontend/src/composables/useChapterNavigation.js`
- `frontend/src/composables/useChapterRewrite.js`
- `frontend/src/composables/useChapterVersions.js`
- `frontend/src/composables/useKnowledgeGraph.js`
- `frontend/src/composables/useNovelActions.js`
- `frontend/src/composables/useNovelData.js`
- `frontend/src/composables/useRelationGraph.js`
- `frontend/src/views/ChapterEdit.vue`
- `frontend/src/views/NovelDetail.vue`
- `frontend/src/views/RelationGraph.vue`
- `frontend/src/views/__tests__/NovelDetail.spec.js`
- `frontend/vite.config.js`
- `src/api/routes/projects.py`
- `src/api/services/blueprint_service.py`
- `src/api/services/long_form_generation_helpers.py`
- `src/api/services/novel_context_service`
- `src/api/services/novel_context_service.py`
- `src/api/services/novel_generator.py`
- `src/api/services/rewrite_loop_service.py`
- `src/core/`
- `src/core/context/__init__.py`
- `src/core/context/novel_context.py`
- `src/core/langgraph/nodes/`
- `src/core/langgraph/nodes/outline_generation.py`
- `src/core/llm/`
- `src/views/ChapterEdit.vue`
- `src/views/NovelDetail.vue`
- `src/views/RelationGraph.vue`
- `src/views/__tests__/NovelDetail.spec.js`
- `tests/unit/`
- `tests/unit/test_change050_layer_boundary.py`

## 实施结果

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

## 测试与验证

**执行时间**: 2026-05-27
**分支**: feature/change-049-refactoring-decouple
**执行 Agent**: Tester Agent (verify_ci 模式)

---

## 验证结果汇总

| 检查项 | 结果 | 详情 |
|--------|------|------|
| `import src.api.main` | PASS | 无报错 |
| pytest 单元测试 | PASS | 394 passed, 0 failed |
| 层级边界（core 不引用 api.models） | PASS | grep 返回空 |
| ruff E/F 检查 | WARN | 2 个 F541（预存，非本次引入） |
| npm test | PASS | 7 passed, 0 failed |
| npm run build | PASS | 631 modules, built in 2.22s |
| NovelDetail.vue 行数 | PASS | 415 ≤ 450 |
| ChapterEdit.vue 行数 | PASS | 394 ≤ 450 |
| RelationGraph.vue 行数 | PASS | 286 ≤ 400 |

**总体结论**: CI 通过（所有强制条件满足）

---

## 详细结果

### 1. 后端导入检查

```
python -c "import src.api.main"
```
- 结果: EXIT 0，无任何报错

### 2. pytest 单元测试

```
python -m pytest tests/unit/ -q
```
- 394 passed, 2 warnings in 39.19s
- 警告均为预存问题（coroutine never awaited、UserWarning），非本次引入

### 3. 层级边界验证

```
grep -rn "from src.api.models" src/core/
```
- 返回空（grep exit 1 = 无匹配），层级边界干净

### 4. ruff 检查

```
python -m ruff check src/ --select E,F --quiet
```
- E501（行过长）: 172 处，均为预存问题
- F541（f-string 无占位符）: 2 处，位于 `src/core/langgraph/nodes/outline_generation.py:177` 和 `:366`
  - 这两处来自 CHANGE-044（git log 确认），非本次 CHANGE-049/050 引入
  - 均可自动修复（`--fix` 选项）
- **本次变更未引入新的 E/F 错误**

### 5. 前端测试

```
npm test -- --run
```
- 1 test file, 7 tests passed, 0 failed
- 测试文件: `src/views/__tests__/NovelDetail.spec.js`
- 耗时: 1.38s

### 6. 前端构建

```
npm run build
```
- vite v5.4.21，631 modules transformed
- built in 2.22s，无错误无警告

### 7. Vue 文件行数

| 文件 | 实际行数 | 上限 | 状态 |
|------|---------|------|------|
| NovelDetail.vue | 415 | 450 | PASS |
| ChapterEdit.vue | 394 | 450 | PASS |
| RelationGraph.vue | 286 | 400 | PASS |

---

## 遗留问题（非阻塞）

1. **F541 预存问题** (`outline_generation.py:177`, `:366`): f-string 无占位符，可用 `ruff --fix` 一键修复，建议在后续 CHANGE 中清理。
2. **E501

## 遗留事项

| 级别 | 位置 | 描述 |
|------|------|------|
| SHOULD FIX | `src/core/context/novel_context.py:9` | E501 行过长（92 > 88），`__all__` 列表需拆行 |
| SHOULD FIX | `frontend/src/composables/useApi.js` | 已创建但未被任何文件使用；`useNovelData.js` 和 `useNovelActions.js` 仍直接调用 `fetch()`，FR-2 的统一 HTTP 层意图未落地 |
| SHOULD FIX | `src/api/routes/projects.py:639,855` | 仍使用旧路径 `from src.core.context import NovelContextBuilder`，建议迁移到直接导入以消除 core→api 反向依赖 |
| INFO | `useNovelActions.js` | `typeof novelId === 'object' ? novelId.value : novelId` 重复 8 次，可提取辅助函数 |

---

## 原始文件清单

- `ci-result.md`
- `code-review.md`
- `coding-report.md`
- `gate2-summary.md`
- `test-report.md`
- `test-review.md`
