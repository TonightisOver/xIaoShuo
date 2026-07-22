# 章节蓝图工作台设计

> 在现有「章节蓝图后端能力 + Creative Control 创作控制台第6阶段」之上，新增一层面向作者的独立**章节蓝图工作台（Chapter Blueprint Workbench）**：全书章节蓝图状态总览、按卷/章号/状态筛选定位、结构化表单编辑、单章与批量生成、确认/锁定/解锁、版本历史/比较/回退、影响预览、与大纲/正文/质量关联，且在数百至数千章规模下服务端分页可用。
>
> **不重做 Creative Control，不重做 BlueprintService**。优先复用现有产物版本/控制/影响/范围规划底座，只补工作台所需的聚合查询、批量操作与专用 UI。

## 现状核查结论（已交叉验证：三路 Explore agent + 第一手代码核读）

### 后端已具备（复用基础，零改动）
| 能力 | 锚点 |
|---|---|
| `ChapterBlueprint` ORM 全字段 + `version_number` 列 + 部分唯一索引(单活) | `src/api/models/db_models.py:928-976` |
| `ArtifactControl`/`ArtifactVersion`/`OperationLog` 三表 | `db_models.py:1065/1118/1169` |
| `BlueprintService.generate/get/update_blueprint` | `src/api/services/content/blueprint_service.py:37/123/138` |
| 单章蓝图 GET/PUT/POST 路由 | `src/api/routes/chapters.py:289/302/318` |
| creative-control 全套路由(lock/unlock/approve/regenerate/impact/mark-stale/versions/compare/rollback/operations/generate-scope/mode/stage) | `src/api/routes/creative_control.py:212-578` |
| `GenerationScopePlanner`(blueprint_only/respect_locked/skip_confirmed) | `src/core/creative_control/scope_planner.py:72-170` |
| `ImpactAnalyzer`(依赖图 + regenerable/to_mark_stale) | `src/core/creative_control/impact_analyzer.py:47-317` |
| 后台生成任务 `generate_blueprint_background` + lease/fencing | `src/api/services/generation/creative_control_tasks.py:19` |
| 正文生成读取活动蓝图 `_get_blueprint` | `src/api/services/generation/chapter_generation_utils.py:89-103` |
| blueprint artifact 适配器(list/load/save/save_in_session/load_in_session) | `src/api/services/creative_control/artifact_adapters.py:81-349` |
| 乐观锁(expected_version 控制层 + expected_active_version 正文层)→409 | `src/api/services/creative_control/artifact_write_service.py:34-182` |
| `verify_novel_owner` 所有权校验 | `src/api/owner_guard.py` |
| 自研 DB 持久化任务队列 + `Task.lease_owner/lease_expires_at` + `TaskCheckpoint` | `db_models.py:330-464`；`src/api/services/tasks/task_worker.py` |

### 前端已具备（复用基础）
| 能力 | 锚点 |
|---|---|
| `useCreativeControl`(全控制操作 + expected_version + 409 解析) | `frontend/src/composables/useCreativeControl.js:15-176` |
| `useApi`/`authHeaders`(token key=`session_token`) | `frontend/src/composables/useApi.js:32-87` |
| `ImpactPreviewPanel`(props `impact`, emits 4 选项) | `frontend/src/components/ImpactPreviewPanel.vue` |
| `GenerationScopeSelector`(blueprint_only/respect_locked/skip_confirmed/章号/范围/卷) | `frontend/src/components/GenerationScopeSelector.vue` |
| CreativeStudio(10 阶段控制台, `/novels/:id/studio`) | `frontend/src/views/CreativeStudio.vue` |
| Tailwind 颜色 token(ink/paper/vermilion) + 组件类(btn/card/input/badge) | `frontend/tailwind.config.js`、`frontend/src/style.css` |
| TaskList 服务端分页 + 轮询先例(offset/limit) | `frontend/src/views/TaskList.vue:128-245` |
| `useWebSocket`/ActiveTaskMonitor 任务进度事件 | 现有 |

### 后端需新增（工作台独有）
1. **章节摘要聚合列表** `GET /api/v1/projects/{novel_id}/blueprints` —— 现 `list_artifacts(blueprint)` 仅列 active 蓝图(`artifact_adapters.py:81-99`)，无法发现未生成蓝图章节。以 chapter 级 Outline 为主轴合并四源。
2. **单章工作台详情聚合** `GET /api/v1/projects/{novel_id}/blueprints/{chapter_number}/workspace` —— 一次请求拿全 blueprint+control+versions+outline+previous_state_delta+chapter_summary+quality_status+available_characters。
3. **蓝图选项** `GET /api/v1/projects/{novel_id}/blueprints/options` —— 暴露权威枚举(现仅在 `src/core/llm/prompts.py:493/500` 字面量，无枚举类)。
4. **批量蓝图生成** —— 扩展 `GenerationScopeIntent` 增 `chapter_numbers`，`blueprint_only` 支持多章(上限 50)，dispatcher 按连续区间合并投递，返回逐章明细。现 `blueprint_only` 仅单章(`scope_planner.py:80-85`)。
5. **批量确认/锁定/解锁** —— 现仅单章(`creative_control.py:212/231/248`)。
6. **统一生成路径** —— 废弃同步 `POST /chapters/{n}/blueprint/generate` 直写(不产 ArtifactVersion)，单章生成也走后台 `NOVEL_BLUEPRINT` 任务(产版本快照 + 自增 version_number)，与批量一致。
7. **scope 筛选按 blueprint 类型** —— 现 `_filter_chapters` 只查 chapter 类型 control(`scope_planner.py:158-201`)，蓝图批量生成需按 blueprint 类型筛选。

