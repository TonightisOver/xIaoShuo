# 长篇小说生成稳定性设计

> 在不另建平行任务系统的前提下，强化现有长篇生成流水线，使百万字级任务可以安全暂停、恢复、重试和故障恢复，并确保重复执行不会产生重复章节、重复版本或错误进度。

## 背景

本项目已具备一套设计成熟的 PostgreSQL 租约任务队列（`task_manager.py` 的 `claim_next_task` 用 `SELECT … FOR UPDATE SKIP LOCKED` 原子领取，`renew_lease` 严格校验 `lease_owner`，`recover_interrupted_tasks` 启动恢复分类），以及长篇逐章生成流水线（`long_form_generation_helpers.py` 的 `generate_volume_chapters`）。但当前实现存在一批致命的稳定性缺口，使百万字级任务无法安全暂停/恢复/重试，且崩溃或重复投递会产生重复章节与重复版本。

### 架构审计结论（已交叉验证）

| # | 风险 | 证据 | 等级 |
|---|---|---|---|
| R1 | **终态推进无 lease 守卫**：`complete_task`/`fail_task`/`update_status` 无 `with_for_update`、无 `lease_owner` 校验，已丢失 lease 的旧 worker 仍可成功写终态 | `task_manager.py:439-537` | 致命 |
| R2 | **业务层无 lease 复查**：`generate_volume_chapters`/`generate_long_form_background` 循环只查 `pause_store.is_paused`，从不查 lease 所有权；dispatch 被 cancel 后当前章的 DB 写可能完成 | `long_form_generation_helpers.py:616,657` | 致命 |
| R3 | **租约过期后整卷从第 1 章重放**：`existing_chapters` 仅用于字数累计（`:601-605`），不跳过已存在章节；claim 字典无章号进度信息；重放产生重复版本（`max+1` 自增） | `long_form_generation_helpers.py:613`、`task_manager.py:246` | 致命 |
| R4 | **ChapterVersion 无 is_active 部分唯一索引**：`is_active=True` 单活跃不变量全靠应用层清零逻辑，并发重试/崩溃可产生多个或零个活跃版本 | `db_models.py:698-714`（对比 `ChapterBlueprint:824-839` 有部分唯一索引） | 致命 |
| R5 | **无 operation_id / 投递去重**：`create_task` 每次新 task_id，重复点击 `/long-form` 产生并发 Task 写同一 novel | 全项目 grep 零命中 | 致命 |
| R6 | **暂停/resume 依赖进程内协程**：`resume_task` 只清标志不重入队；`recover_interrupted_tasks` 不处理 `paused` 状态；pause 期间独占 worker 单线程 | `novel_generator.py:45-53`、`task_manager.py:636` | 致命 |
| R7 | **进度事件失败把已成功章节判为失败**：`_emit_progress` 无 try/except → `except ch_error` → 跳过 `record_chapter_artifacts`，Chapter 行已存在但无版本 | `chapter_generation_utils.py:29`、`long_form_generation_helpers.py:763` | 高 |
| R8 | **7 个写操作各自独立事务**：Chapter 行、gate 字段、chapter_type、版本、StoryBible、进度事件、LFP 进度无任何两两同事务，中途崩溃留下部分写入的章节，无补偿机制 | `long_form_generation_helpers.py:697-808` | 高 |
| R9 | **三层进度非原子、LFP 计入失败章**：`chapters_completed = len(generated_chapters)` 含失败章；长篇路径不更新 Novel.status；卷失败时 LFP=failed 但 Volume 停在 generating | `long_form_generation_helpers.py:802,1005,1280` | 高 |
| R10 | **fail_task 无前置状态校验可覆盖终态**：可把已完成任务改 failed | `task_manager.py:508-537` | 中 |

### 与正文质量设计的集成约束

正文质量设计文档（`docs/superpowers/specs/2026-07-20-novel-body-quality-design.md`）已确立以下契约，本设计必须遵守：

1. **最终活跃版本所有权**：生成编排器不得在门禁后自行创建第二个活跃 generation 版本。`GateResult.final_content`/`final_version_number` 是唯一最终产物。
2. **原子激活**：用 `with_for_update()` 锁章节及该章所有版本 + `expected_active_version` 乐观锁 + `StaleChapterVersionError`（正文质量计划 Task 7）。
3. **state_delta / StoryBible / 知识图谱只消费最终活跃版本**。
4. **正文质量问题进入待处理队列**，不因单章质量永久阻塞整卷任务。

> **边界声明**：本设计**不负责**修复 `long_form_generation_helpers.py:728-730` 中 gate 返回后 `final_content` 未回写 `chapter_result["content"]` 的问题（那是正文质量计划 Task 9 的职责）。本设计只在检查点契约里约定：当推进到 `quality_finalized` 阶段时，最终活跃版本已由 QualityGate 原子确立，后续副作用只消费该最终版本。两个任务通过"`quality_finalized` 阶段契约"对接，互不侵入。

## 目标

1. 服务重启后可从数据库检查点恢复，从最后一个已提交阶段继续，而非从头重生成。
2. 暂停状态跨进程、跨重启有效；暂停期间不独占 worker。
3. 重试相同章节不产生重复版本；每章任何时刻最多一个活跃版本。
4. lease 丢失的 worker 不再执行持久化写入或终态推进。
5. 同一任务重复投递不产生两份正文（operation_id 去重）。
6. 章节、卷、全书进度保持一致且单调递增。
7. 可恢复错误提供明确重试入口；不可恢复错误保留诊断信息，不伪造完成。
8. 现有短篇生成与正文质量契约不被破坏。

## 非目标

- 不重构 LangGraph 短篇流水线的 checkpointer（短篇已用 sqlite 持久化 checkpointer）。
- 不实现正文质量闭环本身（属正文质量任务）。
- 不引入新的任务队列框架（Celery 已在技术栈中但本设计不依赖它）。
- 不改变 LLM 调用方式或重试策略（复用现有 `should_retry` 分类）。
- 不实现卷级硬暂停的人工审核（正文质量设计已声明为后续独立增强）。

## 方案比较

### 方案一：增量强化现有任务系统（采用）

演进 `TaskManager` 的 lease/claim/recover，新增章节检查点表与现有 Task 表 1:1 关联，给终态推进函数加 lease 守卫，给业务层加阶段提交前的 lease 复查。复用最多现有代码与测试，与正文质量设计的"演进现有 L0–L3 门禁"路线一致。

**可行性证据**：
- `claim_next_task` 的 SKIP LOCKED 已正确防并发领取（R3 的并发领取部分无需重写，只需补"跳过已完成章节"）。
- `renew_lease` 的 owner 校验已正确（R1/R2 只需把同样的守卫推广到终态函数与业务层）。
- `ChapterBlueprint` 已有 `is_active` 部分唯一索引的先例（R4 可直接照搬模式到 ChapterVersion）。
- `pause_state_store` 已是 DB+Redis 双写、DB 为准的模型（R6 只需让 resume 重入队 + recover 处理 paused）。

### 方案二：引入独立检查点服务 + 重写 worker

新建一套基于 outbox/event-sourcing 的检查点服务，worker 重写为事件驱动。隔离性好，但与现有 lease 队列、HITL resume、短篇 checkpointer 三套机制并存，复杂度爆炸，且违反"不创建第二套任务系统"原则。不采用。

### 方案三：依赖 Celery 替换 lease 队列

用 Celery 的任务幂等与重试替代自研 lease。但 Celery 的可见性超时（visibility timeout）同样面临"长任务超时被重投"问题，且会破坏现有 `recover_interrupted_tasks` 与 HITL resume 契约。不采用。

## 核心设计

### 一、operation_id 与投递去重

每个生成任务在 `create_task` 时分配稳定 `operation_id`，语义为"对某 novel 执行某类生成操作"。

- `operation_id` 格式：`{novel_id}:{operation_type}[:{volume_number}]`，例如 `novel-abc:long_form`、`novel-abc:volume:3`、`novel-abc:chapters:5-8`。
- `operation_type` 取自 dispatcher 白名单：`novel.generate` / `novel.full_generate` / `novel.long_form` / `novel.volume` / `novel.chapters` / `pipeline.resume`。
- Task 表新增 `operation_id` 列 + 部分唯一索引：同一 `operation_id` 在非终态（`status NOT IN ('completed','failed','cancelled')`）时只能存在一行。`pipeline.resume` 因是续作同一 operation，复用原 task 的 operation_id（不新建 task，走 `enqueue_existing_task`）。

**去重语义**：用户重复点击 `/long-form` 时，`create_task` 先按 operation_id 尝试插入；命中活跃冲突则返回已存在的 task_id。这从源头消除"同一 novel 两个并发 Task"。

