# 章节蓝图工作台实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有章节蓝图后端能力 + Creative Control 第6阶段之上，新增面向作者的独立「章节蓝图工作台」：全书章节蓝图状态总览（含未生成）、按卷/章号/状态筛选定位、结构化表单编辑、单章与批量生成、确认/锁定/解锁、版本历史/比较/回退、影响预览、与大纲/正文/质量关联，数百至数千章规模服务端分页可用。

**Architecture:** 新增独立路由 `/novels/:id/blueprints` + `ChapterBlueprintWorkbench.vue` 三栏布局。后端新增最小聚合层（`BlueprintWorkbenchService`：章节摘要列表 + workspace 聚合 + options；扩展 `GenerationScopePlanner`/`CreativeGenerationDispatcher` 支持 blueprint_only 多章；批量 lock/unlock/approve 路由）。控制操作（编辑保存/确认/锁定/重生成/版本/回退/影响）全部复用现有 creative-control 通用路由（`artifact_type="blueprint"`）与 `useCreativeControl`。生成统一走后台 `NOVEL_BLUEPRINT` 任务。零 DB 迁移。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy(async) · pytest · ruff · mypy；Vue 3 Composition API · Vitest · Tailwind(ink/paper/vermilion)。

**关键约束（贯穿全部任务，不得违反）：**
- 不重做 BlueprintService 内部生成逻辑、不重做 Creative Control 控制层、不新增第二套蓝图/版本/任务/控制表。
- `_get_blueprint`（`chapter_generation_utils.py:89-103`）同步自动生成路径**保持不动**（正文生成同步依赖）。
- 所有新路由 `await verify_novel_owner(novel_id, current_user)`。
- 测试禁止真实调用 LLM（mock `get_llm_client` / `generate_and_parse_json`）。
- 后端契约测试直调路由 async 函数 + mock service；集成测试用隔离 PG（`TEST_DATABASE_URL`）。
- 前端测试用 `vi.stubGlobal('fetch', makeFetch(routes))` + `data-*` selector，沿用现有风格。
- 每个任务只提交本功能相关文件，不推送、不部署。

**现有复用锚点（已第一手核读，禁止再改动这些已确认签名）：**
- `BlueprintService`：`generate_blueprint(novel_id, chapter_number, chapter_outline, volume_context="", *, persist=True)` / `get_blueprint(novel_id, chapter_number) -> dict|None` / `update_blueprint(novel_id, chapter_number, updates) -> dict`（`BLUEPRINT_FIELDS` 已定义 8 字段）。
- `CreativeControlService`：`get_or_create / lock / unlock / approve / assert_generation_allowed_in_session / record_generated`，均带 `expected_version`。
- `ArtifactVersionStore.list_versions(novel_id, artifact_type, artifact_id)` / `compare_versions(novel_id, artifact_type, artifact_id, a, b)` / `restore_callback=adapters.save`。
- `CreativeArtifactWriteService.rollback_artifact(novel_id, artifact_type, artifact_id, target_version, expected_control_version, expected_active_version, operator_id)`。
- `ImpactAnalyzer.analyze(novel_id, artifact_type, artifact_id)`。
- `verify_novel_owner(novel_id, current_user) -> dict`（404/403）。
- `GenerationScopePlanner`：`plan(intent)->ScopePlan`、`preview(intent)->ScopePreview`、`_filter_chapters(intent, target)`、`_load_locked_chapters`、`_load_confirmed_chapters`。
- `CreativeGenerationDispatcher.dispatch_scope(novel, owner_id, plan) -> DispatchedGeneration`。
- `_to_intent(novel_id, request)`（creative_control.py 内）把 `GenerateScopeRequest` 转 `GenerationScopeIntent`。
- `useCreativeControl`（前端）：`editArtifact/lockArtifact/unlockArtifact/approveArtifact/regenerateArtifact/rollbackVersion/listVersions/compareVersions/loadImpact/listOperations` + 409 解析。
- `useApi` → `apiGet/apiPost/apiPut/apiDelete` + `authHeaders`（token key `session_token`）。
- 路由注册：`src/api/routes/__init__.py` 导出 `router`，`app` 聚合处 `include_router`。

---

## 文件结构

### 后端新增
- `src/core/creative_control/blueprint_enums.py` — `ChapterType`/`BlueprintPacing`/`ForeshadowAction` StrEnum + `BLUEPRINT_FIELD_OPTIONS`（纯逻辑，无 DB）。
- `src/api/services/content/blueprint_workbench_service.py` — `BlueprintWorkbenchService`：`list_chapter_summaries` / `get_workspace` / `get_options`。
- `src/api/routes/blueprint_workbench.py` — 4 路由（list/options/workspace/batch）。
- `tests/unit/test_blueprint_enums.py`
- `tests/unit/test_blueprint_workbench_service.py`
- `tests/unit/test_blueprint_workbench_api_contract.py`

### 后端修改
- `src/api/services/content/blueprint_service.py` — `generate_blueprint`/`update_blueprint` 写入前校验枚举值（422）。
- `src/api/models/creative_control.py` — `GenerateScopeRequest` 增 `chapter_numbers` + 放宽 `blueprint_only` 校验。
- `src/core/creative_control/scope_planner.py` — `GenerationScopeIntent` 增 `chapter_numbers`；`plan` 扩展 blueprint_only 多章；`_filter_chapters` 增 `artifact_type` 参数 + blueprint 类型加载。
- `src/api/services/creative_control/generation_dispatch.py` — `DispatchedGeneration` 增逐章明细字段；blueprint_only 多章按区间投递 + 填充逐章结果。
- `src/api/routes/chapters.py` — `POST /{n}/blueprint/generate` 行为改投后台任务（URL 保留）。
- `src/api/routes/__init__.py` — 注册 `blueprint_workbench_router`。
- `tests/unit/test_blueprint_service.py`（扩展枚举校验用例）
- `tests/unit/test_scope_planner.py`（扩展 blueprint_only 多章）
- `tests/unit/test_creative_generation_dispatch.py`（扩展多章逐章明细）
- `tests/integration/test_creative_control_atomic_writes.py`（扩展 blueprint 后台生成/lease/批量跳过）

### 前端新增
- `frontend/src/views/ChapterBlueprintWorkbench.vue` — 三栏容器。
- `frontend/src/components/blueprints/BlueprintChapterList.vue`
- `frontend/src/components/blueprints/BlueprintEditor.vue`
- `frontend/src/components/blueprints/BlueprintContextPanel.vue`
- `frontend/src/components/blueprints/BlueprintBatchToolbar.vue`
- `frontend/src/components/blueprints/BlueprintVersionDialog.vue`
- `frontend/src/composables/useBlueprintWorkbench.js`
- `frontend/src/views/__tests__/ChapterBlueprintWorkbench.spec.js`
- `frontend/src/components/__tests__/blueprints/*.spec.js`（5 个）
- `frontend/src/composables/__tests__/useBlueprintWorkbench.spec.js`

### 前端修改
- `frontend/src/router/index.js` — 增 `/novels/:id/blueprints` 路由。
- `frontend/src/views/NovelDetail.vue` — 入口区增「章节蓝图」按钮（`data-blueprint-link`）。
- `frontend/src/views/CreativeStudio.vue` — 第6阶段区域增「进入蓝图工作台」链接（零改动既有逻辑）。

---

## Task 1：枚举契约 + BlueprintService 写入校验

**Files:**
- Create: `src/core/creative_control/blueprint_enums.py`
- Modify: `src/api/services/content/blueprint_service.py`（`generate_blueprint` L99-112 写入、`update_blueprint` L156-158 写入）
- Test: `tests/unit/test_blueprint_enums.py`
- Test: `tests/unit/test_blueprint_service.py`（扩展）

- [ ] **Step 1：写失败测试 `test_blueprint_enums.py`**

```python
"""蓝图枚举契约：值必须与 prompts.py 现有字面量严格一致，禁止发明。"""

from src.core.creative_control.blueprint_enums import (
    BLUEPRINT_FIELD_OPTIONS,
    BlueprintPacing,
    ChapterType,
    ForeshadowAction,
)


def test_chapter_type_values_match_prompts():
    assert {e.value for e in ChapterType} == {
        "main_advance", "climax", "aftermath", "daily", "setup"
    }


def test_pacing_values_match_prompts():
    assert {e.value for e in BlueprintPacing} == {"fast", "medium", "slow"}


def test_foreshadow_action_values_match_prompts():
    assert {e.value for e in ForeshadowAction} == {
        "plant", "callback", "advance"
    }


def test_options_dict_exposes_all_enums():
    assert set(BLUEPRINT_FIELD_OPTIONS["chapter_type"]) == {
        e.value for e in ChapterType
    }
    assert set(BLUEPRINT_FIELD_OPTIONS["pacing_target"]) == {
        e.value for e in BlueprintPacing
    }
    assert set(BLUEPRINT_FIELD_OPTIONS["foreshadow_action"]) == {
        e.value for e in ForeshadowAction
    }
```

- [ ] **Step 2：运行确认失败**

Run: `poetry run pytest tests/unit/test_blueprint_enums.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.core.creative_control.blueprint_enums'`

- [ ] **Step 3：实现 `blueprint_enums.py`**

```python
"""章节蓝图字段枚举契约。

值严格取自 src/core/llm/prompts.py 的现有字面量（chapter_type/pacing_target/
foreshadow_action），禁止发明不兼容枚举。DB 列保持 String 不变，不引入 CHECK。
"""

from __future__ import annotations

from enum import StrEnum


class ChapterType(StrEnum):
    MAIN_ADVANCE = "main_advance"
    CLIMAX = "climax"
    AFTERMATH = "aftermath"
    DAILY = "daily"
    SETUP = "setup"


class BlueprintPacing(StrEnum):
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"


class ForeshadowAction(StrEnum):
    PLANT = "plant"
    CALLBACK = "callback"
    ADVANCE = "advance"


BLUEPRINT_FIELD_OPTIONS: dict[str, list[str]] = {
    "chapter_type": [e.value for e in ChapterType],
    "pacing_target": [e.value for e in BlueprintPacing],
    "foreshadow_action": [e.value for e in ForeshadowAction],
}


def validate_blueprint_fields(data: dict) -> None:
    """写入前校验 chapter_type/pacing_target/word_target。不符抛 ValueError（路由层映射 422）。"""
    chapter_type = data.get("chapter_type")
    if chapter_type is not None and chapter_type not in BLUEPRINT_FIELD_OPTIONS["chapter_type"]:
        raise ValueError(f"非法 chapter_type: {chapter_type}")
    pacing = data.get("pacing_target")
    if pacing is not None and pacing not in BLUEPRINT_FIELD_OPTIONS["pacing_target"]:
        raise ValueError(f"非法 pacing_target: {pacing}")
    word_target = data.get("word_target")
    if word_target is not None:
        if not isinstance(word_target, int) or isinstance(word_target, bool) or word_target < 2000 or word_target > 6000:
            raise ValueError(f"word_target 必须为 2000-6000 的正整数: {word_target}")
```

- [ ] **Step 4：运行确认通过**

Run: `poetry run pytest tests/unit/test_blueprint_enums.py -q`
Expected: PASS（4 passed）

- [ ] **Step 5：写 BlueprintService 枚举校验失败测试（扩展 `test_blueprint_service.py`）**

在 `tests/unit/test_blueprint_service.py` 末尾追加：

```python
class TestBlueprintFieldValidation:
    """BlueprintService 写入前校验枚举值（Task 1）。"""

    @pytest.mark.asyncio
    async def test_generate_blueprint_rejects_invalid_chapter_type(self):
        from src.api.services.content.blueprint_service import BlueprintService

        ctx_factory, _ = _fake_session()
        mock_client = AsyncMock()
        mock_client.generate = AsyncMock(return_value=json.dumps({
            "chapter_type": "invalid_type", "plot_goal": "x",
            "hook_design": "", "foreshadow_actions": [], "cliffhanger": "",
            "pacing_target": "medium", "key_characters": [], "word_target": 3000,
        }))
        svc = BlueprintService()
        with (
            patch("src.api.services.content.blueprint_service.get_db_session", ctx_factory),
            patch("src.api.services.content.blueprint_service.get_llm_client", return_value=mock_client),
            patch.object(svc, "_build_context", new_callable=AsyncMock, return_value={
                "previous_chapter": "", "story_bible": "", "kg_context": "", "volume_context": "",
            }),
        ):
            with pytest.raises(ValueError, match="非法 chapter_type"):
                await svc.generate_blueprint(_novel_id(), 1, {"plot": "x"}, persist=True)

    @pytest.mark.asyncio
    async def test_update_blueprint_rejects_invalid_pacing(self):
        from src.api.services.content.blueprint_service import BlueprintService

        mock_bp = _make_blueprint_model()
        ctx_factory, _ = _fake_session(bp=mock_bp)
        svc = BlueprintService()
        with patch("src.api.services.content.blueprint_service.get_db_session", ctx_factory):
            with pytest.raises(ValueError, match="非法 pacing_target"):
                await svc.update_blueprint(_novel_id(), 1, {"pacing_target": "turbo"})

    @pytest.mark.asyncio
    async def test_update_blueprint_rejects_word_target_out_of_range(self):
        from src.api.services.content.blueprint_service import BlueprintService

        mock_bp = _make_blueprint_model()
        ctx_factory, _ = _fake_session(bp=mock_bp)
        svc = BlueprintService()
        with patch("src.api.services.content.blueprint_service.get_db_session", ctx_factory):
            with pytest.raises(ValueError, match="word_target"):
                await svc.update_blueprint(_novel_id(), 1, {"word_target": 100})
```

- [ ] **Step 6：运行确认失败**

Run: `poetry run pytest tests/unit/test_blueprint_service.py::TestBlueprintFieldValidation -q`
Expected: FAIL — 测试通过不抛错（因尚未加校验），即 `DID NOT RAISE`

- [ ] **Step 7：在 `blueprint_service.py` 接入校验**

在 `blueprint_service.py` 顶部 import 块（L17 后）追加：

```python
from src.core.creative_control.blueprint_enums import validate_blueprint_fields
```

在 `generate_blueprint` 的 `if not persist:` 之前（L75 前，即拿到 `blueprint_data` 后、persist 分支前）插入：

```python
        validate_blueprint_fields(blueprint_data)
```

在 `update_blueprint` 的 `for field, value in updates.items():` 之前（L156 前）插入：

```python
            validate_blueprint_fields(updates)
```

- [ ] **Step 8：运行确认通过**

Run: `poetry run pytest tests/unit/test_blueprint_service.py -q`
Expected: PASS（全部，含原有 + 新增 3 例）

- [ ] **Step 9：提交**

```bash
git add src/core/creative_control/blueprint_enums.py \
        src/api/services/content/blueprint_service.py \
        tests/unit/test_blueprint_enums.py \
        tests/unit/test_blueprint_service.py
git commit -m "feat(blueprint-workbench): 枚举契约 + BlueprintService 写入校验(T1)"
```

---

## Task 2：`GenerateScopeRequest` 增 `chapter_numbers` + planner blueprint_only 多章

**Files:**
- Modify: `src/api/models/creative_control.py`（`GenerateScopeRequest` L41-69）
- Modify: `src/core/creative_control/scope_planner.py`（`GenerationScopeIntent` L32-46、`plan` L78-128、`_filter_chapters` L158-201、新增 blueprint 类型加载）
- Test: `tests/unit/test_scope_planner.py`（扩展）

- [ ] **Step 1：写失败测试（扩展 `test_scope_planner.py`）**

在 `tests/unit/test_scope_planner.py` 末尾追加：

```python
# ---------------------------------------------------------------- blueprint batch


@pytest.mark.asyncio
async def test_plan_blueprint_only_multi_chapter_uses_chapter_numbers():
    planner = GenerationScopePlanner()
    with patch.object(planner, "_load_locked_blueprints", new=AsyncMock(return_value=[])), \
         patch.object(planner, "_load_confirmed_blueprints", new=AsyncMock(return_value=[])):
        plan = await planner.plan(_intent(
            mode="blueprint_only", chapter_numbers=[3, 5, 1]
        ))
    assert plan.endpoint == "blueprint/generate"
    assert plan.target_chapters == [1, 3, 5]  # 排序去重
    assert plan.payload.get("chapter_numbers") == [1, 3, 5]


@pytest.mark.asyncio
async def test_plan_blueprint_only_single_chapter_still_works():
    """单章兼容：无 chapter_numbers 时退回 chapter_number。"""
    planner = GenerationScopePlanner()
    plan = await planner.plan(_intent(mode="blueprint_only", chapter_number=7))
    assert plan.endpoint == "blueprint/generate"
    assert plan.target_chapters == [7]


@pytest.mark.asyncio
async def test_plan_blueprint_only_rejects_over_50():
    planner = GenerationScopePlanner()
    with pytest.raises(ValueError, match="50"):
        await planner.plan(_intent(
            mode="blueprint_only", chapter_numbers=list(range(1, 52))
        ))


@pytest.mark.asyncio
async def test_plan_blueprint_only_filters_by_blueprint_type_control():
    """respect_locked/skip_confirmed 按 blueprint 类型 control 过滤，非 chapter 类型。"""
    planner = GenerationScopePlanner()
    with patch.object(planner, "_load_locked_blueprints", new=AsyncMock(return_value=[3])), \
         patch.object(planner, "_load_confirmed_blueprints", new=AsyncMock(return_value=[5])):
        plan = await planner.plan(_intent(
            mode="blueprint_only", chapter_numbers=[1, 3, 5, 7],
            respect_locked=True, skip_confirmed=True,
        ))
    assert plan.target_chapters == [1, 7]
    assert plan.skipped_locked == [3]
    assert plan.skipped_confirmed == [5]
```

注意：`_intent` helper 需补 `chapter_numbers=None` 默认键。先在 helper `base` dict 里加一行 `"chapter_numbers": None,`。

- [ ] **Step 2：运行确认失败**

Run: `poetry run pytest tests/unit/test_scope_planner.py -q`
Expected: FAIL — `GenerationScopeIntent` 无 `chapter_numbers` 字段 / `_load_locked_blueprints` 不存在

- [ ] **Step 3：修改 `GenerationScopeIntent` 增字段**

在 `scope_planner.py` 的 `GenerationScopeIntent`（L32）末尾 `words_per_chapter: int = 3000` 后追加：

```python
    chapter_numbers: list[int] | None = None
```

- [ ] **Step 4：修改 `plan` 的 blueprint_only 分支**

把 `scope_planner.py` L80-85 的 blueprint_only 分支替换为：

