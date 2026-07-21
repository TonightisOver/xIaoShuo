# 小说创作过程可控性设计

> 在现有「一键黑盒」生成流水线之上，叠加一层**阶段控制层（Creative Control Layer）**，把创作过程升级为可查看、可编辑、可锁定、可审批、可局部重生成、可回退、并发安全的阶段式流程，同时保留一键自动生成能力。复用现有 `ChapterVersion` / 质量门禁 / 候选版本 / `Task` / `TaskCheckpoint` 基础设施，不另造第二套正文版本系统。

## 背景

### 现状（已交叉验证三路探索 + 第一手代码核读）

当前生成是「一键黑盒连续生成」：`create_task` 投入 `PersistentTaskWorker` 后端到端串行跑完，默认无强制人工门禁。三条流水线（短篇 LangGraph / 全功能 13 阶段 / 长篇按卷）共用 `task_manager` 队列与 `pause_state_store` 运行中暂停。

各创作产物的版本/锁定/审计能力**严重不均**：

| 产物 | ORM 模型 | 状态字段 | 版本 | 锁定 | 乐观锁 | 审计 |
|---|---|---|---|---|---|---|
| 项目参数 | `Novel` | `status`(draft/generating/failed/completed) | ✗ | ✗ | ✗ | ✗ |
| 世界观 | `WorldSetting` | 仅 `updated_at` | ✗ | ✗ | ✗ | ✗ |
| 力量体系 | `PowerSystem` | 仅 `updated_at` | ✗ | ✗ | ✗ | ✗ |
| 角色 | `Character` | 仅 `updated_at` | ✗ | ✗ | ✗ | ✗ |
| 总纲 | `Outline(level=master)` / `Novel.master_outline` | `status` | ✗ | ✗ | ✗ | ✗ |
| 卷纲 | `Volume.outline` / `Outline(level=volume)` | `status` | ✗ | ✗ | ✗ | ✗ |
| 章节蓝图 | `ChapterBlueprint` | `is_active`(单活+历史留痕) | 半(无 version_number) | ✗ | ✗ | 被动留痕 |
| 章节正文 | `ChapterVersion` | `is_active` + `Chapter.quality_status` | ✅ 完备 | ✗ | ✗(StaleChapterVersionError 死代码) | 被动留痕 |
| 操作记录 | — | — | — | — | — | **无任何审计表** |

已存在但**未接线 / 未落地**的基础设施（关键风险）：

1. **`checkpoint_store` + `TaskCheckpoint`（迁移 `20260721d`）已建表、已写 store 代码，但全仓零调用**——崩溃恢复未实现，长篇仍会从头重生成。这是长篇稳定性计划未完成的部分。
2. **`StaleChapterVersionError` 定义于 `exceptions.py:39` 但零 raise（死代码）**——正文版本无乐观锁。乐观锁只存在于 `TaskCheckpoint.checkpoint_version` + `CheckpointConflict`。
3. **正文质量计划（`2026-07-20-novel-body-quality`）是平行未落地的设计**：`contracts.py`/`candidate_selector.py` 不存在；`ChapterVersion.quality_report` 字段不存在；`gate.py` 仍是旧签名（`GatePersistCallbacks` + `chapter_result` 注入，`GateResult` 无 `final_version_number`）；`auto_improve_chapter` 仍直接 `activate_chapter_version`。
4. **HITL `human_review` interrupt 架构完整但 `HITL_AUTO_APPROVE=True` 默认跳过**，且长篇 `generate_volume_chapters` 路径不走 LangGraph human_review 节点。
5. 前端：无创作控制台；控制全在 `/task/:id` 的 `TaskDetail`（任务监控器，非阶段控制器）；无锁定 UI / 通用影响范围 UI / 范围选择器。可复用：`StageIndicator`/`ReviewDialog`/`OutlineEditor.analyzeImpact`/`ChapterRangeDialog`/`NovelQualityTab`/`ReaderSimPanel`/`GenerationControlBar`/`VersionDiffView`。

### 本设计与平行计划的关系