> **B4 决议 — `create_task` 去重的落地实现**（原设计的 `ON CONFLICT DO NOTHING` 在 SQLAlchemy ORM `session.add` 下不会回填已存在行，必须改）：
>
> `create_task` 新签名与实现：
>
> ```python
> async def create_task(
>     self, idea, novel_type, target_words, novel_id=None, *,
>     owner_id=None, task_type=None, task_payload=None, max_attempts=1,
>     operation_id: str | None = None,   # 新增：调用方派生并传入
> ) -> tuple[str, bool]:                  # 返回 (task_id, created)；created=False 表示命中去重
> ```
>
> 实现（单事务、行锁语义靠部分唯一索引兜底，先查后插 + 冲突捕获双保险）：
> 1. 若 `operation_id` 为 None（短篇/无去重需求路径），保持旧行为直接插入，返回 `(new_task_id, True)`。
> 2. 否则先 `SELECT task_id FROM tasks WHERE operation_id = :op AND status NOT IN ('completed','failed','cancelled') LIMIT 1 FOR UPDATE`；命中则返回 `(existing_task_id, False)`。
> 3. 未命中则 `session.add(task)`，`try: await session.commit()`；
>    `except IntegrityError`（并发下另一请求刚插入，触碰 `uq_tasks_operation_active`）→ `rollback` 后重跑第 2 步 SELECT，返回已存在行 `(existing_task_id, False)`。
> 4. 调用方（`novels.py` 的 `/long-form` `/volume` `/chapters`）用返回的 `created` 决定是"新建成功"还是"复用进行中任务"，二者都回 200 + task_id（复用时前端提示"该操作正在进行中"）。
>
> `operation_id` 由**路由层**在调 `create_task` 前派生（见下方"operation_id 派生规则"），不在 `create_task` 内部拼装，保持 TaskManager 不感知业务语义。
>
> **operation_id 派生规则**（路由层）：
> | task_type | operation_id |
> |---|---|
> | `novel.generate` / `novel.full_generate` | `{novel_id}:{task_type}`（novel_id 为占位或新建的 id） |
> | `novel.long_form` | `{novel_id}:long_form` |
> | `novel.volume` | `{novel_id}:volume:{volume_number}` |
> | `novel.chapters` | `{novel_id}:chapters:{chapter_start}-{chapter_end}` |
> | `pipeline.resume` | 复用原 task 的 operation_id（不新建 task，走 `enqueue_existing_task`，见 B13 决议） |

### 二、持久化检查点表

新增 `task_checkpoints` 表，与 Task 表 1:1（每个生成任务一行检查点），字段如下：

| 字段 | 类型 | 说明 |
|---|---|---|
| `task_id` | String, PK, FK→tasks.task_id | 所属任务 |
| `novel_id` | String, index | 小说 |
| `operation_id` | String, index | 稳定操作标识 |
| `current_stage` | String(40) | 当前章节阶段（见下）或 `volume_start`/`volume_end`/`task_end` |
| `volume_number` | Int, nullable | 当前卷号 |
| `chapter_number` | Int, nullable | 当前章号（全局） |
| `last_completed_volume` | Int, default 0 | 最后已完成的卷号 |
| `last_completed_chapter` | Int, default 0 | 最后已完成的章号（全局） |
| `active_version_number` | Int, nullable | 当前章已确立的最终活跃版本号 |
| `checkpoint_version` | Int, default 0 | 检查点版本号，每次推进单调递增（乐观锁） |
| `attempt_number` | Int, default 0 | 当前检查点的尝试次数 |
| `last_event_sequence` | BigInt, default 0 | 最后已发出的事件序列号 |
| `status` | String(20) | 检查点状态：`pending`/`running`/`paused`/`succeeded`/`failed` |
| `pause_requested` | Boolean, default False | 用户请求暂停（与"已暂停执行"区分） |
| `failure_category` | String(30), nullable | `recoverable`/`needs_human`/`unrecoverable` |
| `recoverable` | Boolean, default True | 是否可自动重试 |
| `failure_detail` | JSON, nullable | 诊断信息（错误栈、失败阶段、上下文快照） |
| `updated_at` | DateTime | 最后更新时间 |

**checkpoint_version 乐观锁**：每次推进检查点（`advance_checkpoint`）在事务内 `UPDATE … SET checkpoint_version = checkpoint_version + 1, … WHERE task_id = ? AND checkpoint_version = ?`，受影响行数为 0 即并发冲突，调用方重读后重试或放弃。这保证同一任务的两个 worker 不会同时推进检查点。

**checkpoint 与 lease 的关系**：checkpoint 是业务进度，lease 是执行权。worker 持有 lease 才能推进 checkpoint；lease 丢失后，推进检查点的写操作必须被 lease 守卫拒绝（见下）。

### 三、章节阶段状态机

每章生成分为 6 个阶段，严格顺序推进，前一阶段未提交不得进入下一阶段：

```
chapter_planned → generation_started → baseline_persisted → quality_finalized → side_effects_recorded → chapter_completed
```

| 阶段 | 含义 | 提交时已完成的 DB 写 | 恢复动作 |
|---|---|---|---|
| `chapter_planned` | 章节蓝图已就绪，准备生成 | 无业务写（蓝图已存在） | 进入 `generation_started` |
| `generation_started` | LLM 开始生成正文（或已生成但未落库） | 无 | 重新生成本章（无残留） |
| `baseline_persisted` | Chapter 行已 upsert，baseline 版本已创建为非活跃 | Chapter 行 + ChapterVersion(baseline, is_active=False) | 跳过生成，从 `quality_finalized` 继续 |
| `quality_finalized` | QualityGate 已跑完，最终活跃版本已原子激活 | 基线版本 + 候选（若有）+ 激活 + quality_status/state_delta | 跳过 gate，从 `side_effects_recorded` 继续 |
| `side_effects_recorded` | StoryBible / 知识图谱 / chapter_type / 进度事件已记录 | 上述副作用 + last_event_sequence 推进 | 跳过副作用，进入 `chapter_completed` |
| `chapter_completed` | 本章全部完成，last_completed_chapter 推进 | 全部 | 跳过本章，进入下一章 `chapter_planned` |

**关键不变量**：
- `chapter_completed` 是幂等终态：重试到已完成章节直接跳过，不重新生成、不创建新版本。
- `baseline_persisted` 到 `quality_finalized` 之间崩溃，恢复时**不重新生成正文**，而是基于已持久化的 baseline 版本重跑 gate。
- `quality_finalized` 阶段约定：最终活跃版本由本设计的 `finalize_chapter_version` 幂等激活（见 B9/B10/B18 决议）。

> **B9 / B10 / B18 决议 — 版本创建与激活的所有权边界（用户已确认"本设计自建幂等版本创建+激活"）**
>
> 现状（已验证）：`run_quality_gate`（`src/core/quality/gate.py`）**不创建也不激活任何 ChapterVersion**，只调 `persist_callbacks` 写 `quality_status`/`state_delta`/`quality_scores`；`GateResult` 无 `final_version_number` 字段；版本创建当前在 gate 之外由 `record_chapter_artifacts`→`create_chapter_version(is_active=True)` 完成，且 gate 与 record 顺序错位导致 L3 改写被覆盖（R-verify 断言 4）。因此"gate 幂等/gate 激活版本"是**未落地断言**，本设计不依赖它。
>
> 本设计自建两个明确阶段，替代 §持久化伪代码中含糊的"gate 内部原子激活"：
>
> **`baseline_persisted` 阶段**（本设计负责创建 baseline 非活跃版本）：
> 1. `persist_single_chapter`（upsert Chapter 行，已有幂等：`(novel_id,chapter_number)` 唯一约束）。
> 2. `create_chapter_version(content=chapter_result["content"], source="generation", is_active=False, idempotency_key="{op}:baseline:{n}")` → 返回 `baseline_vn`。幂等：命中已存在 idempotency_key 则返回其 version_number（见 B18 决议的新签名）。
> 3. `advance_checkpoint(stage="baseline_persisted", active_version_number=baseline_vn)`。
>
> **`quality_finalized` 阶段**（本设计负责跑 gate + 幂等激活最终版本）：
> 1. 若 checkpoint 已是 `quality_finalized`（恢复场景），**跳过整个 gate**，直接读 `active_version_number` 进入下一阶段——这是"gate 不需要幂等"的正确解法：checkpoint 记录了 gate 已完成，恢复时不重跑 gate。
> 2. 否则 `run_quality_gate(...)` 得到 `gate_result`。gate 内部若走 L3 改写，会自建 `source="ai_rewrite"` 候选版本（现有 `rewrite_loop_service` 行为，`is_active=False`）。
> 3. 计算 `final_vn`：若 gate L3 激活了候选，则 `final_vn` = 该候选版本号；否则 `final_vn = baseline_vn`。
> 4. 调用本设计新增的 `finalize_chapter_version`（在 `ChapterService`，见 B10 决议签名）做**原子激活**：`with_for_update` 锁 Chapter + 所有版本 → 校验 `expected_active_version == checkpoint.active_version_number`（乐观锁，不匹配抛 `StaleChapterVersionError`）→ 仅激活 `final_vn`、清零其余 → 写回 Chapter.content。
> 5. `advance_checkpoint(stage="quality_finalized", active_version_number=final_vn)`。
>
> **与正文质量任务的合并策略**：正文质量计划 Task 7 也要实现 `finalize_quality_result`（`with_for_update + expected_active_version + StaleChapterVersionError`）。本设计的 `finalize_chapter_version` 与之**是同一个原子激活原语**。实施时：若正文质量 Task 7 已落地，本设计**直接复用** `finalize_quality_result`，只补 `idempotency_key` 与 checkpoint 推进；若未落地，本设计先实现该原语，正文质量任务后续复用。两个计划在实施计划的"依赖顺序"章节显式声明这一共享组件，避免重复实现。
>
> **`active_version_number` 的来源**（修正 B10）：不改 `GateResult`，`final_vn` 直接来自 `create_chapter_version`/候选版本的 `int` 返回值，写入 checkpoint。