```python
        if mode == "blueprint_only":
            raw = set(intent.chapter_numbers or [])
            if intent.chapter_number is not None:
                raw.add(intent.chapter_number)
            if not raw:
                raise ValueError("blueprint_only 必须提供 chapter_number 或 chapter_numbers")
            if len(raw) > 50:
                raise ValueError("blueprint_only 单次最多 50 章")
            target = sorted(raw)
            filtered, skipped_locked, skipped_confirmed = await self._filter_chapters(
                intent, target, artifact_type="blueprint"
            )
            return ScopePlan(
                endpoint="blueprint/generate",
                payload={"chapter_numbers": filtered},
                target_chapters=filtered,
                skipped_locked=skipped_locked,
                skipped_confirmed=skipped_confirmed,
            )
```

- [ ] **Step 5：修改 `_filter_chapters` 增 `artifact_type` 参数**

把 `_filter_chapters`（L158）签名与体替换为：

```python
    async def _filter_chapters(
        self,
        intent: GenerationScopeIntent,
        target: list[int],
        *,
        artifact_type: str = "chapter",
    ) -> tuple[list[int], list[int], list[int]]:
        if not target:
            return [], [], []
        if artifact_type == "blueprint":
            locked = set(await self._load_locked_blueprints(intent.novel_id)) if intent.respect_locked else set()
            confirmed = set(await self._load_confirmed_blueprints(intent.novel_id)) if intent.skip_confirmed else set()
        else:
            locked = set(await self._load_locked_chapters(intent.novel_id)) if intent.respect_locked else set()
            confirmed = set(await self._load_confirmed_chapters(intent.novel_id)) if intent.skip_confirmed else set()
        kept = [c for c in target if c not in locked]
        skipped_confirmed = [c for c in kept if c in confirmed]
        if intent.skip_confirmed:
            kept = [c for c in kept if c not in confirmed]
        skipped_locked = [c for c in target if c in locked]
        return kept, skipped_locked, skipped_confirmed
```

- [ ] **Step 6：新增 blueprint 类型加载方法**

在 `_load_confirmed_chapters`（L201）后追加：

```python
    async def _load_locked_blueprints(self, novel_id: str) -> list[int]:
        """返回该小说所有 locked 的章号（blueprint 类型 control）。"""
        ArtifactControl, _, _ = _orm()  # noqa: N806
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactControl.artifact_id).where(
                    ArtifactControl.novel_id == novel_id,
                    ArtifactControl.artifact_type == "blueprint",
                    or_(
                        ArtifactControl.locked.is_(True),
                        ArtifactControl.control_status == "locked",
                    ),
                )
            )
            return sorted(int(r) for r in result.scalars().all() if r is not None)

    async def _load_confirmed_blueprints(self, novel_id: str) -> list[int]:
        """返回 approved 状态的章号（blueprint 类型 control）。"""
        ArtifactControl, _, _ = _orm()  # noqa: N806
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactControl.artifact_id).where(
                    ArtifactControl.novel_id == novel_id,
                    ArtifactControl.artifact_type == "blueprint",
                    ArtifactControl.control_status == "approved",
                )
            )
            return sorted(int(r) for r in result.scalars().all() if r is not None)
```

- [ ] **Step 7：修改 `GenerateScopeRequest` 模型**

在 `src/api/models/creative_control.py` 的 `GenerateScopeRequest`（L41）中：
- 在 `chapter_number` 字段后追加：

```python
    chapter_numbers: list[int] | None = Field(default=None, min_length=1)
```

- 把 `model_validator` 的 `blueprint_only` 分支（L66-68）替换为：

```python
        elif self.mode == "blueprint_only":
            if self.chapter_number is None and not self.chapter_numbers:
                raise ValueError("blueprint_only 必须提供 chapter_number 或 chapter_numbers")
        elif self.mode == "fix_quality":
            if self.chapter_number is None:
                raise ValueError("fix_quality 必须提供 chapter_number")
```

（即把原 `elif self.mode in {"continue", "blueprint_only", "fix_quality"}` 拆成两支，`continue` 仍要求 `chapter_number`。）

- [ ] **Step 8：更新 `_to_intent`**

在 `src/api/routes/creative_control.py` 找到 `_to_intent` 函数（搜索 `def _to_intent`），在构造 `GenerationScopeIntent(...)` 时追加 `chapter_numbers=request.chapter_numbers`。

- [ ] **Step 9：运行确认通过**

Run: `poetry run pytest tests/unit/test_scope_planner.py -q`
Expected: PASS（全部，含原有 + 新增 4 例）

- [ ] **Step 10：提交**

```bash
git add src/api/models/creative_control.py \
        src/core/creative_control/scope_planner.py \
        src/api/routes/creative_control.py \
        tests/unit/test_scope_planner.py
git commit -m "feat(blueprint-workbench): Intent chapter_numbers + planner 多章(T2)"
```

---

## Task 3：dispatcher blueprint_only 多章逐章明细

**Files:**
- Modify: `src/api/services/creative_control/generation_dispatch.py`（`DispatchedGeneration` L12-19、`dispatch_scope` blueprint 分支 L34-38）
- Test: `tests/unit/test_creative_generation_dispatch.py`（扩展）

- [ ] **Step 1：写失败测试（扩展 `test_creative_generation_dispatch.py`）**

在 `tests/unit/test_creative_generation_dispatch.py` 末尾追加：

```python
@pytest.mark.asyncio
async def test_blueprint_multi_chapter_dispatches_contiguous_ranges_with_per_chapter_detail():
    """blueprint_only 多章按连续区间合并投递 + 逐章 accepted/skipped 明细。"""
    manager = AsyncMock()
    manager.create_task.side_effect = ["task-a", "task-b"]
    plan = ScopePlan(
        endpoint="blueprint/generate",
        payload={"chapter_numbers": [1, 2, 4]},
        target_chapters=[1, 2, 4],
        skipped_locked=[3],
        skipped_confirmed=[],
    )
    with patch(
        "src.api.services.creative_control.generation_dispatch.get_task_manager",
        return_value=manager,
    ):
        result = await CreativeGenerationDispatcher().dispatch_scope(_novel(), 3, plan)

    # 两个连续区间 [1,2] 和 [4,4] → 两个任务
    assert result.task_ids == ["task-a", "task-b"]
    payloads = [call.kwargs["task_payload"] for call in manager.create_task.await_args_list]
    assert payloads == [
        {"novel_id": "novel-1", "chapter_start": 1, "chapter_end": 2},
        {"novel_id": "novel-1", "chapter_start": 4, "chapter_end": 4},
    ]
    # 逐章明细
    accepted_chapters = {a["chapter_number"] for a in result.accepted}
    assert accepted_chapters == {1, 2, 4}
    assert result.skipped_locked == [3]
    assert result.skipped_confirmed == []


@pytest.mark.asyncio
async def test_blueprint_dispatch_already_generating_skipped():
    """control_status=generating 的章被标 already_generating（由 planner 预计算经 plan 传入）。"""
    manager = AsyncMock()
    manager.create_task.return_value = "task-x"
    plan = ScopePlan(
        endpoint="blueprint/generate",
        payload={"chapter_numbers": [5]},
        target_chapters=[5],
    )
    with patch(
        "src.api.services.creative_control.generation_dispatch.get_task_manager",
        return_value=manager,
    ):
        result = await CreativeGenerationDispatcher().dispatch_scope(_novel(), 3, plan)
    assert {a["chapter_number"] for a in result.accepted} == {5}


@pytest.mark.asyncio
async def test_blueprint_dispatch_failed_to_enqueue_records_error():
    """入队异常的章进 failed_to_enqueue，不中断其他章。"""
    manager = AsyncMock()

    async def _boom(**kwargs):
        if kwargs.get("task_payload", {}).get("chapter_start") == 4:
            raise RuntimeError("queue down")
        return "task-ok"

    manager.create_task.side_effect = _boom
    plan = ScopePlan(
        endpoint="blueprint/generate",
        payload={"chapter_numbers": [1, 2, 4]},
        target_chapters=[1, 2, 4],
    )
    with patch(
        "src.api.services.creative_control.generation_dispatch.get_task_manager",
        return_value=manager,
    ):
        result = await CreativeGenerationDispatcher().dispatch_scope(_novel(), 3, plan)
    failed = {f["chapter_number"]: f["error"] for f in result.failed_to_enqueue}
    assert 4 in failed
    accepted = {a["chapter_number"] for a in result.accepted}
    assert accepted == {1, 2}
```

- [ ] **Step 2：运行确认失败**

Run: `poetry run pytest tests/unit/test_creative_generation_dispatch.py -q`
Expected: FAIL — `DispatchedGeneration` 无 `accepted`/`failed_to_enqueue` 属性

- [ ] **Step 3：扩展 `DispatchedGeneration` 数据类**

把 `generation_dispatch.py` 的 `DispatchedGeneration`（L12-19）替换为：

```python
@dataclass(frozen=True)
class DispatchedGeneration:
    task_id: str
    task_ids: list[str]
    task_type: str
    target_chapters: list[int]
    skipped_locked: list[int]
    skipped_confirmed: list[int]
    accepted: list[dict] = field(default_factory=list)  # [{chapter_number, task_id}]
    already_generating: list[int] = field(default_factory=list)
    failed_to_enqueue: list[dict] = field(default_factory=list)  # [{chapter_number, error}]
```

（需在文件顶部 import 补 `field`：`from dataclasses import dataclass, field`）

- [ ] **Step 4：重写 blueprint 分支为多章区间投递 + 逐章明细**

把 `dispatch_scope` 中 blueprint 分支（L34-38）替换为：

```python
        if plan.endpoint == "blueprint/generate":
            chapter_numbers = plan.payload.get("chapter_numbers")
            if chapter_numbers:
                # 多章：按连续区间合并投递
                task_type = TaskType.NOVEL_BLUEPRINT.value
                ranges = _contiguous_ranges(list(chapter_numbers))
                payloads = [
                    {"novel_id": novel_id, "chapter_start": s, "chapter_end": e}
                    for s, e in ranges
                ]
                operation_ids = [
                    f"{novel_id}:blueprint:{p['chapter_start']}-{p['chapter_end']}:{dispatch_id}"
                    for p in payloads
                ]
                generation_targets = [
                    [
                        {"artifact_type": "blueprint", "artifact_id": str(c)}
                        for c in range(p["chapter_start"], p["chapter_end"] + 1)
                    ]
                    for p in payloads
                ]
            else:
                # 单章兼容（旧 regenerate 路径）
                chapter_number = int(plan.payload["chapter_number"])
                task_type = TaskType.NOVEL_BLUEPRINT.value
                payloads = [{"novel_id": novel_id, "chapter_number": chapter_number}]
                operation_ids = [f"{novel_id}:blueprint:{chapter_number}:{dispatch_id}"]
                generation_targets = [
                    [{"artifact_type": "blueprint", "artifact_id": str(chapter_number)}]
                ]
```

然后在文件末尾（`return DispatchedGeneration(...)` 之前，即入队循环之后）构造逐章明细。把现有入队循环后的 `return DispatchedGeneration(...)` 替换为下面的逐章明细构造 + return：

```python
        # 逐章明细（blueprint_only 多章）
        accepted: list[dict] = []
        failed_to_enqueue: list[dict] = []
        if plan.endpoint == "blueprint/generate" and plan.payload.get("chapter_numbers"):
            # 建立 chapter -> task_id 映射
            chap_to_task: dict[int, str] = {}
            for payload, tid in zip(payloads, task_ids, strict=True):
                if "chapter_start" in payload:
                    for c in range(payload["chapter_start"], payload["chapter_end"] + 1):
                        chap_to_task[c] = tid
            for c in plan.target_chapters:
                tid = chap_to_task.get(c)
                if tid:
                    accepted.append({"chapter_number": c, "task_id": tid})
                else:
                    failed_to_enqueue.append({"chapter_number": c, "error": "未入队"})

        return DispatchedGeneration(
            task_id=task_ids[0],
            task_ids=task_ids,
            task_type=task_type,
            target_chapters=plan.target_chapters,
            skipped_locked=plan.skipped_locked,
            skipped_confirmed=plan.skipped_confirmed,
            accepted=accepted,
            already_generating=[],
            failed_to_enqueue=failed_to_enqueue,
        )
```

入队循环（L88-145）需包裹异常以记录 `failed_to_enqueue`。把入队循环体改为：

```python
        task_ids = []
        for payload, operation_id, gtargets in zip(payloads, operation_ids, generation_targets, strict=True):
            try:
                tid = await get_task_manager().create_task(
                    idea=novel["idea"],
                    novel_type=novel["novel_type"],
                    target_words=novel["target_words"],
                    novel_id=novel_id,
                    owner_id=owner_id,
                    task_type=task_type,
                    task_payload=payload,
                    max_attempts=get_settings().LONG_FORM_MAX_ATTEMPTS,
                    operation_id=operation_id,
                    generation_targets=gtargets,
                )
                task_ids.append(tid)
            except Exception as exc:  # noqa: BLE001 - 入队失败逐章隔离
                logger.warning("dispatch_enqueue_failed", error=str(exc), payload=payload)
                task_ids.append(None)  # placeholder，逐章明细阶段识别
```

注意：现有入队循环里 `generation_targets` 是循环内按 task_type 算的，本 Task 把它提取为循环外预计算的 `generation_targets` 列表（与 payloads/operation_ids 一一对应）。对非 blueprint 分支，保留原逻辑构造 `generation_targets`：把原 `generation_targets = [...]` 的分支判断挪到循环前，产出 `generation_targets: list[list[dict]]`。完整重写 `dispatch_scope` 见 Step 4b。

- [ ] **Step 4b：完整重写 `dispatch_scope`（避免分支错位）**

把 `dispatch_scope` 方法整体替换为下面完整版本（保留原有非 blueprint 分支行为不变，仅 blueprint 分支多章化 + 入队异常隔离 + 逐章明细）：

```python
    async def dispatch_scope(
        self,
        novel: dict,
        owner_id: int,
        plan: ScopePlan,
    ) -> DispatchedGeneration:
        novel_id = novel["novel_id"]
        dispatch_id = uuid4().hex
        control_target = plan.payload.get("_control_target")
        payloads: list[dict] = []
        operation_ids: list[str] = []
        task_type: str = ""

        if plan.endpoint == "blueprint/generate":
            chapter_numbers = plan.payload.get("chapter_numbers")
            if chapter_numbers:
                task_type = TaskType.NOVEL_BLUEPRINT.value
                ranges = _contiguous_ranges(list(chapter_numbers))
                payloads = [
                    {"novel_id": novel_id, "chapter_start": s, "chapter_end": e}
                    for s, e in ranges
                ]
                operation_ids = [
                    f"{novel_id}:blueprint:{p['chapter_start']}-{p['chapter_end']}:{dispatch_id}"
                    for p in payloads
                ]
            else:
                chapter_number = int(plan.payload["chapter_number"])
                task_type = TaskType.NOVEL_BLUEPRINT.value
                payloads = [{"novel_id": novel_id, "chapter_number": chapter_number}]
                operation_ids = [f"{novel_id}:blueprint:{chapter_number}:{dispatch_id}"]
        elif plan.endpoint == "auto-improve":
            chapter_number = int(plan.payload["chapter_number"])
            task_type = TaskType.NOVEL_QUALITY_FIX.value
            payloads = [{
                "novel_id": novel_id, "chapter_number": chapter_number,
                "issue_ids": list(plan.payload.get("issue_ids") or []),
            }]
            operation_ids = [f"{novel_id}:quality-fix:{chapter_number}:{dispatch_id}"]
        elif plan.endpoint == "generate-volume-outline":
            volume_number = int(plan.payload["volume_number"])
            task_type = TaskType.NOVEL_VOLUME_OUTLINE.value
            payloads = [{"novel_id": novel_id, "volume_number": volume_number}]
            operation_ids = [f"{novel_id}:volume-outline:{volume_number}:{dispatch_id}"]
        elif plan.endpoint in {"generate-chapters", "generate-volume"} and not (
            plan.skipped_locked or plan.skipped_confirmed
        ) and plan.endpoint == "generate-volume":
            volume_number = int(plan.payload["volume_number"])
            task_type = TaskType.NOVEL_VOLUME.value
            payloads = [{"novel_id": novel_id, "volume_number": volume_number}]
            operation_ids = [f"{novel_id}:volume:{volume_number}:{dispatch_id}"]
        elif plan.endpoint in {"generate-chapters", "generate-volume"}:
            if not plan.target_chapters:
                raise ValueError("生成范围没有可执行章节")
            task_type = TaskType.NOVEL_CHAPTERS.value
            ranges = _contiguous_ranges(plan.target_chapters)
            payloads = [
                {"novel_id": novel_id, "chapter_start": s, "chapter_end": e}
                for s, e in ranges
            ]
            operation_ids = [
                f"{novel_id}:chapters:{p['chapter_start']}-{p['chapter_end']}:{dispatch_id}"
                for p in payloads
            ]
        else:
            raise ValueError(f"暂不支持执行生成端点: {plan.endpoint}")

        # generation_targets 每个任务一组
        generation_targets_list: list[list[dict]] = []
        for payload in payloads:
            if control_target is not None:
                gts = [dict(control_target)]
                if (
                    task_type in {TaskType.NOVEL_CHAPTERS.value, TaskType.NOVEL_QUALITY_FIX.value}
                    and str(control_target["artifact_type"]) != "chapter"
                ):
                    gts.append({
                        "artifact_type": "chapter",
                        "artifact_id": str(payload.get("chapter_number") or payload.get("chapter_start")),
                    })
            elif task_type == TaskType.NOVEL_CHAPTERS.value:
                gts = [
                    {"artifact_type": "chapter", "artifact_id": str(c)}
                    for c in range(int(payload["chapter_start"]), int(payload["chapter_end"]) + 1)
                ]
            elif task_type == TaskType.NOVEL_VOLUME.value:
                gts = [
                    {"artifact_type": "chapter", "artifact_id": str(c)}
                    for c in plan.target_chapters
                ]
            elif task_type == TaskType.NOVEL_BLUEPRINT.value:
                if "chapter_number" in payload:
                    gts = [{"artifact_type": "blueprint", "artifact_id": str(payload["chapter_number"])}]
                else:
                    gts = [
                        {"artifact_type": "blueprint", "artifact_id": str(c)}
                        for c in range(int(payload["chapter_start"]), int(payload["chapter_end"]) + 1)
                    ]
            elif task_type == TaskType.NOVEL_QUALITY_FIX.value:
                gts = [{"artifact_type": "quality", "artifact_id": str(payload["chapter_number"])}]
            else:
                gts = [{"artifact_type": "volume_outline", "artifact_id": str(payload["volume_number"])}]
            generation_targets_list.append(gts)

        task_ids: list[str | None] = []
        for payload, operation_id, gts in zip(payloads, operation_ids, generation_targets_list, strict=True):
            try:
                tid = await get_task_manager().create_task(
                    idea=novel["idea"],
                    novel_type=novel["novel_type"],
                    target_words=novel["target_words"],
                    novel_id=novel_id,
                    owner_id=owner_id,
                    task_type=task_type,
                    task_payload=payload,
                    max_attempts=get_settings().LONG_FORM_MAX_ATTEMPTS,
                    operation_id=operation_id,
                    generation_targets=gts,
                )
                task_ids.append(tid)
            except Exception as exc:  # noqa: BLE001 - 入队失败逐章隔离
                logger.warning("dispatch_enqueue_failed", error=str(exc), payload=payload)
                task_ids.append(None)

        # 逐章明细（blueprint_only 多章）
        accepted: list[dict] = []
        failed_to_enqueue: list[dict] = []
        if plan.endpoint == "blueprint/generate" and plan.payload.get("chapter_numbers"):
            chap_to_task: dict[int, str] = {}
            for payload, tid in zip(payloads, task_ids, strict=True):
                if tid is None or "chapter_start" not in payload:
                    continue
                for c in range(payload["chapter_start"], payload["chapter_end"] + 1):
                    chap_to_task[c] = tid
            for c in plan.target_chapters:
                tid = chap_to_task.get(c)
                if tid:
                    accepted.append({"chapter_number": c, "task_id": tid})
                else:
                    failed_to_enqueue.append({"chapter_number": c, "error": "未入队"})

        real_task_ids = [t for t in task_ids if t]
        return DispatchedGeneration(
            task_id=real_task_ids[0] if real_task_ids else "",
            task_ids=real_task_ids,
            task_type=task_type,
            target_chapters=plan.target_chapters,
            skipped_locked=plan.skipped_locked,
            skipped_confirmed=plan.skipped_confirmed,
            accepted=accepted,
            already_generating=[],
            failed_to_enqueue=failed_to_enqueue,
        )
```

