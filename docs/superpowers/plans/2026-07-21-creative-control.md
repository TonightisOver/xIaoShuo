# Creative Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有"一键黑盒"生成流水线之上叠加阶段控制层，实现可查看/可编辑/可锁定/可审批/可局部重生成/可回退/并发安全的阶段式创作流程，保留一键自动生成能力。复用 `ChapterVersion` / 质量门禁 / 候选版本 / `Task` / `operation_id`，不另造第二套正文版本系统。

**Architecture:** 新增 `artifact_controls`(控制元数据/乐观锁/锁定) + `artifact_versions`(非正文产物版本快照) + `operation_logs`(操作审计) 三张表，由 `CreativeControlService` 统一收口受控写操作。生成流水线不改 LangGraph/gate 内部，只在 5 个产物落库出口最小插桩；自动模式净行为 = 现状 + 元数据。三模式由 `Novel.creation_mode` 决定。

**Tech Stack:** Python 3.11、FastAPI、Pydantic v2、SQLAlchemy async、Alembic、PostgreSQL、LangGraph、Vue 3、Vitest、pytest、Ruff。

**设计依据:** `docs/superpowers/specs/2026-07-21-creative-control-design.md`

**迁移链头:** `20260721d_task_checkpoints`（当前 head）。本设计迁移 `20260721e_creative_control` 以 `d` 为前驱。

---

## Scope and file map

### New files

- `src/core/creative_control/__init__.py` — 包出口。
- `src/core/creative_control/contracts.py` — 阶段/产物类型/控制状态/动作枚举与依赖图。
- `src/core/creative_control/control_service.py` — `CreativeControlService`：乐观锁/锁定/状态/stale 级联。
- `src/core/creative_control/artifact_version_store.py` — `ArtifactVersionStore`：非正文产物版本/比较/回退。
- `src/core/creative_control/impact_analyzer.py` — `ImpactAnalyzer`：依赖图影响范围。
- `src/core/creative_control/scope_planner.py` — `GenerationScopePlanner`：生成范围翻译+预览。
- `src/core/creative_control/operation_log.py` — `OperationLogService`：审计写入与查询。
- `src/api/services/creative_control_service.py` — API 层组合服务（DB session 注入到 core 层）。
- `src/api/routes/creative_control.py` — 路由层。
- `src/api/models/creative_control.py` — API 请求/响应模型。
- `alembic/versions/20260721e_add_creative_control.py` — 迁移。
- `tests/unit/test_creative_control_service.py`
- `tests/unit/test_artifact_version_store.py`
- `tests/unit/test_impact_analyzer.py`
- `tests/unit/test_scope_planner.py`
- `tests/unit/test_operation_log.py`
- `tests/unit/test_creative_control_api_contract.py`
- `tests/unit/test_creative_control_generation_instrumentation.py`
- `frontend/src/composables/useCreativeControl.js`
- `frontend/src/components/CreativeStudio.vue`
- `frontend/src/components/CreativeStageNav.vue`
- `frontend/src/components/ImpactPreviewPanel.vue`
- `frontend/src/components/GenerationScopeSelector.vue`
- `frontend/src/components/OperationTimeline.vue`
- `frontend/src/components/__tests__/CreativeStudio.spec.js`
- `frontend/src/components/__tests__/ImpactPreviewPanel.spec.js`
- `frontend/src/components/__tests__/GenerationScopeSelector.spec.js`

### Main modified files

- `src/api/models/db_models.py` — 3 新模型 + `Novel.creation_mode`/`Novel.creative_stage` + `ChapterBlueprint.version_number`。
- `src/core/exceptions.py` — `ArtifactConflictError`/`ArtifactLockedError`/`ArtifactBusyError`。
- `src/api/app.py` 或路由注册处 — 挂载 creative_control 路由。
- `src/api/services/content/chapter_service.py` — `update_chapter` 插桩 + `expected_active_version`。
- `src/api/services/content/blueprint_service.py` — 蓝图生成/编辑插桩 + version_number。
- `src/api/services/generation/chapter_persistence_service.py` — 落库插桩。
- `src/api/services/generation/long_form_generation_helpers.py` — 锁定章跳过插桩。
- `src/api/routes/chapters.py` — versions 路由补 `expected_active_version` + 409。
- `frontend/src/views/NovelDetail.vue` — 控制台入口。
- `frontend/src/router/index.js` — `/novels/:id/studio` 路由。