### 四、lease 守卫（fence token）

给所有持久化推进操作加 lease 所有权校验。引入 `LeaseGuard` 上下文，业务层在每个阶段提交前调用：

```python
class LeaseLost(Exception):
    """Worker 不再持有任务租约，必须停止后续写入。"""

async def assert_lease_held(task_id: str, worker_id: str) -> None:
    """在每次持久化写入前校验仍持有 lease。失败抛 LeaseLost。"""
    async with get_db_session() as session:
        result = await session.execute(
            select(Task.lease_owner, Task.lease_expires_at, Task.queue_state)
            .where(Task.task_id == task_id).with_for_update()
        )
        row = result.one_or_none()
        now = datetime.now(UTC)
        if (row is None or row.queue_state != "leased"
                or row.lease_owner != worker_id
                or row.lease_expires_at <= now):
            raise LeaseLost(task_id)
```

**应用点**：
1. `complete_task` / `fail_task` / `update_status`：加 `with_for_update` + `lease_owner == worker_id` 校验，否则拒绝写入并抛 `LeaseLost`。这直接修复 R1。
2. `advance_checkpoint`：把 `assert_lease_held` 的校验**内联到同一事务**（见 B3 决议），而非两个独立事务，消除 TOCTOU 窗口。
3. `generate_volume_chapters` 每章循环开头、每个阶段提交前调用 `assert_lease_held`，捕获 `LeaseLost` 后干净退出（见下 B7/B12 决议的传播协议）。这直接修复 R2。
4. dispatcher 在 claim 后把 `worker_id` 注入生成函数签名，业务层全程携带（见下 B1 决议）。

**与 cancel 的关系**：现有 `task_worker.py:123` 的 `dispatch.cancel()` 保留作为快速中断；lease 守卫作为业务层的协作式中断点，保证即使在 cancel 生效前，业务层也不会提交新的持久化写入。两者叠加：cancel 负责尽快停止，lease 守卫负责"停止后绝不再写"。

> **B1 决议 — worker_id 全链路注入路径**
>
> 现状（已验证）：`claim_next_task` 返回的 dict **不含 worker_id**；`dispatch_task(task)` 与所有 `generate_*` 函数签名都不接收 worker_id。选定**最小侵入方案**：
> 1. `task_worker.py:_run_claim`：把 `self.worker_id` 注入 claim dict —— `claim["worker_id"] = self.worker_id`（在调 dispatcher 前）。**不改** `claim_next_task` 的返回结构（避免动 `test_task_manager.py` 对 claim dict 形状的断言；worker_id 由 worker 自己注入，语义更正确）。
> 2. `dispatch_task(task)`：从 `task["worker_id"]` 取出，传给每个 `generate_*` 函数。
> 3. 需加 `worker_id: str` 形参的函数清单（全部在 `long_form_generation_helpers.py` / `novel_generator.py`）：
>    - `generate_long_form_background(task_id, novel_id, request, *, worker_id)`
>    - `generate_volume_background(task_id, novel_id, volume_number, *, worker_id)`
>    - `generate_chapters_background(task_id, novel_id, chapter_start, chapter_end, *, worker_id)`
>    - `generate_volume_chapters(...)` 内部循环 → 一路透传 worker_id
>    - `generate_novel_background` / `generate_novel_full_background`（短篇）：**加形参但可忽略**（短篇不接 checkpoint，worker_id 仅用于终态函数的 lease 守卫）。
>    - `resume_pipeline(task_id, decision, *, worker_id)`：HITL 路径，worker_id 用于终态函数守卫。
> 4. `worker_id` 用 keyword-only（`*`）避免与现有位置参数调用点冲突；测试可显式传 `worker_id="test-worker"`。
>
> **B7 / B12 决议 — LeaseLost 传播协议（修正"release_claim 误标 failed"）**
>
> 现状（已验证）：`release_claim`（`task_manager.py:303-312`）在"非终态且非 waiting_for_review"时会把任务标 `failed`；`_run_claim` 在 dispatch 正常返回时调 `release_claim`、异常时调 `retry_or_fail_claim`。若业务层捕获 `LeaseLost` 后正常 return，会被误标 failed。
>
> 选定协议：**`LeaseLost` 一路向上抛，由 `_run_claim` 专门识别**：
> 1. `generate_volume_chapters` 等业务层捕获 `assert_lease_held` 抛的 `LeaseLost` 后，**不吞掉、不 return**，而是**重新抛出**（或不捕获，直接向上传播）。
> 2. `task_worker.py:_run_claim` 的异常分支改为：
>    ```python
>    except LeaseLost:
>        logger.warning("lease_lost_clean_exit", task_id=task_id, worker_id=self.worker_id)
>        return  # 不调 release_claim / retry_or_fail_claim；lease 已归属新 worker，让其接管
>    except Exception as exc:
>        ...  # 现有逻辑：retry_or_fail_claim
>    ```
> 3. 这样 `LeaseLost` 路径**既不调 `release_claim`（避免误标 failed）也不调 `retry_or_fail_claim`**。任务此刻的 `lease_owner` 已是新 worker，旧 worker 静默退出，新 worker 的 heartbeat 继续，任务从 checkpoint 继续。
> 4. `release_claim` 自身**无需修改**——因为旧 worker 根本不会调它（LeaseLost 分支直接 return）。这比"改 release_claim 加 LeaseLost 例外"更干净。

### 五、幂等键

每个可重放写操作拥有确定性 `idempotency_key`，格式 `{operation_id}:{stage}:{chapter}`：

| 写操作 | idempotency_key | 幂等机制 |
|---|---|---|
| 创建 Chapter 行 | `{op}:chapter:{n}` | upsert by `(novel_id, chapter_number)` 唯一约束（已有） |
| 创建 baseline 版本 | `{op}:baseline:{n}` | 新增 ChapterVersion.`idempotency_key` 列 + 唯一索引，冲突时返回已存在版本号 |
| 激活最终版本 | 无独立幂等键 | 由 checkpoint `stage='quality_finalized'` 保证：恢复时若已达该阶段则跳过整个 gate + 激活（见 §五 B18/B10 决议）；激活本身用 `finalize_chapter_version` 的 `expected_active_version` 乐观锁 + 行锁保证原子与幂等 |
| StoryBible 更新 | `{op}:bible:{n}` | 在 Chapter 行记录 `bible_applied_version`，已应用则跳过 |
| 知识图谱更新 | `{op}:kg:{n}` | 在 Chapter 行记录 `kg_applied_version`，已应用则跳过 |
| 进度事件 | `{op}:event:{seq}` | 事件带 `sequence`，订阅方/持久层按 seq 去重 |
| 推进 last_completed_chapter | `{op}:complete_chapter:{n}` | checkpoint_version 乐观锁 + 阶段已是 `chapter_completed` 则跳过 |

ChapterVersion 新增 `idempotency_key` 列（nullable，新版本写入时填入），加 `UniqueConstraint(novel_id, chapter_number, idempotency_key)`（nullable 列的多行 NULL 不冲突，符合 SQL 语义）。重试同检查点时，`create_chapter_version` 先按 idempotency_key 查找已存在版本，命中则返回其 version_number 而非新建——这直接修复 R3 的重复版本问题。