注意：`generation_dispatch.py` 顶部需补 `import structlog` 与 `logger = structlog.get_logger(__name__)`（若已存在则跳过）。检查文件头部，若无则加。

- [ ] **Step 5：修改 `plan_generate_scope` 路由透传逐章明细**

在 `src/api/routes/creative_control.py` 的 `plan_generate_scope`（L514）的 return（L533-541）追加字段：

```python
    return {
        "task_id": dispatched.task_id,
        "task_ids": getattr(dispatched, "task_ids", [dispatched.task_id]),
        "task_type": dispatched.task_type,
        "target_chapters": dispatched.target_chapters,
        "skipped_locked": dispatched.skipped_locked,
        "skipped_confirmed": dispatched.skipped_confirmed,
        "accepted": getattr(dispatched, "accepted", []),
        "already_generating": getattr(dispatched, "already_generating", []),
        "failed_to_enqueue": getattr(dispatched, "failed_to_enqueue", []),
    }
```

（用 `getattr` 防御旧 `DispatchedGeneration` 无字段时的兼容，但 Task 3 已加字段，可直接用 `dispatched.accepted`。统一用 `getattr` 更安全。）

- [ ] **Step 6：运行确认通过**

Run: `poetry run pytest tests/unit/test_creative_generation_dispatch.py -q`
Expected: PASS（全部，含原有 + 新增 3 例）

- [ ] **Step 7：提交**

```bash
git add src/api/services/creative_control/generation_dispatch.py \
        src/api/routes/creative_control.py \
        tests/unit/test_creative_generation_dispatch.py
git commit -m "feat(blueprint-workbench): dispatcher 多章逐章明细(T3)"
```

---

## Task 4：废弃同步直写路由行为（单章生成走后台任务）

**Files:**
- Modify: `src/api/routes/chapters.py`（`generate_blueprint` 路由 L318-350）
- Test: `tests/unit/test_blueprint_workbench_api_contract.py`（部分，本任务先加单章生成异步用例；其余路由用例在 Task 6）

- [ ] **Step 1：写失败测试（新建 `test_blueprint_workbench_api_contract.py`，先只放单章生成异步用例）**

```python
"""章节蓝图工作台路由契约测试。

直调路由 async 函数 + mock service，断言 HTTPException。
禁止真实调用 LLM。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.routes import chapters as chapters_mod
from src.core.auth_models import User


def _user():
    u = MagicMock()
    u.id = 1
    return u


@pytest.mark.asyncio
async def test_generate_blueprint_route_dispatches_background_task():
    """POST /chapters/{n}/blueprint/generate 改为投递后台 NOVEL_BLUEPRINT 任务，
    不再同步直写，返回 task_id + status=generating（URL 保留，行为异步）。"""
    novel = {"novel_id": "novel-1", "title": "T", "owner_id": 1}
    with (
        patch.object(chapters_mod, "verify_novel_owner", new=AsyncMock(return_value=novel)),
        patch.object(chapters_mod, "get_current_user", new=MagicMock()),
        patch("src.api.routes.chapters.verify_novel_owner", new=AsyncMock(return_value=novel)),
    ):
        # 路由内部应构造 ScopePlan 并 dispatch；mock dispatcher
        fake_dispatched = MagicMock()
        fake_dispatched.task_id = "task-1"
        fake_dispatched.task_ids = ["task-1"]
        fake_dispatched.task_type = "novel_blueprint"
        fake_dispatched.target_chapters = [5]
        fake_dispatched.accepted = [{"chapter_number": 5, "task_id": "task-1"}]
        fake_dispatched.skipped_locked = []
        fake_dispatched.skipped_confirmed = []
        fake_dispatched.already_generating = []
        fake_dispatched.failed_to_enqueue = []
        with (
            patch("src.api.routes.chapters.CreativeGenerationDispatcher") as DispCls,
            patch("src.api.routes.chapters.get_novel_manager") as mgr,
            patch("src.api.routes.chapters.get_db_session") as dbctx,
        ):
            DispCls.return_value.dispatch_scope = AsyncMock(return_value=fake_dispatched)
            mgr.return_value.get_novel = AsyncMock(return_value=novel)
            # mock 一个 async context manager 返回带 outline 的 session
            session = AsyncMock()
            res = MagicMock()
            res.scalar_one_or_none.return_value = MagicMock(content={"chapter": 5})
            session.execute = AsyncMock(return_value=res)

            class _Ctx:
                async def __aenter__(self_inner):
                    return session

                async def __aexit__(self_inner, *a):
                    return False

            dbctx.return_value = _Ctx()
            result = await chapters_mod.generate_blueprint("novel-1", 5, _user())

    assert result["status"] == "generating"
    assert result["task_id"] == "task-1"
    assert result["task_type"] == "novel_blueprint"
```

- [ ] **Step 2：运行确认失败**

Run: `poetry run pytest tests/unit/test_blueprint_workbench_api_contract.py::test_generate_blueprint_route_dispatches_background_task -q`
Expected: FAIL — 当前路由返回同步 blueprint dict（无 `status`/`task_id` 字段），assert 失败或 `CreativeGenerationDispatcher` 未在 chapters 模块导入

- [ ] **Step 3：重写 `generate_blueprint` 路由为投递后台任务**

把 `src/api/routes/chapters.py` 的 `generate_blueprint`（L318-350）整体替换为：

```python
@router.post(
    "/{novel_id}/chapters/{chapter_number}/blueprint/generate",
    status_code=202,
)
async def generate_blueprint(novel_id: str, chapter_number: int, current_user: User = Depends(get_current_user)):
    """触发蓝图生成（URL 保留向后兼容；行为已由同步直写改为投递后台 NOVEL_BLUEPRINT 任务）。

    统一与批量生成路径一致：后台任务产 ArtifactVersion 快照 + version_number 自增。
    不再同步调 BlueprintService.generate_blueprint(persist=True)。
    """
    novel = await verify_novel_owner(novel_id, current_user)
    from sqlalchemy import select

    from src.api.models.db_models import Outline
    from src.api.services.creative_control.generation_dispatch import (
        CreativeGenerationDispatcher,
    )
    from src.core.creative_control.scope_planner import ScopePlan
    from src.core.database import get_db_session

    async with get_db_session() as session:
        stmt = select(Outline).where(
            Outline.novel_id == novel_id,
            Outline.level == "chapter",
            Outline.chapter_number == chapter_number,
        )
        result = await session.execute(stmt)
        outline = result.scalar_one_or_none()

    _ = (
        outline.content
        if outline
        else {"chapter": chapter_number, "title": f"第{chapter_number}章"}
    )  # outline 仅用于占位；后台任务自行从 DB 取上下文

    plan = ScopePlan(
        endpoint="blueprint/generate",
        payload={"chapter_numbers": [chapter_number]},
        target_chapters=[chapter_number],
    )
    dispatched = await CreativeGenerationDispatcher().dispatch_scope(
        novel, current_user.id, plan
    )
    return {
        "status": "generating",
        "task_id": dispatched.task_id,
        "task_ids": getattr(dispatched, "task_ids", [dispatched.task_id]),
        "task_type": dispatched.task_type,
        "target_chapters": dispatched.target_chapters,
        "accepted": getattr(dispatched, "accepted", []),
        "skipped_locked": getattr(dispatched, "skipped_locked", []),
        "skipped_confirmed": getattr(dispatched, "skipped_confirmed", []),
        "already_generating": getattr(dispatched, "already_generating", []),
        "failed_to_enqueue": getattr(dispatched, "failed_to_enqueue", []),
    }
```

注意：原路由 `status_code=201` 改为 `202`（异步任务接受语义）。`BlueprintService` 与 `generate_blueprint` 的 import 不再需要（路由不再同步调），移除函数内 `from src.api.services.content.blueprint_service import BlueprintService`。

- [ ] **Step 4：运行确认通过**

Run: `poetry run pytest tests/unit/test_blueprint_workbench_api_contract.py::test_generate_blueprint_route_dispatches_background_task -q`
Expected: PASS

- [ ] **Step 5：确认既有 blueprint 测试不回归**

Run: `poetry run pytest tests/unit/test_blueprint_service.py tests/unit/test_creative_control_api_contract.py -q`
Expected: PASS（既有契约测试若断言旧 201 同步行为，需更新：见 Step 6）

- [ ] **Step 6：如有旧契约断言 201/同步返回，更新**

检索 `tests/unit/test_creative_control_api_contract.py` 是否断言 `generate_blueprint` 返回 201 或 blueprint dict。若有，把断言改为 `202` + `status=="generating"`。若无则跳过。

Run: `grep -n "blueprint/generate\|generate_blueprint" tests/unit/test_creative_control_api_contract.py`
若命中且断言旧行为，更新断言后重跑 `poetry run pytest tests/unit/test_creative_control_api_contract.py -q`。

- [ ] **Step 7：提交**

```bash
git add src/api/routes/chapters.py \
        tests/unit/test_blueprint_workbench_api_contract.py
git commit -m "feat(blueprint-workbench): 单章生成路由改投后台任务(T4)"
```

---

## Task 5：`BlueprintWorkbenchService` 章节摘要聚合 + workspace + options

**Files:**
- Create: `src/api/services/content/blueprint_workbench_service.py`
- Test: `tests/unit/test_blueprint_workbench_service.py`

- [ ] **Step 1：写失败测试 `test_blueprint_workbench_service.py`**

```python
"""BlueprintWorkbenchService 单元测试。

聚合查询：章节摘要列表（含未生成）+ workspace 详情 + options。
所有 DB 交互通过 mock session 注入，禁止真实 LLM/DB。
"""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.services.content.blueprint_workbench_service import (
    BlueprintWorkbenchService,
)


def _row(**kw):
    """构造一个 mock ORM 行，按属性名访问。"""
    m = MagicMock()
    for k, v in kw.items():
        setattr(m, k, v)
    return m


def _session_ctx(rows_by_stmt=None):
    """构造 async session context manager；rows_by_stmt: list[返回 result]。"""
    session = AsyncMock()

    results = list(rows_by_stmt or [])

    async def execute(stmt, *a, **kw):
        return results.pop(0) if results else MagicMock()

    session.execute = AsyncMock(side_effect=execute)

    class _Ctx:
        async def __aenter__(self):
            return session

        async def __aexit__(self, *a):
            return False

    return _Ctx, session


@pytest.mark.asyncio
async def test_list_summaries_includes_chapters_without_blueprint():
    """Outline 有章号但无 ChapterBlueprint → 仍出现且 has_blueprint=false。"""
    svc = BlueprintWorkbenchService()
    # mock _load_* 方法返回原始 ORM 行集合
    with (
        patch.object(svc, "_load_chapter_outlines", new=AsyncMock(return_value=[
            _row(chapter_number=1, volume_number=1, content={"title": "首章"}),
            _row(chapter_number=2, volume_number=1, content={"title": "次章"}),
        ])),
        patch.object(svc, "_load_active_blueprints", new=AsyncMock(return_value={
            1: _row(chapter_number=1, version_number=3, updated_at="t1"),
        })),
        patch.object(svc, "_load_chapters", new=AsyncMock(return_value={
            2: _row(chapter_number=2, title="次章正文", quality_status="verified"),
        })),
        patch.object(svc, "_load_volumes", new=AsyncMock(return_value=[])),
        patch.object(svc, "_load_blueprint_controls", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_generating_chapters", new=AsyncMock(return_value=set())),
    ):
        result = await svc.list_chapter_summaries("novel-1")

    items = result["items"]
    assert len(items) == 2
    ch1 = next(i for i in items if i["chapter_number"] == 1)
    ch2 = next(i for i in items if i["chapter_number"] == 2)
    assert ch1["has_blueprint"] is True
    assert ch1["blueprint_version"] == 3
    assert ch2["has_blueprint"] is False
    assert ch2["blueprint_version"] is None
    assert ch2["has_chapter"] is True
    assert ch2["quality_status"] == "verified"
    # 章号排序
    assert [i["chapter_number"] for i in items] == [1, 2]
    assert result["total"] == 2


@pytest.mark.asyncio
async def test_list_summaries_dedup_by_chapter_number():
    """多源同章号合并为一行。"""
    svc = BlueprintWorkbenchService()
    with (
        patch.object(svc, "_load_chapter_outlines", new=AsyncMock(return_value=[
            _row(chapter_number=5, volume_number=1, content={"title": "大纲"}),
        ])),
        patch.object(svc, "_load_active_blueprints", new=AsyncMock(return_value={
            5: _row(chapter_number=5, version_number=1, updated_at="t"),
        ])),
        patch.object(svc, "_load_chapters", new=AsyncMock(return_value={
            5: _row(chapter_number=5, title="正文", quality_status=None),
        ])),
        patch.object(svc, "_load_volumes", new=AsyncMock(return_value=[])),
        patch.object(svc, "_load_blueprint_controls", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_generating_chapters", new=AsyncMock(return_value=set())),
    ):
        result = await svc.list_chapter_summaries("novel-1")
    assert len(result["items"]) == 1
    item = result["items"][0]
    assert item["has_outline"] is True
    assert item["has_blueprint"] is True
    assert item["has_chapter"] is True


@pytest.mark.asyncio
async def test_list_summaries_filter_by_volume():
    svc = BlueprintWorkbenchService()
    with (
        patch.object(svc, "_load_chapter_outlines", new=AsyncMock(return_value=[
            _row(chapter_number=1, volume_number=1, content={}),
            _row(chapter_number=2, volume_number=2, content={}),
        ])),
        patch.object(svc, "_load_active_blueprints", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_chapters", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_volumes", new=AsyncMock(return_value=[])),
        patch.object(svc, "_load_blueprint_controls", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_generating_chapters", new=AsyncMock(return_value=set())),
    ):
        result = await svc.list_chapter_summaries("novel-1", volume_number=2)
    assert [i["chapter_number"] for i in result["items"]] == [2]


@pytest.mark.asyncio
async def test_list_summaries_page_size_capped_at_100():
    svc = BlueprintWorkbenchService()
    outlines = [_row(chapter_number=i, volume_number=1, content={}) for i in range(1, 151)]
    with (
        patch.object(svc, "_load_chapter_outlines", new=AsyncMock(return_value=outlines)),
        patch.object(svc, "_load_active_blueprints", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_chapters", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_volumes", new=AsyncMock(return_value=[])),
        patch.object(svc, "_load_blueprint_controls", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_generating_chapters", new=AsyncMock(return_value=set())),
    ):
        result = await svc.list_chapter_summaries("novel-1", page=1, page_size=200)
    assert result["page_size"] == 100
    assert len(result["items"]) == 100
    assert result["total"] == 150


@pytest.mark.asyncio
async def test_list_summaries_status_counts():
    svc = BlueprintWorkbenchService()
    # ch1 有蓝图无 control → draft；ch2 无蓝图 → not_generated
    with (
        patch.object(svc, "_load_chapter_outlines", new=AsyncMock(return_value=[
            _row(chapter_number=1, volume_number=1, content={}),
            _row(chapter_number=2, volume_number=1, content={}),
        ])),
        patch.object(svc, "_load_active_blueprints", new=AsyncMock(return_value={
            1: _row(chapter_number=1, version_number=1, updated_at="t"),
        ])),
        patch.object(svc, "_load_chapters", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_volumes", new=AsyncMock(return_value=[])),
        patch.object(svc, "_load_blueprint_controls", new=AsyncMock(return_value={})),
        patch.object(svc, "_load_generating_chapters", new=AsyncMock(return_value=set())),
    ):
        result = await svc.list_chapter_summaries("novel-1")
    assert result["status_counts"]["draft"] == 1
    assert result["status_counts"]["not_generated"] == 1


@pytest.mark.asyncio
async def test_get_workspace_aggregates_all_fields():
    svc = BlueprintWorkbenchService()
    with (
        patch.object(svc, "_get_blueprint_dict", new=AsyncMock(return_value={"chapter_type": "climax"})),
        patch.object(svc, "_get_control_dict", new=AsyncMock(return_value={"control_status": "draft", "version": 1, "locked": False})),
        patch.object(svc, "_get_versions_list", new=AsyncMock(return_value=[{"version_number": 1}])),
        patch.object(svc, "_get_chapter_outline_dict", new=AsyncMock(return_value={"content": {"plot": "x"}})),
        patch.object(svc, "_get_previous_state_delta", new=AsyncMock(return_value={"events": []})),
        patch.object(svc, "_get_chapter_summary", new=AsyncMock(return_value={"status": "draft", "word_count": 0, "quality_status": None})),
        patch.object(svc, "_get_available_characters", new=AsyncMock(return_value=[{"id": 1, "name": "主角", "role": "protagonist"}])),
    ):
        ws = await svc.get_workspace("novel-1", 5)
    assert ws["blueprint"]["chapter_type"] == "climax"
    assert ws["control"]["version"] == 1
    assert ws["versions"] == [{"version_number": 1}]
    assert ws["outline"]["content"]["plot"] == "x"
    assert ws["available_characters"][0]["name"] == "主角"
    assert ws["quality_status"] is None


@pytest.mark.asyncio
async def test_get_workspace_blueprint_null_when_missing():
    svc = BlueprintWorkbenchService()
    with (
        patch.object(svc, "_get_blueprint_dict", new=AsyncMock(return_value=None)),
        patch.object(svc, "_get_control_dict", new=AsyncMock(return_value={"control_status": "draft", "version": 1, "locked": False})),
        patch.object(svc, "_get_versions_list", new=AsyncMock(return_value=[])),
        patch.object(svc, "_get_chapter_outline_dict", new=AsyncMock(return_value=None)),
        patch.object(svc, "_get_previous_state_delta", new=AsyncMock(return_value=None)),
        patch.object(svc, "_get_chapter_summary", new=AsyncMock(return_value=None)),
        patch.object(svc, "_get_available_characters", new=AsyncMock(return_value=[])),
    ):
        ws = await svc.get_workspace("novel-1", 9)
    assert ws["blueprint"] is None
    assert ws["versions"] == []
    assert ws["outline"] is None


def test_get_options_returns_enum_values():
    svc = BlueprintWorkbenchService()
    opts = svc.get_options()
    assert "main_advance" in opts["chapter_type"]
    assert "fast" in opts["pacing_target"]
    assert "plant" in opts["foreshadow_action"]
```