---

## Task 1: Define the creative control contract

**Files:**
- Create: `src/core/creative_control/contracts.py`
- Create: `src/core/creative_control/__init__.py`
- Create: `tests/unit/test_creative_control_contracts.py`

- [ ] **Step 1: Write failing contract tests**

Create `tests/unit/test_creative_control_contracts.py` asserting the stage list, artifact types, control status enum, dependency graph edges, and legal status transitions:

```python
from src.core.creative_control.contracts import (
    ARTIFACT_TYPES,
    CREATIVE_STAGES,
    CreationMode,
    ControlStatus,
    DEPENDENCY_GRAPH,
    legal_transitions,
    stage_of,
)


def test_ten_stages_defined():
    assert [s.number for s in CREATIVE_STAGES] == list(range(1, 11))


def test_chapter_uses_chapter_version_not_generic_version():
    assert stage_of("chapter_version") == 7
    assert "chapter_version" not in ARTIFACT_TYPES_VERSIONED_GENERICALLY
    assert "world" in ARTIFACT_TYPES_VERSIONED_GENERICALLY


def test_world_upstream_of_character_and_outline():
    downstream = DEPENDENCY_GRAPH["world"]
    assert "character" in downstream
    assert "master_outline" in downstream


def test_locked_is_not_auto_reachable_from_generated():
    transitions = legal_transitions(ControlStatus.GENERATED)
    assert ControlStatus.GENERATED not in transitions  # no self-loop
    assert ControlStatus.LOCKED not in transitions  # must go via approved


def test_any_status_can_go_stale():
    for status in ControlStatus:
        assert ControlStatus.STALE in legal_transitions(status)
```

- [ ] **Step 2: Verify failure**

`poetry run pytest tests/unit/test_creative_control_contracts.py -q` → ModuleNotFoundError.

- [ ] **Step 3: Implement the contract**

Create `src/core/creative_control/contracts.py` with:
- `CreationMode` StrEnum: `AUTO / ASSISTED / MANUAL`.
- `ControlStatus` StrEnum: `DRAFT / GENERATED / EDITED / APPROVED / LOCKED / STALE / GENERATING / FAILED`.
- `ARTIFACT_TYPES` tuple: `novel/world/character/master_outline/volume_outline/blueprint/chapter/chapter_version/quality/final`.
- `ARTIFACT_TYPES_VERSIONED_GENERICALLY`: `world/character/master_outline/volume_outline/blueprint`（正文除外）。
- `CREATIVE_STAGES`：10 阶段 dataclass(number, name, artifact_type)。
- `DEPENDENCY_GRAPH`：dict[type→list[downstream type]]，按设计文档依赖图。
- `legal_transitions(status)->set[ControlStatus]`：DRAFT→GENERATING; GENERATING→{GENERATED,FAILED}; GENERATED→{EDITED,APPROVED,STALE}; EDITED→{APPROVED,STALE,GENERATING}; APPROVED→{LOCKED,STALE,GENERATING}; LOCKED→{STALE,GENERATING}(后者需 force); 任意→STALE; STALE→{GENERATING,APPROVED}; FAILED→{GENERATING}。
- `stage_of(artifact_type)->int`。

- [ ] **Step 4: Export from `__init__.py`**

- [ ] **Step 5: Run focused tests**

`poetry run pytest tests/unit/test_creative_control_contracts.py -q` → pass.

- [ ] **Step 6: Commit**

```bash
git add src/core/creative_control/contracts.py src/core/creative_control/__init__.py tests/unit/test_creative_control_contracts.py
git commit -m "feat(creative-control): define stage/artifact/status contract"
```

## Task 2: Persist control metadata, versions, and operation logs

**Files:**
- Create: `alembic/versions/20260721e_add_creative_control.py`
- Modify: `src/api/models/db_models.py`
- Modify: `src/core/exceptions.py`
- Create: `tests/unit/test_creative_control_migration.py`

- [ ] **Step 1: Write failing ORM tests**

`tests/unit/test_creative_control_migration.py`:

```python
def test_artifact_controls_table_columns():
    from src.api.models.db_models import ArtifactControl
    cols = ArtifactControl.__table__.columns
    for name in ("control_status", "locked", "version", "stage",
                 "generation_meta", "stale_reason", "awaiting_review"):
        assert name in cols
    assert "novel_id" in cols and "artifact_type" in cols and "artifact_id" in cols


def test_artifact_versions_unique_active_partial_index():
    from src.api.models.db_models import ArtifactVersion
    idxs = [str(i) for i in ArtifactVersion.__table__.indexes]
    assert any("active" in i and "unique" in i.lower() or "uq" in i for i in idxs)


def test_operation_log_columns():
    from src.api.models.db_models import OperationLog
    cols = OperationLog.__table__.columns
    for name in ("action", "from_version", "to_version",
                 "operator_id", "reason", "task_id", "operation_id", "meta"):
        assert name in cols


def test_novel_has_creation_mode_and_creative_stage():
    from src.api.models.db_models import Novel
    assert "creation_mode" in Novel.__table__.columns
    assert "creative_stage" in Novel.__table__.columns


def test_blueprint_has_version_number():
    from src.api.models.db_models import ChapterBlueprint
    assert "version_number" in ChapterBlueprint.__table__.columns
```

- [ ] **Step 2: Verify failure**

`poetry run pytest tests/unit/test_creative_control_migration.py -q` → missing columns.

- [ ] **Step 3: Add Alembic migration**

`alembic/versions/20260721e_add_creative_control.py`, `down_revision = "20260721d_task_checkpoints"`. Create `artifact_controls`, `artifact_versions`, `operation_logs` per design doc; add `Novel.creation_mode`(default 'auto')/`Novel.creative_stage`(default 1); add `ChapterBlueprint.version_number`(nullable, backfill via `is_active` ordering or 1).

- [ ] **Step 4: Add ORM models**

`ArtifactControl` / `ArtifactVersion` / `OperationLog` in `db_models.py`; add `creation_mode`/`creative_stage` to `Novel`; add `version_number` to `ChapterBlueprint`.

Add exceptions to `src/core/exceptions.py`:

```python
class ArtifactConflictError(Exception):
    """expected_version does not match current control version (HTTP 409)."""

class ArtifactLockedError(Exception):
    """artifact is locked and force was not requested (HTTP 409)."""

class ArtifactBusyError(Exception):
    """artifact is currently generating (HTTP 409)."""
```

- [ ] **Step 5: Run migration + ORM tests**

```bash
poetry run alembic heads   # expect 20260721e_creative_control as single head
poetry run pytest tests/unit/test_creative_control_migration.py -q
```

- [ ] **Step 6: Commit**

```bash
git add alembic/versions/20260721e_add_creative_control.py src/api/models/db_models.py src/core/exceptions.py tests/unit/test_creative_control_migration.py
git commit -m "feat(creative-control): persist control/version/audit tables"
```

## Task 3: Implement CreativeControlService (optimistic lock / lock / status / stale cascade)

**Files:**
- Create: `src/core/creative_control/control_service.py`
- Create: `tests/unit/test_creative_control_service.py`

- [ ] **Step 1: Write failing service tests**

Tests (mocking `get_db_session` with `AsyncMock` + `with_for_update` row):
- `assert_writable` version mismatch → `ArtifactConflictError`.
- `assert_writable` locked & not force → `ArtifactLockedError`.
- `assert_writable` generating → `ArtifactBusyError`.
- `assert_writable` force bypasses locked.
- `begin_generating` / `complete_generating` / `fail_generating` transition + version bump + operation_log write.
- `mark_stale` cascades downstream: locked/approved downstream go to `to_mark_stale`, unlocked go to `regenerable`; sets `stale_reason`.
- `lock` / `unlock` / `approve` / `set_status` bump version, write op log, reject illegal transitions.
- history product without control row → lazy `generated`/`version=1` on read.

```python
@pytest.mark.asyncio
async def test_assert_writable_rejects_stale_version():
    session = _session_with_control_row(version=3)
    service = CreativeControlService()
    with patch("src.core.creative_control.control_service.get_db_session", return_value=session):
        with pytest.raises(ArtifactConflictError):
            await service.assert_writable("novel-1", "world", "w1", expected_version=1)
```