> **B18 决议 — `create_chapter_version` 幂等签名（现有 gate 不创建版本）**
>
> 现状（已验证）：`run_quality_gate`（`gate.py:52`）全程**不创建、不激活任何 ChapterVersion**，只调 `persist_callbacks` 三个回调。版本创建/激活都在 gate 之外由 `record_chapter_artifacts`→`create_chapter_version(is_active=True)` 完成，且 `create_chapter_version`（`chapter_service.py:190-265`）用 `max(version_number)+1` 自增，**无任何幂等查重**。所以设计正文里"gate 本身是幂等的"是**未来态描述，不是现状**——本设计按用户决策**自建幂等版本创建 + 激活**，不依赖正文质量 Task 7/8 先落地。
>
> `create_chapter_version` 新签名（增加 keyword-only `idempotency_key`）：
> ```python
> async def create_chapter_version(
>     self, novel_id, chapter_number, content,
>     source="manual", ...,  # 现有参数不变
>     is_active=False,
>     idempotency_key: str | None = None,   # 新增
> ) -> int:
>     async with get_db_session() as session:
>         # 幂等查重：命中已存在版本则直接返回其 version_number
>         if idempotency_key is not None:
>             existing = await session.execute(
>                 select(ChapterVersion.version_number).where(
>                     ChapterVersion.novel_id == novel_id,
>                     ChapterVersion.chapter_number == chapter_number,
>                     ChapterVersion.idempotency_key == idempotency_key,
>                 )
>             )
>             hit = existing.scalar_one_or_none()
>             if hit is not None:
>                 return hit   # 幂等命中，不新建
>         # ... 现有 with_for_update + max+1 逻辑不变，写入时带上 idempotency_key
> ```
> 幂等键来源：baseline 版本用 `{op}:baseline:{n}`，激活候选用 `{op}:activate:{n}`。`record_chapter_artifacts` 与 gate 外的激活调用点都要传入 idempotency_key。
>
> **B19 决议 — StoryBible 幂等（`update_bible_after_generation` 加版本号，哨兵回填）**
>
> 现状（已验证）：`update_bible_after_generation(novel_id, chapter_number, chapter_content, chapter_outline)`（`content/story_bible_service.py:210`）**不接收版本号**，每次调用都跑 LLM + append timeline/hooks（append 语义，重跑会重复累加）。
>
> 新签名（增加 keyword-only `applied_version`）：
> ```python
> async def update_bible_after_generation(
>     novel_id, chapter_number, chapter_content, chapter_outline,
>     *, applied_version: int,   # 新增：本次消费的最终活跃版本号
> ) -> dict:
>     async with get_db_session() as session:
>         # 幂等：读 Chapter.bible_applied_version
>         ch = await session.get_chapter_row(...)  # 查 Chapter 行
>         if ch.bible_applied_version is not None and ch.bible_applied_version >= applied_version:
>             return {"skipped": True}   # 已应用，跳过 LLM + append
>         # ... 现有 LLM 分析 + merge 逻辑不变
>         ch.bible_applied_version = applied_version   # 成功后写标记（同事务）
> ```
> `bible_applied_version=NULL` 即"未应用"，重试时 NULL < applied_version 触发重跑。历史章由迁移 3 回填哨兵 `-1`（见迁移决议），避免对历史稳定章重复 append。调用点 `record_chapter_artifacts`（`chapter_persistence_service.py:236`）需传入 `applied_version=final_version_number`。
>
> **B20 决议 — 长篇补接 KG（幂等判定用 KnowledgeExtractionLog）**
>
> 现状（已验证）：`extract_from_chapter`（`knowledge/knowledge_graph_service.py:38`）签名兼容长篇调用，但长篇路径 `generate_volume_chapters` **完全不调用它**；且 KG 三元组是 append-only（`add_triple` 每次 `uuid4()` 新 id，无去重）。
>
> - **幂等判定数据源**：用已有的 `KnowledgeExtractionLog`（每章一条抽取记录，有 `status` 字段）。`side_effects_recorded` 阶段调 `extract_from_chapter` 前先查该章 `KnowledgeExtractionLog.status == 'completed'`，命中则跳过。成功后写 `status='completed'` + `kg_applied_version`（Chapter 行）。
> - **`final_version_content` 来源**：`side_effects_recorded` 阶段在 `quality_finalized` 之后，此时 checkpoint 的 `active_version_number` 已确立，从 `ChapterVersion(is_active=True)` 读取最终正文（**不依赖** `chapter_result["content"]`，规避正文质量 Task 9 未落地的问题）。这也满足集成约束"KG 只消费最终活跃版本"。

### 六、ChapterVersion 单活跃不变量（部分唯一索引）

照搬 `ChapterBlueprint` 的模式，给 ChapterVersion 加部分唯一索引：

```python
Index(
    "uq_chapter_version_active",
    "novel_id", "chapter_number",
    unique=True,
    postgresql_where=Column("is_active").is_(True),
),
```

这从 DB 层保证每章至多一个 `is_active=True` 版本，应用层清零逻辑失效时由 DB 拒绝写入。这直接修复 R4。迁移时需先清理历史脏数据（存在多活跃版本的章），否则创建索引会失败——清理策略见迁移 2 决议（按 `version_number` 最大者保留 active，而非 `MAX(id)`，避免回滚场景选错版本；迁移前须停 worker）。

### 七、暂停/恢复跨进程化

将 pause 从"进程内协程阻塞"改为"DB 标志 + 重入队"。**核心状态区分**（修正现有 `set_paused` 瞬间置 `status='paused'` 的问题）：

- `pause_requested=True`：用户已请求暂停，但 worker 可能还在跑到安全边界。**此时 `status` 仍是 `running`**。
- `status='paused'`：worker 已确认到达安全边界、清 lease、退出。这是"已暂停执行"的权威信号。

改造点：

1. **`set_paused` 只设意图，不动 status**：`pause_state_store.set_paused(task_id)` 改为设 checkpoint `pause_requested=True` + Redis `PAUSE_REQUESTED` 通知，**不再** `_set_db_status(task_id, "paused")`。避免"用户点暂停瞬间 status 就变 paused 但 worker 还在写"的假象。
2. **`is_paused` 拆成两个语义**：
   - `is_pause_requested(task_id) -> bool`：读 checkpoint `pause_requested`（Redis 加速 + DB 兜底）。业务层循环用它判断"是否该在安全边界停下"。
   - `is_paused_confirmed(task_id) -> bool`：读 checkpoint `status == 'paused'`。路由/前端用它判断"是否真的已暂停"。
   - 现有 `novel_generator.py:56` 的 `is_task_paused` 语义映射到 `is_pause_requested`（业务层调用点），保持调用方兼容。
3. **worker 协作式暂停**：`generate_volume_chapters` 每章循环开头检查 `is_pause_requested`，为真则在当前章 `chapter_completed` 之后：`advance_checkpoint(status='paused')`（lease 守卫内）→ 通过一个新的 `TaskManager.mark_paused(task_id, worker_id)`（行锁 + owner 校验）把 `queue_state='idle'`、清 lease → 抛内部信号 `PausedExit` 让 dispatch 干净返回。**不再 `while is_paused: sleep(1)` 阻塞 worker**。`_run_claim` 识别 `PausedExit` 后**跳过 `release_claim`/`retry_or_fail_claim`**（与 `LeaseLost` 同样处理，见 §四）。这修复 R6 的"独占 worker"。
4. **resume 重入队**（修正 B5 的自相矛盾）：新增 `TaskManager.requeue_paused_task(task_id)`（行锁）：
   - 前置校验：checkpoint `status == 'paused'` **且** `pause_requested == True`。不满足则返回 `RequeueResult(requeued=False, reason=...)`，路由据此返回 409（状态不匹配）或 200 no-op（已在 running/queued）。
   - 满足则：checkpoint `pause_requested=False`、`status='running'`；Task `queue_state='queued'`、`status='pending'`、`available_at=now`、清 lease。
   - **幂等**：第二次调用时 checkpoint `status` 已是 `running`（非 `paused`），返回 `requeued=False, reason='not_paused'`，路由返回 **200 + 当前 checkpoint 摘要**（视作 no-op，因为目标态已达成）。仅当 `status` 处于既非 paused 也非 running/queued 的非法态时返回 409。
   - `resume_task` 重写为调 `requeue_paused_task`，不再 `clear_paused` 硬切 running。长篇非 HITL 暂停 resume 用此路径（**不新增 TaskType**，复用原 task 的 task_type 重新 claim）。HITL resume 仍走 `enqueue_existing_task(task_type='pipeline.resume')`（见 §十四 HITL 边界）。
5. **recover_interrupted_tasks 处理 paused**：启动恢复时，checkpoint `status='paused'` 的任务：若 `pause_requested=False`（被 resume 过但 worker 没起来），重入队；若 `pause_requested=True`，保持 paused 等待用户 resume。**现有 `recover_interrupted_tasks` 只查 Task 表**，需扩展 join checkpoint 表。
6. **volume 级 pause 统一**：`pause_volume_generate`（`novels.py:491`）同时写所属 task 的 checkpoint `pause_requested=True`（不再只写 LFP.status）。因一个 task 可能跨多卷，卷级 pause 语义定义为"task 在下一章安全边界暂停"——即卷级 pause 等价于 task 级 pause，checkpoint 的 `volume_number` 记录暂停发生的卷。消除 LFP.status 与 task 状态的双轨制。

### 八、进度单调递增与事件序列号

1. **last_event_sequence**：checkpoint 表维护单调递增的事件序列号。`_emit_progress` 改为先从 checkpoint 取 `last_event_sequence + 1` 作为事件 seq，写入后推进 checkpoint。订阅方按 seq 去重/排序。
2. **进度事件失败不判失败**：`_emit_progress` 包裹 try/except，失败仅 log + 记入 `failure_detail`，不抛异常，不阻断章节流程。这修复 R7。
3. **percentage 单调**：进度计算基于 `last_completed_chapter`（持久值），不再用 `len(generated_chapters)`（含失败章）。失败章不计入 completed。这修复 R9 的计数偏差。
4. **complete_task 不覆盖 100%**：`complete_task` 在 `partially_completed`/`completed_with_unverified_quality` 时写真实 percentage，不强制 100。