### 前端需新增
- `frontend/src/views/ChapterBlueprintWorkbench.vue`(三栏)
- `frontend/src/components/blueprints/`：`BlueprintChapterList.vue`、`BlueprintEditor.vue`、`BlueprintContextPanel.vue`、`BlueprintBatchToolbar.vue`、`BlueprintVersionDialog.vue`
- `frontend/src/composables/useBlueprintWorkbench.js`
- 路由 `/novels/:id/blueprints`；NovelDetail + CreativeStudio 第6阶段入口
- 现有 creative-control 控制操作**零改动**复用

### 关键设计缝隙（本设计处理）
- **同步生成路径不产版本快照**：`BlueprintService.generate_blueprint(persist=True)`(`blueprint_service.py:99-113`)直写 ChapterBlueprint 表、旧 active 置 false，**不产 ArtifactVersion、不维护 version_number 自增**；后台 `generate_blueprint_background`(persist=False + `record_generated_artifact`)才产快照自增。→ **废弃同步直写，单章生成统一走后台任务路径**，与批量一致，版本语义彻底统一。

## 已确认的设计决策（brainstorming 阶段用户拍板）

1. 生成路径统一走后台任务（单章也异步，产 ArtifactVersion 快照 + version_number 自增）。
2. 批量生成复用 generate-scope 统一任务（扩展 Intent + dispatcher 按连续区间合并投递 + 逐章明细）。
3. 工作台独立页面 + CreativeStudio 保留并加第6阶段入口。
4. 章节索引以 chapter 级 Outline 为主轴合并四源（Outline/ChapterBlueprint/Chapter/Volume）。
5. **废弃工作台/路由的同步直写入口**：`POST /chapters/{n}/blueprint/generate` 路由内部改投后台任务（URL 保留）。**正文生成内部 `_get_blueprint`（`chapter_generation_utils.py:89-103`）的同步自动生成（`persist=True`）保持不动**——它是正文生成的同步依赖，改异步会破坏正文生成流程，且不在工作台范围。其版本不自增是既有缝隙，工作台对该章显示「无版本历史」边界（提示用户从工作台重新生成以建立版本）。工作台读版本走 `ArtifactVersion` 表（`record_generated_artifact` 写入，版本语义正确）。
6. 生成中状态感知：WebSocket 事件 + 轮询兜底（复用 progress_event_bus / useWebSocket）。
7. contracts.py 新增 `ChapterType`/`BlueprintPacing`/`ForeshadowAction` StrEnum + options 接口（值取自 prompts.py 现有字面量，禁止发明）。
8. `GenerationScopeIntent` 增 `chapter_numbers: list[int]` 字段，blueprint_only 多章上限 50。
9. 批量蓝图锁定/已确认筛选按 blueprint 类型 control。
10. 单章详情走新增 workspace 聚合接口。
11. 未保存草稿：前端 dirty 标记 + 确认框，显式保存走 PUT creative-control。
12. 零 DB 迁移（artifact_controls/artifact_versions/operation_logs/ChapterBlueprint.version_number 均已在迁移 `20260721e` 建好）。

## 方案比较

### 方案一：独立工作台页面 + 复用 Creative Control 底座（采用）

新增独立路由 `/novels/:id/blueprints` + `ChapterBlueprintWorkbench.vue` 三栏布局。后端新增最小聚合层（3 个只读接口 + 扩展 generate-scope + 批量 lock/unlock/approve）。控制操作（编辑保存/确认/锁定/重生成/版本/回退/影响）全部复用现有 creative-control 通用路由（`artifact_type="blueprint"`）与 `useCreativeControl`。生成统一走后台任务。零 DB 迁移。

**优点**：风险最小、复用最多、CreativeStudio 零改动、版本语义统一、改动可逐阶段验证、长篇分页可用。
**缺点**：单章生成由同步变异步（需轮询/WS 感知状态）——这是为版本语义统一付出的必要代价，且复用现有任务进度基础设施。

### 方案二：CreativeStudio 内嵌工作台（不采用）