- [ ] **Step 2: Verify failure** → import error.

- [ ] **Step 3: Implement service**

`CreativeControlService` with `get_db_session()` transactions, `with_for_update()` on `ArtifactControl` row. `assert_writable` / `begin_generating` / `complete_generating` / `fail_generating` / `mark_stale` / `lock` / `unlock` / `approve` / `set_status` / `bump_version`. `mark_stale` uses `DEPENDENCY_GRAPH` + downstream control rows to split `regenerable` vs `to_mark_stale`. Each mutating method writes an `OperationLog` row and bumps `version`.

Delegate DB to injected session via `get_db_session` context manager (core layer stays testable, no direct FastAPI dependency).

- [ ] **Step 4: Run tests**

`poetry run pytest tests/unit/test_creative_control_service.py -q` → pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/creative_control/control_service.py tests/unit/test_creative_control_service.py
git commit -m "feat(creative-control): optimistic-lock/lock/stale-cascade service"
```

## Task 4: Implement ArtifactVersionStore (non-body versions / compare / rollback)

**Files:**
- Create: `src/core/creative_control/artifact_version_store.py`
- Create: `tests/unit/test_artifact_version_store.py`

- [ ] **Step 1: Write failing tests**

- `save_version` sets old active=False, inserts new active=True, returns version_number.
- per-artifact single active enforced at app layer (matches DB partial unique index).
- `list_versions` desc by version_number, includes content_snapshot summary.
- `compare_versions(a, b)` returns diff structure (field-level for dict snapshots).
- `rollback_to(v)` restores content_snapshot to the source product row (calls existing product service upsert) + new active + op log.
- blueprint path: reuse `ChapterBlueprint.is_active`, set `version_number` on new row, old row `is_active=False`.

- [ ] **Step 2: Verify failure**.

- [ ] **Step 3: Implement store**

`ArtifactVersionStore.save_version(novel_id, artifact_type, artifact_id, content_snapshot, source, model, operator_id, task_id, operation_id) -> int`. For blueprint, delegate to `BlueprintService`-shaped helper that writes `version_number`. `rollback_to` calls the corresponding existing content service (`WorldService.upsert_world_setting`, `CharacterService`, `OutlineService`, `VolumeService`, `BlueprintService`) to restore content, then marks the target version active and logs `rollback` op.

- [ ] **Step 4: Run tests**

`poetry run pytest tests/unit/test_artifact_version_store.py -q` → pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/creative_control/artifact_version_store.py tests/unit/test_artifact_version_store.py
git commit -m "feat(creative-control): generic artifact versioning/compare/rollback"
```

## Task 5: Implement ImpactAnalyzer (dependency-aware scope)

**Files:**
- Create: `src/core/creative_control/impact_analyzer.py`
- Create: `tests/unit/test_impact_analyzer.py`

- [ ] **Step 1: Write failing tests**

Cover the 5 user-specified cases:
- edit world → downstream = {character, master_outline, volume_outline, blueprint, un-finalized chapter content}; locked chapters in `to_mark_stale`.
- edit character → relevant volume_outline/blueprint/chapters where character appears (use `ChapterBlueprint.key_characters` + chapter `state_delta.character_changes`).
- edit volume_outline → only that volume's unlocked blueprints + chapters.
- edit blueprint → that chapter's content + subsequent chapters' continuity state.
- edit chapter content → new version + `quality_status=unverified` (no downstream regen).

Return shape matches design doc `direct_downstream/full_downstream/regenerable/to_mark_stale`.

- [ ] **Step 2: Verify failure**.

- [ ] **Step 3: Implement analyzer**

`ImpactAnalyzer.analyze(novel_id, artifact_type, artifact_id) -> ImpactReport`. Traverses `DEPENDENCY_GRAPH`; for character-appearance and volume-scoping, query `ChapterBlueprint.key_characters` / `Chapter.state_delta` / `Volume.chapter_start/end`. Splits by downstream `ArtifactControl.locked`/`control_status in (APPROVED,LOCKED)`. Reuses `OutlineSyncSuggestion` chapter-level rows where present.

- [ ] **Step 4: Run tests**