- **不依赖**正文质量计划落地——本设计自带可工作的乐观锁 + 操作审计 + 阶段状态层，与正文质量计划的集成点以「若已落地则复用其 X，否则用兼容路径 Y」表述。
- **不接线** `checkpoint_store`（那是长篇稳定性计划的职责，且其崩溃恢复语义与本设计的「阶段审批暂停」语义不同——前者是故障续跑，后者是人工把关）。
- **复用** `ChapterVersion`（正文版本）、`Task`/`operation_id`（任务去重）、`pause_state_store`（运行中暂停）、`OutlineSyncSuggestion`（上游变更→受影响章节建议表，可做影响范围）。

## 目标

1. 创作过程划分为 10 个明确阶段，每阶段可查看产物、编辑、保存草稿、锁定/解锁、标记已确认、重新生成、选择影响范围、查看版本历史、比较版本、回退、显示来源（模型/时间/操作人）、对过期编辑返回 409。
2. 上游修改展示受影响范围，用户可选「只保存 / 重生成直接下游 / 重生成全部受影响 / 保留下游仅标记过期」。
3. 统一控制状态 `draft/generated/edited/approved/locked/stale/generating/failed`；锁定内容不被后台自动覆盖，重生成锁定内容需显式确认。
4. 所有受控写操作携带 `expected_version`，冲突返回 HTTP 409。
5. 生成范围可控：单章 / 范围 / 单卷 / 从某章继续 / 仅重蓝图 / 仅重正文 / 仅修复质量问题 / 保留已锁定 / 跳过已确认 / 预览章数 Token 影响范围。
6. 关键创作操作有结构化审计记录。
7. 三模式并存：自动（连续生成）/ 辅助（关键阶段等确认）/ 手动（逐阶段），**不把每步都改成强制人工审批**。
8. 保留原有一键生成模式。
9. 后端 API + Vue 组件都有自动化测试。

## 非目标

- 不实现长篇崩溃恢复 / checkpoint 接线（长篇稳定性计划职责）。
- 不重构正文质量门禁内部（L0-L3 改进是正文质量计划职责）。
- 不改变短篇 LangGraph 节点内部逻辑，只在阶段边界加控制层。
- 不实现用户级作者偏好学习。
- 不在本阶段做卷级硬审核暂停（长篇卷级硬审核是正文质量计划后续增强）。
- 不为每个产物表逐个加 `version` 列（用统一 control 元数据表集中管理，见下）。

## 方案比较

### 方案一：阶段控制层叠加于现有流水线（采用，渐进）

新增两张通用表 + 一层 control 服务，把现有各产物 CRUD 与生成端点包起来：

- `artifact_controls`：产物类型 + 产物 ID → `control_status` / `locked` / `version`(乐观锁) / `generation_meta`(来源模型/时间/操作人/任务ID) / `stale_reason`。
- `artifact_versions`：通用产物版本快照（仅覆盖现状无版本的 world/character/master_outline/volume_outline/blueprint；正文除外，复用 `ChapterVersion`）。
- `operation_logs`：结构化创作操作审计。

生成流水线**不改核心逻辑**，只在「阶段产物落库」处增加 control 写入与锁定校验；局部重生成复用现有 `generate-volume`/`generate-chapters` 端点 + 新增影响范围计算与范围选择。阶段编排是「后端轻量阶段进度 + 前端协调」，三模式由 `Novel.creation_mode` 决定，自动模式行为与现状完全一致。

**优点**：风险最小、可独立落地、不阻塞平行计划、复用最多、保留一键生成、改动可逐阶段验证。
**缺点**：阶段顺序是「软编排」（后端不强制阻塞生成进入下一阶段）；锁定校验需在各产物写路径插桩（用统一 control 服务收敛，避免散落）。

### 方案二：阶段状态机内嵌生成流水线（强门禁）

在 `Task`/`TaskCheckpoint` 上接出真正的阶段状态机，每阶段 `generating→awaiting_review→approved` 才进下一阶段，接线 `checkpoint_store` 让生成按阶段暂停。

**优点**：后端强一致、阶段顺序有保证。
**缺点**：改动深、与未落地的长篇稳定性计划强耦合、风险高、可能破坏现有「一键生成」体验、违反「渐进、复用」约束。不采用。

### 方案三：新建独立阶段编排引擎（重写）

全新 `StageOrchestrator` + 通用 `ArtifactVersion` 全量接管。