在 CreativeStudio.vue 第6阶段内嵌三栏蓝图视图，不新增路由。但 CreativeStudio 单栏编辑器与三栏布局风格冲突、改动大（已 446 行）、违背「原有能力保留不删除」。

### 方案三：新建独立蓝图编排引擎（不采用）

新建 StageOrchestrator + 独立蓝图存储接管蓝图生命周期。违背「不另造第二套系统」硬约束（蓝图/版本/控制已完备），风险与工作量最大。

## 目标与非目标

### 目标
1. 全书章节蓝图状态总览，含未生成蓝图的章节。
2. 按卷/章号/状态筛选与快速定位，服务端分页（page_size ≤ 100）。
3. 结构化表单编辑蓝图（非 JSON 文本框）。
4. 单章与批量生成蓝图（批量上限 50，逐章明细）。
5. 保存/确认/锁定/解锁，带并发保护。
6. 版本历史/字段比较/回退。
7. 修改前影响预览。
8. 显示蓝图与章节大纲/正文/质量状态关联。
9. 长篇数百至数千章可用（不一次加载全书）。
10. 正文生成仍消费活动蓝图（不变）。

### 非目标
- 不重做 BlueprintService 内部生成逻辑（只统一写入口）。
- 不重做 Creative Control 控制层（只复用）。
- 不新增第二套蓝图/版本/任务/控制表。
- 不做卷级硬审核暂停（属 Creative Control 既有范畴）。
- 不在本阶段实现蓝图 AI 质量评分（蓝图无 quality_status，关联的是正文 `Chapter.quality_status`）。

## 数据模型

**零 DB 迁移。** 复用现有全部表与列：

- `ChapterBlueprint`（`chapter_blueprints`）：活动蓝图本体 + is_active 历史；`version_number` 列已存在。
- `ArtifactControl`（`artifact_controls`）：`artifact_type="blueprint"`、`artifact_id=str(chapter_number)` 的控制元数据（control_status/locked/version 乐观锁/generation_meta/stale_reason/awaiting_review）。
- `ArtifactVersion`（`artifact_versions`）：蓝图版本快照（content_snapshot/version_number/is_active/source/task_id），`artifact_type="blueprint"`。**蓝图版本历史以此表为单一真源**。
- `OperationLog`（`operation_logs`）：操作审计。
- `Outline`（`level="chapter"`）：章节大纲（章节索引主轴）。
- `Chapter`/`ChapterVersion`：正文与正文版本（只读关联）。
- `Volume`（`chapter_start/chapter_end`）：卷范围（章节索引补充源 + volume 筛选）。
- `Character`：`available_characters` 候选源（`key_characters` 是角色名字符串数组）。
- `Task`/`TaskCheckpoint`：后台生成任务 + lease/fencing。

**章节索引不新增表**：由上述现有表按 `chapter_number` 在查询时合并推导（见下「章节摘要聚合」）。

## 核心不变量（沿用 Creative Control，本设计不破坏）

1. 同一章节只能有一个活动蓝图版本（`ChapterBlueprint` 部分唯一索引 `uq_blueprint_novel_chapter_active` 保证）。
2. 重新生成保存新版本，不覆盖历史（旧 active 置 false + 新 ArtifactVersion 行）。
3. 生成中状态绑定当前任务（`ArtifactControl.control_status="generating"` + `generation_meta.task_id`）。
4. 旧 worker 失去 lease 后不得写入蓝图或控制元数据（`assert_generation_allowed` + checkpoint lease/fencing，已有测试 `test_creative_control_atomic_writes.py:564` 覆盖）。
5. 锁定蓝图不被后台自动覆盖，除非用户显式 force（`assert_generation_allowed_in_session` 校验 locked，已有测试覆盖）。
6. `skip_confirmed`/`respect_locked` 真正执行（后端 `_filter_chapters` 按 blueprint 类型 control 过滤，非仅前端参数）。
7. 保存编辑带 `expected_version`（控制层乐观锁，409 冲突）。
8. 回退走现有版本与 Creative Control 事务逻辑（`rollback_artifact`）。
9. 蓝图改动影响用现有 `ImpactAnalyzer`。
10. 工作台不直接修改 ArtifactControl 或版本表（全部经 `CreativeControlService`/`ArtifactVersionStore`/`CreativeArtifactWriteService`）。

## 后端设计

### 1. 枚举契约（`src/core/creative_control/contracts.py` 新增）

值**严格取自** `src/core/llm/prompts.py:493/500/497` 现有字面量，禁止发明：

```python
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

BLUEPRINT_FIELD_OPTIONS = {
    "chapter_type": [e.value for e in ChapterType],
    "pacing_target": [e.value for e in BlueprintPacing],
    "foreshadow_action": [e.value for e in ForeshadowAction],
}
```

`BlueprintService.generate_blueprint`/`update_blueprint` 写入前校验 `chapter_type`/`pacing_target` 值在枚举内（不在则 422）。DB 列保持 `String(30)`/`String(20)` 不变（不引入 DB CHECK，避免迁移）。`word_target` 校验正整数（2000-6000，取自 prompt L510）。

