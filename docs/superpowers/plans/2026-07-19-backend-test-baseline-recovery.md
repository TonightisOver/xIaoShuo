# Backend Test Baseline Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 消除 15 个存量后端单元测试失败，并通过依赖注入恢复 `src/core` 不依赖 `src.api` 的层级边界。

**Architecture:** 过期测试直接对齐当前定义模块、参数对象、激活语义和 ORM 默认值；质量节点只消费 LangGraph `configurable` 中的回调/服务，API 编排层负责初始执行与 resume 的具体注入。除依赖来源外不改变业务行为。

**Tech Stack:** Python 3.11、pytest、unittest.mock、LangGraph RunnableConfig、Poetry、Ruff、Vue 3/Vitest/Vite

---

## 执行约束

- 不执行 `git add`、`git commit`、`git push`。
- 不使用子 Agent，在当前会话内逐组执行并验证。
- 不修改安全、认证、密钥、管理员或部署配置。
- 不触碰 `.claude/worktrees/*`、`archive/` 原始归档内容和无关工作区改动。
- 不连接真实数据库；数据库集成验证保持独立待办。

## File Structure

**Create:**

- `docs/superpowers/specs/2026-07-19-backend-test-baseline-recovery-design.md` — 根因、范围和依赖注入设计。
- `docs/superpowers/plans/2026-07-19-backend-test-baseline-recovery.md` — 本实施计划。

**Modify tests:**

- `tests/unit/test_novel_generator_auto_calc.py` — patch 长篇函数真实定义模块。
- `tests/unit/test_novel_generator_outline_persist.py` — patch 长篇函数真实定义模块。
- `tests/unit/test_change037_chapter_editor.py` — 激活版本测试显式传 `is_active=True`。
- `tests/unit/test_change038_dedup_and_timeout.py` — 使用 `ChapterGenContext`。
- `tests/unit/test_change049_refactoring.py` — 章节 Mock 的 `state_delta=None`。
- `tests/unit/test_novel_context_service.py` — helper 生成真实默认 `state_delta=None`。
- `tests/unit/test_langgraph/test_nodes.py` — 验证空章节 `unverified` 语义。
- `tests/unit/test_change034_quality_eval.py` — 验证 `rewrite_service` 注入透传。
- `tests/unit/test_novel_generator_supplement.py` — 锁定初始 pipeline 与 resume 的 API 注入配置。

**Modify production:**

- `src/core/langgraph/nodes/quality_check.py` — 移除 API import，仅消费注入依赖。
- `src/api/services/novel_generator.py` — 初始 pipeline 和 resume 注入持久化及改写服务。

### Task 1: Capture the red baseline

**Files:** No changes.

- [x] **Step 1: Reproduce the 13 contract failures**

Run:

```bash
poetry run pytest tests/unit/test_novel_generator_auto_calc.py tests/unit/test_novel_generator_outline_persist.py tests/unit/test_change037_chapter_editor.py tests/unit/test_change038_dedup_and_timeout.py tests/unit/test_change049_refactoring.py tests/unit/test_novel_context_service.py tests/unit/test_langgraph/test_nodes.py -q
```

Expected: 13 failures matching patch path, `is_active`, `ChapterGenContext`, `state_delta` and empty-quality assertions.

- [x] **Step 2: Reproduce the 2 layer-boundary failures**

Run:

```bash
poetry run pytest tests/unit/test_change050_layer_boundary.py::TestLayerBoundary::test_core_has_no_api_imports tests/unit/test_change050_layer_boundary.py::TestLayerBoundary::test_core_langgraph_nodes_do_not_import_api_services -q
```

Expected: 2 failures naming the two imports in `quality_check.py`.

### Task 2: Align long-form test patch namespaces

**Files:**

- Modify: `tests/unit/test_novel_generator_auto_calc.py`
- Modify: `tests/unit/test_novel_generator_outline_persist.py`

- [x] **Step 1: Replace long-form collaborator patch targets**

For the seven collaborators in both files, use the defining namespace:

```python
patch("src.api.services.long_form_generation_helpers.get_task_manager")
patch("src.api.services.long_form_generation_helpers.get_long_form_progress_service")
patch("src.api.services.long_form_generation_helpers.generate_master_outline", ...)
patch("src.api.services.long_form_generation_helpers.generate_volume_outline", ...)
patch("src.api.services.long_form_generation_helpers.generate_volume_chapters", ...)
patch("src.api.services.long_form_generation_helpers.generate_volume_quality_report", ...)
patch("src.api.services.long_form_generation_helpers._emit_progress", ...)
```

Keep these lazy-import patches unchanged:

```python
patch("src.api.services.outline_service.get_outline_service", ...)
patch("src.api.services.novel_manager.get_novel_manager", ...)
```

- [x] **Step 2: Run the eight long-form tests**

Run:

```bash
poetry run pytest tests/unit/test_novel_generator_auto_calc.py tests/unit/test_novel_generator_outline_persist.py -q
```

Expected: all tests pass without external LLM or database access.

### Task 3: Align chapter and context test contracts

**Files:**

- Modify: `tests/unit/test_change037_chapter_editor.py`
- Modify: `tests/unit/test_change038_dedup_and_timeout.py`
- Modify: `tests/unit/test_change049_refactoring.py`
- Modify: `tests/unit/test_novel_context_service.py`
- Modify: `tests/unit/test_langgraph/test_nodes.py`

- [x] **Step 1: Activate the version that is expected to update Chapter**

Change the failing call to:

```python
await NovelManager().create_chapter_version(
    novel_id="novel-001",
    chapter_number=1,
    content=content,
    source="manual",
    is_active=True,
)
```

- [x] **Step 2: Use ChapterGenContext in the timeout test**

Import and call the current API:

```python
from src.core.llm.chapter_generator import ChapterGenContext, generate_single_chapter

ctx = ChapterGenContext(
    client=MagicMock(),
    chapter_outline={"chapter": 1, "title": "Test"},
    previous_chapter="",
    characters_json="[]",
    world_setting_json="{}",
)
result = await asyncio.wait_for(generate_single_chapter(ctx), timeout=5)
```

- [x] **Step 3: Model real ORM state_delta defaults**

In `test_change049_refactoring.py` set both chapter mocks explicitly:

```python
mock_prev_ch.state_delta = None
mock_next_ch.state_delta = None
```

In `test_novel_context_service.py`, extend `_chapter`:

```python
ch.state_delta = kwargs.get("state_delta", None)
```

- [x] **Step 4: Assert unverified semantics for an empty chapter list**

Replace the positive-score assertion with:

```python
assert result["quality_scores"]["overall"] is None
assert result["quality_scores"]["status"] == "unverified"
assert result["quality_scores"]["consistency_blocked"] is False
```

- [x] **Step 5: Run the five affected test groups**

Run:

```bash
poetry run pytest tests/unit/test_change037_chapter_editor.py tests/unit/test_change060_is_active_semantics.py tests/unit/test_change038_dedup_and_timeout.py tests/unit/test_change049_refactoring.py tests/unit/test_novel_context_service.py tests/unit/test_langgraph/test_nodes.py -q
```

Expected: all tests pass; inactive candidate semantics remain covered.

### Task 4: Add the quality dependency-injection regression test

**Files:**

- Modify: `tests/unit/test_change034_quality_eval.py`

- [x] **Step 1: Make the happy-path test require rewrite-service passthrough**

Create a sentinel and pass it through config:

```python
rewrite_service = object()
config = {"configurable": {"rewrite_service": rewrite_service}}
updated_state = await node(state, config)
```

After the call, inspect the mocked gate call:

```python
assert mock_gate.await_args.kwargs["rewrite_service"] is rewrite_service
```

- [x] **Step 2: Run the new assertion and verify RED**

Run:

```bash
poetry run pytest tests/unit/test_change034_quality_eval.py::TestQualityCheckNode::test_quality_check_happy_path -q
```

Expected: FAIL because the node currently constructs `RewriteLoopService()` instead of forwarding the injected sentinel.

### Task 5: Remove Core → API imports and inject API dependencies

**Files:**

- Modify: `src/core/langgraph/nodes/quality_check.py`
- Modify: `src/api/services/novel_generator.py`

- [x] **Step 1: Consume only configurable dependencies in quality_check**

Keep gate imports in Core and use safe defaults:

```python
from src.core.quality.gate import GatePersistCallbacks, run_quality_gate

async def _noop(*args, **kwargs):
    return None

persist_quality_fn = configurable.get("persist_quality") or _noop
rewrite_service = configurable.get("rewrite_service")
```

Pass the injected service:

```python
rewrite_service=rewrite_service,
```

Remove both `src.api.services` imports from the node.

- [x] **Step 2: Inject concrete dependencies in the initial pipeline**

In `_run_langgraph_pipeline`, import `RewriteLoopService` from the API layer and add:

```python
"persist_quality": _persist_quality_to_version,
"rewrite_service": RewriteLoopService(),
```

- [x] **Step 3: Preserve dependencies after HITL resume**

In `resume_pipeline`, build configurable as:

```python
configurable: dict[str, Any] = {
    "thread_id": task_id,
    "persist_quality": _persist_quality_to_version,
    "rewrite_service": RewriteLoopService(),
}
```