**优点**：架构干净。
**缺点**：违反「不另造第二套系统、不为一抽象而抽象」硬约束，工作量与风险最大。不采用。

## 核心原则

1. **控制层与产物分离**：产物本体（`WorldSetting`/`Character`/`Outline`/…）表不动，控制元数据集中在 `artifact_controls`。这避免给每个产物表加列的散弹改动，且让锁定/版本/审计有统一入口。
2. **正文不重复版本化**：正文版本继续走 `ChapterVersion`；control 层只记录正文的 control_status 与锁定，不复制版本内容。
3. **乐观锁统一在 control 层**：`artifact_controls.version` 每次受控写 +1，写请求带 `expected_version`，不符返回 409。正文复用 `expected_active_version`（control 层实现等价机制；若正文质量计划落地其 `StaleChapterVersionError`，则让路复用）。
4. **锁定是硬约束**：`locked=True` 的产物，后台生成路径写入前必须检查并跳过/报错；重生成锁定产物需显式 `force=True` 或先解锁。
5. **三模式非阻塞**：自动模式 = 现状行为；辅助模式 = 关键阶段产物落库后置 `awaiting_review`（前端拦截提示，但不硬暂停后台任务，长篇避免百万字任务停滞）；手动模式 = 每阶段产物落库后置 `awaiting_review`，前端阶段导航驱动下一步生成。
6. **影响范围基于依赖图**：复用 `OutlineSyncSuggestion` 的「上游→受影响章节」思路，扩展为产物级依赖图（见下）。
7. **事实优先**：手动编辑正文后 `quality_status` 立即 `unverified`（与正文质量计划 Task2 一致，但本设计在 control 层保证，不依赖其落地）。

## 阶段定义与依赖

### 10 阶段

| # | 阶段 | 产物 | 现有 ORM | 版本化方式 |
|---|---|---|---|---|
| 1 | 创意与项目参数 | `Novel`(idea/type/style/字数目标) | `Novel` | control(无内容版本，仅 control 版本号) |
| 2 | 世界观与力量体系 | `WorldSetting`+`PowerSystem`+`CareerSystem` | 现有 | `artifact_versions` |
| 3 | 角色设定 | `Character`(+`CharacterArc`) | 现有 | `artifact_versions` |
| 4 | 全书总纲 | `Outline(level=master)` / `Novel.master_outline` | 现有 | `artifact_versions` |
| 5 | 卷纲 | `Volume.outline` / `Outline(level=volume)` | 现有 | `artifact_versions` |
| 6 | 章节蓝图 | `ChapterBlueprint` | 现有(is_active) | control + 复用 is_active 历史(补 version_number) |
| 7 | 章节正文 | `Chapter`+`ChapterVersion` | 现有 | **复用 ChapterVersion** |
| 8 | 正文质量检查 | `ChapterVersion.quality_*` + 质量报告 | 现有 | control(只读自正文质量) |
| 9 | 人工确认与版本采纳 | 版本激活/回退/采纳候选 | 现有 | **复用 ChapterVersion 激活/回退** |
| 10 | 定稿 | `Novel.status=completed` + 卷/章终态 | 现有 | control 标记 |

### 产物依赖图（影响范围计算依据）

```
项目参数 ─┬─> 世界观 ─┬─> 角色 ──┬─> 总纲 ──> 卷纲 ──> 蓝图 ──> 正文 ──> 质量检查 ──> 确认采纳 ──> 定稿
          │           └─────────┴──────────┘        │
          └─> 力量体系 ──────────────────────────────┘
```

上游修改的受影响范围（用户硬约束映射）：

| 修改 | 直接下游 | 全量受影响 |
|---|---|---|
| 世界规则(WorldSetting/PowerSystem) | 角色 | 角色→总纲→卷纲→蓝图→未定稿正文 |
| 角色设定 | 相关卷纲、蓝图、角色出场章 | 相关卷纲/蓝图/正文 + 连续性 |
| 卷纲 | 该卷未锁蓝图、正文 | 该卷全部未锁蓝图/正文 |
| 章节蓝图 | 该章正文 + 后续连续性状态 | 该章正文 + 后续章连续性 |
| 正文 | 新版本 + `quality_status=unverified` | — |

影响范围计算由 `ImpactAnalyzer`（新服务）基于依赖图 + 各产物 control 状态（`locked`/`approved` 的下游不计入「需重生成」，只计入「需标记 stale」）产出。