- [ ] **Step 2：运行确认失败**

Run: `poetry run pytest tests/unit/test_blueprint_workbench_service.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.api.services.content.blueprint_workbench_service'`

- [ ] **Step 3：实现 `blueprint_workbench_service.py`**

```python
"""章节蓝图工作台聚合服务。

职责：
- list_chapter_summaries：以 chapter 级 Outline 为主轴合并四源（Outline/ChapterBlueprint/
  Chapter/Volume），按 chapter_number 去重，服务端分页（page_size 上限 100），返回统一摘要
  含 control_status/locked/quality_status。能发现「未生成蓝图」的章节。
- get_workspace：单章详情聚合（blueprint+control+versions+outline+previous_state_delta+
  chapter_summary+quality_status+available_characters），单事务，子查询失败降级 null。
- get_options：蓝图字段枚举（取自 blueprint_enums，无 DB）。

不直接修改 ArtifactControl/版本表，全部经现有 service 读取。
设计依据：docs/superpowers/specs/2026-07-22-chapter-blueprint-workbench-design.md
"""

from __future__ import annotations

from typing import Any

import structlog
from sqlalchemy import select

from src.api.models.db_models import (
    ArtifactControl,
    Chapter,
    ChapterBlueprint,
    Outline,
    Volume,
)
from src.api.services.content.blueprint_service import BlueprintService
from src.api.services.content.character_service import get_character_service
from src.core.creative_control.artifact_version_store import ArtifactVersionStore
from src.core.creative_control.blueprint_enums import BLUEPRINT_FIELD_OPTIONS
from src.core.creative_control.control_service import CreativeControlService
from src.core.database import get_db_session

logger = structlog.get_logger(__name__)

_MAX_PAGE_SIZE = 100
_DEFAULT_PAGE_SIZE = 50
_BLUEPRINT_BATCH_LIMIT = 50


class BlueprintWorkbenchService:
    """章节蓝图工作台聚合查询入口。"""

    # ----------------------------------------------------- 章节摘要列表

    async def list_chapter_summaries(
        self,
        novel_id: str,
        *,
        volume_number: int | None = None,
        status: str | None = None,
        search: str | None = None,
        chapter_start: int | None = None,
        chapter_end: int | None = None,
        page: int = 1,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> dict[str, Any]:
        page = max(1, page)
        page_size = min(max(1, page_size), _MAX_PAGE_SIZE)

        outlines = await self._load_chapter_outlines(novel_id, volume_number)
        blueprints = await self._load_active_blueprints(novel_id)
        chapters = await self._load_chapters(novel_id)
        volumes = await self._load_volumes(novel_id)
        controls = await self._load_blueprint_controls(novel_id)
        generating = await self._load_generating_chapters(novel_id)

        # 合并章号集合（Outline 为主轴，Blueprint/Chapter/Volume 补齐）
        chapter_set: set[int] = {o.chapter_number for o in outlines}
        chapter_set.update(blueprints.keys())
        chapter_set.update(chapters.keys())
        for v in volumes:
            if v.chapter_start and v.chapter_end:
                chapter_set.update(range(v.chapter_start, v.chapter_end + 1))

        # volume 推导：Outline 无 volume_number 时按 Volume 范围
        vol_map: dict[int, int] = {}
        for v in volumes:
            if v.chapter_start and v.chapter_end:
                for c in range(v.chapter_start, v.chapter_end + 1):
                    vol_map[c] = v.volume_number

        all_items: list[dict[str, Any]] = []
        for c in sorted(chapter_set):
            if chapter_start is not None and c < chapter_start:
                continue
            if chapter_end is not None and c > chapter_end:
                continue
            outline = next((o for o in outlines if o.chapter_number == c), None)
            bp = blueprints.get(c)
            ch = chapters.get(c)
            ctrl = controls.get(c)
            vol = (getattr(outline, "volume_number", None) if outline else None) or vol_map.get(c)

            title = None
            if ch is not None and getattr(ch, "title", None):
                title = ch.title
            elif outline is not None:
                content = getattr(outline, "content", None) or {}
                title = content.get("title") if isinstance(content, dict) else None

            if search:
                if title is None or search not in title:
                    continue

            has_blueprint = bp is not None
            control_status = self._derive_status(
                ctrl, has_blueprint, c in generating
            )
            if status and control_status != status:
                continue

            all_items.append({
                "chapter_number": c,
                "volume_number": vol,
                "title": title,
                "has_outline": outline is not None,
                "has_blueprint": has_blueprint,
                "has_chapter": ch is not None,
                "blueprint_version": getattr(bp, "version_number", None) if bp else None,
                "control_status": control_status,
                "locked": bool(getattr(ctrl, "locked", False)) if ctrl else False,
                "quality_status": getattr(ch, "quality_status", None) if ch else None,
                "updated_at": getattr(bp, "updated_at", None) if bp else None,
            })

        total = len(all_items)
        offset = (page - 1) * page_size
        page_items = all_items[offset:offset + page_size]

        status_counts: dict[str, int] = {}
        for it in all_items:
            status_counts[it["control_status"]] = status_counts.get(it["control_status"], 0) + 1

        return {
            "items": page_items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "status_counts": status_counts,
        }

    @staticmethod
    def _derive_status(ctrl: Any | None, has_blueprint: bool, generating: bool) -> str:
        """章节摘要状态推导（映射提示词 8 态 + not_generated 派生态）。"""
        if ctrl is None:
            return "generating" if generating else ("not_generated" if not has_blueprint else "generated")
        cs = getattr(ctrl, "control_status", None)
        if generating or cs == "generating":
            return "generating"
        if cs == "failed":
            return "failed"
        if getattr(ctrl, "locked", False) or cs == "locked":
            return "locked"
        if cs == "approved":
            return "confirmed"
        if cs == "stale":
            return "stale"
        if cs == "edited":
            return "edited"
        if cs == "generated":
            return "generated"
        if cs == "draft":
            return "draft" if has_blueprint else "not_generated"
        return "draft" if has_blueprint else "not_generated"

    # ----------------------------------------------------- 单章 workspace

    async def get_workspace(self, novel_id: str, chapter_number: int) -> dict[str, Any]:
        workspace: dict[str, Any] = {
            "blueprint": None,
            "control": None,
            "versions": [],
            "outline": None,
            "previous_state_delta": None,
            "chapter_summary": None,
            "quality_status": None,
            "available_characters": [],
        }
        async with get_db_session() as session:
            try:
                workspace["blueprint"] = await self._get_blueprint_dict(novel_id, chapter_number)
            except Exception as exc:  # noqa: BLE001 - 子查询降级
                logger.warning("workspace_blueprint_failed", error=str(exc))
            try:
                workspace["control"] = await self._get_control_dict(novel_id, chapter_number)
            except Exception as exc:  # noqa: BLE001
                logger.warning("workspace_control_failed", error=str(exc))
            try:
                workspace["versions"] = await self._get_versions_list(novel_id, chapter_number)
            except Exception as exc:  # noqa: BLE001
                logger.warning("workspace_versions_failed", error=str(exc))
            try:
                workspace["outline"] = await self._get_chapter_outline_dict(novel_id, chapter_number)
            except Exception as exc:  # noqa: BLE001
                logger.warning("workspace_outline_failed", error=str(exc))
            try:
                workspace["previous_state_delta"] = await self._get_previous_state_delta(novel_id, chapter_number)
            except Exception as exc:  # noqa: BLE001
                logger.warning("workspace_prev_delta_failed", error=str(exc))
            try:
                chapter_summary = await self._get_chapter_summary(novel_id, chapter_number)
                workspace["chapter_summary"] = chapter_summary
                workspace["quality_status"] = chapter_summary.get("quality_status") if chapter_summary else None
            except Exception as exc:  # noqa: BLE001
                logger.warning("workspace_chapter_failed", error=str(exc))
            try:
                workspace["available_characters"] = await self._get_available_characters(novel_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning("workspace_characters_failed", error=str(exc))
        return workspace

    def get_options(self) -> dict[str, list[str]]:
        return BLUEPRINT_FIELD_OPTIONS

    # ----------------------------------------------------- 子查询（可 mock）

    async def _get_blueprint_dict(self, novel_id: str, chapter_number: int) -> dict | None:
        return await BlueprintService().get_blueprint(novel_id, chapter_number)

    async def _get_control_dict(self, novel_id: str, chapter_number: int) -> dict | None:
        return await CreativeControlService().get_or_create(
            novel_id, "blueprint", str(chapter_number), stage=6
        )

    async def _get_versions_list(self, novel_id: str, chapter_number: int) -> list[dict]:
        return await ArtifactVersionStore().list_versions(
            novel_id, "blueprint", str(chapter_number)
        )

    async def _get_chapter_outline_dict(self, novel_id: str, chapter_number: int) -> dict | None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Outline).where(
                    Outline.novel_id == novel_id,
                    Outline.level == "chapter",
                    Outline.chapter_number == chapter_number,
                )
            )
            o = result.scalar_one_or_none()
            if o is None:
                return None
            return {"id": o.id, "volume_number": o.volume_number,
                    "chapter_number": o.chapter_number, "content": o.content, "status": o.status}

    async def _get_previous_state_delta(self, novel_id: str, chapter_number: int) -> dict | None:
        if chapter_number <= 1:
            return None
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter.state_delta).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number - 1,
                ).order_by(Chapter.id.desc()).limit(1)
            )
            row = result.first()
            return row.state_delta if row else None

    async def _get_chapter_summary(self, novel_id: str, chapter_number: int) -> dict | None:
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(
                    Chapter.novel_id == novel_id,
                    Chapter.chapter_number == chapter_number,
                ).order_by(Chapter.id.desc()).limit(1)
            )
            c = result.scalar_one_or_none()
            if c is None:
                return None
            return {"status": c.status, "word_count": c.word_count,
                    "quality_status": c.quality_status, "title": c.title}

    async def _get_available_characters(self, novel_id: str) -> list[dict]:
        rows = await get_character_service().list_characters(novel_id)
        return [{"id": r["id"], "name": r["name"], "role": r.get("role")} for r in rows]

    # ----------------------------------------------------- 批量加载（可 mock）

    async def _load_chapter_outlines(self, novel_id: str, volume_number: int | None = None) -> list[Any]:
        async with get_db_session() as session:
            query = select(Outline).where(
                Outline.novel_id == novel_id,
                Outline.level == "chapter",
            )
            if volume_number is not None:
                query = query.where(Outline.volume_number == volume_number)
            query = query.order_by(Outline.chapter_number)
            result = await session.execute(query)
            return list(result.scalars().all())

    async def _load_active_blueprints(self, novel_id: str) -> dict[int, Any]:
        async with get_db_session() as session:
            result = await session.execute(
                select(ChapterBlueprint).where(
                    ChapterBlueprint.novel_id == novel_id,
                    ChapterBlueprint.is_active.is_(True),
                )
            )
            return {b.chapter_number: b for b in result.scalars().all()}

    async def _load_chapters(self, novel_id: str) -> dict[int, Any]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Chapter).where(Chapter.novel_id == novel_id)
            )
            latest: dict[int, Any] = {}
            for c in result.scalars().all():
                prev = latest.get(c.chapter_number)
                if prev is None or c.id > prev.id:
                    latest[c.chapter_number] = c
            return latest

    async def _load_volumes(self, novel_id: str) -> list[Any]:
        async with get_db_session() as session:
            result = await session.execute(
                select(Volume).where(Volume.novel_id == novel_id)
            )
            return list(result.scalars().all())

    async def _load_blueprint_controls(self, novel_id: str) -> dict[int, Any]:
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactControl).where(
                    ArtifactControl.novel_id == novel_id,
                    ArtifactControl.artifact_type == "blueprint",
                )
            )
            return {int(r.artifact_id): r for r in result.scalars().all() if r.artifact_id is not None}

    async def _load_generating_chapters(self, novel_id: str) -> set[int]:
        """返回 control_status=generating 的章号。"""
        async with get_db_session() as session:
            result = await session.execute(
                select(ArtifactControl.artifact_id).where(
                    ArtifactControl.novel_id == novel_id,
                    ArtifactControl.artifact_type == "blueprint",
                    ArtifactControl.control_status == "generating",
                )
            )
            return {int(r) for r in result.scalars().all() if r is not None}
```

- [ ] **Step 4：运行确认通过**

Run: `poetry run pytest tests/unit/test_blueprint_workbench_service.py -q`
Expected: PASS（8 例）

- [ ] **Step 5：提交**

```bash
git add src/api/services/content/blueprint_workbench_service.py \
        tests/unit/test_blueprint_workbench_service.py
git commit -m "feat(blueprint-workbench): 聚合服务 list/workspace/options(T5)"
```

---

## Task 6：工作台路由（list/options/workspace/batch）+ 注册

**Files:**
- Create: `src/api/routes/blueprint_workbench.py`
- Modify: `src/api/routes/__init__.py`（注册）
- Modify: `src/api/main.py` 或 app 聚合处（`include_router`）
- Test: `tests/unit/test_blueprint_workbench_api_contract.py`（扩展）

- [ ] **Step 1：写失败测试（追加到 `test_blueprint_workbench_api_contract.py`）**

```python
@pytest.mark.asyncio
async def test_list_blueprints_route_returns_summaries():
    from src.api.routes import blueprint_workbench as wb

    novel = {"novel_id": "novel-1", "owner_id": 1}
    fake_service = MagicMock()
    fake_service.list_chapter_summaries = AsyncMock(return_value={
        "items": [{"chapter_number": 1, "has_blueprint": False, "control_status": "not_generated"}],
        "total": 1, "page": 1, "page_size": 50, "status_counts": {"not_generated": 1},
    })
    with (
        patch("src.api.routes.blueprint_workbench.verify_novel_owner", new=AsyncMock(return_value=novel)),
        patch("src.api.routes.blueprint_workbench.BlueprintWorkbenchService", return_value=fake_service),
    ):
        result = await wb.list_blueprints("novel-1", _user())
    assert result["total"] == 1
    assert result["items"][0]["control_status"] == "not_generated"


@pytest.mark.asyncio
async def test_list_blueprints_route_owner_check_404():
    from src.api.routes import blueprint_workbench as wb

    async def _deny(*a, **kw):
        raise HTTPException(status_code=404, detail="Novel not found")

    with patch("src.api.routes.blueprint_workbench.verify_novel_owner", new=_deny):
        with pytest.raises(HTTPException) as exc:
            await wb.list_blueprints("missing", _user())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_workspace_route_aggregates():
    from src.api.routes import blueprint_workbench as wb

    novel = {"novel_id": "novel-1", "owner_id": 1}
    fake_service = MagicMock()
    fake_service.get_workspace = AsyncMock(return_value={
        "blueprint": {"chapter_type": "climax"}, "control": {"version": 1},
        "versions": [], "outline": None, "previous_state_delta": None,
        "chapter_summary": None, "quality_status": None, "available_characters": [],
    })
    with (
        patch("src.api.routes.blueprint_workbench.verify_novel_owner", new=AsyncMock(return_value=novel)),
        patch("src.api.routes.blueprint_workbench.BlueprintWorkbenchService", return_value=fake_service),
    ):
        result = await wb.get_workspace_route("novel-1", 5, _user())
    assert result["blueprint"]["chapter_type"] == "climax"


@pytest.mark.asyncio
async def test_options_route_returns_enums():
    from src.api.routes import blueprint_workbench as wb

    novel = {"novel_id": "novel-1", "owner_id": 1}
    fake_service = MagicMock()
    fake_service.get_options = MagicMock(return_value={
        "chapter_type": ["main_advance", "climax"],
        "pacing_target": ["fast", "medium", "slow"],
        "foreshadow_action": ["plant", "callback", "advance"],
    })
    with (
        patch("src.api.routes.blueprint_workbench.verify_novel_owner", new=AsyncMock(return_value=novel)),
        patch("src.api.routes.blueprint_workbench.BlueprintWorkbenchService", return_value=fake_service),
    ):
        result = await wb.get_options("novel-1", _user())
    assert "main_advance" in result["chapter_type"]


@pytest.mark.asyncio
async def test_batch_lock_returns_per_chapter_results():
    from src.api.routes import blueprint_workbench as wb
    from src.api.models.creative_control import LockRequest  # noqa: F401  (确保模型已 import)

    novel = {"novel_id": "novel-1", "owner_id": 1}
    fake_control = MagicMock()
    fake_control.lock = AsyncMock(side_effect=[3, ArtifactConflictError("novel-1", "blueprint", "13", 1, 2)])
    # 构造 batch 请求体 dict（路由用 pydantic 模型解析）
    with (
        patch("src.api.routes.blueprint_workbench.verify_novel_owner", new=AsyncMock(return_value=novel)),
        patch("src.api.routes.blueprint_workbench.CreativeControlService", return_value=fake_control),
    ):
        body = wb.BatchControlRequest(
            action="lock", artifact_type="blueprint",
            chapter_numbers=[12, 13], expected_versions={"12": 2, "13": 1},
        )
        result = await wb.batch_control("novel-1", body, _user())
    assert len(result["results"]) == 2
    by_ch = {r["chapter_number"]: r for r in result["results"]}
    assert by_ch[12]["status"] == "ok"
    assert by_ch[13]["status"] == "conflict"
    assert by_ch[13]["current_version"] == 2


@pytest.mark.asyncio
async def test_batch_rejects_over_50():
    from src.api.routes import blueprint_workbench as wb

    novel = {"novel_id": "novel-1", "owner_id": 1}
    with patch("src.api.routes.blueprint_workbench.verify_novel_owner", new=AsyncMock(return_value=novel)):
        with pytest.raises(HTTPException) as exc:
            body = wb.BatchControlRequest(
                action="lock", artifact_type="blueprint",
                chapter_numbers=list(range(1, 52)), expected_versions={},
            )
            await wb.batch_control("novel-1", body, _user())
    assert exc.value.status_code == 422
```