### 九、错误分类

`failure_category` 三类 + `pause_requested` + `lease_lost`，替代当前"只看 attempt_count"：

| 类别 | 判定 | 处理 |
|---|---|---|
| `recoverable` | LLM 超时/429/连接错误（复用 `should_retry`）、gate 临时失败、进度事件失败 | 自动重试，attempt_number++，受 max_attempts 限制 |
| `needs_human` | `consistency_blocked` 质量问题、StoryBible/KG 持续失败超阈值 | 不重试，进入待处理队列，保留诊断，任务 `status='paused'` 等待人工介入（不伪造完成） |
| `unrecoverable` | operation_id 冲突无法解决、checkpoint 损坏、不可重放的 legacy 任务 | `status='failed'`，保留 `failure_detail`，不重试 |
| 正常暂停 | `pause_requested=True` | `status='paused'`，可 resume |
| lease 丢失 | `LeaseLost` | 不改变 task 状态（让 lease 过期后被新 worker 接管），旧 worker 干净退出 |

**长篇 max_attempts 提升**：长篇任务在 `/long-form` 创建路径（`novels.py`）传 `max_attempts=settings.LONG_FORM_MAX_ATTEMPTS`（默认 3），配合 checkpoint 使重试从断点继续而非从头。短篇 `novel.generate`/`novel.full_generate` 保持 `max_attempts=1`。

**attempt_count 与 attempt_number 的权威关系**（修正 B13）：
- Task 表的 `attempt_count` 保持为 **claim 次数计数器**（`claim_next_task` 自增），是 lease 队列层的重投计数，语义不变。
- checkpoint 表的 `attempt_number` 是 **当前断点的业务重试计数**，只在 `advance_checkpoint` 遇到 recoverable 失败时自增。
- 二者独立：`attempt_count` 管"任务被 claim 了几次"（含 lease 过期重投），`attempt_number` 管"当前章节阶段重试了几次"。当某章成功推进到 `chapter_completed` 时，`attempt_number` 归零（新章节从 0 起）。
- **HITL resume 时**：`enqueue_existing_task` 已重置 `Task.attempt_count=0`（现有行为，保留）；checkpoint 的 `attempt_number` **不受影响**（HITL resume 走 LangGraph checkpointer，不触碰 task_checkpoints，见 §十四）。因此两个计数器脱节问题不存在——它们服务于两条互不重叠的路径。

**短篇路径的 recover 行为（修正 B11）**：短篇 `max_attempts=1`，lease 过期后 `recover_interrupted_tasks` 会走"attempt >= max → failed"分支。这是**既有行为，本设计不改**：短篇的 LangGraph sqlite checkpointer 保的是 pipeline 内部状态（节点进度），Task 行标 failed 后，用户可通过现有 HITL resume 或重新触发生成从 LangGraph checkpoint 恢复。本设计的 task_checkpoints **只服务长篇非 HITL 路径**，不与短篇 checkpointer 交叉。设计明确声明：短篇 lease 过期=Task failed 是保留行为，短篇恢复依赖 LangGraph checkpointer 而非 task_checkpoints。

### 十、三层进度一致性

1. **单一真相源**：checkpoint 的 `last_completed_volume`/`last_completed_chapter` 是进度的唯一权威。LFP 表的 `chapters_completed` 由 checkpoint 派生（`last_completed_chapter - chapter_start + 1`），不再独立计数。
2. **推进顺序**：章节完成 → 推进 checkpoint `last_completed_chapter` → 派生更新 LFP → 卷完成时推进 `last_completed_volume` + 更新 Volume.status + LFP.status → 全书完成时更新 Novel.status。每步带 lease 守卫。
3. **长篇路径补 Novel.status 更新**：`generate_long_form_background` 全部卷完成时调 `update_novel(status='completed')`，失败时 `failed`。这修复 R9 的"长篇不更新 Novel.status"。

### 十四、HITL 与 task_checkpoints 的边界（B21 决议）

按用户决策，**task_checkpoints 只服务长篇非 HITL 路径**，与 HITL/短篇的 LangGraph checkpointer 严格分离，避免两套恢复机制交叉。

| 路径 | 恢复机制 | task_checkpoints |
|---|---|---|
| 长篇 `generate_long_form_background`/`generate_volume_background`/`generate_chapters_background` | task_checkpoints 章节 6 阶段 | **有** checkpoint 行，驱动恢复 |
| HITL `pipeline.resume`（短篇 LangGraph 审核后续作） | LangGraph sqlite checkpointer | **无** checkpoint 行（或存在但恢复不读它） |
| 短篇 `novel.generate`/`novel.full_generate` | LangGraph checkpointer | **无** checkpoint 行 |

**落地规则**：
1. `task_checkpoints` 行**只在长篇任务 dispatch 时创建**（`generate_long_form_background` 入口 `ensure_checkpoint`）。短篇/HITL 任务不创建 checkpoint 行。
2. `advance_checkpoint`/`assert_lease_held` 的 lease 守卫**对所有路径生效**（lease 是队列层机制，与 checkpoint 无关）——即短篇任务的 `complete_task`/`fail_task` 也受 lease 守卫保护（修复 R1 覆盖全路径），但不涉及 checkpoint 推进。
3. HITL resume（`enqueue_existing_task(task_type='pipeline.resume')`）**不重置也不读取 checkpoint**。若某长篇任务历史上有 checkpoint 行而后走了 HITL（不会发生，因长短篇 task_type 互斥），恢复时以 task_type 为准选择机制。
4. `recover_interrupted_tasks` 扩展 join checkpoint 时，**只对有 checkpoint 行的任务**应用"从断点继续"逻辑；无 checkpoint 行的任务保持现有分类恢复（queued 保留、过期 leased 重排/失败、legacy 失败），短篇 sqlite checkpointer 独立恢复。
5. `complete_task` 的 progress 覆盖问题：对有 checkpoint 的长篇任务，**checkpoint 是进度唯一真相源**，`complete_task` 不再写 `progress.current_stage`（改为只写终态 result）；短篇任务保持现有 progress 写入（无 checkpoint，progress 仍是其进度源）。

## 持久化与事务边界

章节生成的 7 个写操作仍可保持各自独立事务（避免单个超长事务持锁），但通过检查点阶段把它们组织成**可恢复的序列**：

```
chapter_planned:
  [无写]
generation_started:
  [LLM 调用，无 DB 写]
  → advance_checkpoint(stage='generation_started')  # lease 守卫
baseline_persisted:
  persist_single_chapter (upsert Chapter 行)
  create_chapter_version(baseline, is_active=False, idempotency_key)
  → advance_checkpoint(stage='baseline_persisted', active_version_number=baseline_vn)
quality_finalized:
  run_quality_gate  # 只产出评分/候选，不激活版本（见 B18/B10 决议：gate 不碰版本）
  finalize_chapter_version(  # 本设计自建：with_for_update 锁章+全版本，乐观锁校验
      expected_active_version=checkpoint.active_version_number,  # =baseline_vn
      selected_version=final_vn,
      idempotency_key='{op}:activate:{n}')  # 幂等：命中已激活则直接返回
  → advance_checkpoint(stage='quality_finalized', active_version_number=final_vn)
side_effects_recorded:
  final_version_content = read ChapterVersion(is_active=True)  # 从最终活跃版本读，不用 chapter_result["content"]
  update_bible_after_generation(final_version_content, applied_version=final_vn)  # 幂等，按 bible_applied_version 跳过
  extract_from_chapter(final_version_content)  # 长篇路径补接 KG，幂等（KnowledgeExtractionLog 判定）
  _sync_chapter_type_to_db
  _emit_progress(seq=last_event_sequence+1)  # try/except，失败不阻断
  → advance_checkpoint(stage='side_effects_recorded', last_event_sequence=seq)
chapter_completed:
  → advance_checkpoint(stage='chapter_completed', last_completed_chapter=n)
  update_volume_status(派生 chapters_completed)  # lease 守卫
```

**崩溃恢复**：重启后 worker claim 该 task，读 checkpoint，若 `current_stage='side_effects_recorded'` 且 `chapter_number=n`，则从"推进到 chapter_completed"继续，跳过 n 章的生成/gate/副作用。若 `current_stage='baseline_persisted'`，则基于已持久化 baseline 版本重跑 gate——重跑时 `create_chapter_version` 用 `{op}:activate:{n}` 幂等键，命中已存在激活版本则直接返回其版本号，不重复激活（见 §五 B18 决议）。**绝不从头重生成已完成的章节**。

### advance_checkpoint 完整签名（修正 B3）