`poetry run pytest tests/unit/test_impact_analyzer.py -q` → pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/creative_control/impact_analyzer.py tests/unit/test_impact_analyzer.py
git commit -m "feat(creative-control): dependency-aware impact analysis"
```

## Task 6: Implement OperationLogService

**Files:**
- Create: `src/core/creative_control/operation_log.py`
- Create: `tests/unit/test_operation_log.py`

- [ ] **Step 1: Write failing tests**

- `record(action, ...)` persists row with all fields; rejects unknown action.
- `list(novel_id, *, artifact_type=None, action=None, since=None)` filters and orders desc.
- 10 action types each round-trip.

- [ ] **Step 2: Verify failure**.

- [ ] **Step 3: Implement**

`OperationLogService.record` / `list`. Action enum from contracts.

- [ ] **Step 4: Run tests** → pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/creative_control/operation_log.py tests/unit/test_operation_log.py
git commit -m "feat(creative-control): structured operation audit log"
```

## Task 7: Implement GenerationScopePlanner

**Files:**
- Create: `src/core/creative_control/scope_planner.py`
- Create: `tests/unit/test_scope_planner.py`

- [ ] **Step 1: Write failing tests**

- `plan(single chapter N)` → calls existing `generate-chapters` payload `{chapter_start=N, chapter_end=N}`, filters locked/skip-confirmed.
- `plan(range a,b)`, `plan(volume V)`, `plan(continue from N)`, `plan(blueprint only, chapter N)`, `plan(content only)`, `plan(fix quality, issue_ids)`.
- locked chapters excluded from regen set, included in `skipped_locked`.
- confirmed chapters skipped when `skip_confirmed=True`.
- `preview` returns `{estimated_chapters, estimated_tokens, impact}`; tokens = `words_per_chapter * chapters * 1.5` heuristic; impact from `ImpactAnalyzer`.

- [ ] **Step 2: Verify failure**.

- [ ] **Step 3: Implement planner**

`GenerationScopePlanner.plan(intent) -> ScopePlan` and `preview(intent) -> ScopePreview`. Translates intent to existing endpoint payloads + control filters (reads `ArtifactControl` for locked/approved). Does not itself enqueue tasks — returns the payload + filter result; the API layer enqueues via existing `task_manager.create_task` with proper `operation_id`.

- [ ] **Step 4: Run tests** → pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/creative_control/scope_planner.py tests/unit/test_scope_planner.py
git commit -m "feat(creative-control): generation scope planning and preview"
```

## Task 8: Minimal generation pipeline instrumentation (auto-mode regression-safe)

**Files:**
- Modify: `src/api/services/generation/chapter_persistence_service.py`
- Modify: `src/api/services/generation/long_form_generation_helpers.py`
- Modify: `src/api/services/content/blueprint_service.py`
- Modify: `src/api/services/content/chapter_service.py`
- Create: `tests/unit/test_creative_control_generation_instrumentation.py`

- [ ] **Step 1: Write failing instrumentation tests**

- After `persist_langgraph_result` persists world/character/outline/chapter, `ArtifactControl` rows exist with `generated` + `version=1` + `generation_meta.source`.
- `generate_volume_chapters` loop skips a chapter whose `ArtifactControl.locked=True` (auto mode) and records it in `skipped`.
- `BlueprintService.generate_blueprint` sets new row `version_number` and old `is_active=False`, writes control `generated`.
- `ChapterService.update_chapter` with `content` change → `Chapter.quality_status="unverified"` + control `edited` + op log `edit`.
- **Auto-mode net behavior**: generation result content identical to pre-instrumentation snapshot (golden test: run a short-form generation with mocked LLM, assert chapter content unchanged; control rows are additive only).

```python
def test_auto_mode_generation_result_unchanged_by_instrumentation():
    # mock LLM deterministic; run generation; assert chapter.content == expected
    # and ArtifactControl rows exist but did not alter content