## 控制状态模型

`artifact_controls.control_status` 取值（用户硬约束）：

| 状态 | 含义 |
|---|---|
| `draft` | 草稿，未生成或手动编辑中 |
| `generated` | 已由生成产生产物，未人工介入 |
| `edited` | 人工编辑过 |
| `approved` | 人工确认通过 |
| `locked` | 锁定，后台不可覆盖 |
| `stale` | 上游已变更，本产物可能过期 |
| `generating` | 正在生成中 |
| `failed` | 生成失败 |

合法转换（部分）：
- `draft→generating→generated→edited→approved→locked`
- 任何状态→`stale`（上游变更触发）；`stale` 经重生成或确认→`generated`/`approved`
- `locked`→重生成需显式确认→`generating`

## 数据模型

### 新增表

#### `artifact_controls`

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | int PK | |
| `novel_id` | str FK | |
| `artifact_type` | str | `novel/world/character/master_outline/volume_outline/blueprint/chapter/chapter_version/quality/final` |
| `artifact_id` | str | 产物标识（novel_id / world_setting.id / character.id / volume_number / chapter_number / version_number 等，按 type 解释） |
| `control_status` | str | 上表八态 |
| `locked` | bool | default false |
| `version` | int | 乐观锁，default 1 |
| `stage` | str | 所属阶段(1-10) |
| `generation_meta` | JSON | `{source, model, generated_at, operator_id, task_id, operation_id}` |
| `stale_reason` | str nullable | 为何过期（上游 artifact_type+id + 变更版本） |
| `awaiting_review` | bool | 辅助/手动模式下置 true 供前端拦截 |
| `created_at`/`updated_at` | datetime | |

约束：`unique(novel_id, artifact_type, artifact_id)`。

#### `artifact_versions`（通用产物版本快照）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | int PK | |
| `novel_id` | str FK | |
| `artifact_type` | str | `world/character/master_outline/volume_outline/blueprint`（不含正文） |
| `artifact_id` | str | |
| `version_number` | int | 该产物内自增 |
| `content_snapshot` | JSON | 产物内容快照 |
| `source` | str | `manual/generation/rollback` |
| `model` | str nullable | |
| `operator_id` | int nullable | |
| `task_id`/`operation_id` | str nullable | |
| `is_active` | bool | default false（每产物至多一活跃，部分唯一索引） |
| `created_at` | datetime | |

约束：`unique(novel_id, artifact_type, artifact_id, version_number)`；部分唯一索引 `unique(novel_id, artifact_type, artifact_id) where is_active`。

#### `operation_logs`（操作审计）

| 列 | 类型 | 说明 |
|---|---|---|
| `id` | int PK | |
| `novel_id` | str FK | |
| `artifact_type` | str | |
| `artifact_id` | str | |
| `action` | str | `edit/generate/regenerate/lock/unlock/approve/rollback/adopt_candidate/keep_baseline/update_params` |
| `from_version`/`to_version` | int nullable | |
| `operator_id` | int nullable | |
| `reason` | str nullable | |
| `task_id`/`operation_id` | str nullable | |
| `meta` | JSON | 额外上下文 |
| `created_at` | datetime | |

### 现有表新增列

- `Novel.creation_mode`：`auto/assisted/manual`，default `auto`（保留一键生成默认行为）。
- `Novel.creative_stage`：当前推进到的阶段号(1-10)，default 1（仅手动/辅助模式有意义，自动模式忽略）。

### 迁移

单个 Alembic 迁移 `20260721e_add_creative_control.py`，down_revision 指向当前 head（`20260720_task_owner` 或 20260721d，取决于提交顺序——本设计以 20260721d 为前驱，因 a-d 尚未提交，实施时与作者协调链头）。历史数据回填：现有产物按其 `updated_at` 建一条 `generated`/`edited` 的 control 行，`version=1`，`locked=false`。

## 组件边界

### `CreativeControlService`（新，核心）

唯一 control 元数据入口，所有受控写操作经此：