- [x] **Step 4: Run injection and boundary tests**

Add two API orchestration tests in `test_novel_generator_supplement.py` that
capture the `config` passed to `graph.astream` for `_run_langgraph_pipeline()`
and `resume_pipeline()`. Both must assert:

```python
assert configurable["persist_quality"] is _persist_quality_to_version
assert isinstance(configurable["rewrite_service"], RewriteLoopService)
```

Run:

```bash
poetry run pytest tests/unit/test_change034_quality_eval.py tests/unit/test_change060_quality_check_unverified.py tests/unit/test_change061_quality_gate.py tests/unit/test_change050_layer_boundary.py tests/unit/test_novel_generator_supplement.py -q
```

Expected: all tests pass and both AST boundary checks find zero violations.

### Task 6: Run the complete verification matrix

**Files:** No intended changes.

- [x] **Step 1: Run the original failure set**

Run:

```bash
poetry run pytest tests/unit/test_novel_generator_auto_calc.py tests/unit/test_novel_generator_outline_persist.py tests/unit/test_change037_chapter_editor.py tests/unit/test_change038_dedup_and_timeout.py tests/unit/test_change049_refactoring.py tests/unit/test_novel_context_service.py tests/unit/test_langgraph/test_nodes.py tests/unit/test_change050_layer_boundary.py -q
```

Expected: zero failures.

- [x] **Step 2: Run all backend unit tests**

Run:

```bash
poetry run pytest tests/unit -q
```

Expected: zero failures; existing skips may remain.

- [x] **Step 3: Run changed-file Ruff and diff checks**

Run:

```bash
poetry run ruff check src/core/langgraph/nodes/quality_check.py src/api/services/novel_generator.py tests/unit/test_novel_generator_auto_calc.py tests/unit/test_novel_generator_outline_persist.py tests/unit/test_change037_chapter_editor.py tests/unit/test_change038_dedup_and_timeout.py tests/unit/test_change049_refactoring.py tests/unit/test_novel_context_service.py tests/unit/test_langgraph/test_nodes.py tests/unit/test_change034_quality_eval.py tests/unit/test_novel_generator_supplement.py
git diff --check
```

Expected: both commands exit 0. Also run `poetry run ruff check src tests/unit`
once to inventory the repository-wide baseline; unrelated historical lint findings are
recorded for a separate cleanup phase rather than mixed into this regression repair.

- [x] **Step 4: Verify FastAPI import**

Run:

```bash
poetry run python -c "from src.api.main import app; print(app.title)"
```

Expected: exit 0 and application title output.

- [x] **Step 5: Run frontend regression tests and build**

Run from `frontend/`:

```bash
npm test
npm run build
```

Expected: 47 tests pass and Vite build exits 0.

### Task 7: Review scope and record results

**Files:**

- Modify: `archive/organization-report.md` only if recording the new verified backend baseline is appropriate; do not rewrite historical archive source files.

- [x] **Step 1: Review the final diff**

Run:

```bash
git diff -- src/core/langgraph/nodes/quality_check.py src/api/services/novel_generator.py tests/unit docs/superpowers
```

Expected: only the planned dependency-source and test-contract changes.

- [x] **Step 2: Confirm excluded areas are untouched**

Run:

```bash
git status --short -- .env .env.docker src/api/routes/auth.py .claude/worktrees archive/changes
```

Expected: no task-created changes in excluded paths; pre-existing nested worktree status may remain unchanged.

- [x] **Step 3: Report actual verification evidence**

Record exact pass/fail/skip counts, Ruff/build results and the database-environment limitation. Do not claim database integration success without a real PostgreSQL run.

## Execution Results

- Original baseline reproduced: 13 contract failures plus 2 layer-boundary failures.
- Long-form namespace tests: 8 passed.
- Original failure set after repair: 78 passed.
- Quality gate, injection and layer-boundary focused suite: 18 passed; 1 existing warning.
- API injection mutation check: removing both injections caused the 2 new tests to fail with `KeyError`; restoring the implementation returned them to green.
- Final backend unit suite: **786 passed, 1 skipped, 7 warnings, 0 failed**.
- Changed-file Ruff: PASS.
- Repository-wide Ruff inventory: 63 historical findings outside this repair scope; no task-created Ruff findings remain.
- `git diff --check`: PASS.
- `src/core` API-import search: no matches.
- FastAPI import: PASS (`xIaoShuo API`).
- Frontend: **47 passed**; Vite production build PASS.
- Independent code review: no Critical findings; the missing API orchestration tests and resume-topology documentation issue were both resolved.
- Database integration: not claimed; current environment still lacks a verified PostgreSQL run.
- Git staging, commit, push and branch creation: not performed.