```

- [ ] **Step 2: Verify failure**.

- [ ] **Step 3: Add instrumentation hooks**

In each of the 5 persistence exits, after successful DB write, call `CreativeControlService().complete_generating(...)` + `ArtifactVersionStore().save_version(...)` (for non-body artifacts) or control-only (for chapter/chapter_version). Wrap in try/except so instrumentation failure never breaks generation (log warning, continue) — consistent with gate.py's "never throw" invariant.

In `generate_volume_chapters` loop head, check `ArtifactControl.locked` for the chapter; if locked and `creation_mode==auto`, skip (append to `skipped`); if assisted/manual, set `awaiting_review` and continue.

- [ ] **Step 4: Run instrumentation + regression tests**

`poetry run pytest tests/unit/test_creative_control_generation_instrumentation.py tests/unit/test_change044_long_form_services.py tests/unit/test_chapter_persistence_service.py -q` → pass, no regression.

- [ ] **Step 5: Commit**

```bash
git add src/api/services/generation/chapter_persistence_service.py src/api/services/generation/long_form_generation_helpers.py src/api/services/content/blueprint_service.py src/api/services/content/chapter_service.py tests/unit/test_creative_control_generation_instrumentation.py
git commit -m "feat(creative-control): instrument generation exits (auto-mode safe)"
```

## Task 9: Add chapter version expected_active_version + 409

**Files:**
- Modify: `src/api/services/content/chapter_service.py`
- Modify: `src/api/routes/chapters.py`
- Modify: `src/api/routes/creative_control.py` (body activate delegates)
- Modify: `tests/unit/test_chapter_service.py`

- [ ] **Step 1: Write failing tests**

- `activate_chapter_version(expected_active_version=...)` raises `ArtifactConflictError` when current active differs.
- `rollback_chapter_version(expected_active_version=...)` same.
- route `POST .../versions/{v}/activate` returns 409 with current version in body on conflict.
- manual `update_chapter` content → new `ChapterVersion` row created (source=manual) when `create_version=True` (new param, default False for backward compat) + control `edited`.

- [ ] **Step 2: Verify failure**.

- [ ] **Step 3: Implement**

Add `expected_active_version: int | None = None` to `activate_chapter_version`/`rollback_chapter_version`; when provided, `with_for_update` the current active row, compare, raise `ArtifactConflictError` on mismatch. Route maps to HTTP 409. If 正文质量计划 later lands `StaleChapterVersionError`, alias it to `ArtifactConflictError` at route layer.

- [ ] **Step 4: Run tests**

`poetry run pytest tests/unit/test_chapter_service.py -q` → pass.

- [ ] **Step 5: Commit**

```bash
git add src/api/services/content/chapter_service.py src/api/routes/chapters.py tests/unit/test_chapter_service.py
git commit -m "feat(creative-control): chapter version optimistic lock + 409"
```

## Task 10: Expose creative-control API routes

**Files:**
- Create: `src/api/models/creative_control.py`
- Create: `src/api/routes/creative_control.py`
- Create: `tests/unit/test_creative_control_api_contract.py`

- [ ] **Step 1: Write failing API contract tests**

Owner isolation, 409 mapping, 422 validation, nullable fields. Cover: `GET /stage`, `GET/PUT /artifacts/{type}/{id}`, `lock/unlock/approve/regenerate`, `GET /impact`, `GET /versions`, `/versions/compare`, `rollback`, `mark-stale`, `GET /operations`, `POST /generate-scope`, `/generate-scope/preview`, `PUT /mode`.

```python
@pytest.mark.asyncio
async def test_edit_artifact_returns_409_on_stale_version():
    user = SimpleNamespace(id=7)
    body = {"content": ..., "expected_version": 1}
    with (patch("...verify_novel_owner", new=AsyncMock()),
          patch("...CreativeControlService.assert_writable",
                new=AsyncMock(side_effect=ArtifactConflictError(current_version=2)))):
        with pytest.raises(HTTPException) as exc:
            await edit_artifact("novel-1", "world", "w1", body, current_user=user)
    assert exc.value.status_code == 409
    assert exc.value.detail["current_version"] == 2