- `get_control(novel_id, artifact_type, artifact_id) -> Control`
- `assert_writable(novel_id, artifact_type, artifact_id, expected_version, *, force=False)`：校验 `expected_version`（不符抛 `ArtifactConflictError`→409）、`locked`（锁定且非 force 抛 `ArtifactLockedError`→409）、`generating` 状态（抛 `ArtifactBusyError`→409）。
- `begin_generating` / `complete_generating` / `fail_generating`：生成前后置状态。
- `mark_stale(novel_id, artifact_type, artifact_id, reason)`：上游变更触发，级联标记下游。
- `lock` / `unlock` / `approve` / `set_status`：带 `expected_version` 的状态转移。
- `bump_version`：受控写成功后 version+1 并写 operation_log。

### `ArtifactVersionStore`（新）

通用产物版本快照读写，仅服务 world/character/master_outline/volume_outline/blueprint：

- `save_version(novel_id, artifact_type, artifact_id, content, source, ...) -> version_number`：旧 active 置 false，插新行，置 active。
- `list_versions` / `get_version` / `compare_versions(a,b)` / `rollback_to(version_number)`。
- 蓝图：复用 `ChapterBlueprint` 的 is_active 历史，补 `version_number` 列（轻量，不另存 snapshot，因蓝图表本身即内容）。

### `ImpactAnalyzer`（新）

输入 `(novel_id, artifact_type, artifact_id)`，依据依赖图 + 各下游 control 状态，返回：

```json
{
  "direct_downstream": [{"artifact_type": "character", "artifact_id": "...", "control_status": "approved", "locked": true}],
  "full_downstream": [...],
  "regenerable": [...],      // 未锁定、可重生成
  "to_mark_stale": [...]      // 锁定/已确认，仅标记
}
```

复用 `OutlineSyncSuggestion` 的章节级影响数据，扩展到产物级。

### `GenerationScopePlanner`（新）

把用户的生成范围意图翻译成现有生成端点调用 + control 锁定/跳过规则：

- 单章/范围/单卷/从某章继续 → 复用 `generate-chapters`/`generate-volume`，按 control 过滤锁定/已确认章。
- 仅重蓝图 → `blueprint/generate` 端点。
- 仅重正文 → `generate-chapters` 带 `regenerate_content_only`。
- 仅修复质量问题 → 复用现有 `auto-improve`/`targeted-rewrite`（候选非活跃化由正文质量计划负责；未落地时本设计在 control 层保证「采纳候选」走 `ChapterVersion` 激活并记 operation_log）。
- 预览：返回预计章节数、估算 Token（按 `words_per_chapter` × 章数 × 每千字 token 估算）、影响范围（调 `ImpactAnalyzer`）。

### 生成流水线集成点（最小插桩）

不改 LangGraph / gate.py 内部，只在产物落库的几个出口加 control 写入：

1. `persist_langgraph_result`（短篇/全功能落库世界观/角色/大纲/章节）→ 落库后调 `CreativeControlService.complete_generating` + `ArtifactVersionStore.save_version`。
2. `long_form_generation_helpers.generate_volume_chapters` 逐章落库 → 同上。
3. `BlueprintService.generate_blueprint` → control 写 `generated` + 蓝图版本。
4. `ChapterService.update_chapter`（手动编辑）→ control 写 `edited` + `Chapter.quality_status=unverified` + operation_log `edit`。
5. 生成前置：`generate_volume_chapters` 每章循环开头检查该章/卷 control 是否 `locked`，锁定则跳过（自动模式）或置 `awaiting_review`（辅助/手动模式）。

**关键：自动模式下这些插桩的净行为 = 现状 + 额外 control 元数据写入，不改变生成结果与流程。** 这是「渐进、不破坏一键生成」的保证。

## 并发与乐观锁

- 所有受控写 API 请求体含 `expected_version`（正文用 `expected_active_version`）。
- `assert_writable` 在事务内 `with_for_update()` 锁 control 行，比对 `version`，不符抛 `ArtifactConflictError`，路由层映射 HTTP 409，响应体含当前 `version` 与产物最新 `updated_at`，提示前端刷新/比较/合并。
- 正文：control 层校验 `expected_active_version` 与 `ChapterVersion.is_active` 行的 `version_number`，不符同样 409。若正文质量计划落地 `StaleChapterVersionError`，control 层复用该异常。
- 生成路径的幂等继续走 `operation_id`（任务级）+ `ChapterVersion.idempotency_key`（版本级），control 层不重复造幂等。