`advance_checkpoint` 是检查点推进的唯一入口，**内含 lease 守卫**（把 `assert_lease_held` 与 UPDATE 放同一事务，消除 TOCTOU）：

```python
class CheckpointConflict(Exception):
    """checkpoint_version 乐观锁冲突：另一 worker 已推进检查点。"""

async def advance_checkpoint(
    task_id: str,
    worker_id: str,
    *,
    expected_checkpoint_version: int,        # 乐观锁：调用方读到的版本
    stage: str,                              # 目标阶段
    volume_number: int | None = None,
    chapter_number: int | None = None,
    active_version_number: int | None = None,
    last_completed_volume: int | None = None,
    last_completed_chapter: int | None = None,
    last_event_sequence: int | None = None,
    status: str | None = None,               # 仅在 paused/succeeded/failed 时传
    failure_category: str | None = None,
    failure_detail: dict | None = None,
    recoverable: bool | None = None,
) -> int:                                    # 返回新的 checkpoint_version
    """在单事务内校验 lease + 乐观锁，推进检查点。

    抛 LeaseLost：worker 不再持有 lease（含暂停后 queue_state=idle 的场景，
      由调用方结合 PausedExit 区分，见下）。
    抛 CheckpointConflict：expected_checkpoint_version 不匹配（并发推进）。
    """
    async with get_db_session() as session:
        # 1. 同事务锁 Task + checkpoint 行
        task_row = (await session.execute(
            select(Task).where(Task.task_id == task_id).with_for_update()
        )).scalar_one_or_none()
        now = datetime.now(UTC)
        # 2. lease 守卫（暂停确认场景例外见 B2 决议）
        if (task_row is None
                or task_row.lease_owner != worker_id
                or task_row.lease_expires_at is None
                or task_row.lease_expires_at <= now):
            raise LeaseLost(task_id)
        # 3. 乐观锁 UPDATE
        result = await session.execute(
            update(TaskCheckpoint)
            .where(TaskCheckpoint.task_id == task_id,
                   TaskCheckpoint.checkpoint_version == expected_checkpoint_version)
            .values(
                current_stage=stage,
                checkpoint_version=expected_checkpoint_version + 1,
                updated_at=now,
                **{k: v for k, v in {
                    "volume_number": volume_number,
                    "chapter_number": chapter_number,
                    "active_version_number": active_version_number,
                    "last_completed_volume": last_completed_volume,
                    "last_completed_chapter": last_completed_chapter,
                    "last_event_sequence": last_event_sequence,
                    "status": status,
                    "failure_category": failure_category,
                    "failure_detail": failure_detail,
                    "recoverable": recoverable,
                }.items() if v is not None},
            )
        )
        if result.rowcount == 0:
            raise CheckpointConflict(task_id, expected_checkpoint_version)
        return expected_checkpoint_version + 1
```

**关于 B2 的 lease 守卫例外**（暂停时 `queue_state='idle'`）：`advance_checkpoint` 的 lease 守卫**只校验 `lease_owner` 和 `lease_expires_at`，不校验 `queue_state`**。这样"worker 到达安全边界、置 `status='paused'`"这一次推进不会因 `queue_state` 尚未改 idle 而误抛 LeaseLost。暂停的时序严格为：先 `advance_checkpoint(status='paused')`（此时 lease 仍持有）→ 再 `mark_paused` 清 lease + 置 `queue_state='idle'`。清 lease 之后业务层不再有任何 `advance_checkpoint` 调用（直接抛 `PausedExit`）。因此 B2 描述的窗口不存在。

**调用方模式**：业务层持有本地 `checkpoint_version`（claim 后读一次），每次 `advance_checkpoint` 用它作 `expected_checkpoint_version`，成功后更新本地值为返回值。`CheckpointConflict` 意味着有第二个 worker 在推进（异常场景），调用方应抛 `LeaseLost` 语义干净退出（不重试，避免双写）。

### 卷级与任务级状态转换（修正 B8）

除 6 个章节阶段外，`current_stage` 还有 3 个跨章/跨卷阶段。完整状态转换表：

| 阶段 | 进入条件 | 提交的 DB 写 | 恢复动作 |
|---|---|---|---|
| `volume_start` | 卷循环开始，上一卷 `volume_end` 或首卷 | LFP 行 upsert(status='generating')；checkpoint `volume_number=v` | 进入本卷第一章 `chapter_planned` |
| （6 个 chapter_* 阶段循环，每章走一遍） | | | |
| `volume_end` | 本卷最后一章 `chapter_completed` | 推进 `last_completed_volume=v`；Volume.status='completed'；LFP.status='completed' | 进入下一卷 `volume_start`（若还有卷）或 `task_end` |
| `task_end` | 所有卷 `volume_end` 完成 | Novel.status='completed'（长篇路径补，修正 R9）；Task 经 `complete_task` 置终态 | 幂等终态，重放直接返回 |

**卷切换伪代码**（每步带 lease 守卫，通过 advance_checkpoint）：

```
for volume in volumes:
    if checkpoint.last_completed_volume >= volume.number:
        continue                                    # 已完成卷，跳过（幂等）
    advance_checkpoint(stage='volume_start', volume_number=volume.number)
    upsert LFP(volume, status='generating')
    for chapter in volume.chapters:
        if checkpoint.last_completed_chapter >= chapter.global_number:
            continue                                # 已完成章，跳过（修正 R3）
        run 6-stage chapter pipeline                # 见持久化伪代码
    advance_checkpoint(stage='volume_end',
                       last_completed_volume=volume.number)
    Volume.status = 'completed'; LFP.status = 'completed'   # lease 守卫
advance_checkpoint(stage='task_end')
Novel.status = 'completed'                           # 长篇补 R9
complete_task(task_id, worker_id, result)            # lease 守卫（修正 R1）
```

**卷失败处理**（修正 R9 的"Volume 停在 generating"）：卷循环中任一章抛非 `LeaseLost`/`PausedExit` 的 recoverable 异常且超 max_attempts 时，`advance_checkpoint(status='failed', failure_category=..., failure_detail=...)`，并把当前 Volume.status 和 LFP.status 一并置 `failed`（不再让 Volume 停在 generating）。

## 故障注入场景覆盖

| 场景 | 当前行为 | 改造后行为 |
|---|---|---|
| LLM 返回前进程退出 | 整卷重跑 | checkpoint 在 `generation_started`，重生成本章，无残留 |
| 正文生成完成未写 DB | 整卷重跑 | checkpoint 在 `generation_started`，重生成本章 |
| Chapter 已写但版本未创建 | 重跑产生重复版本 | checkpoint 在 `baseline_persisted` 前，gate 重跑基于已写 Chapter 行；baseline 版本按 idempotency_key 去重 |
| baseline 版本创建后退出 | 产生 v2 重复版本 | checkpoint 在 `baseline_persisted`，跳过生成，从 `quality_finalized` 继续；baseline 版本按 idempotency_key 去重（不产生 v2） |
| 质量门禁选出最终版本后退出 | L3 改写被 v2 覆盖 | checkpoint 在 `quality_finalized`，最终版本已原子激活，跳过 gate |
| Story Bible 更新失败 | 静默吞掉，永久不一致 | 记录 `bible_applied_version` 未应用，重试时按 idempotency 重跑；超阈值转 `needs_human` |
| 知识图谱更新失败 | 长篇根本未接 KG | 长篇补接 KG，幂等重试；超阈值转 `needs_human` |
| 进度事件发送失败 | 已成功章节被判失败 | try/except 吞掉，seq 不推进但章节继续；下次重发 |
| Worker 执行期间 lease 过期 | 旧 worker 继续写终态 | lease 守卫拒绝终态写入，旧 worker 抛 LeaseLost 退出 |
| 同一任务两个 Worker 同时领取 | SKIP LOCKED 已防（但 lease 过期后可能） | checkpoint_version 乐观锁 + lease 守卫双重保证只有一个推进成功 |
| 暂停后服务重启 | paused 任务永久孤儿 | resume 重入队，任意 worker 从 checkpoint 继续 |
| 恢复接口被重复调用 | clear_paused 硬切 running，可能覆盖正在执行的任务 | resume 幂等（§七.4 决议）：`pause_requested=True` 生效；已 running/queued 则 200 no-op；终态返回 409 |
| 已完成章节被再次执行 | 重新生成、重复版本 | checkpoint `last_completed_chapter >= n` 直接跳过 |
| HITL resume 后再崩溃 | 两套恢复机制无定义 | HITL 走 LangGraph checkpointer 恢复（§十四），task_checkpoints 不介入，无交叉 |
| 长篇某卷中间 abort 后重启 | abort 后 checkpoint 语义未定义 | abort 置 `status='failed'` + 保留 checkpoint；用户 `/retry` 从断点续跑，不新建 task（operation_id 复用） |
| 迁移期间 worker 并发写多活跃版本 | 加索引失败 | 迁移 2 在 `ACCESS EXCLUSIVE` 锁下清理+建索引，或部署窗口停 worker（见迁移决议） |