```

- [ ] **Step 2: Verify failure** (404/imports).

- [ ] **Step 3: Implement models + routes**

`src/api/models/creative_control.py`: `EditArtifactRequest{content:dict, expected_version:int}`, `RegenerateRequest{expected_version:int, scope:dict|None, force:bool=False}`, `GenerateScopeRequest`, `SetModeRequest{creation_mode}`. Responses include control metadata.

`src/api/routes/creative_control.py`: all routes guarded by `verify_novel_owner`. Map `ArtifactConflictError`/`ArtifactLockedError`/`ArtifactBusyError` → 409 with `current_version`/`locked`/`status` in detail. Register router in app.

- [ ] **Step 4: Run tests**

`poetry run pytest tests/unit/test_creative_control_api_contract.py tests/api/test_routes.py -q` → pass.

- [ ] **Step 5: Commit**

```bash
git add src/api/models/creative_control.py src/api/routes/creative_control.py tests/unit/test_creative_control_api_contract.py
git commit -m "feat(api): expose creative-control endpoints"
```

## Task 11: Frontend creative studio

**Files:**
- Create: `frontend/src/composables/useCreativeControl.js`
- Create: `frontend/src/components/CreativeStudio.vue`
- Create: `frontend/src/components/CreativeStageNav.vue`
- Create: `frontend/src/components/ImpactPreviewPanel.vue`
- Create: `frontend/src/components/GenerationScopeSelector.vue`
- Create: `frontend/src/components/OperationTimeline.vue`
- Modify: `frontend/src/views/NovelDetail.vue`
- Modify: `frontend/src/router/index.js`
- Create tests for the three key components.

- [ ] **Step 1: Write failing component tests**

`CreativeStudio.spec.js`: stage nav renders 10 stages with completion status; clicking a stage loads artifact; edit save sends `expected_version`; 409 shows "版本已变化，请刷新" + reloads; locked badge shows. `ImpactPreviewPanel.spec.js`: renders 4 options (save only / regen direct / regen all / mark stale); selecting emits chosen scope. `GenerationScopeSelector.spec.js`: single/range/volume/continue/blueprint-only/content-only/fix-quality options; preview shows chapters+tokens+impact.

- [ ] **Step 2: Verify failure**.

- [ ] **Step 3: Implement composable + components**

`useCreativeControl(novelId)` exposing `stage`, `artifacts`, `loadStage`, `editArtifact`, `lock/unlock/approve/regenerate`, `loadImpact`, `chooseImpactOption`, `listVersions`, `compareVersions`, `rollback`, `planScope`, `previewScope`, `setMode`, `operations`. 409 handler reloads current artifact.

`CreativeStudio.vue` orchestrates: stage nav (reuse `StageIndicator` styling, make clickable) + artifact edit area (dispatch by type to existing editors) + lock/approve/regenerate buttons + impact panel + version history/diff (reuse `VersionDiffView`) + stale list + scope selector + operation timeline.

`ImpactPreviewPanel.vue`: 4 radio options + downstream summary. `GenerationScopeSelector.vue`: extend `ChapterRangeDialog` to volume/chapter tree + option radios + preview card. `OperationTimeline.vue`: filterable list.

Add `/novels/:id/studio` route; add entry in `NovelDetail.vue` (new button → studio).

- [ ] **Step 4: Run component tests**

`cd frontend && npm run test -- CreativeStudio.spec.js ImpactPreviewPanel.spec.js GenerationScopeSelector.spec.js` → pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/composables/useCreativeControl.js frontend/src/components/CreativeStudio.vue frontend/src/components/CreativeStageNav.vue frontend/src/components/ImpactPreviewPanel.vue frontend/src/components/GenerationScopeSelector.vue frontend/src/components/OperationTimeline.vue frontend/src/views/NovelDetail.vue frontend/src/router/index.js frontend/src/components/__tests__/
git commit -m "feat(frontend): add creative studio console"
```

## Task 12: Three-mode behavior + assisted/manual awaiting_review

**Files:**
- Modify: `src/core/creative_control/control_service.py`
- Modify: `src/api/services/generation/long_form_generation_helpers.py`
- Modify: `tests/unit/test_creative_control_generation_instrumentation.py`

- [ ] **Step 1: Write failing mode tests**

- auto mode: no `awaiting_review` set on generated artifacts.
- assisted: stage 1/4/7/9 artifacts get `awaiting_review=True` after generation; background task does NOT hard-pause.
- manual: every stage artifact gets `awaiting_review=True`; next stage not auto-advanced (verified by absence of subsequent stage control rows until explicit regenerate).
- switching mode mid-task: in-flight task unaffected, next stage respects new mode.

- [ ] **Step 2: Verify failure**.

- [ ] **Step 3: Implement mode-aware awaiting_review**