## API 契约

新增路由前缀 `/api/v1/projects/{novel_id}/creative-control`（owner 校验复用 `verify_novel_owner`）：

```
GET    /stage                                 # 阶段导航与完成状态（10 阶段 + 各产物 control 摘要）
GET    /artifacts/{type}/{id}                 # 查看当前产物 + control 元数据
PUT    /artifacts/{type}/{id}                 # 人工编辑（带 expected_version）
POST   /artifacts/{type}/{id}/lock            # 锁定（带 expected_version）
POST   /artifacts/{type}/{id}/unlock
POST   /artifacts/{type}/{id}/approve         # 标记已确认
POST   /artifacts/{type}/{id}/regenerate      # 重新生成（带 expected_version + scope 选项 + force）
GET    /artifacts/{type}/{id}/impact          # 影响范围预览
GET    /artifacts/{type}/{id}/versions        # 版本历史
GET    /artifacts/{type}/{id}/versions/compare?a=&b=
POST   /artifacts/{type}/{id}/versions/{v}/rollback
POST   /artifacts/{type}/{id}/mark-stale      # 仅标记过期（保留下游）
GET    /operations                            # 操作记录（支持按产物/动作/时间筛选）
POST   /generate-scope                        # 生成范围控制（单章/范围/卷/继续/仅蓝图/仅正文/仅修复）
POST   /generate-scope/preview                # 预览章数/Token/影响范围
PUT    /mode                                  # 切换 creation_mode（auto/assisted/manual）
```

正文版本相关复用现有 `/chapters/{n}/versions*` 路由，仅补 `expected_active_version` 参数与 409。

## 三模式行为

| 模式 | 阶段产物落库后 | 后台任务行为 | 前端 |
|---|---|---|---|
| `auto`（默认） | control=`generated`，`awaiting_review=false` | 连续生成（=现状） | 一键生成，控制台只读查看 |
| `assisted` | 关键阶段（1/4/7/9）control=`generated`+`awaiting_review=true` | 不硬暂停，继续生成但标记 | 控制台提示关键阶段待确认，用户可后置审批 |
| `manual` | 每阶段 control=`generated`+`awaiting_review=true` | 该阶段产物落库后不自动推进下一阶段（由前端显式触发 `regenerate` 推进） | 阶段导航驱动逐阶段生成 |

切换 `creation_mode` 不影响已生成内容；只影响后续生成的插桩行为。

## 前端设计

在 `NovelDetail.vue` 增加「创作控制台」入口（新增 tab 或 `/novels/:id/studio` 视图），不重设计整套应用。复用 `StageIndicator`（改可点击）、`ReviewDialog`、`OutlineEditor.analyzeImpact`、`ChapterRangeDialog`、`NovelQualityTab`、`ReaderSimPanel`、`GenerationControlBar`、`VersionDiffView`。

控制台包含：
- 阶段导航与完成状态（10 阶段，可点击进入阶段产物）。
- 当前阶段产物编辑区（按产物类型渲染：世界观文本/角色卡/大纲树/正文编辑器）。
- 锁定 / 确认 / 重新生成按钮（带 `expected_version`，409 时提示刷新/比较/合并）。
- 影响范围预览面板（改上游时弹出，四选项：只保存/重生成直接下游/重生成全部/仅标记过期）。
- 版本历史与差异比较（复用 `VersionDiffView`）。
- 后续内容过期提示（`stale` 标记列表）。
- 生成范围选择器（扩展 `ChapterRangeDialog` 为卷/章树 + 选项）。
- 失败和恢复入口（`failed` 状态产物 + 重试）。
- 正文质量面板入口（链到 `ChapterQualityPanel`/`NovelQualityTab`）。
- 操作记录时间线（`operation_logs`）。

## 异常与降级

- **control 元数据缺失**：历史产物无 control 行时，读路径惰性创建 `generated`/`version=1` 行，不阻塞。
- **锁定与生成的竞争**：生成路径检查 control 锁定用 `with_for_update`，锁定与生成并发时锁定写入先于生成检查则生成跳过该产物。
- **乐观锁冲突**：返回 409 + 当前版本，前端刷新后重试，不静默覆盖。
- **影响范围计算失败**：降级为「标记全量下游 stale」并记 operation_log，不阻塞编辑。
- **正文质量计划未落地**：质量检查阶段 control 只读 `ChapterVersion.quality_score/quality_scores`（现状字段），不依赖 `quality_report`；若已落地则读 `quality_report`。
- **creation_mode 切换中途**：不影响进行中任务，下一阶段起生效。