需在 `test_blueprint_workbench_api_contract.py` 顶部补 import：

```python
from src.core.exceptions import ArtifactConflictError
```

- [ ] **Step 2：运行确认失败**

Run: `poetry run pytest tests/unit/test_blueprint_workbench_api_contract.py -q`
Expected: FAIL — `No module named 'src.api.routes.blueprint_workbench'`

- [ ] **Step 3：实现 `blueprint_workbench.py`**

```python
"""章节蓝图工作台路由 —— 面向作者的独立蓝图工作台后端。

只读聚合（list/options/workspace）+ 批量控制（batch lock/unlock/approve）。
单章编辑保存/确认/锁定/重生成/版本/回退/影响均复用现有 creative-control 通用路由。
设计依据：docs/superpowers/specs/2026-07-22-chapter-blueprint-workbench-design.md
"""

from __future__ import annotations

from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.owner_guard import verify_novel_owner
from src.api.services.content.blueprint_workbench_service import (
    BlueprintWorkbenchService,
)
from src.core.auth_models import User
from src.core.creative_control.control_service import CreativeControlService
from src.core.exceptions import ArtifactConflictError
from src.core.security.auth import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["blueprint-workbench"])

_BATCH_LIMIT = 50


class BatchControlRequest(BaseModel):
    action: str = Field(..., pattern="^(lock|unlock|approve)$")
    artifact_type: str = "blueprint"
    chapter_numbers: list[int] = Field(..., min_length=1)
    expected_versions: dict[str, int] = Field(default_factory=dict)


@router.get("/{novel_id}/blueprints")
async def list_blueprints(
    novel_id: str,
    current_user: User = Depends(get_current_user),
    volume_number: int | None = Query(None, ge=1),
    status: str | None = Query(None),
    search: str | None = Query(None, max_length=100),
    chapter_start: int | None = Query(None, ge=1),
    chapter_end: int | None = Query(None, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=100),
):
    """章节摘要列表（服务端分页 + 筛选 + status_counts）。"""
    await verify_novel_owner(novel_id, current_user)
    service = BlueprintWorkbenchService()
    return await service.list_chapter_summaries(
        novel_id,
        volume_number=volume_number,
        status=status,
        search=search,
        chapter_start=chapter_start,
        chapter_end=chapter_end,
        page=page,
        page_size=page_size,
    )


@router.get("/{novel_id}/blueprints/options")
async def get_options(
    novel_id: str, current_user: User = Depends(get_current_user),
):
    """蓝图字段枚举选项（静态，无 DB）。"""
    await verify_novel_owner(novel_id, current_user)
    return BlueprintWorkbenchService().get_options()


@router.get("/{novel_id}/blueprints/{chapter_number}/workspace")
async def get_workspace_route(
    novel_id: str, chapter_number: int, current_user: User = Depends(get_current_user),
):
    """单章工作台详情聚合。"""
    await verify_novel_owner(novel_id, current_user)
    service = BlueprintWorkbenchService()
    return await service.get_workspace(novel_id, chapter_number)


@router.post("/{novel_id}/creative-control/batch")
async def batch_control(
    novel_id: str, request: BatchControlRequest,
    current_user: User = Depends(get_current_user),
):
    """批量 lock/unlock/approve（首期仅 blueprint）。逐章独立事务，部分失败不整体回滚。"""
    await verify_novel_owner(novel_id, current_user)
    if len(request.chapter_numbers) > _BATCH_LIMIT:
        raise HTTPException(status_code=422, detail=f"单次最多 {_BATCH_LIMIT} 章")
    if request.artifact_type != "blueprint":
        raise HTTPException(status_code=422, detail="首期仅支持 blueprint 类型批量操作")

    control_service = CreativeControlService()
    action_map = {
        "lock": control_service.lock,
        "unlock": control_service.unlock,
        "approve": control_service.approve,
    }
    fn = action_map[request.action]
    results: list[dict[str, Any]] = []
    for ch in request.chapter_numbers:
        expected = request.expected_versions.get(str(ch), 0)
        try:
            new_v = await fn(
                novel_id, "blueprint", str(ch),
                expected_version=expected, operator_id=current_user.id,
            )
            results.append({"chapter_number": ch, "status": "ok", "version": new_v})
        except ArtifactConflictError as exc:
            results.append({
                "chapter_number": ch, "status": "conflict",
                "current_version": exc.current_version,
                "expected_version": exc.expected_version,
            })
        except ValueError as exc:
            results.append({"chapter_number": ch, "status": "skipped", "error": str(exc)})
    return {"action": request.action, "results": results}
```

- [ ] **Step 4：注册路由**

在 `src/api/routes/__init__.py` 的 import 块追加（按字母序，放在 `book_import` 后或 `careers` 前，实际位置不影响功能）：

```python
from .blueprint_workbench import router as blueprint_workbench_router
```

并在 `__all__` 列表中追加 `"blueprint_workbench_router"`。

然后在 app 聚合处（通常是 `src/api/main.py` 或 `src/main.py`，搜索 `include_router` 找到现有注册点）追加：

```python
from .routes import blueprint_workbench_router  # 若已有 from .routes import * 则跳过
app.include_router(blueprint_workbench_router)
```

Run: `grep -rn "include_router(creative_control_router\|include_router(chapters_router" src/` 找到 app 聚合文件，按现有模式追加 `blueprint_workbench_router`。

- [ ] **Step 5：运行确认通过**

Run: `poetry run pytest tests/unit/test_blueprint_workbench_api_contract.py -q`
Expected: PASS（全部，含 Task 4 单章生成用例 + Task 6 六例）

- [ ] **Step 6：compileall + ruff**

Run: `python -m compileall -q src && poetry run ruff check src/api/routes/blueprint_workbench.py src/api/services/content/blueprint_workbench_service.py`
Expected: 无错误（若有 unused import 等按提示修）

- [ ] **Step 7：提交**

```bash
git add src/api/routes/blueprint_workbench.py \
        src/api/routes/__init__.py \
        src/api/main.py \
        tests/unit/test_blueprint_workbench_api_contract.py
git commit -m "feat(blueprint-workbench): list/options/workspace/batch 路由(T6)"
```

（`src/api/main.py` 按实际聚合文件名替换）

---

## Task 7：前端工作台（composable + 三栏视图 + 5 组件 + 路由/入口）

**Files:**
- Create: `frontend/src/composables/useBlueprintWorkbench.js`
- Create: `frontend/src/views/ChapterBlueprintWorkbench.vue`
- Create: `frontend/src/components/blueprints/BlueprintChapterList.vue`
- Create: `frontend/src/components/blueprints/BlueprintEditor.vue`
- Create: `frontend/src/components/blueprints/BlueprintContextPanel.vue`
- Create: `frontend/src/components/blueprints/BlueprintBatchToolbar.vue`
- Create: `frontend/src/components/blueprints/BlueprintVersionDialog.vue`
- Modify: `frontend/src/router/index.js`（增路由）
- Modify: `frontend/src/views/NovelDetail.vue`（入口按钮）
- Modify: `frontend/src/views/CreativeStudio.vue`（第6阶段入口链接，零改动逻辑）

**说明：** 前端组件较多，本 Task 按「先 composable → 再各组件 → 再视图 → 再路由/入口」顺序，每写一个组件即单独提交，保持改动可回溯。组件测试在 Task 8。

- [ ] **Step 1：创建 `useBlueprintWorkbench.js`**

```javascript
import { ref, computed } from 'vue'
import { useApi, authHeaders } from './useApi.js'

/**
 * useBlueprintWorkbench —— 章节蓝图工作台状态与 API。
 *
 * 只负责工作台独有的聚合查询（list/workspace/options）+ 批量操作。
 * 控制操作（edit/lock/unlock/approve/regenerate/rollback/impact/versions）
 * 复用 useCreativeControl（artifact_type="blueprint"）。
 *
 * 快速切章防覆盖：reqSeq 请求序号，旧请求结果丢弃。
 */
export function useBlueprintWorkbench(novelId) {
  const { apiGet, apiPost } = useApi()

  const summaries = ref([])
  const statusCounts = ref({})
  const page = ref(1)
  const pageSize = ref(50)
  const total = ref(0)
  const listLoading = ref(false)
  const listError = ref(null)

  const workspace = ref(null)
  const workspaceLoading = ref(false)
  const workspaceError = ref(null)

  const options = ref({ chapter_type: [], pacing_target: [], foreshadow_action: [] })

  const selectedChapter = ref(null)
  const selectedSet = ref(new Set())
  const draft = ref(null)
  const dirty = ref(false)
  const conflict = ref(null) // 409 冲突信息
  const saving = ref(false)

  let reqSeq = 0

  const base = `/api/v1/projects/${novelId}`

  async function fetchOptions() {
    try {
      options.value = await apiGet(`${base}/blueprints/options`)
    } catch (e) { /* 静默降级 */ }
  }

  async function fetchSummaries(filters = {}) {
    listLoading.value = true
    listError.value = null
    try {
      const qs = new URLSearchParams()
      if (filters.volume_number != null) qs.set('volume_number', filters.volume_number)
      if (filters.status) qs.set('status', filters.status)
      if (filters.search) qs.set('search', filters.search)
      if (filters.chapter_start != null) qs.set('chapter_start', filters.chapter_start)
      if (filters.chapter_end != null) qs.set('chapter_end', filters.chapter_end)
      qs.set('page', filters.page ?? page.value)
      qs.set('page_size', filters.page_size ?? pageSize.value)
      const suffix = qs.toString() ? `?${qs.toString()}` : ''
      const res = await apiGet(`${base}/blueprints${suffix}`)
      summaries.value = res.items || []
      statusCounts.value = res.status_counts || {}
      total.value = res.total || 0
      page.value = res.page || 1
      pageSize.value = res.page_size || 50
    } catch (e) {
      listError.value = e
    } finally {
      listLoading.value = false
    }
  }

  async function fetchWorkspace(chapterNumber) {
    // 防快速切章：旧请求结果丢弃
    const seq = ++reqSeq
    workspaceLoading.value = true
    workspaceError.value = null
    try {
      const res = await apiGet(`${base}/blueprints/${chapterNumber}/workspace`)
      if (seq !== reqSeq) return // 旧请求，丢弃
      workspace.value = res
      selectedChapter.value = chapterNumber
      draft.value = res.blueprint ? structuredClone(res.blueprint) : null
      dirty.value = false
      conflict.value = null
    } catch (e) {
      if (seq !== reqSeq) return
      workspaceError.value = e
    } finally {
      if (seq === reqSeq) workspaceLoading.value = false
    }
  }

  function updateDraft(field, value) {
    if (!draft.value) draft.value = {}
    draft.value[field] = value
    dirty.value = true
  }

  function discardDraft() {
    draft.value = workspace.value?.blueprint ? structuredClone(workspace.value.blueprint) : null
    dirty.value = false
    conflict.value = null
  }

  // 控制操作复用 useCreativeControl：由视图层注入 controlApi
  async function saveDraft(controlApi) {
    if (!workspace.value || !draft.value) return
    saving.value = true
    conflict.value = null
    try {
      await controlApi.editArtifact(
        'blueprint', String(selectedChapter.value), draft.value,
        workspace.value.control?.version ?? 0,
      )
      dirty.value = false
      await fetchWorkspace(selectedChapter.value) // 刷新
      return true
    } catch (e) {
      if (e.code === 'stale_version' || e.current_version != null) {
        conflict.value = { current_version: e.current_version, expected_version: e.expected_version }
      }
      throw e
    } finally {
      saving.value = false
    }
  }

  async function batchGenerate(chapterNumbers, { respect_locked = true, skip_confirmed = false } = {}) {
    return apiPost(`${base}/creative-control/generate-scope`, {
      mode: 'blueprint_only',
      chapter_numbers: chapterNumbers,
      respect_locked,
      skip_confirmed,
    })
  }

  async function previewBatchGenerate(chapterNumbers, { respect_locked = true, skip_confirmed = false } = {}) {
    const res = await fetch(`${base}/creative-control/generate-scope/preview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify({ mode: 'blueprint_only', chapter_numbers: chapterNumbers, respect_locked, skip_confirmed }),
    })
    if (!res.ok) throw new Error('预览失败')
    return res.json()
  }

  async function batchControl(action, chapterNumbers, expectedVersions = {}) {
    return apiPost(`${base}/creative-control/batch`, {
      action,
      artifact_type: 'blueprint',
      chapter_numbers: chapterNumbers,
      expected_versions: expectedVersions,
    })
  }

  return {
    summaries, statusCounts, page, pageSize, total, listLoading, listError,
    workspace, workspaceLoading, workspaceError, options,
    selectedChapter, selectedSet, draft, dirty, conflict, saving,
    fetchOptions, fetchSummaries, fetchWorkspace, updateDraft, discardDraft,
    saveDraft, batchGenerate, previewBatchGenerate, batchControl,
  }
}
```

- [ ] **Step 2：提交 composable**

```bash
git add frontend/src/composables/useBlueprintWorkbench.js
git commit -m "feat(blueprint-workbench): useBlueprintWorkbench composable(T7)"
```

- [ ] **Step 3：创建 `BlueprintChapterList.vue`（左栏）**

```vue
<template>
  <div class="flex flex-col h-full border-r border-ink-200 bg-paper-50">
    <!-- 筛选区 -->
    <div class="p-3 space-y-2 border-b border-ink-200">
      <select v-model="volFilter" @change="emitFilter" data-volume-filter
              class="input text-sm w-full">
        <option :value="null">全部卷</option>
        <option v-for="v in volumes" :key="v" :value="v">第{{ v }}卷</option>
      </select>
      <select v-model="statusFilter" @change="emitFilter" data-status-filter
              class="input text-sm w-full">
        <option :value="null">全部状态</option>
        <option v-for="s in statuses" :key="s.value" :value="s.value">{{ s.label }}</option>
      </select>
      <input v-model="searchQuery" @keyup.enter="emitFilter" data-search-input
             placeholder="搜索章号/标题" class="input text-sm w-full" />
      <button @click="emitFilter" class="btn-secondary text-sm w-full">筛选</button>
    </div>

    <!-- 列表 -->
    <div class="flex-1 overflow-auto">
      <div v-if="loading" class="p-8 text-center text-ink-400 text-sm">加载中...</div>
      <div v-else-if="!summaries.length" class="p-8 text-center text-ink-400 text-sm">
        全书尚无章节大纲
      </div>
      <ul v-else data-chapter-list>
        <li v-for="item in summaries" :key="item.chapter_number"
            @click="select(item.chapter_number)"
            :class="['px-3 py-2 cursor-pointer border-b border-ink-100 flex items-center gap-2',
                     selectedChapter === item.chapter_number ? 'bg-vermilion-50' : 'hover:bg-paper-100']">
          <input type="checkbox" :checked="selectedSet.has(item.chapter_number)"
                 @click.stop="toggleSelect(item.chapter_number)"
                 :data-batch-checkbox="item.chapter_number" class="w-3.5 h-3.5" />
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-xs font-mono text-ink-500">{{ item.chapter_number }}</span>
              <span class="text-sm text-ink-700 truncate">{{ item.title || `第${item.chapter_number}章` }}</span>
            </div>
            <div class="flex items-center gap-1 mt-0.5">
              <span :class="['text-[10px] px-1.5 py-0.5 rounded', statusClass(item.control_status)]"
                    :data-status="item.control_status">
                {{ statusLabel(item.control_status) }}
              </span>
              <span v-if="item.has_outline" class="text-[10px] text-ink-400">纲</span>
              <span v-if="item.has_chapter" class="text-[10px] text-ink-400">文</span>
              <span v-if="item.quality_status" class="text-[10px] text-ink-400">{{ item.quality_status }}</span>
            </div>
          </div>
        </li>
      </ul>
    </div>

    <!-- 分页 -->
    <div class="p-2 border-t border-ink-200 flex items-center justify-between text-xs">
      <button @click="prev" :disabled="page <= 1" class="btn-secondary text-xs disabled:opacity-40">上一页</button>
      <span class="text-ink-500">{{ page }}/{{ totalPages }}</span>
      <button @click="next" :disabled="page >= totalPages" class="btn-secondary text-xs disabled:opacity-40">下一页</button>
    </div>
  </div>
</template>

<script setup>
import { computed, ref } from 'vue'

const props = defineProps({
  summaries: { type: Array, default: () => [] },
  statusCounts: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  selectedChapter: { type: [Number, null], default: null },
  selectedSet: { type: Set, default: () => new Set() },
  page: { type: Number, default: 1 },
  pageSize: { type: Number, default: 50 },
  total: { type: Number, default: 0 },
})
const emit = defineEmits(['select', 'filter-change', 'page-change', 'selection-change'])

const volFilter = ref(null)
const statusFilter = ref(null)
const searchQuery = ref('')

const volumes = computed(() => {
  const s = new Set()
  for (const item of props.summaries) {
    if (item.volume_number != null) s.add(item.volume_number)
  }
  return [...s].sort((a, b) => a - b)
})

const totalPages = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))
const statuses = [
  { value: 'not_generated', label: '未生成' },
  { value: 'generated', label: '已生成' },
  { value: 'edited', label: '已编辑' },
  { value: 'confirmed', label: '已确认' },
  { value: 'locked', label: '已锁定' },
  { value: 'stale', label: '已过期' },
  { value: 'generating', label: '生成中' },
  { value: 'failed', label: '失败' },
]

function statusLabel(s) {
  return statuses.find(x => x.value === s)?.label || s
}
function statusClass(s) {
  const m = {
    not_generated: 'bg-ink-100 text-ink-500', generated: 'bg-blue-100 text-blue-700',
    edited: 'bg-amber-100 text-amber-700', confirmed: 'bg-green-100 text-green-700',
    locked: 'bg-vermilion-100 text-vermilion-700', stale: 'bg-gray-200 text-gray-600',
    generating: 'bg-blue-100 text-blue-600 animate-pulse', failed: 'bg-red-100 text-red-700',
  }
  return m[s] || 'bg-ink-100 text-ink-500'
}