`complete_generating` reads `Novel.creation_mode`; sets `awaiting_review` per mode rules. Manual mode: generation of stage N does not trigger stage N+1 generation (already true — generation is explicit per call; verify no auto-advance exists and document).

- [ ] **Step 4: Run tests**

`poetry run pytest tests/unit/test_creative_control_generation_instrumentation.py tests/unit/test_creative_control_service.py -q` → pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/creative_control/control_service.py src/api/services/generation/long_form_generation_helpers.py tests/unit/test_creative_control_generation_instrumentation.py
git commit -m "feat(creative-control): three-mode awaiting_review semantics"
```

## Task 13: Compatibility, migration, full verification, docs

**Files:**
- Modify: `README.md`
- Modify: `CONTEXT.md`
- Modify: `.env.example`
- Modify: tests discovered by full verification only when they encode obsolete semantics.

- [ ] **Step 1: Add compatibility regression assertions**

`rg -n 'expected_version|creation_mode|ArtifactControl|awaiting_review' src tests frontend/src` — classify each match. Ensure no test encodes "generation silently overwrites locked content".

- [ ] **Step 2: Verify migration chain**

```bash
poetry run alembic heads      # single head 20260721e
poetry run alembic upgrade head
poetry run alembic current
```

- [ ] **Step 3: Run focused backend tests**

```bash
poetry run pytest tests/unit/test_creative_control_contracts.py tests/unit/test_creative_control_migration.py tests/unit/test_creative_control_service.py tests/unit/test_artifact_version_store.py tests/unit/test_impact_analyzer.py tests/unit/test_scope_planner.py tests/unit/test_operation_log.py tests/unit/test_creative_control_api_contract.py tests/unit/test_creative_control_generation_instrumentation.py -q
```

- [ ] **Step 4: Run all backend partitions**

```bash
make test-unit
make test-api
make test-integration
make test-root
```

Do not combine pytest groups.

- [ ] **Step 5: Run frontend tests + build**

```bash
make test-frontend
make build-frontend
```

- [ ] **Step 6: Run static/structural gates**

```bash
make ruff
make check-structure
make check-legacy-paths
make check-secrets
```

- [ ] **Step 7: Update docs**

README: creative-control section (three modes, lock/approval, scoped regen, 409, audit). CONTEXT.md: control statuses + artifact_types. `.env.example`: `CREATION_MODE=auto`.

- [ ] **Step 8: Run aggregate gate**

```bash
make verify
```

If DB groups unavailable, report them as not run with exact connection error — do not claim full verification.

- [ ] **Step 9: Review final diff**

```bash
git diff --check
git status --short
rg -n 'NotImplementedError|pass[[:space:]]*$' src/core/creative_control src/api/routes/creative_control.py frontend/src/components/CreativeStudio.vue
```

- [ ] **Step 10: Commit docs + final fixes**

```bash
git add README.md CONTEXT.md .env.example
git commit -m "docs(creative-control): document staged creative workflow"
```

---

## Completion checklist

### Spec coverage matrix

| Design requirement | Task |
|---|---|
| 10 stages, artifact types, control status, dependency graph | 1 |
| control/version/audit tables + Novel.creation_mode | 2 |
| optimistic lock / lock / stale cascade | 3 |
| non-body artifact version/compare/rollback | 4 |
| dependency-aware impact (5 cases) | 5 |
| operation audit (10 actions) | 6 |
| generation scope + preview | 7 |
| minimal generation instrumentation (auto-safe) | 8 |
| chapter expected_active_version + 409 | 9 |
| creative-control API routes | 10 |
| frontend creative studio | 11 |
| three-mode awaiting_review | 12 |
| migration, full verification, docs | 13 |

- [ ] Any stage can be paused/edited (three modes).
- [ ] Locked content not overwritten by auto tasks.
- [ ] Upstream edits compute + show impact.
- [ ] No unconfirmed delete/overwrite of downstream.
- [ ] Scoped regen (volume/range/single).
- [ ] Rollback from history.
- [ ] 409 on concurrent modification.
- [ ] Manual body edit → old quality score not shown as current.
- [ ] All key operations auditable.
- [ ] One-click generation preserved (auto mode = status quo).
- [ ] Backend + API + Vue components have tests.