## 兼容与迁移

1. 新增 3 张表 + `Novel.creation_mode`/`Novel.creative_stage` 2 列。
2. 历史产物回填 control 行（`generated`/`version=1`/`locked=false`），历史正文版本回填 `chapter`/`chapter_version` control。
3. 现有生成端点行为不变（自动模式 = 现状）。
4. 现有 `/chapters/{n}/versions*` 路由补 `expected_active_version` 可选参数，未带时走旧路径（向后兼容）。
5. 前端先加控制台为新视图，不替换现有 NovelDetail tab，灰度切换。

## 测试策略

### control 层单元
- `assert_writable`：版本不符→409、锁定→409、generating→409、force 解锁。
- 状态转换合法性。
- `mark_stale` 级联下游正确，锁定/已确认下游进 `to_mark_stale` 而非 `regenerable`。

### 版本快照
- save_version 旧 active 置 false、新 active 唯一。
- compare/rollback 正确还原内容。
- 蓝图 version_number 补列后历史兼容。

### 影响范围
- 改世界规则→角色/总纲/卷纲/蓝图/未定稿正文。
- 改卷纲→仅该卷未锁下游。
- 改蓝图→该章正文+后续连续性。
- 改正文→新版本+unverified。

### 乐观锁
- 并发写：第二个 409，响应含当前版本。
- 正文 expected_active_version 冲突 409。

### 生成范围
- 各范围意图正确翻译为端点调用 + 锁定/跳过过滤。
- 预览章数/Token/影响范围。

### 三模式
- auto 不阻塞；assisted 关键阶段 awaiting_review；manual 逐阶段不自动推进。
- 切换模式不影响已生成内容。

### 生成插桩回归
- 自动模式下生成结果与现状一致（快照对比）。
- 锁定章在自动模式被跳过。
- 手动编辑正文→quality_status=unverified + operation_log。

### 操作审计
- 10 类 action 各有记录，字段完整。

### 前端
- 控制台阶段导航、编辑保存、锁定、影响范围四选项、版本比较、409 提示、范围选择器、操作时间线。

## 验收标准

1. 用户可在任何主要创作阶段暂停自动流程并编辑产物（三模式）。
2. 锁定内容不会被自动任务覆盖（生成路径插桩校验）。
3. 上游修改计算并展示影响范围（`ImpactAnalyzer`）。
4. 系统不会未经确认删除或覆盖下游内容（四选项 + 锁定）。
5. 可仅重生成指定卷、章节范围或单章（`GenerationScopePlanner`）。
6. 可从历史版本回退（`ArtifactVersionStore` + `ChapterVersion` rollback）。
7. 并发修改通过 409 冲突保护（`expected_version`）。
8. 手动修改正文后旧质量分数不会作为当前分数展示（control 层置 unverified）。
9. 所有关键操作可追溯（`operation_logs`）。
10. 保留原有一键生成模式（auto 模式 = 现状）。
11. 相关后端、API 和 Vue 组件都有自动化测试。

## 实施拆分建议

设计确认后按可独立验证顺序拆为实施计划：

1. control 元数据表 + `CreativeControlService` + 乐观锁/锁定/状态（含 control 单元测试）。
2. `ArtifactVersionStore` + 通用产物版本/比较/回退。
3. `ImpactAnalyzer` + 依赖图 + 影响范围四选项。
4. 生成流水线最小插桩（5 个落库出口）+ auto 模式回归。
5. `GenerationScopePlanner` + 生成范围 API + 预览。
6. `operation_logs` 审计 + 三模式。
7. creative-control API 路由层 + owner 校验 + 409。
8. 前端创作控制台视图 + 阶段导航 + 编辑/锁定/影响范围/版本/范围选择器/操作时间线。
9. 正文 expected_active_version 集成（与正文质量计划集成点）。
10. 端到端回归 + 迁移 + 文档 + 全量验证。