function select(ch) { emit('select', ch) }
function toggleSelect(ch) {
  const next = new Set(props.selectedSet)
  if (next.has(ch)) next.delete(ch); else next.add(ch)
  emit('selection-change', next)
}
function emitFilter() {
  emit('filter-change', { volume_number: volFilter.value, status: statusFilter.value, search: searchQuery.value || null })
}
function prev() { if (props.page > 1) emit('page-change', props.page - 1) }
function next() { if (props.page < totalPages.value) emit('page-change', props.page + 1) }
</script>
```

- [ ] **Step 4：提交**

```bash
git add frontend/src/components/blueprints/BlueprintChapterList.vue
git commit -m "feat(blueprint-workbench): BlueprintChapterList 左栏(T7)"
```

- [ ] **Step 5：创建 `BlueprintEditor.vue`（中栏）**

```vue
<template>
  <div class="flex flex-col h-full">
    <div v-if="!workspace || !workspace.blueprint" class="flex-1 flex items-center justify-center p-8">
      <div class="text-center space-y-3">
        <p class="text-ink-400 text-sm">该章节尚无蓝图</p>
        <button @click="$emit('generate', selectedChapter)" data-generate-btn class="btn-primary text-sm">生成蓝图</button>
      </div>
    </div>
    <div v-else class="flex-1 overflow-auto p-4 space-y-4">
      <!-- 状态条 -->
      <div class="flex items-center justify-between text-xs text-ink-500">
        <div class="flex items-center gap-2">
          <span>版本 {{ workspace.control?.version ?? '—' }}</span>
          <span class="text-ink-300">|</span>
          <span>{{ statusLabel }}</span>
          <span v-if="locked" class="text-vermilion-600">·已锁定</span>
        </div>
        <span>{{ updatedAt }}</span>
      </div>

      <!-- 冲突提示 -->
      <div v-if="conflict" class="p-3 rounded-lg bg-vermilion-50 border border-vermilion-200 text-sm">
        <p class="text-vermilion-700 font-medium">版本冲突：服务端已更新到 v{{ conflict.current_version }}</p>
        <p class="text-ink-500 mt-1">本地草稿已保留，可刷新、比较或重新应用修改。</p>
        <div class="flex gap-2 mt-2">
          <button @click="$emit('discard')" class="btn-secondary text-xs">丢弃草稿</button>
          <button @click="$emit('refresh')" class="btn-secondary text-xs">刷新版本</button>
        </div>
      </div>

      <!-- dirty 提示 -->
      <div v-if="dirty" class="text-xs text-amber-600">有未保存修改</div>

      <div class="grid grid-cols-2 gap-4">
        <label class="block">
          <span class="text-xs text-ink-500">章节类型</span>
          <select v-model="localChapterType" :disabled="readonly"
                  @change="onUpdate('chapter_type', localChapterType)"
                  data-field-chapter_type class="input text-sm w-full">
            <option v-for="o in options.chapter_type" :key="o" :value="o">{{ o }}</option>
          </select>
        </label>
        <label class="block">
          <span class="text-xs text-ink-500">节奏</span>
          <select v-model="localPacing" :disabled="readonly"
                  @change="onUpdate('pacing_target', localPacing)"
                  data-field-pacing_target class="input text-sm w-full">
            <option v-for="o in options.pacing_target" :key="o" :value="o">{{ o }}</option>
          </select>
        </label>
      </div>

      <label class="block">
        <span class="text-xs text-ink-500">情节目标</span>
        <textarea v-model="localPlotGoal" :disabled="readonly"
                  @input="onUpdate('plot_goal', localPlotGoal)"
                  data-field-plot_goal rows="2" class="input text-sm w-full"></textarea>
      </label>

      <label class="block">
        <span class="text-xs text-ink-500">钩子设计</span>
        <textarea v-model="localHook" :disabled="readonly"
                  @input="onUpdate('hook_design', localHook)" rows="2"
                  class="input text-sm w-full"></textarea>
      </label>

      <!-- foreshadow_actions 列表编辑器 -->
      <div>
        <span class="text-xs text-ink-500">伏笔动作</span>
        <div v-for="(fa, idx) in localForeshadow" :key="idx" class="flex gap-2 mt-1">
          <select v-model="fa.action" :disabled="readonly" data-foreshadow-action
                  class="input text-sm flex-1">
            <option v-for="o in options.foreshadow_action" :key="o" :value="o">{{ o }}</option>
          </select>
          <input v-model="fa.target" :disabled="readonly" placeholder="对象"
                 class="input text-sm flex-1" />
          <button @click="removeForeshadow(idx)" :disabled="readonly"
                  class="btn-secondary text-xs">删</button>
        </div>
        <button @click="addForeshadow" :disabled="readonly"
                data-add-foreshadow class="btn-secondary text-xs mt-1">+ 添加伏笔</button>
      </div>

      <label class="block">
        <span class="text-xs text-ink-500">悬念结尾</span>
        <textarea v-model="localCliffhanger" :disabled="readonly"
                  @input="onUpdate('cliffhanger', localCliffhanger)" rows="2"
                  class="input text-sm w-full"></textarea>
      </label>

      <!-- key_characters 多选 -->
      <div>
        <span class="text-xs text-ink-500">关键角色</span>
        <div class="flex flex-wrap gap-2 mt-1">
          <label v-for="c in availableCharacters" :key="c.id"
                 class="flex items-center gap-1 text-xs text-ink-600">
            <input type="checkbox" :value="c.name" :checked="localKeyChars.includes(c.name)"
                   :disabled="readonly" @change="toggleChar($event, c.name)" />
            {{ c.name }}
          </label>
        </div>
      </div>

      <label class="block">
        <span class="text-xs text-ink-500">目标字数</span>
        <input type="number" v-model.number="localWordTarget" :disabled="readonly"
               @change="onUpdate('word_target', localWordTarget)" min="2000" max="6000"
               data-field-word_target class="input text-sm w-full" />
      </label>

      <div class="flex gap-2 pt-2">
        <button @click="onSave" :disabled="readonly || saving || !dirty"
                data-save-btn class="btn-primary text-sm flex-1">保存</button>
        <button @click="$emit('discard')" :disabled="!dirty" class="btn-secondary text-sm">放弃</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'

const props = defineProps({
  workspace: { type: Object, default: null },
  options: { type: Object, default: () => ({ chapter_type: [], pacing_target: [], foreshadow_action: [] }) },
  draft: { type: Object, default: null },
  dirty: { type: Boolean, default: false },
  saving: { type: Boolean, default: false },
  conflict: { type: Object, default: null },
  selectedChapter: { type: [Number, null], default: null },
})
const emit = defineEmits(['update', 'save', 'discard', 'refresh', 'generate'])

const locked = computed(() => props.workspace?.control?.locked)
const readonly = computed(() => !!locked.value)
const statusLabel = computed(() => props.workspace?.control?.control_status || '—')
const updatedAt = computed(() => props.workspace?.blueprint?.updated_at || '—')
const availableCharacters = computed(() => props.workspace?.available_characters || [])

// 本地表单状态（跟随 draft）
const localChapterType = ref('')
const localPacing = ref('')
const localPlotGoal = ref('')
const localHook = ref('')
const localCliffhanger = ref('')
const localWordTarget = ref(3000)
const localForeshadow = ref([])
const localKeyChars = ref([])

watch(() => props.draft, (d) => {
  if (!d) return
  localChapterType.value = d.chapter_type || ''
  localPacing.value = d.pacing_target || ''
  localPlotGoal.value = d.plot_goal || ''
  localHook.value = d.hook_design || ''
  localCliffhanger.value = d.cliffhanger || ''
  localWordTarget.value = d.word_target || 3000
  localForeshadow.value = (d.foreshadow_actions || []).map(fa =>
    typeof fa === 'string' ? { action: '', target: fa } : { action: fa.action || '', target: fa.target || '' }
  )
  localKeyChars.value = [...(d.key_characters || [])]
}, { immediate: true, deep: true })

function onUpdate(field, value) { emit('update', field, value) }
function onSave() { emit('save') }
function addForeshadow() {
  localForeshadow.value.push({ action: '', target: '' })
  emit('update', 'foreshadow_actions', localForeshadow.value.map(f => ({ action: f.action, target: f.target })))
}
function removeForeshadow(idx) {
  localForeshadow.value.splice(idx, 1)
  emit('update', 'foreshadow_actions', localForeshadow.value.map(f => ({ action: f.action, target: f.target })))
}
function toggleChar(e, name) {
  const next = new Set(localKeyChars.value)
  if (e.target.checked) next.add(name); else next.delete(name)
  localKeyChars.value = [...next]
  emit('update', 'key_characters', localKeyChars.value)
}
</script>
```

- [ ] **Step 6：提交**

```bash
git add frontend/src/components/blueprints/BlueprintEditor.vue
git commit -m "feat(blueprint-workbench): BlueprintEditor 中栏(T7)"
```

- [ ] **Step 7：创建 `BlueprintContextPanel.vue`（右栏）+ `BlueprintBatchToolbar.vue` + `BlueprintVersionDialog.vue`**

`BlueprintContextPanel.vue`：

```vue
<template>
  <div class="flex flex-col h-full overflow-auto p-4 space-y-4 text-sm">
    <!-- 章节大纲 -->
    <section>
      <h4 class="text-xs font-semibold text-ink-500 mb-1">章节大纲</h4>
      <div v-if="workspace?.outline" class="text-ink-700 text-xs whitespace-pre-wrap">
        {{ JSON.stringify(workspace.outline.content, null, 2) }}
      </div>
      <p v-else class="text-ink-400 text-xs">无大纲</p>
    </section>

    <!-- 上章 state_delta -->
    <section>
      <h4 class="text-xs font-semibold text-ink-500 mb-1">上一章连续性</h4>
      <div v-if="workspace?.previous_state_delta" class="text-ink-700 text-xs">
        {{ JSON.stringify(workspace.previous_state_delta) }}
      </div>
      <p v-else class="text-ink-400 text-xs">无</p>
    </section>

    <!-- 正文摘要 + 质量 -->
    <section>
      <h4 class="text-xs font-semibold text-ink-500 mb-1">正文状态</h4>
      <div v-if="workspace?.chapter_summary" class="text-xs text-ink-700">
        <span>{{ workspace.chapter_summary.status }}</span>
        <span class="text-ink-400 mx-1">·</span>
        <span>{{ workspace.chapter_summary.word_count }} 字</span>
        <span v-if="workspace.quality_status" class="text-ink-400 mx-1">·</span>
        <span v-if="workspace.quality_status" data-quality-status>{{ workspace.quality_status }}</span>
      </div>
      <p v-else class="text-ink-400 text-xs">无正文</p>
    </section>

    <!-- 影响预览 -->
    <section>
      <h4 class="text-xs font-semibold text-ink-500 mb-1">影响范围</h4>
      <button @click="$emit('load-impact')" class="btn-secondary text-xs">预览影响</button>
      <div v-if="impact" class="mt-1 text-xs text-ink-600">
        <ImpactPreviewPanel :impact="impact" @choice="onChoice" />
      </div>
    </section>

    <!-- 控制 -->
    <section class="space-y-2">
      <button @click="$emit('confirm')" :disabled="!canControl"
              class="btn-secondary text-xs w-full">确认</button>
      <button @click="$emit('lock')" :disabled="!canLock"
              class="btn-secondary text-xs w-full">锁定</button>
      <button @click="$emit('unlock')" :disabled="!locked"
              class="btn-secondary text-xs w-full">解锁</button>
      <button @click="$emit('regenerate')" class="btn-primary text-xs w-full">重新生成</button>
      <button @click="$emit('view-versions')" class="btn-secondary text-xs w-full">版本历史</button>
    </section>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import ImpactPreviewPanel from '../ImpactPreviewPanel.vue'

const props = defineProps({
  workspace: { type: Object, default: null },
  impact: { type: Object, default: null },
  operations: { type: Array, default: () => [] },
})
const emit = defineEmits(['confirm', 'lock', 'unlock', 'regenerate', 'view-versions', 'load-impact', 'choice'])

const locked = computed(() => props.workspace?.control?.locked)
const canControl = computed(() => props.workspace?.control && !locked.value)
const canLock = computed(() => {
  const s = props.workspace?.control?.control_status
  return s === 'confirmed' || s === 'approved'
})

function onChoice(c) { emit('choice', c) }
</script>
```

`BlueprintBatchToolbar.vue`：

```vue
<template>
  <div class="p-3 border-b border-ink-200 bg-paper-50 flex flex-wrap items-center gap-2">
    <span class="text-xs text-ink-500">已选 {{ selectedCount }} 章</span>
    <button @click="onPreview('generate')" data-batch-generate class="btn-primary text-xs">批量生成</button>
    <button @click="$emit('batch-confirm')" data-batch-confirm class="btn-secondary text-xs">批量确认</button>
    <button @click="$emit('batch-lock')" data-batch-lock class="btn-secondary text-xs">批量锁定</button>
    <button @click="$emit('batch-unlock')" data-batch-unlock class="btn-secondary text-xs">批量解锁</button>

    <!-- 预览 -->
    <div v-if="batchPreview" class="w-full mt-2 p-2 rounded bg-ink-50 text-xs text-ink-600" data-batch-preview>
      将处理 {{ batchPreview.target_chapters?.length || 0 }} 章 ·
      跳过锁定 {{ batchPreview.skipped_locked?.length || 0 }} ·
      跳过已确认 {{ batchPreview.skipped_confirmed?.length || 0 }}
    </div>

    <!-- 逐章结果 -->
    <div v-if="batchResult" class="w-full mt-2 space-y-1" data-batch-result>
      <div v-for="r in batchResult.accepted" :key="r.chapter_number"
           class="text-xs text-green-700">第{{ r.chapter_number }}章 → 任务 {{ r.task_id }}</div>
      <div v-for="r in batchResult.failed_to_enqueue" :key="r.chapter_number"
           class="text-xs text-red-700">第{{ r.chapter_number }}章 → {{ r.error }}</div>
      <div v-if="!batchResult.accepted?.length && !batchResult.failed_to_enqueue?.length"
           class="text-xs text-ink-400">无结果</div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
const props = defineProps({
  selectedSet: { type: Set, default: () => new Set() },
  batchPreview: { type: Object, default: null },
  batchResult: { type: Object, default: null },
})
const emit = defineEmits(['batch-generate', 'batch-confirm', 'batch-lock', 'batch-unlock', 'preview-generate'])
const selectedCount = computed(() => props.selectedSet.size)
function onPreview(kind) {
  if (kind === 'generate') emit('preview-generate')
}
</script>
```

`BlueprintVersionDialog.vue`（骨架，比较/回退确认；完整字段对比在 Task 8 测试驱动补全）：

```vue
<template>
  <div v-if="visible" class="fixed inset-0 bg-black/30 flex items-center justify-center z-50" data-version-dialog>
    <div class="bg-paper-50 rounded-lg p-6 w-[640px] max-h-[80vh] overflow-auto">
      <h3 class="heading-serif text-lg mb-4">版本历史</h3>
      <ul class="space-y-1 mb-4">
        <li v-for="v in versions" :key="v.version_number"
            class="flex items-center gap-2 text-sm">
          <button @click="$emit('compare', v.version_number)"
                  class="text-vermilion-600 text-xs">对比</button>
          <span>v{{ v.version_number }}</span>
          <span class="text-ink-400 text-xs">{{ v.source }}</span>
        </li>
      </ul>

      <!-- 字段对比表 -->
      <table v-if="compareResult" class="w-full text-xs mb-4" data-compare-table>
        <thead><tr class="text-ink-500">
          <th class="text-left">字段</th><th class="text-left">旧值</th><th class="text-left">新值</th><th>变化</th>
        </tr></thead>
        <tbody>
          <tr v-for="d in compareResult.fields" :key="d.field">
            <td>{{ d.field }}</td><td>{{ format(d.old) }}</td><td>{{ format(d.new) }}</td>
            <td>{{ d.changed ? '是' : '否' }}</td>
          </tr>
        </tbody>
      </table>

      <!-- 回退确认 -->
      <div v-if="targetVersion" class="p-3 rounded bg-vermilion-50 text-sm" data-rollback-confirm>
        <p>确认回退到 v{{ targetVersion }}？</p>
        <button @click="onRollback" class="btn-primary text-xs mt-2">确认回退</button>
        <button @click="$emit('close')" class="btn-secondary text-xs mt-2 ml-2">取消</button>
      </div>

      <button @click="$emit('close')" class="btn-secondary text-xs w-full mt-4">关闭</button>
    </div>
  </div>
</template>

<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  versions: { type: Array, default: () => [] },
  compareResult: { type: Object, default: null },
  targetVersion: { type: [Number, null], default: null },
  impact: { type: Object, default: null },
})
const emit = defineEmits(['compare', 'rollback', 'close'])
function onRollback() { emit('rollback', this.targetVersion) }
function format(v) {
  if (Array.isArray(v) || typeof v === 'object') return JSON.stringify(v)
  return v
}
</script>
```

- [ ] **Step 8：提交三个组件**

```bash
git add frontend/src/components/blueprints/BlueprintContextPanel.vue \
        frontend/src/components/blueprints/BlueprintBatchToolbar.vue \
        frontend/src/components/blueprints/BlueprintVersionDialog.vue