### 2. 章节摘要聚合服务（新增 `src/api/services/content/blueprint_workbench_service.py`）

`class BlueprintWorkbenchService`：

- `async def list_chapter_summaries(novel_id, *, volume_number, status, search, chapter_start, chapter_end, page, page_size) -> dict`
  - **章节索引主轴**：chapter 级 `Outline`（`Outline.level="chapter"`，含 chapter_number/volume_number/title）。
  - **合并四源**（按 chapter_number 去重，Outline 为主轴，缺 Outline 的章号由 ChapterBlueprint/Chapter/Volume 补齐）：
    1. `Outline` chapter 级（主轴：章号/卷号/标题）。
    2. `ChapterBlueprint(is_active=True)`（has_blueprint/blueprint_version/updated_at）。
    3. `Chapter`（has_chapter/title/quality_status）。
    4. `Volume.chapter_start/chapter_end`（卷号补齐，Outline 无 volume_number 时按 Volume 范围推导）。
  - **筛选**：volume_number（Outline.volume_number 或 Volume 范围）、status（见下「状态推导」）、search（title 模糊）、chapter_start/chapter_end（章号范围）。
  - **分页**：服务端按 chapter_number 排序，`page`/`page_size`（上限 100，默认 50）。`total` 为筛选后总数。
  - **status_counts**：各状态计数（用于筛选 tab）。
  - **control 状态批量加载**：一次查询该页所有章号的 `ArtifactControl(artifact_type="blueprint")`，避免 N+1。
  - **生成中状态**：control_status="generating" 或有未完成 `Task`(task_type=NOVEL_BLUEPRINT, target=该章) → status="generating"。
  - 返回结构：
    ```json
    {
      "items": [{
        "chapter_number": 12, "volume_number": 2, "title": "雨夜来客",
        "has_outline": true, "has_blueprint": false, "has_chapter": false,
        "blueprint_version": null, "control_status": "draft",
        "locked": false, "quality_status": null, "updated_at": null
      }],
      "total": 0, "page": 1, "page_size": 50, "status_counts": {}
    }
    ```

- **状态推导**（章节摘要的 `control_status` 字段，映射提示词 8 态）：
  - 无 ArtifactControl 行 + 无蓝图 → `not_generated`（未生成，提示词专用态）。
  - control_status="generating" 或有活跃任务 → `generating`。
  - control_status="failed" → `failed`。
  - control_status="locked" 或 locked=True → `locked`。
  - control_status="approved" → `confirmed`（已确认）。
  - control_status="stale" → `stale`（已过期）。
  - control_status="edited" → `edited`（已编辑）。
  - control_status="generated" → `generated`（已生成）。
  - control_status="draft" 且 has_blueprint → `draft`。
  - 注：列表态名与 Creative Control 内部 `control_status` 八态对齐，`not_generated` 为工作台新增的「无蓝图」派生态（不写入 DB，仅查询时推导）。

- `async def get_workspace(novel_id, chapter_number) -> dict`
  - 一次事务聚合：
    - `blueprint`：`BlueprintService.get_blueprint`（无则 null）。
    - `control`：`CreativeControlService.get_or_create(novel_id, "blueprint", str(chapter_number))`。
    - `versions`：`ArtifactVersionStore.list_versions(novel_id, "blueprint", str(chapter_number))`。
    - `outline`：chapter 级 Outline（无则 null）。
    - `previous_state_delta`：上一章 `Chapter.state_delta`（无则 null）。
    - `chapter_summary`：`Chapter`（status/word_count/quality_status，无则 null）。
    - `quality_status`：`Chapter.quality_status`（无蓝图对应正文则 null）。
    - `available_characters`：`CharacterService.list_characters(novel_id)` → `[{id, name, role}]`。
  - 所有子查询在单事务内，复用现有 service 的 session 入口或 `_in_session` 变体；任一子查询失败降级为 null 并记日志，不整体 500。

- `async def get_options() -> dict`：返回 `BLUEPRINT_FIELD_OPTIONS`（纯静态，无 DB）。

### 3. 生成路径统一（修改 `chapters.py` + `scope_planner.py` + `generation_dispatch.py`）