## API 契约

现有生成 API 路径保持兼容，扩展以下能力。所有接口先做 owner 校验（复用现有 `_require_task_owner`），checkpoint 不存在时（HITL/短篇任务或 legacy）返回 404 或降级见各接口说明。

### `POST /api/v1/novels/{task_id}/pause`

- **前置**：checkpoint 存在且 `status='running'`（或 `pending`）；`pause_requested=False`。
- **动作**：设 `pause_requested=True`，发 `PAUSE_REQUESTED` 事件。不改 `status`（worker 到安全边界后自行置 paused）。
- **后置**：`pause_requested=True`。
- **响应**：200 + checkpoint 摘要。若已 `pause_requested=True`，幂等返回 200（no-op）。若 `status` 已是终态（succeeded/failed），返回 409。
- **HITL/短篇任务**（无 checkpoint）：降级到现有 `pause_state_store.set_paused` 行为，只设 Task.status。

### `POST /api/v1/novels/{task_id}/resume`

- **前置**：checkpoint 存在且 `pause_requested=True`（无论 `status` 是 `paused` 还是仍 `running`——worker 可能还没到安全边界）。
- **动作**：设 `pause_requested=False`、`status='running'`、`queue_state='queued'`、`available_at=now`，清 lease。
- **后置**：任务可被任意 worker 重新 claim，从 checkpoint 的 `last_completed_chapter` 继续。
- **响应**：200 + checkpoint 摘要。
- **幂等规则（修正 B5）**：
  - `pause_requested=True` → 生效，返回 200。
  - `pause_requested=False` 且 `status='running'`/`queued` → no-op（任务本就在跑或排队），返回 200 + 摘要（不报错，因为用户目标"让它继续"已达成）。
  - `status` 终态（succeeded/failed）→ 返回 409（无法 resume 已结束的任务）。

### `GET /api/v1/novels/{task_id}/checkpoint`

- **响应**：200 + 检查点公开字段：`current_stage`、`volume_number`、`chapter_number`、`last_completed_volume`、`last_completed_chapter`、`active_version_number`、`status`、`pause_requested`、`failure_category`、`recoverable`、`attempt_number`、`updated_at`。
- **不返回** `failure_detail`（可能含错误栈/上下文，敏感），单独走需权限的诊断接口或日志。
- checkpoint 不存在 → 404。

### `POST /api/v1/novels/{task_id}/retry`

- **前置**：checkpoint `status='failed'` 或 `status='paused'` 且 `failure_category IN ('recoverable','needs_human')`。`needs_human` 需请求体带 `confirm=true`（人工已处理确认）。
- **动作**：清 `failure_category`/`failure_detail`，`attempt_number=0`（重置预算，视为人工干预后的新一轮），`status='running'`、`queue_state='queued'`、`available_at=now`，Task.attempt_count 同步归零。checkpoint 的 `current_stage`/`last_completed_chapter` **保留**（从断点续跑）。
- **后置**：任务重新入队，从断点继续。
- **响应**：200 + 摘要。`failure_category='unrecoverable'` 时返回 409（须先 abort 或人工修数据）。
- **与 `enqueue_existing_task` 关系**：retry 复用 `enqueue_existing_task` 的重入队机制，但不改 operation_id、不重置 checkpoint 进度。

### `POST /api/v1/novels/{task_id}/abort`

- **前置**：任意非终态 status。
- **动作**：Task.status='failed'（复用现有终态，不引入 cancelled 以免污染 status 枚举），checkpoint `status='failed'`、`failure_category='unrecoverable'`、保留 `failure_detail`。清 lease、`queue_state='idle'`。checkpoint 进度**保留**（供事后诊断）。
- **后置**：任务终止。abort 后可再 `/retry`（retry 会重建可执行状态并从断点续跑）；operation_id 部分唯一索引因 status 进入终态而释放，允许对同 novel 新建 operation。
- **响应**：200。

### HITL 与 checkpoint 的边界（修正 B21）

**长篇非 HITL 路径**（`generate_long_form_background` / `generate_volume_background` / `generate_chapters_background`）由 task_checkpoints 驱动，每章走 6 阶段状态机。

**HITL 路径**（`pipeline.resume` → `resume_pipeline`）继续由 LangGraph sqlite checkpointer 驱动，**不触碰 task_checkpoints**。当 HITL 任务被 claim 时，若无 checkpoint 行则跳过 checkpoint 逻辑，走原有 LangGraph 恢复。这避免两套恢复机制在同一任务上打架。`complete_task` 对 HITL 任务不写 checkpoint（`current_stage` 真相源仍是 LangGraph state + Task.progress）；对长篇任务则 checkpoint 是唯一进度真相源，`complete_task` 不再覆盖 `progress.current_stage`（改为从 checkpoint 派生只读展示）。

所有写操作继续执行 owner 校验。

## 数据库迁移

**迁移前提（修正 B26）**：生产 schema 目前由 `Base.metadata.create_all`（`database.py:74`）与 alembic 双路径建表。本设计的 4 个迁移**必须走 alembic**（`op.*`），并显式声明 `down_revision` 链接到当前 head `20260720_task_owner`。新表 `task_checkpoints` 加入 `db_models.py` 后 `create_all` 会在测试库自动建表；生产库以 alembic 为准。每个迁移都提供 `downgrade()`。

**迁移执行窗口（修正 B22 并发 / B24 停服）**：迁移 2 的多活跃版本清理 + 部分唯一索引创建**要求停止 worker**（`TASK_WORKER_ENABLED=false` 或维护窗口），避免清理与加索引之间有 worker 按旧逻辑写入新的 is_active 行导致 `CREATE UNIQUE INDEX` 失败。运维说明会明确这一步。

### 迁移 1：Task 表增加 operation_id 与去重

```python
down_revision = "20260720_task_owner"

def upgrade():
    op.add_column("tasks", sa.Column("operation_id", sa.String(200), nullable=True))
    # 历史回填：按业务格式 {novel_id}:{task_type} 推导，而非直接用 task_id（修正 B23）。
    # 无 novel_id 的历史任务用 task_id 兜底（这些多为短篇早期数据，operation_id 唯一性由 task_id 保证）。
    op.execute("""
        UPDATE tasks SET operation_id = CASE
            WHEN novel_id IS NOT NULL AND task_type IS NOT NULL
                THEN novel_id || ':' || task_type
            WHEN novel_id IS NOT NULL
                THEN novel_id || ':legacy'
            ELSE task_id
        END
    """)
    # 回填后处理历史重复：同一 (novel_id, task_type) 有多个非终态历史行时，
    # 只保留最新一行的推导 operation_id，其余追加 task_id 后缀避免部分唯一索引冲突。
    op.execute("""
        UPDATE tasks t SET operation_id = t.operation_id || ':' || t.task_id
        WHERE t.status NOT IN ('completed','failed','cancelled')
          AND EXISTS (
            SELECT 1 FROM tasks t2
            WHERE t2.operation_id = t.operation_id
              AND t2.status NOT IN ('completed','failed','cancelled')
              AND t2.task_id <> t.task_id
          )
    """)
    op.alter_column("tasks", "operation_id", nullable=False)
    op.create_index(
        "uq_tasks_operation_active",
        "tasks", ["operation_id"],
        unique=True,
        postgresql_where=sa.text("status NOT IN ('completed', 'failed', 'cancelled')"),
    )

def downgrade():
    op.drop_index("uq_tasks_operation_active", table_name="tasks")
    op.drop_column("tasks", "operation_id")
```

### 迁移 2：ChapterVersion 增加 idempotency_key 与部分唯一索引（停服窗口）

```python
def upgrade():
    op.add_column("chapter_versions", sa.Column("idempotency_key", sa.String(200), nullable=True))
    # 清理历史多活跃版本：每章保留"当前应视为活跃"的版本，其余置 inactive。
    # 选择依据用 (version_number DESC, id DESC) 而非 MAX(id)——version_number 是业务版本序，
    # 更贴近"最新版本"语义；id 仅作同版本号的 tiebreak（修正 B22 选错版本）。
    op.execute("""
        WITH ranked AS (
            SELECT id,
                   ROW_NUMBER() OVER (
                       PARTITION BY novel_id, chapter_number
                       ORDER BY version_number DESC, id DESC
                   ) AS rn
            FROM chapter_versions
            WHERE is_active = true
        )
        UPDATE chapter_versions cv SET is_active = false
        FROM ranked r
        WHERE cv.id = r.id AND r.rn > 1
    """)
    # 补激活：若某章 0 个 active（历史 bug），激活其最高 version_number 版本，避免正文显示空白。
    op.execute("""
        WITH need_active AS (
            SELECT novel_id, chapter_number
            FROM chapter_versions
            GROUP BY novel_id, chapter_number
            HAVING SUM(CASE WHEN is_active THEN 1 ELSE 0 END) = 0
        ), pick AS (
            SELECT DISTINCT ON (cv.novel_id, cv.chapter_number) cv.id
            FROM chapter_versions cv
            JOIN need_active na ON na.novel_id = cv.novel_id
                               AND na.chapter_number = cv.chapter_number
            ORDER BY cv.novel_id, cv.chapter_number, cv.version_number DESC, cv.id DESC
        )
        UPDATE chapter_versions cv SET is_active = true
        FROM pick p WHERE cv.id = p.id
    """)
    op.create_index(
        "uq_chapter_version_active",
        "chapter_versions", ["novel_id", "chapter_number"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )
    op.create_index(
        "uq_chapter_version_idem",
        "chapter_versions", ["novel_id", "chapter_number", "idempotency_key"],
        unique=True,
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

def downgrade():
    op.drop_index("uq_chapter_version_idem", table_name="chapter_versions")
    op.drop_index("uq_chapter_version_active", table_name="chapter_versions")
    op.drop_column("chapter_versions", "idempotency_key")
```