git commit -m "feat(blueprint-workbench): ContextPanel/BatchToolbar/VersionDialog(T7)"
```

- [ ] **Step 9：创建 `ChapterBlueprintWorkbench.vue`（三栏容器）**

```vue
<template>
  <div class="min-h-screen bg-paper-50">
    <div class="max-w-7xl mx-auto px-4 py-6">
      <div class="flex items-center justify-between mb-4">
        <div class="flex items-center gap-2">
          <router-link :to="`/novels/${novelId}`" class="text-xs text-vermilion-500 font-semibold">← 返回</router-link>
          <h1 class="heading-serif text-2xl">章节蓝图工作台</h1>
        </div>
      </div>

      <BlueprintBatchToolbar
        :selected-set="wb.selectedSet.value"
        :batch-preview="batchPreview"
        :batch-result="batchResult"
        @preview-generate="onPreviewGenerate"
        @batch-generate="onBatchGenerate"
        @batch-confirm="onBatch('approve')"
        @batch-lock="onBatch('lock')"
        @batch-unlock="onBatch('unlock')"
      />

      <div class="grid grid-cols-1 lg:grid-cols-[280px_1fr_320px] gap-0 border border-ink-200 rounded-lg overflow-hidden min-h-[600px]">
        <!-- 左栏 -->
        <BlueprintChapterList
          :summaries="wb.summaries.value"
          :status-counts="wb.statusCounts.value"
          :loading="wb.listLoading.value"
          :selected-chapter="wb.selectedChapter.value"
          :selected-set="wb.selectedSet.value"
          :page="wb.page.value"
          :page-size="wb.pageSize.value"
          :total="wb.total.value"
          @select="onSelect"
          @filter-change="onFilter"
          @page-change="onPage"
          @selection-change="wb.selectedSet.value = $event"
        />
        <!-- 中栏 -->
        <div class="border-x border-ink-200">
          <div v-if="dirty && showSwitchPrompt" class="p-2 bg-amber-50 text-xs text-amber-700 flex items-center gap-2">
            有未保存修改，切换将丢失。
            <button @click="confirmSwitch" class="btn-secondary text-xs">确认切换</button>
            <button @click="cancelSwitch" class="btn-secondary text-xs">取消</button>
          </div>
          <BlueprintEditor
            :workspace="wb.workspace.value"
            :options="wb.options.value"
            :draft="wb.draft.value"
            :dirty="wb.dirty.value"
            :saving="wb.saving.value"
            :conflict="wb.conflict.value"
            :selected-chapter="wb.selectedChapter.value"
            @update="wb.updateDraft"
            @save="onSave"
            @discard="wb.discardDraft"
            @refresh="onRefresh"
            @generate="onGenerateSingle"
          />
        </div>
        <!-- 右栏 -->
        <BlueprintContextPanel
          :workspace="wb.workspace.value"
          :impact="impact"
          @confirm="onControl('approve')"
          @lock="onControl('lock')"
          @unlock="onControl('unlock')"
          @regenerate="onRegenerate"
          @view-versions="showVersionDialog = true"
          @load-impact="onLoadImpact"
          @choice="onImpactChoice"
        />
      </div>
    </div>

    <BlueprintVersionDialog
      :visible="showVersionDialog"
      :versions="versions"
      :compare-result="compareResult"
      :target-version="targetVersion"
      :impact="versionImpact"
      @compare="onCompare"
      @rollback="onRollback"
      @close="showVersionDialog = false"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useBlueprintWorkbench } from '../composables/useBlueprintWorkbench.js'
import { useCreativeControl } from '../composables/useCreativeControl.js'
import BlueprintChapterList from '../components/blueprints/BlueprintChapterList.vue'
import BlueprintEditor from '../components/blueprints/BlueprintEditor.vue'
import BlueprintContextPanel from '../components/blueprints/BlueprintContextPanel.vue'
import BlueprintBatchToolbar from '../components/blueprints/BlueprintBatchToolbar.vue'
import BlueprintVersionDialog from '../components/blueprints/BlueprintVersionDialog.vue'

const route = useRoute()
const novelId = route.params.id
const wb = useBlueprintWorkbench(novelId)
const control = useCreativeControl(novelId)

const batchPreview = ref(null)
const batchResult = ref(null)
const impact = ref(null)
const versions = ref([])
const compareResult = ref(null)
const targetVersion = ref(null)
const versionImpact = ref(null)
const showVersionDialog = ref(false)

const dirty = wb.dirty
const showSwitchPrompt = ref(false)
let pendingChapter = null

onMounted(async () => {
  await wb.fetchOptions()
  await wb.fetchSummaries({ page: 1 })
})

async function onFilter(f) { await wb.fetchSummaries({ ...f, page: 1 }) }
async function onPage(p) { await wb.fetchSummaries({ page: p }) }

async function onSelect(ch) {
  if (dirty.value) {
    showSwitchPrompt.value = true
    pendingChapter = ch
    return
  }
  await wb.fetchWorkspace(ch)
}
function confirmSwitch() {
  showSwitchPrompt.value = false
  dirty.value = false
  if (pendingChapter) wb.fetchWorkspace(pendingChapter)
  pendingChapter = null
}
function cancelSwitch() { showSwitchPrompt.value = false; pendingChapter = null }

async function onSave() {
  try {
    await wb.saveDraft(control)
  } catch { /* 冲突已写入 wb.conflict */ }
}
function onRefresh() { if (wb.selectedChapter.value) wb.fetchWorkspace(wb.selectedChapter.value) }

async function onGenerateSingle(ch) {
  await control.regenerate('blueprint', String(ch), wb.workspace.value?.control?.version ?? 0)
  await wb.fetchSummaries({ page: wb.page.value })
}

async function onControl(action) {
  try {
    const ev = wb.workspace.value?.control?.version ?? 0
    if (action === 'lock') await control.lock('blueprint', String(wb.selectedChapter.value), ev)
    if (action === 'unlock') await control.unlock('blueprint', String(wb.selectedChapter.value), ev)
    if (action === 'approve') await control.approve('blueprint', String(wb.selectedChapter.value), ev)
    await onRefresh()
  } catch { /* 409 已解析 */ }
}
async function onRegenerate() {
  await onGenerateSingle(wb.selectedChapter.value)
}

async function onPreviewGenerate() {
  const chs = [...wb.selectedSet.value]
  batchPreview.value = await wb.previewBatchGenerate(chs)
}
async function onBatchGenerate() {
  const chs = [...wb.selectedSet.value]
  batchResult.value = await wb.batchGenerate(chs)
  await wb.fetchSummaries({ page: wb.page.value })
}
async function onBatch(action) {
  const chs = [...wb.selectedSet.value]
  batchResult.value = await wb.batchControl(action, chs)
  await wb.fetchSummaries({ page: wb.page.value })
}

async function onLoadImpact() {
  if (!wb.selectedChapter.value) return
  impact.value = await control.getImpact('blueprint', String(wb.selectedChapter.value))
}
async function onImpactChoice() { /* 复用 CreativeStudio 逻辑，简化：刷新 */ await onLoadImpact() }

async function loadVersions() {
  if (!wb.selectedChapter.value) return
  versions.value = await control.listVersions('blueprint', String(wb.selectedChapter.value))
}
async function onCompare(b) {
  const a = versions.value[0]?.version_number
  if (a) compareResult.value = await control.compareVersions('blueprint', String(wb.selectedChapter.value), a, b)
}
async function onRollback(v) {
  targetVersion.value = v
  versionImpact.value = await control.getImpact('blueprint', String(wb.selectedChapter.value))
  const ev = wb.workspace.value?.control?.version ?? 0
  await control.rollback('blueprint', String(wb.selectedChapter.value), v, ev)
  showVersionDialog.value = false
  await onRefresh()
}
</script>
```

- [ ] **Step 10：提交视图**

```bash
git add frontend/src/views/ChapterBlueprintWorkbench.vue
git commit -m "feat(blueprint-workbench): ChapterBlueprintWorkbench 三栏视图(T7)"
```

- [ ] **Step 11：注册路由**

在 `frontend/src/router/index.js` 的 routes 数组中（`studio` 路由后）追加：

```javascript
  { path: '/novels/:id/blueprints', name: 'blueprints', component: () => import('../views/ChapterBlueprintWorkbench.vue') },
```

- [ ] **Step 12：NovelDetail 入口按钮**

在 `frontend/src/views/NovelDetail.vue` 的入口按钮区（L71-80 studio 链接后）追加：

```vue
          <router-link
            :to="`/novels/${novelId}/blueprints`"
            class="btn-secondary text-sm flex items-center gap-1.5"
            data-blueprint-link
          >
            <svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke-width="2.5" stroke="currentColor" class="w-4 h-4 text-vermilion-500">
              <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75A3.75 3.75 0 017.5 3h9a3.75 3.75 0 013.75 3.75v10.5A3.75 3.75 0 0116.5 21h-9a3.75 3.75 0 01-3.75-3.75V6.75z M6.75 8.25h10.5 M6.75 12h10.5 M6.75 15.75h6" />
            </svg>
            <span>章节蓝图</span>
          </router-link>
```

- [ ] **Step 13：CreativeStudio 第6阶段入口链接**

在 `frontend/src/views/CreativeStudio.vue` 模板中，stage 6（章节蓝图）渲染区找一个合适容器，追加一个跳转链接（零改动既有逻辑，仅新增一个 `<router-link>`）：

```vue
          <router-link
            v-if="selectedStage?.number === 6"
            :to="`/novels/${novelId}/blueprints`"
            class="btn-secondary text-xs mt-2"
            data-workbench-link
          >进入蓝图工作台 →</router-link>
```

（若 `novelId` 在 setup 未暴露，用现有 studio 上下文中的小说 id ref；检索 `grep -n "novelId\|novel_id\|route.params" frontend/src/views/CreativeStudio.vue` 确认变量名后替换。）

- [ ] **Step 14：前端构建冒烟**

Run: `cd frontend && npm run build`
Expected: 构建通过（无 import 错误、无 Vue 编译错误）。若失败按提示修。

- [ ] **Step 15：提交路由/入口**

```bash
git add frontend/src/router/index.js \
        frontend/src/views/NovelDetail.vue \
        frontend/src/views/CreativeStudio.vue
git commit -m "feat(blueprint-workbench): 路由 + NovelDetail/CreativeStudio 入口(T7)"
```

---

## Task 8：前端测试 + 后端集成测试 + 全量验证

**Files:**
- Create: `frontend/src/composables/__tests__/useBlueprintWorkbench.spec.js`
- Create: `frontend/src/components/__tests__/blueprints/BlueprintChapterList.spec.js`
- Create: `frontend/src/components/__tests__/blueprints/BlueprintEditor.spec.js`
- Create: `frontend/src/components/__tests__/blueprints/BlueprintBatchToolbar.spec.js`
- Create: `frontend/src/views/__tests__/ChapterBlueprintWorkbench.spec.js`
- Modify: `tests/integration/test_creative_control_atomic_writes.py`（扩展 blueprint 后台生成/lease/批量跳过用例）

### 8A：后端集成测试（需隔离 PG）

- [ ] **Step 1：扩展集成测试（追加到 `test_creative_control_atomic_writes.py`）**

注意：`generate_blueprint_background` 真实签名为 `(task_id, novel_id, chapter_number, *, worker_id=None)`，内部依赖 `task_manager.update_status/get_task/complete_task` + `BlueprintService.generate_blueprint(persist=False)`（经 `generate_and_parse_json` 调 LLM）+ `CreativeArtifactWriteService.record_generated_artifact`。有 generation fence 时 `assert_generation_allowed_in_session` 会查真实 Task 行的 lease。本集成测试**不绑 fence**（`worker_id=None`，fence 为空 → 跳过 lease 校验），并 mock `get_task_manager` 与 LLM，直接断言 `record_generated_artifact` 产出的版本快照。

```python
@pytest.mark.asyncio
async def test_blueprint_background_generation_produces_version_snapshot():
    """单章蓝图走后台任务路径后产 ArtifactVersion 快照 + version_number 自增。

    不绑 generation fence（worker_id=None），避免 LeaseLost；mock task_manager 与 LLM。
    """
    novel_id = await _seed()
    from src.api.services.generation.creative_control_tasks import (
        generate_blueprint_background,
    )

    async with get_db_session() as session:
        session.add(Outline(
            novel_id=novel_id, level="chapter", volume_number=1,
            chapter_number=1, content={"chapter": 1, "title": "第一章"},
            status="draft",
        ))
        await session.execute(text(
            "INSERT INTO artifact_controls "
            "(novel_id, artifact_type, artifact_id, control_status, version, stage) "
            "VALUES (:n, 'blueprint', '1', 'draft', 1, 6) "
            "ON CONFLICT DO NOTHING"
        ), {"n": novel_id})

    fake_bp = {
        "chapter_type": "climax", "plot_goal": "x", "hook_design": "",
        "foreshadow_actions": [], "cliffhanger": "", "pacing_target": "fast",
        "key_characters": [], "word_target": 3000,
    }
    fake_tm = MagicMock()
    fake_tm.update_status = AsyncMock()
    fake_tm.get_task = AsyncMock(return_value={"operation_id": "op-bp-1"})
    fake_tm.complete_task = AsyncMock()
    with (
        patch("src.api.services.content.blueprint_service.generate_and_parse_json",
              new=AsyncMock(return_value=dict(fake_bp))),
        patch("src.api.services.generation.creative_control_tasks.get_task_manager",
              return_value=fake_tm),
    ):
        await generate_blueprint_background("task-bp-1", novel_id, 1, worker_id=None)

    async with get_db_session() as session:
        versions = list((await session.execute(
            select(ArtifactVersion).where(
                ArtifactVersion.novel_id == novel_id,
                ArtifactVersion.artifact_type == "blueprint",
                ArtifactVersion.artifact_id == "1",
            )
        )).scalars().all())
    assert len(versions) >= 1
    active = [v for v in versions if v.is_active]
    assert len(active) == 1  # 不变量1：单活版本
    assert active[0].version_number == max(v.version_number for v in versions)  # 不变量2：新版本自增
    assert active[0].source == "generation"


@pytest.mark.asyncio
async def test_blueprint_regenerate_keeps_history_versions():
    """重新生成不破坏历史版本（历史 ArtifactVersion 仍在）。"""
    novel_id = await _seed()
    async with get_db_session() as session:
        await session.execute(text(
            "INSERT INTO artifact_controls "
            "(novel_id, artifact_type, artifact_id, control_status, version, stage) "
            "VALUES (:n, 'blueprint', '1', 'generated', 1, 6) "
            "ON CONFLICT DO NOTHING"
        ), {"n": novel_id})
        session.add(Outline(
            novel_id=novel_id, level="chapter", volume_number=1,
            chapter_number=1, content={"chapter": 1}, status="draft",
        ))
        session.add(ArtifactVersion(
            novel_id=novel_id, artifact_type="blueprint", artifact_id="1",
            version_number=1, content_snapshot={"plot_goal": "旧"},
            source="manual", is_active=True,
        ))

    from src.api.services.generation.creative_control_tasks import (
        generate_blueprint_background,
    )
    fake_tm = MagicMock()
    fake_tm.update_status = AsyncMock()
    fake_tm.get_task = AsyncMock(return_value={"operation_id": "op-bp-2"})
    fake_tm.complete_task = AsyncMock()
    with (
        patch("src.api.services.content.blueprint_service.generate_and_parse_json",
              new=AsyncMock(return_value={
                  "chapter_type": "main_advance", "plot_goal": "新", "hook_design": "",
                  "foreshadow_actions": [], "cliffhanger": "", "pacing_target": "medium",
                  "key_characters": [], "word_target": 3000,
              })),
        patch("src.api.services.generation.creative_control_tasks.get_task_manager",
              return_value=fake_tm),
    ):
        await generate_blueprint_background("task-bp-2", novel_id, 1, worker_id=None)

    async with get_db_session() as session:
        versions = list((await session.execute(
            select(ArtifactVersion).where(
                ArtifactVersion.novel_id == novel_id,
                ArtifactVersion.artifact_type == "blueprint",
                ArtifactVersion.artifact_id == "1",
            )
        )).scalars().all())
    version_numbers = sorted(v.version_number for v in versions)
    assert 1 in version_numbers  # 历史版本仍在（不破坏历史）
    assert version_numbers[-1] >= 2  # 新版本自增
    active = [v for v in versions if v.is_active]
    assert len(active) == 1  # 单活
    assert active[0].version_number == version_numbers[-1]


@pytest.mark.asyncio
async def test_blueprint_batch_generate_skips_locked_and_confirmed():
    """批量蓝图生成 respect_locked/skip_confirmed 按 blueprint 类型 control 过滤。"""
    novel_id = await _seed()
    async with get_db_session() as session:
        # ch1 locked, ch2 approved(confirmed), ch3 可生成
        session.add(ArtifactControl(
            novel_id=novel_id, artifact_type="blueprint", artifact_id="1",
            control_status="locked", version=1, stage=6, locked=True,
        ))
        session.add(ArtifactControl(
            novel_id=novel_id, artifact_type="blueprint", artifact_id="2",
            control_status="approved", version=1, stage=6,
        ))
        for c in (1, 2, 3):
            session.add(Outline(
                novel_id=novel_id, level="chapter", volume_number=1,
                chapter_number=c, content={"chapter": c}, status="draft",
            ))

    from src.core.creative_control.scope_planner import (
        GenerationScopeIntent, GenerationScopePlanner,
    )
    planner = GenerationScopePlanner()
    intent = GenerationScopeIntent(
        novel_id=novel_id, mode="blueprint_only", chapter_numbers=[1, 2, 3],
        respect_locked=True, skip_confirmed=True,
    )
    plan = await planner.plan(intent)
    assert 3 in plan.target_chapters
    assert 1 in plan.skipped_locked
    assert 2 in plan.skipped_confirmed