- **废弃同步直写行为**：`POST /api/v1/projects/{novel_id}/chapters/{chapter_number}/blueprint/generate`（`chapters.py:318`）的 URL **保留**（向后兼容），但**内部行为改为投递 `NOVEL_BLUEPRINT` 后台任务**（与 `regenerate` 的 blueprint 分支一致），返回 `{task_id, task_type, status:"generating"}`，**不再同步调 `BlueprintService.generate_blueprint(persist=True)`**。
  - 即「废弃」的是「工作台/路由同步直写表」这一**行为**，不是删除路由。URL 保留避免破坏调用方，行为由同步变异步。
  - **正文生成内部 `_get_blueprint`（`chapter_generation_utils.py:89-103`）的同步自动生成（`persist=True`）保持不动**——它是正文生成的同步依赖，改异步会破坏正文生成流程，且不在工作台范围。其版本不自增是既有缝隙：工作台对该章显示「无版本历史」边界，提示用户从工作台重新生成以建立版本。本设计不触碰正文生成核心路径。
  - 旧 `BlueprintService.generate_blueprint(persist=True)` 方法保留（`_get_blueprint` 仍调用），但工作台/路由不再调用。
  - 不删除 `BlueprintService.generate_blueprint`（`generate_blueprint_background` 内部仍以 `persist=False` 调用）。
- **`GenerationScopeIntent` 增字段**：`chapter_numbers: list[int] | None = None`。
- **`GenerationScopePlanner.plan` 扩展 blueprint_only**：
  - `mode="blueprint_only"` 时，目标章号集 = `chapter_numbers`（若提供）∪ `{chapter_number}`（单章兼容）。上限校验 ≤ 50，超限 422。
  - target_chapters 为该集合排序去重。
- **scope 筛选按 blueprint 类型**：`_filter_chapters` 增 `artifact_type` 参数（默认 "chapter"），blueprint_only 模式传 "blueprint"，查 `ArtifactControl(artifact_type="blueprint")` 的 locked/approved。
  - 新增 `_load_locked_blueprints`/`_load_confirmed_blueprints`（或参数化现有方法），按 blueprint 类型 control 查章号。
- **dispatcher 逐章明细**：`CreativeGenerationDispatcher.dispatch_scope` 对 blueprint_only 多章，按连续区间合并投递 `NOVEL_BLUEPRINT` 任务（复用 `_contiguous_ranges`），返回 `DispatchedGeneration` + 新增逐章结果：
  - `accepted`：成功入队的章号 + 对应 task_id。
  - `skipped_locked`：被 respect_locked 跳过的章号。
  - `skipped_confirmed`：被 skip_confirmed 跳过的章号。
  - `already_generating`：该章已有活跃 NOVEL_BLUEPRINT 任务（control_status=generating）的章号。
  - `failed_to_enqueue`：入队异常的章号 + 错误信息。
  - 这些明细由 planner 预计算 + dispatcher 入队时填充，路由层透传。

### 4. 批量确认/锁定/解锁（新增路由，放在 `blueprint_workbench.py`）

`POST /api/v1/projects/{novel_id}/creative-control/batch`（URL 挂在 creative-control 语义下，但路由代码放在 `blueprint_workbench.py` 以收敛工作台相关端点；首期 `artifact_type` 仅支持 `"blueprint"`），请求体：
```json
{
  "action": "lock|unlock|approve",
  "artifact_type": "blueprint",
  "chapter_numbers": [12, 13, 14],
  "expected_versions": {"12": 3, "13": 1}
}
```
- 逐章调 `CreativeControlService.lock/unlock/approve`，每章带各自 `expected_version`（从 `expected_versions` map 取，缺则视为该章当前版本）。
- 单次上限 50 章。
- 返回逐章结果：`[{chapter_number, status:"ok|skipped|conflict", version, error?}]`，部分失败不整体回滚（每章独立事务），不显示「全部成功」。
- 409 冲突逐章标注 `conflict` + `current_version`，不中断其他章。

### 5. 路由汇总（新增 `src/api/routes/blueprint_workbench.py`）