> 注：`uq_chapter_version_idem` 加 `WHERE idempotency_key IS NOT NULL` 部分条件，让历史 NULL 行与新写入的手动/回滚版本（无幂等键）不参与唯一约束，只有生成路径写入的确定性键参与去重。

### 迁移 3：Chapter 表增加副作用应用版本标记（含哨兵回填）

```python
def upgrade():
    op.add_column("chapters", sa.Column("bible_applied_version", sa.Integer, nullable=True))
    op.add_column("chapters", sa.Column("kg_applied_version", sa.Integer, nullable=True))
    # 历史章节回填哨兵 -1，语义"已应用，版本未知，跳过重跑"，避免 retry 时对历史稳定章
    # 重复调用 update_bible_after_generation / extract_from_chapter 产生重复 append（修正 B25）。
    op.execute("UPDATE chapters SET bible_applied_version = -1, kg_applied_version = -1")

def downgrade():
    op.drop_column("chapters", "kg_applied_version")
    op.drop_column("chapters", "bible_applied_version")
```

### 迁移 4：新增 task_checkpoints 表（历史任务只回填诊断，不自动恢复）

```python
def upgrade():
    op.create_table(
        "task_checkpoints",
        sa.Column("task_id", sa.String(120), sa.ForeignKey("tasks.task_id"), primary_key=True),
        sa.Column("novel_id", sa.String(120), nullable=False, index=True),
        sa.Column("operation_id", sa.String(200), nullable=False, index=True),
        sa.Column("current_stage", sa.String(40), nullable=False),
        sa.Column("volume_number", sa.Integer, nullable=True),
        sa.Column("chapter_number", sa.Integer, nullable=True),
        sa.Column("last_completed_volume", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_completed_chapter", sa.Integer, nullable=False, server_default="0"),
        sa.Column("active_version_number", sa.Integer, nullable=True),
        sa.Column("checkpoint_version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("attempt_number", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_event_sequence", sa.BigInteger, nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("pause_requested", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("failure_category", sa.String(30), nullable=True),
        sa.Column("recoverable", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("failure_detail", sa.JSON, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    # 历史任务回填（修正 B24）：不尝试把自由格式的 progress.current_stage 映射到新状态机，
    # 那会写入 'chapter_generation' 等非法值导致恢复时状态机不认识。
    # 策略：历史任务一律回填 current_stage='task_end' + recoverable=false + failure_category='unrecoverable'，
    # 表示"legacy 任务不自动从 checkpoint 恢复"，只保留诊断。真正需要续作的历史任务由用户显式 /retry
    # （会重建 checkpoint）或重新触发生成。checkpoint.status 只写合法枚举，非法的 Task.status
    # （cancelled/partially_completed/...）统一归一化为 'failed'。
    op.execute("""
        INSERT INTO task_checkpoints (
            task_id, novel_id, operation_id, current_stage,
            status, recoverable, failure_category, updated_at
        )
        SELECT
            t.task_id,
            COALESCE(t.novel_id, ''),
            COALESCE(t.operation_id, t.task_id),
            'task_end',
            CASE WHEN t.status IN ('pending','running','paused','completed','failed')
                 THEN (CASE WHEN t.status = 'completed' THEN 'succeeded'
                            WHEN t.status = 'running' THEN 'pending'
                            ELSE t.status END)
                 ELSE 'failed' END,
            false,
            CASE WHEN t.status = 'completed' THEN NULL ELSE 'unrecoverable' END,
            NOW()
        FROM tasks t
        WHERE t.task_type IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM task_checkpoints c WHERE c.task_id = t.task_id)
    """)

def downgrade():
    op.drop_table("task_checkpoints")
```

## 测试策略

### 故障注入测试（新增 `tests/integration/test_long_form_fault_injection.py`）

用进程级隔离 + DB 状态断言模拟崩溃，不依赖真实进程 kill：

1. **检查点恢复**：在指定阶段后人为中断 dispatch（mock dispatcher 抛 `LeaseLost`），重新 claim，断言从 checkpoint 继续、不重复生成。
2. **幂等重试**：重放同一章节，断言不产生重复 ChapterVersion（按 idempotency_key 去重）。
3. **lease 丢失停写**：模拟 lease 被另一 worker 抢占，断言旧 worker 的 `complete_task`/`advance_checkpoint` 抛 `LeaseLost` 且 DB 未被写入。
4. **暂停跨重启**：pause 后重启 worker（重新 `start()`），断言从 checkpoint 继续。
5. **resume 幂等**：连续调 resume 两次，断言第二次 no-op、不产生重复入队。
6. **已完成章节跳过**：checkpoint `last_completed_chapter=5`，断言重放从第 6 章开始。
7. **重复投递去重**：连续两次 `create_task` 同一 operation_id，断言返回同一 task_id。
8. **单活跃版本**：并发创建两版本，断言 DB 部分唯一索引拒绝第二个 active。
9. **进度单调**：失败章不计入 completed，percentage 不回退。
10. **错误分类**：注入 `consistency_blocked` 断言转 `needs_human` 而非 failed。

### 单元测试（扩展 `tests/unit/test_task_manager.py`、新增 `test_checkpoint_store.py`）

- `advance_checkpoint` 乐观锁并发冲突。
- `assert_lease_held` 各类 lease 状态。
- `complete_task`/`fail_task` lease 守卫拒绝旧 worker。
- `resume_task` 幂等性。
- `create_task` operation_id 去重。
- checkpoint 状态机阶段转换合法性。

### 回归测试

- 现有 `test_task_manager.py`、`test_task_worker.py`、`test_chapter_persistence_service.py`、`test_change044_long_form_api.py`、`test_change036_retry_and_chilience.py` 全部通过。
- 短篇生成路径（`test_full_generate_api.py`、`test_langgraph/test_graph_contract.py`）不受影响。
- 正文质量计划 Task 7/8/9 的 `finalize_quality_result` 原子激活契约不被破坏（本设计只消费 `quality_finalized` 阶段，不修改激活逻辑）。

## 验收标准

1. 服务重启后从数据库 checkpoint 恢复，从最后已提交阶段继续。
2. 暂停状态跨进程、跨重启有效，暂停期间 worker 可处理其他任务。
3. 重试相同章节不增加重复版本（idempotency_key 去重 + 部分唯一索引）。
4. 每章任何时刻最多一个活跃版本（DB 部分唯一索引保证）。
5. lease 丢失的 worker 不再执行持久化写入或终态推进（lease 守卫）。
6. 同一任务重复投递不产生两份正文（operation_id 去重）。
7. 章节、卷、全书进度一致且单调递增（checkpoint 为唯一真相源）。
8. 可恢复错误提供明确重试入口（`/retry` 接口 + `recoverable=true`）。
9. 不可恢复错误保留诊断信息，不伪造完成（`failure_detail` + `needs_human`/`unrecoverable`）。
10. 现有短篇生成与正文质量契约不被破坏（回归测试全通过）。
11. 故障注入测试证明上述行为（12 个场景全覆盖）。

## 实施拆分建议

设计确认后按可独立验证的顺序拆为实施计划：

1. 数据库迁移（operation_id、ChapterVersion 索引、Chapter 副作用标记、task_checkpoints 表）+ 模型字段。
2. CheckpointStore 服务 + 状态机 + 乐观锁。
3. lease 守卫（`assert_lease_held`、`LeaseLost`）+ 终态推进函数加守卫。
4. operation_id 投递去重（`create_task` ON CONFLICT）。
5. ChapterVersion idempotency_key 幂等创建。
6. `generate_volume_chapters` 接入检查点阶段 + lease 复查 + 跳过已完成章节。
7. 暂停/resume 跨进程化（重入队 + recover 处理 paused）。
8. 进度单调 + 事件序列号 + 进度事件失败不阻断。
9. 三层进度一致性（LFP 派生 + Novel.status 更新）。
10. 错误分类 + `/retry` `/abort` `/checkpoint` 接口。
11. 长篇路径补接知识图谱 + StoryBible 消费最终版本。
12. 故障注入测试套件 + 回归验证。