```

需在文件顶部 import 补 `from unittest.mock import AsyncMock, MagicMock, patch`（若无）和 `from src.api.models.db_models import Outline`（若未 import）。

- [ ] **Step 2：运行集成测试（需隔离 PG）**

Run: `export TEST_DATABASE_URL='postgresql+asyncpg://<user>@localhost:5432/xiaoshuo_test' && poetry run pytest tests/integration/test_creative_control_atomic_writes.py -q`

若无可用 PG，标记集成用例 `@pytest.mark.skipif(os.environ.get("TEST_DATABASE_URL") is None, ...)` 或用 `pytest --co` 确认用例可收集。**禁止连接生产数据库。**

Expected: 新增 3 例 PASS（PG 可用时）。

- [ ] **Step 3：提交集成测试**

```bash
git add tests/integration/test_creative_control_atomic_writes.py
git commit -m "test(blueprint-workbench): 集成测试 蓝图后台生成/版本/批量跳过(T8)"
```

### 8B：前端测试

- [ ] **Step 4：`useBlueprintWorkbench.spec.js`**

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useBlueprintWorkbench } from '../useBlueprintWorkbench.js'

function makeFetch(routes = []) {
  return vi.fn(async (url, opts = {}) => {
    const method = (opts.method || 'GET').toUpperCase()
    for (const route of routes) {
      const matched = typeof route.match === 'string' ? url === route.match : route.match.test(url)
      if (matched && (!route.method || route.method === method)) {
        const body = route.body ?? {}
        return {
          ok: route.ok ?? true, status: route.status ?? 200,
          json: async () => body,
          text: async () => (typeof body === 'string' ? body : JSON.stringify(body)),
        }
      }
    }
    return { ok: false, status: 404, json: async () => ({ detail: 'nf' }), text: async () => '' }
  })
}

beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('fetch', makeFetch([]))
})

describe('useBlueprintWorkbench', () => {
  it('fetchSummaries 加载列表含未生成章节', async () => {
    vi.stubGlobal('fetch', makeFetch([
      { match: /\/blueprints\?/, method: 'GET', body: {
        items: [{ chapter_number: 1, has_blueprint: false, control_status: 'not_generated' }],
        total: 1, page: 1, page_size: 50, status_counts: { not_generated: 1 },
      } },
    ]))
    const wb = useBlueprintWorkbench('novel-1')
    await wb.fetchSummaries({ page: 1 })
    expect(wb.summaries.value.length).toBe(1)
    expect(wb.summaries.value[0].control_status).toBe('not_generated')
  })

  it('快速切章时旧请求不覆盖新选择', async () => {
    let resolveFirst
    vi.stubGlobal('fetch', vi.fn(async (url) => {
      if (/workspace/.test(url) && /11$/.test(url)) {
        return new Promise(r => { resolveFirst = () => r({ ok: true, status: 200, json: async () => ({ blueprint: { chapter_type: 'OLD' } }), text: async () => '' }) })
      }
      return { ok: true, status: 200, json: async () => ({ blueprint: { chapter_type: 'NEW' } }), text: async () => '' }
    }))
    const wb = useBlueprintWorkbench('novel-1')
    const p1 = wb.fetchWorkspace(11)   // 旧请求挂起
    const p2 = wb.fetchWorkspace(12)   // 新请求先返回
    await p2
    expect(wb.workspace.value.blueprint.chapter_type).toBe('NEW')
    resolveFirst()  // 旧请求晚返回
    await p1
    // 旧结果被丢弃，仍为 NEW
    expect(wb.workspace.value.blueprint.chapter_type).toBe('NEW')
  })

  it('batchGenerate 发 blueprint_only + chapter_numbers', async () => {
    const fetchMock = vi.fn(async () => ({
      ok: true, status: 202,
      json: async () => ({ accepted: [{ chapter_number: 1, task_id: 't1' }] }),
      text: async () => '',
    }))
    vi.stubGlobal('fetch', fetchMock)
    const wb = useBlueprintWorkbench('novel-1')
    await wb.batchGenerate([1, 2])
    const call = fetchMock.mock.calls[0]
    const body = JSON.parse(call[1].body)
    expect(body.mode).toBe('blueprint_only')
    expect(body.chapter_numbers).toEqual([1, 2])
  })
})
```

- [ ] **Step 5：`BlueprintChapterList.spec.js`**

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BlueprintChapterList from '../../BlueprintChapterList.vue'

describe('BlueprintChapterList', () => {
  it('渲染含未生成状态的章节列表', async () => {
    const wrapper = mount(BlueprintChapterList, {
      props: {
        summaries: [
          { chapter_number: 1, title: '首章', has_blueprint: true, control_status: 'draft', has_outline: true },
          { chapter_number: 2, title: '', has_blueprint: false, control_status: 'not_generated' },
        ],
        statusCounts: {}, loading: false, selectedChapter: null, selectedSet: new Set(),
        page: 1, pageSize: 50, total: 2,
      },
    })
    const items = wrapper.findAll('[data-chapter-list] li')
    expect(items.length).toBe(2)
    expect(wrapper.find('[data-status="not_generated"]').text()).toContain('未生成')
  })

  it('点击章节触发 select', async () => {
    const wrapper = mount(BlueprintChapterList, {
      props: {
        summaries: [{ chapter_number: 5, title: 'x', has_blueprint: true, control_status: 'draft' }],
        statusCounts: {}, loading: false, selectedChapter: null, selectedSet: new Set(),
        page: 1, pageSize: 50, total: 1,
      },
    })
    await wrapper.findAll('[data-chapter-list] li')[0].trigger('click')
    expect(wrapper.emitted('select')[0]).toEqual([5])
  })

  it('状态筛选触发 filter-change', async () => {
    const wrapper = mount(BlueprintChapterList, {
      props: { summaries: [], statusCounts: {}, loading: false, selectedChapter: null, selectedSet: new Set(), page: 1, pageSize: 50, total: 0 },
    })
    await wrapper.find('[data-status-filter]').setValue('locked')
    await wrapper.find('[data-status-filter]').trigger('change')
    expect(wrapper.emitted('filter-change')[0][0].status).toBe('locked')
  })
})
```

- [ ] **Step 6：`BlueprintEditor.spec.js`**

```javascript
import { describe, it, expect } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import BlueprintEditor from '../../BlueprintEditor.vue'

const WS = {
  blueprint: { chapter_type: 'main_advance', plot_goal: 'x', hook_design: '', foreshadow_actions: [], cliffhanger: '', pacing_target: 'medium', key_characters: [], word_target: 3000 },
  control: { version: 1, control_status: 'draft', locked: false },
  available_characters: [{ id: 1, name: '主角', role: 'protagonist' }],
}

describe('BlueprintEditor', () => {
  it('锁定蓝图禁用编辑', async () => {
    const wrapper = mount(BlueprintEditor, {
      props: { workspace: { ...WS, control: { ...WS.control, locked: true, control_status: 'locked' } }, options: { chapter_type: ['main_advance'], pacing_target: ['medium'], foreshadow_action: [] }, draft: WS.blueprint, dirty: false, saving: false, conflict: null, selectedChapter: 1 },
    })
    await flushPromises()
    expect(wrapper.find('[data-field-chapter_type]').attributes('disabled')).toBeDefined()
  })

  it('409 冲突保留草稿并提示', async () => {
    const wrapper = mount(BlueprintEditor, {
      props: { workspace: WS, options: { chapter_type: ['main_advance'], pacing_target: ['medium'], foreshadow_action: [] }, draft: { ...WS.blueprint, plot_goal: '改' }, dirty: true, saving: false, conflict: { current_version: 3, expected_version: 1 }, selectedChapter: 1 },
    })
    await flushPromises()
    expect(wrapper.text()).toContain('版本冲突')
    expect(wrapper.text()).toContain('v3')
    expect(wrapper.find('[data-field-plot_goal]').element.value).toBe('改')
  })

  it('保存按钮触发 save 事件', async () => {
    const wrapper = mount(BlueprintEditor, {
      props: { workspace: WS, options: { chapter_type: ['main_advance'], pacing_target: ['medium'], foreshadow_action: [] }, draft: WS.blueprint, dirty: true, saving: false, conflict: null, selectedChapter: 1 },
    })
    await flushPromises()
    await wrapper.find('[data-save-btn]').trigger('click')
    expect(wrapper.emitted('save')).toBeTruthy()
  })

  it无蓝图时显示生成按钮', async () => {
    const wrapper = mount(BlueprintEditor, {
      props: { workspace: { blueprint: null, control: { version: 0, locked: false }, available_characters: [] }, options: { chapter_type: [], pacing_target: [], foreshadow_action: [] }, draft: null, dirty: false, saving: false, conflict: null, selectedChapter: 1 },
    })
    expect(wrapper.find('[data-generate-btn]').exists()).toBe(true)
  })
})
```

注意：第 4 个 it 有笔误 `it无蓝图时`，实际应为 `it('无蓝图时显示生成按钮', ...)`，实现时修正。

- [ ] **Step 7：`BlueprintBatchToolbar.spec.js`**

```javascript
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import BlueprintBatchToolbar from '../../BlueprintBatchToolbar.vue'

describe('BlueprintBatchToolbar', () => {
  it('批量生成预览展示逐章明细与部分失败', () => {
    const wrapper = mount(BlueprintBatchToolbar, {
      props: {
        selectedSet: new Set([1, 2, 3]),
        batchPreview: { target_chapters: [1, 2], skipped_locked: [3], skipped_confirmed: [] },
        batchResult: { accepted: [{ chapter_number: 1, task_id: 't1' }], failed_to_enqueue: [{ chapter_number: 2, error: 'queue down' }] },
      },
    })
    expect(wrapper.find('[data-batch-preview]').text()).toContain('将处理 2 章')
    expect(wrapper.find('[data-batch-result]').text()).toContain('第2章')
    expect(wrapper.find('[data-batch-result]').text()).toContain('queue down')
  })

  it('批量生成按钮触发 preview-generate', async () => {
    const wrapper = mount(BlueprintBatchToolbar, { props: { selectedSet: new Set([1]) } })
    await wrapper.find('[data-batch-generate]').trigger('click')
    expect(wrapper.emitted('preview-generate')).toBeTruthy()
  })
})
```

- [ ] **Step 8：`ChapterBlueprintWorkbench.spec.js`**

```javascript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import ChapterBlueprintWorkbench from '../ChapterBlueprintWorkbench.vue'

const NOVEL_ID = '7'

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/novels/:id/blueprints', name: 'blueprints', component: ChapterBlueprintWorkbench },
      { path: '/novels/:id', name: 'novel-detail', component: { template: '<div/>' } },
    ],
  })
}

function makeFetch(routes = []) {
  return vi.fn(async (url, opts = {}) => {
    const method = (opts.method || 'GET').toUpperCase()
    for (const route of routes) {
      const matched = typeof route.match === 'string' ? url === route.match : route.match.test(url)
      if (matched && (!route.method || route.method === method)) {
        const body = route.body ?? {}
        return { ok: route.ok ?? true, status: route.status ?? 200, json: async () => body, text: async () => JSON.stringify(body) }
      }
    }
    return { ok: false, status: 404, json: async () => ({ detail: 'nf' }), text: async () => '' }
  })
}

beforeEach(() => { localStorage.clear() })

describe('ChapterBlueprintWorkbench', () => {
  it('挂载后加载列表与选项', async () => {
    vi.stubGlobal('fetch', makeFetch([
      { match: /\/blueprints\/options$/, body: { chapter_type: ['main_advance'], pacing_target: ['medium'], foreshadow_action: [] } },
      { match: /\/blueprints\?/, body: { items: [{ chapter_number: 1, control_status: 'not_generated', has_blueprint: false }], total: 1, page: 1, page_size: 50, status_counts: { not_generated: 1 } } },
    ]))
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    expect(wrapper.find('[data-chapter-list]').exists()).toBe(true)
    expect(wrapper.find('[data-status="not_generated"]').text()).toContain('未生成')
  })

  it('选择章节后加载结构化表单', async () => {
    vi.stubGlobal('fetch', makeFetch([
      { match: /\/blueprints\/options$/, body: { chapter_type: ['main_advance'], pacing_target: ['medium'], foreshadow_action: [] } },
      { match: /\/blueprints\?/, body: { items: [{ chapter_number: 1, control_status: 'draft', has_blueprint: true }], total: 1, page: 1, page_size: 50, status_counts: {} } },
      { match: /\/blueprints\/1\/workspace$/, body: { blueprint: { chapter_type: 'main_advance', plot_goal: 'x', foreshadow_actions: [], key_characters: [], word_target: 3000, pacing_target: 'medium' }, control: { version: 1, locked: false, control_status: 'draft' }, available_characters: [], versions: [], outline: null, previous_state_delta: null, chapter_summary: null, quality_status: null } },
    ]))
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    await wrapper.findAll('[data-chapter-list] li')[0].trigger('click')
    await flushPromises()
    expect(wrapper.find('[data-field-chapter_type]').exists()).toBe(true)
  })

  it('未保存修改时切章提示', async () => {
    vi.stubGlobal('fetch', makeFetch([
      { match: /\/blueprints\/options$/, body: { chapter_type: ['main_advance'], pacing_target: ['medium'], foreshadow_action: [] } },
      { match: /\/blueprints\?/, body: { items: [{ chapter_number: 1, control_status: 'draft', has_blueprint: true }, { chapter_number: 2, control_status: 'draft', has_blueprint: true }], total: 2, page: 1, page_size: 50, status_counts: {} } },
      { match: /\/blueprints\/1\/workspace$/, body: { blueprint: { chapter_type: 'main_advance', plot_goal: 'x', foreshadow_actions: [], key_characters: [], word_target: 3000, pacing_target: 'medium' }, control: { version: 1, locked: false, control_status: 'draft' }, available_characters: [], versions: [], outline: null, previous_state_delta: null, chapter_summary: null, quality_status: null } },
    ]))
    const wrapper = mount(ChapterBlueprintWorkbench, { global: { plugins: [makeRouter()] } })
    await flushPromises()
    await wrapper.findAll('[data-chapter-list] li')[0].trigger('click')
    await flushPromises()
    // 触发编辑使 dirty
    await wrapper.find('[data-field-plot_goal]').setValue('改了')
    await wrapper.find('[data-field-plot_goal]').trigger('input')
    await flushPromises()
    // 切到第二章
    await wrapper.findAll('[data-chapter-list] li')[1].trigger('click')
    expect(wrapper.text()).toContain('有未保存修改')
  })
})
```

- [ ] **Step 9：运行前端测试**

Run: `cd frontend && npm test -- --run`
Expected: 全部 PASS（含新增 + 既有 CreativeStudio.spec.js 回归）。修正 Task 8 Step 6 笔误 `it无蓝图时` → `it('无蓝图时显示生成按钮'`。

- [ ] **Step 10：提交前端测试**

```bash
git add frontend/src/composables/__tests__/useBlueprintWorkbench.spec.js \
        frontend/src/components/__tests__/blueprints/*.spec.js \
        frontend/src/views/__tests__/ChapterBlueprintWorkbench.spec.js
git commit -m "test(blueprint-workbench): 前端测试 composable/组件/视图(T8)"
```

### 8C：全量验证

- [ ] **Step 11：后端 ruff + compileall**

Run: `poetry run ruff check src tests && python -m compileall -q src tests`
Expected: 无错误。若有 lint，按提示修（不改动无关文件）。

- [ ] **Step 12：后端全量 unit 测试**

Run: `poetry run pytest tests/unit -q`
Expected: 全部 PASS（含本功能新增 + 既有不回归）。

- [ ] **Step 13：前端构建**

Run: `cd frontend && npm run build`
Expected: 构建成功。

- [ ] **Step 14：Git 检查**

Run: `git diff --check && git status --short`
Expected: 无空白错误；仅本功能相关文件已提交，无 stray 文件。

- [ ] **Step 15：最终提交（若有零散修正）**

```bash
# 仅当 8C 修正了文件时
git add -A
git commit -m "chore(blueprint-workbench): 全量验证修正(T8)"
```

- [ ] **Step 16：完成汇报**

按提示词十六要求汇报：实际功能、新增/修改文件、API 变更、是否有迁移、测试命令与通过数、限制/技术债、分支与提交号、是否推送/合并/部署（默认否）。**不推送、不部署、不连接生产服务器，除非用户另行明确授权。**

---

## 自审（writing-plans self-review）

**1. Spec coverage（设计文档各需求 → Task 映射）：**
- 枚举契约 + options + 写入校验 → T1 ✓
- 章节摘要聚合 + list 路由 → T5（service）+ T6（路由）✓
- workspace 聚合 + 路由 → T5 + T6 ✓
- 生成路径统一（废弃同步直写 + Intent chapter_numbers + scope 按 blueprint 类型筛选）→ T2 + T4 ✓
- dispatcher 逐章明细 + generate-scope 多章 → T3 ✓
- 批量 lock/unlock/approve 路由 → T6 ✓
- 前端 useBlueprintWorkbench + 三栏 + 5 组件 + 路由/入口 → T7 ✓
- 前端测试 + 后端集成测试 + 全量验证 → T8 ✓
- 不变量 1-10（设计 §核心不变量）：
  - 1/2 单活版本+不覆盖历史 → T8 集成测试断言 ✓
  - 3 generating 绑定任务 → 复用既有（generate_blueprint_background）✓
  - 4 lease fencing → T8 集成（bind_generation_task）+ 既有测试覆盖 ✓
  - 5 锁定不被覆盖 → 复用 assert_generation_allowed ✓
  - 6 skip_confirmed/respect_locked 真执行 → T2 按 blueprint 类型筛选 + T8 集成 ✓
  - 7 expected_version → 复用 + T6 批量逐章 ✓
  - 8 回退走现有事务 → 复用 rollback_artifact + T7 VersionDialog ✓
  - 9 影响用 ImpactAnalyzer → 复用 + T7 ContextPanel ✓
  - 10 工作台不直接改 control/版本表 → BlueprintWorkbenchService 全只读 + 批量经 CreativeControlService ✓
- _get_blueprint 同步路径保持不动 → T4 明确不动，设计决策5 ✓

**2. Placeholder scan：** 已扫描，无 TBD/TODO/"实现 later"/"类似 Task N"。每个 step 含完整代码或确切命令。

**3. Type consistency：**
- `DispatchedGeneration` 新增字段 `accepted: list[dict]` / `already_generating: list[int]` / `failed_to_enqueue: list[dict]` 在 T3 定义，T4/T6 路由透传用 `getattr` 一致读取。
- `BlueprintWorkbenchService.list_chapter_summaries` 返回结构 `{items, total, page, page_size, status_counts}` 在 T5 定义，T6 路由透传，前端 T7 `fetchSummaries` 解析一致。
- `get_workspace` 返回 `{blueprint, control, versions, outline, previous_state_delta, chapter_summary, quality_status, available_characters}` 在 T5 定义，T6 路由透传，前端 T7 `fetchWorkspace` + Editor 解析一致。
- `BatchControlRequest{action, artifact_type, chapter_numbers, expected_versions}` 在 T6 定义，T8 Step 1 测试构造一致。
- `useBlueprintWorkbench` 返回的 ref/方法在 T7 Step 1 定义，Step 9 视图与 T8 测试消费一致。
- 状态枚举：后端 `_derive_status` 产出 `not_generated/generated/edited/confirmed/locked/stale/generating/failed`，前端 `statuses` 列表与之一致。
- 已知修正点：T8 Step 6 笔误 `it无蓝图时` → 实施时改为 `it('无蓝图时显示生成按钮'`（已在 Step 9 注明）。

**4. 依赖与隔离说明：**
- 本计划全部在 worktree `claude/chapter-blueprint-workbench`（基于 `codex/audit-remediation`）执行。
- 集成测试用 `TEST_DATABASE_URL` 隔离 PG，禁止连生产（由 `tests/conftest.py` 既有机制保证）。
- 不推送、不部署、不连生产，除非用户明确授权。
- 每个任务独立提交，只提交本功能相关文件。

---

## Execution Handoff

计划已保存至 `docs/superpowers/plans/2026-07-22-chapter-blueprint-workbench.md`。

**两种执行方式：**

**1. Subagent-Driven（推荐）** — 每个 Task 派发独立 subagent，任务间审查，快速迭代。

**2. Inline Execution** — 在当前会话用 executing-plans 批量执行，检查点审查。

请回复「计划通过，开始实施」并选择执行方式（或直接说「计划通过，开始实施」即默认 Inline）。