`router = APIRouter(prefix="/api/v1/projects", tags=["blueprint-workbench"])`，全部带 `verify_novel_owner` + `get_current_user`：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/{novel_id}/blueprints` | 章节摘要列表（分页+筛选+status_counts） |
| GET | `/{novel_id}/blueprints/options` | 枚举选项（静态） |
| GET | `/{novel_id}/blueprints/{chapter_number}/workspace` | 单章详情聚合 |
| POST | `/{novel_id}/creative-control/batch` | 批量 lock/unlock/approve（放 `blueprint_workbench.py`，首期仅 blueprint） |

蓝图生成（单章+批量）统一走现有 `POST /{novel_id}/creative-control/generate-scope`（扩展后支持 blueprint_only 多章）+ `POST /{novel_id}/creative-control/artifacts/blueprint/{n}/regenerate`（单章重生成）。
蓝图编辑保存走现有 `PUT /{novel_id}/creative-control/artifacts/blueprint/{n}`。
版本/回退/影响走现有 `creative-control/artifacts/blueprint/{n}/versions*`、`/impact`。

`src/api/routes/__init__.py` 注册 `blueprint_workbench_router`。

### 6. 所有权校验与并发

- 所有新路由 `await verify_novel_owner(novel_id, current_user)`（小说不存在/无权限 → 404/403，复用现有）。
- 章节摘要/workspace 查询为只读，不加乐观锁。
- 编辑保存/锁定/确认/回退复用现有 `expected_version` 乐观锁 → 409。
- 批量操作每章独立 `with_for_update` 锁 control 行 + 独立事务，部分失败隔离。
- 生成中状态：`assert_generation_allowed` 拒绝对 generating/locked 章重复投递（已有）。

## 前端设计

### 路由与入口

- `frontend/src/router/index.js` 新增 `/novels/:id/blueprints` → `ChapterBlueprintWorkbench.vue`。
- `frontend/src/views/NovelDetail.vue`（L61-100 入口区）新增「章节蓝图」入口按钮（`data-blueprint-link`）。
- `frontend/src/views/CreativeStudio.vue` 第6阶段区域（通过 `REGENERATABLE_ARTIFACT_TYPES` 含 blueprint，L231-233）新增「进入蓝图工作台」链接 → `router.push(/novels/:id/blueprints)`。CreativeStudio 原有能力**零改动**。

### 三栏布局（`ChapterBlueprintWorkbench.vue`）

桌面端三栏 CSS Grid；窄屏折叠为「章节列表 → 编辑 → 上下文」分段（响应式 `@media`）。

```
┌─────────────┬──────────────────────┬─────────────────┐
│ 左栏 章节     │ 中栏 结构化编辑器     │ 右栏 上下文控制   │
│ 导航(筛选/   │ (表单+版本/状态/     │ (大纲/state_delta│
│  搜索/分页/  │  时间/草稿提示/保存) │  /正文/质量/影响/│
│  多选)       │                      │  确认锁定/版本/  │
│             │                      │  回退/操作记录)  │
└─────────────┴──────────────────────┴─────────────────┘
```

### 组件边界

| 组件 | 职责 | props | emits |
|---|---|---|---|
| `BlueprintChapterList.vue` | 左栏：卷/状态筛选、搜索、分页、多选、渲染章号/标题/状态/大纲正文质量标记 | `novelId`, `summaries`, `statusCounts`, `loading`, `selectedChapter`, `selectedSet`, `page`, `pageSize`, `total` | `select(chapter_number)`, `filter-change`, `page-change`, `selection-change` |
| `BlueprintEditor.vue` | 中栏：结构化表单编辑 8 字段（chapter_type/pacing_target 下拉从 options、foreshadow_actions 列表编辑器、key_characters 人物多选、word_target 正整数校验）+ 版本/状态/更新时间 + dirty 提示 + 保存按钮（带 expected_version）+ 409 冲突保留草稿 | `workspace`, `options`, `dirty`, `saving`, `conflict` | `update(field, value)`, `save`, `discard` |
| `BlueprintContextPanel.vue` | 右栏：章节大纲/上一章 state_delta/正文摘要/quality_status/影响预览（复用 `ImpactPreviewPanel`）/确认锁定解锁/重生成/版本历史入口/操作记录 | `workspace`, `impact`, `operations` | `confirm`, `lock`, `unlock`, `regenerate`, `view-versions`, `choice` |
| `BlueprintBatchToolbar.vue` | 批量操作栏：选中章数 + 批量生成/确认/锁定/解锁 + 预览（将处理/跳过锁定/跳过已确认/生成中/预计任务数）+ 部分失败逐章展示 | `selectedSet`, `batchPreview`, `batchResult` | `batch-generate`, `batch-confirm`, `batch-lock`, `batch-unlock` |
| `BlueprintVersionDialog.vue` | 版本历史/字段比较/回退确认：字段名/旧值/新值/是否变化；数组字段新增项删除项；回退前显示目标版本+影响预览+确认+expected_version+409 保留上下文 | `versions`, `compareResult`, `targetVersion`, `impact` | `compare(a,b)`, `rollback(version, expected_version)`, `close` |

### composable `useBlueprintWorkbench.js`

封装工作台状态与 API（复用 `useApi`/`authHeaders`）：
- `summaries`/`statusCounts`/`page`/`pageSize`/`total`/`loading`：列表状态。
- `workspace`/`workspaceLoading`：当前选中章详情。
- `options`：枚举选项（一次加载缓存）。
- `draft`/`dirty`：本地草稿与 dirty 标记。
- `selectedChapter`/`selectedSet`：单选/多选。
- `reqSeq`：请求序号（防快速切章旧请求覆盖，见下）。
- 方法：`fetchSummaries(filters)`、`fetchWorkspace(chapter_number)`、`saveDraft()`、`generate(chapter_number|batch)`、`batchOp(action, chapter_numbers)`、`loadImpact()`、`compareVersions(a,b)`、`rollback(version, expected_version)`、`fetchOperations()`。
- 生成状态轮询：`useWebSocket` 订阅任务进度事件 + 列表轮询兜底（3s，仅 generating 章存在时）。
- 控制操作（lock/unlock/approve/regenerate/rollback/impact/versions）**直接复用 `useCreativeControl`**（`artifact_type="blueprint"`）。

### 数据流

1. 进入页面 → `fetchSummaries({page:1})` + `fetchOptions()`。
2. 点击章节 → 检测 `dirty`：有未保存 → 确认框（保留/丢弃）→ `fetchWorkspace(n)`（带 reqSeq）。
3. 编辑表单 → 更新 `draft` + `dirty=true`。
4. 保存 → `useCreativeControl.editArtifact("blueprint", n, draft, expected_version)` → 409 则 `conflict=true` 保留 draft + 提示刷新/比较；成功 → `dirty=false` + 刷新 workspace + 列表该行状态。
5. 单章生成 → `useCreativeControl.regenerate("blueprint", n, expected_version, {force})` 或 `executeGenerateScope({mode:"blueprint_only", chapter_number:n})` → 返回 task_id → WS/轮询感知状态。
6. 批量生成 → `BlueprintBatchToolbar` 预览（`previewGenerateScope({mode:"blueprint_only", chapter_numbers:[...]})`）→ 确认 → `executeGenerateScope(...)` → 逐章结果展示。
7. 版本比较/回退 → `BlueprintVersionDialog`。

### 并发与错误处理（前端）

- **快速切章防覆盖**：`fetchWorkspace` 用 `reqSeq` 自增序号，返回时比对当前序号，旧请求结果丢弃（也可用 `AbortController`，二选一，reqSeq 更轻且与现有 fetch 风格一致）。
- **409 冲突**：`useCreativeControl._req` 已解析 409（`code/current_version/expected_version`），工作台据此显示 conflictHint + 保留 draft，不丢弃输入。
- **dirty 切章**：`beforeunload`/`select` 前确认。
- **网络失败重试**：`fetchSummaries`/`fetchWorkspace` 失败显示重试按钮（不静默）。
- **部分失败**：批量结果逐章展示，不显示「全部成功」。
- **生成中/失败/锁定**：编辑器按 `control.locked`/`control_status` 禁用编辑（locked 默认不可编辑）。
- **边界状态**：小说不存在/无权限（404/403 提示）、全书无大纲（空列表引导）、章节无蓝图（编辑器显示「未生成，点击生成」）、版本历史为空、影响分析失败（降级提示）。

## 测试策略

### 后端测试（`tests/unit/` + `tests/integration/`，禁止真实 LLM）

新增 `tests/unit/test_blueprint_workbench_service.py`（service 层，mock DB）：
1. 列表包含没有蓝图的章节（Outline 有章号但无 ChapterBlueprint）。
2. 多来源按 chapter_number 去重（Outline+Blueprint+Chapter+Volume 同章号合并为一行）。
3. 按卷/状态/章号范围筛选。
4. 分页与 page_size 上限（>100 截断为 100）。
5. 单章 workspace 详情聚合（各字段正确，缺蓝图时 blueprint=null）。
6. status_counts 正确。
7. options 返回枚举值与 prompts.py 字面量一致。

新增 `tests/unit/test_blueprint_workbench_api_contract.py`（路由层，直调路由函数，mock service，断言 HTTPException）：
8. 无权限访问 → 404/403（verify_novel_owner 拒绝）。
9. workspace 404（章号不存在）。
10. options 静态返回。
11. 批量 lock/unlock/approve 逐章结果 + 部分失败不整体回滚 + 上限 50。

扩展 `tests/unit/test_scope_planner.py`：
12. blueprint_only 多章（chapter_numbers）→ target_chapters 正确 + 上限 50 超限 422。
13. blueprint_only respect_locked/skip_confirmed 按 blueprint 类型 control 过滤。

扩展 `tests/unit/test_creative_generation_dispatch.py`：
14. 多章 blueprint_only 非连续章号拆连续区间 + 逐章 accepted/skipped/already_generating/failed_to_enqueue。

扩展 `tests/unit/test_blueprint_service.py`：
15. chapter_type/pacing_target 非法值 → 422；word_target 非正整数 → 422。

扩展 `tests/integration/test_creative_control_atomic_writes.py`（真实 PG）：
16. 单章生成走后台任务后产 ArtifactVersion 快照 + version_number 自增 + control=generating→generated。
17. 旧 worker 失去 lease 后不能写蓝图（已有 fencing 测试，补 blueprint 路径）。
18. 活动蓝图版本唯一（重新生成后旧 active 失活）。
19. 重新生成/回退不破坏历史版本（历史 ArtifactVersion 仍在）。
20. 批量生成跳过 locked/approved 蓝图（blueprint 类型 control）。

### 前端测试（Vitest + `vi.stubGlobal('fetch')` + `data-*` selector，沿用现有风格）

新增 `frontend/src/views/__tests__/ChapterBlueprintWorkbench.spec.js`：
1. 从 NovelDetail 进入工作台（入口存在 + 路由跳转）。
2. 显示包含「未生成」的章节列表。
3. 按卷和状态筛选。
4. 选择章节后加载结构化表单。
5. 编辑字段并保存正确 payload（含 expected_version）。
6. 锁定蓝图禁用编辑。
7. 409 时保留本地草稿并提示冲突。
8. 有未保存修改时切章提示。
9. 单章生成（POST generate-scope blueprint_only）。
10. 批量生成预览和提交（逐章明细）。
11. 批量部分失败展示。
12. 版本字段对比。
13. 回退确认（带 expected_version + 影响预览）。
14. 快速切章时旧请求不覆盖新选择（reqSeq）。
15. CreativeStudio 原有功能不回归（现有 `CreativeStudio.spec.js` 全过）。

新增组件测试 `frontend/src/components/__tests__/blueprints/*.spec.js`（各组件独立 mount + props/emits 断言）。
新增 `frontend/src/composables/__tests__/useBlueprintWorkbench.spec.js`。

### 验证命令
- 后端：`poetry run ruff check src tests`、`python -m compileall -q src tests`、`poetry run pytest tests/unit/test_blueprint_workbench_service.py tests/unit/test_blueprint_workbench_api_contract.py tests/unit/test_scope_planner.py tests/unit/test_creative_generation_dispatch.py tests/unit/test_blueprint_service.py -q`、`poetry run pytest tests/unit -q`、`poetry run pytest tests/integration/test_creative_control_atomic_writes.py -q`（需隔离 PG 测试库）。
- 前端：`cd frontend && npm test -- --run`、`npm run build`。
- Git：`git diff --check`、`git status --short`。

## 异常与降级

- **control 元数据缺失**：历史蓝图无 ArtifactControl 行 → `get_or_create` 惰性建 `generated`/version=1 行（复用现有）。
- **章节无 Outline**：章节索引该章号仍可由 Blueprint/Chapter/Volume 补齐出现。
- **workspace 子查询失败**：降级 null + 日志，不整体 500。
- **影响分析失败**：降级提示「影响分析失败，建议手动确认」，不阻塞编辑（沿用 Creative Control）。
- **生成中重复投递**：`assert_generation_allowed` 拒绝 → `already_generating`。
- **批量部分失败**：逐章独立事务，不整体回滚，逐章展示。
- **同步生成路径废弃后**：旧 `POST /chapters/{n}/blueprint/generate` 路由保留但改为投递后台任务（向后兼容 URL，行为变更：异步返回 task_id）。

## 兼容与迁移

1. 零 DB 迁移。
2. 现有 creative-control 路由与 CreativeStudio 零改动。
3. `POST /chapters/{n}/blueprint/generate` URL 保留，行为由同步变异步（返回 task_id）—— 调用方需适配，但该路由现仅工作台/内部使用，影响可控。
4. `GenerationScopeIntent` 新增可选字段 `chapter_numbers`，向后兼容（默认 None）。
5. `_filter_chapters` 新增可选 `artifact_type` 参数，默认 "chapter"，向后兼容。
6. 枚举校验为新增约束，历史数据若含非法 chapter_type/pacing_target 值（理论上不应有，因 prompt 约束）会在编辑保存时 422——读取仍正常（只读不校验）。

## 验收标准映射

完成后满足提示词十四验收标准：
1. NovelDetail 进入工作台 ✓（入口+路由）
2. 看到所有已规划章节含无蓝图 ✓（Outline 主轴合并）
3. 数秒定位卷/章 ✓（服务端筛选+分页）
4. 结构化表单编辑非 JSON ✓（BlueprintEditor）
5. 单章/批量生成、编辑、确认、锁定、解锁 ✓
6. 保存/回退并发保护 ✓（expected_version + 409）
7. 版本查看/比较/回退 ✓（BlueprintVersionDialog）
8. 修改前影响预览 ✓（ImpactPreviewPanel 复用）
9. 显示与大纲/正文/质量关联 ✓（workspace 聚合）
10. 数百千章服务端分页 ✓（page_size≤100）
11. 正文生成仍消费活动蓝图 ✓（不改 `_get_blueprint`）
12. CreativeStudio 不受影响 ✓（零改动 + 回归测试）
13. 后端/前端测试+构建通过 ✓
14. 无第二套蓝图/版本/任务/控制系统 ✓（全部复用）

## 实施拆分建议（设计确认后由 writing-plans 细化）

1. 枚举契约 + options 接口 + BlueprintService 写入校验。
2. `BlueprintWorkbenchService` 章节摘要聚合 + list 路由。
3. `BlueprintWorkbenchService.get_workspace` + workspace 路由。
4. 生成路径统一（废弃同步直写 + Intent chapter_numbers + scope 按 blueprint 类型筛选）。
5. dispatcher 逐章明细 + generate-scope 多章。
6. 批量 lock/unlock/approve 路由。
7. 前端 useBlueprintWorkbench + ChapterBlueprintWorkbench 三栏 + 5 组件 + 路由/入口。
8. 前端测试 + 后端集成测试 + 全量验证。
