# 长篇小说生成稳定性实施计划

> 对应设计：`docs/superpowers/specs/2026-07-20-long-form-stability-design.md`
> 方案：增量强化现有 PostgreSQL 租约队列，不另建平行系统。
> 执行方式：TDD 逐任务实施（红→绿→重构），每个任务运行聚焦测试，最后跑后端完整测试 + 相关前端测试。

## 全局约束

- 保留所有现有未提交修改，不碰 `docs/superpowers/{specs,plans}/2026-07-20-novel-body-quality*.md`（另一任务负责）。
- 迁移走 alembic（`revision`/`down_revision` 字符串风格），当前 head = `20260720_task_owner`。
- Task 表 `task_id` 是 `String(100)`，`task_checkpoints.task_id` FK 必须匹配 `String(100)`。
- 测试需 PG 测试库（`conftest.py` 自动探测，无 SQLite 回退）；门禁 `make verify`。
- `get_db_session()` 退出即 commit，异常回滚。

## 任务依赖关系

```
T1 (迁移+模型) ──┬── T2 (CheckpointStore)
                 ├── T3 (lease 守卫 + 终态函数)
                 └── T4 (operation_id 去重)
T2 ── T5 (ChapterVersion 幂等 create/finalize)
T3,T5 ── T6 (generate_volume_chapters 接入检查点)
T6 ── T7 (暂停/resume 跨进程)
T6 ── T8 (进度单调 + 事件 seq)
T6 ── T9 (三层进度一致)
T2,T3 ── T10 (错误分类 + API 接口)
T5,T6 ── T11 (副作用幂等 + 长篇补 KG)
全部 ── T12 (故障注入测试 + 回归)
```

---

## Task 1：数据库迁移 + 模型字段

**目标**：4 个 alembic 迁移 + `db_models.py` 新增字段/表，修正 B22/B23/B24/B25/B26。

**文件**：
- Create: `alembic/versions/20260721a_add_operation_id.py`
- Create: `alembic/versions/20260721b_add_chapter_version_idem.py`
- Create: `alembic/versions/20260721c_add_chapter_side_effect_versions.py`
- Create: `alembic/versions/20260721d_add_task_checkpoints.py`
- Modify: `src/api/models/db_models.py`（Task.operation_id、ChapterVersion.idempotency_key、Chapter.bible_applied_version/kg_applied_version、新增 TaskCheckpoint 模型 + ChapterVersion 部分唯一索引）
- Modify/Create: `tests/api/test_task_queue_model_and_migration.py`（扩展）

**步骤**：

1. **[红] 写模型契约测试**：断言 `TaskCheckpoint` 表存在、字段齐全、`task_id` PK+FK；`ChapterVersion.idempotency_key` 列存在 + `uq_chapter_version_active` / `uq_chapter_version_idem` 索引存在；`Task.operation_id` 列存在 + `uq_tasks_operation_active` 部分唯一索引；`Chapter.bible_applied_version`/`kg_applied_version` 列存在。用 `inspect(engine)` 读 schema。

2. **[红] 跑测试确认失败**：`poetry run pytest tests/api/test_task_queue_model_and_migration.py -q`。

3. **[绿] 改 `db_models.py`**：
   - `Task`：加 `operation_id: Mapped[str] = mapped_column(String(200), nullable=False)`（模型层非空，迁移回填后置非空）+ `__table_args__` 加部分唯一索引 `Index("uq_tasks_operation_active", "operation_id", unique=True, postgresql_where=text("status NOT IN ('completed','failed','cancelled')"))`。
   - `ChapterVersion`：加 `idempotency_key: Mapped[str | None] = mapped_column(String(200), nullable=True)` + `__table_args__` 加 `Index("uq_chapter_version_active", "novel_id","chapter_number", unique=True, postgresql_where=Column("is_active").is_(True))` 和 `Index("uq_chapter_version_idem","novel_id","chapter_number","idempotency_key", unique=True, postgresql_where=text("idempotency_key IS NOT NULL"))`。
   - `Chapter`：加 `bible_applied_version: Mapped[int | None]`、`kg_applied_version: Mapped[int | None]`（Integer nullable）。
   - 新增 `TaskCheckpoint(Base)`（字段见设计 §二，`task_id` String(100) PK+FK→tasks.task_id，`operation_id` String(200)，全部 server_default 与设计一致）。

4. **[绿] 写 4 个迁移**（内容照搬设计 §数据库迁移的最终 SQL，含 downgrade）：
   - 迁移 1 `20260721a`：down_revision=`20260720_task_owner`。加 operation_id + 按 `{novel_id}:{task_type}` 回填 + 历史重复追加 task_id 后缀 + 置非空 + 部分唯一索引。
   - 迁移 2 `20260721b`：down_revision=`20260721a`。加 idempotency_key + 用 `ROW_NUMBER() OVER (ORDER BY version_number DESC, id DESC)` 清理多活跃 + 补激活 0 活跃章 + 两个部分唯一索引。
   - 迁移 3 `20260721c`：down_revision=`20260721b`。加 bible_applied_version/kg_applied_version + 回填哨兵 `-1`。
   - 迁移 4 `20260721d`：down_revision=`20260721c`。create task_checkpoints + 历史任务回填 `current_stage='task_end'`+`recoverable=false`+status 归一化。

5. **[绿] 跑测试确认通过 + `alembic upgrade head` 在测试库可执行**：`poetry run pytest tests/api/test_task_queue_model_and_migration.py -q`。

6. **[重构]** 确保 `create_all` 与 alembic 无冲突（新表加入 Base 即可，测试库走 create_all，本任务只验证 schema 一致）。

**验收**：schema 契约测试通过；4 个迁移 upgrade/downgrade 可逆。

---

## Task 2：CheckpointStore 服务 + 状态机 + 乐观锁

**目标**：`advance_checkpoint` 单事务内 lease 守卫 + checkpoint_version 乐观锁（B3），阶段状态机合法性。

**文件**：
- Create: `src/api/services/tasks/checkpoint_store.py`
- Create: `src/core/exceptions.py` 补 `LeaseLost`、`CheckpointConflict`（若 `StaleChapterVersionError` 已由正文质量任务加则复用）
- Create: `tests/unit/test_checkpoint_store.py`

**步骤**：

1. **[红] 写测试**：
   - `ensure_checkpoint(task_id, novel_id, operation_id)` 幂等创建初始 checkpoint（`current_stage='chapter_planned'`, `checkpoint_version=0`）。
   - `advance_checkpoint` 正常推进返回 `checkpoint_version+1`。
   - `expected_checkpoint_version` 不匹配抛 `CheckpointConflict`。
   - lease_owner 不匹配 / lease 过期抛 `LeaseLost`。
   - `advance_checkpoint` 只校验 lease_owner+lease_expires_at，**不校验 queue_state**（B2：暂停时 queue_state 已变但仍能推进 status='paused'）。
   - 阶段非法转换（如从 `chapter_planned` 跳到 `chapter_completed`）由调用方保证，store 不强制（但提供 `STAGE_ORDER` 常量供校验）。

2. **[红] 跑测试确认失败**：`poetry run pytest tests/unit/test_checkpoint_store.py -q`。

3. **[绿] 实现 `checkpoint_store.py`**：
   - `STAGE_ORDER = [...]` 6 章节阶段 + volume/task 阶段。
   - `CheckpointStore.ensure_checkpoint(...)`：`INSERT ... ON CONFLICT (task_id) DO NOTHING`。
   - `CheckpointStore.advance_checkpoint(task_id, worker_id, *, expected_checkpoint_version, stage, ...)`：照搬设计 §advance_checkpoint 完整签名——单事务锁 Task 行校验 lease → `update(TaskCheckpoint).where(checkpoint_version==expected)` 乐观锁 → rowcount==0 抛 CheckpointConflict → 返回新版本。
   - `CheckpointStore.read(task_id)`：读当前 checkpoint dict。

4. **[绿] 跑测试确认通过**。

5. **[重构]** 提取 lease 守卫为内部 `_assert_lease_in_session(session, task_id, worker_id, now)`，供 T3 复用。

**验收**：乐观锁并发冲突、lease 守卫、幂等创建全覆盖。

---

## Task 3：lease 守卫 + 终态推进函数加守卫

**目标**：`assert_lease_held` + `complete_task`/`fail_task`/`update_status` 加 lease 守卫（R1）；`_run_claim` 识别 `LeaseLost`/`PausedExit` 跳过 release（B7/B12）。

**文件**：
- Modify: `src/api/services/tasks/task_manager.py`
- Modify: `src/api/services/tasks/task_worker.py`
- Modify: `tests/unit/test_task_manager.py`、`tests/api/test_task_worker.py`

**步骤**：

1. **[红] 写测试**：
   - `assert_lease_held` 各状态（正常/owner 不符/过期/queue_state≠leased）。
   - `complete_task(task_id, result, *, worker_id)` 当 worker_id≠lease_owner 时**拒绝写入并抛 LeaseLost**，DB status 不变。
   - `fail_task`/`update_status` 同样加 worker_id 守卫。
   - **向后兼容**：`worker_id=None` 时保持旧行为（不校验），供非 worker 调用方（如路由）使用。
   - `_run_claim`：dispatch 抛 `LeaseLost` → 不调 release_claim/retry_or_fail_claim，干净 return。

2. **[红] 跑测试确认失败**。

3. **[绿] 改 `task_manager.py`**：
   - 加 `assert_lease_held(task_id, worker_id)`（独立函数，供业务层调用；内部同 T2 的守卫）。
   - `complete_task`/`fail_task`/`update_status` 加 keyword-only `worker_id: str | None = None`；非 None 时 `with_for_update` + 校验 `lease_owner==worker_id`，不符抛 `LeaseLost`。
   - 保留现有无 worker_id 调用方兼容（HITL 路由等）。

4. **[绿] 改 `task_worker.py`**：`_run_claim` 的异常分支加 `except LeaseLost: logger.warning(...); return`（在通用 `except Exception` 之前）。dispatcher 调用链传 `worker_id`（见 T6，本任务先加 worker 侧的 LeaseLost 识别）。

5. **[绿] 跑测试确认通过**。

6. **[重构]** 统一 `LeaseLost` 从 `src/core/exceptions.py` 导入。

**验收**：旧 worker 终态写入被拒；LeaseLost 干净退出不误标 failed。

---

## Task 4：operation_id 投递去重

**目标**：`create_task` 分配 operation_id + SELECT-FOR-UPDATE 去重（R5/B4）。

**文件**：
- Modify: `src/api/services/tasks/task_manager.py`
- Modify: `src/api/routes/novels.py`（各生成入口传 operation_type + max_attempts）
- Modify: `tests/unit/test_task_manager.py`

**步骤**：

1. **[红] 写测试**：
   - `create_task(..., operation_id=X)` 首次创建返回新 task_id。
   - 同一 operation_id 在非终态存在时，第二次 `create_task` 返回**已存在的 task_id**（不新建）。
   - 已存在任务为终态时，同 operation_id 可新建。

2. **[红] 跑测试确认失败**。

3. **[绿] 改 `create_task`**：
   - 新增 keyword-only `operation_id: str | None = None`；None 时 fallback 到 task_id（兼容短篇）。
   - 实现去重：先 `SELECT task_id FROM tasks WHERE operation_id=? AND status NOT IN (终态) FOR UPDATE`（在同一 session），命中则返回已存在 task_id；否则 INSERT。捕获 `IntegrityError`（并发窗口）后重查返回已存在。
   - 返回值保持 `str`（task_id）。

4. **[绿] 改 `novels.py`**：长篇 `/long-form` 入口构造 `operation_id=f"{novel_id}:novel.long_form"`，传 `max_attempts=settings.LONG_FORM_MAX_ATTEMPTS`（新增 config，默认 3）。卷/章节入口同理带 volume/range 后缀。

5. **[绿] 跑测试确认通过**。

6. **[重构]** 抽 `_build_operation_id(novel_id, task_type, **kw)` 辅助。

**验收**：重复投递返回同一 task_id；config `LONG_FORM_MAX_ATTEMPTS` 生效。

---

## Task 5：ChapterVersion 幂等创建 + finalize_chapter_version 原子激活

**目标**：`create_chapter_version` 加 idempotency_key 幂等查重（B18）；新增 `finalize_chapter_version` 原子激活（B10，用 expected_active_version 乐观锁）。

**文件**：
- Modify: `src/api/services/content/chapter_service.py`
- Modify: `src/core/exceptions.py`（`StaleChapterVersionError`，若正文质量任务未加）
- Create: `tests/unit/test_chapter_version_idempotency.py`

**步骤**：

1. **[红] 写测试**：
   - `create_chapter_version(..., idempotency_key=K)` 首次创建返回版本号。
   - 同 idempotency_key 第二次调用**返回已存在版本号，不新建**（DB 版本数不增）。
   - `finalize_chapter_version(novel_id, chapter_number, *, expected_active_version, selected_version, ...)`：激活 selected，清零其余，写回 Chapter.content。
   - `expected_active_version` 不匹配当前活跃版本时抛 `StaleChapterVersionError`。
   - 激活后每章恰好一个 `is_active=True`（DB 部分唯一索引保证）。

2. **[红] 跑测试确认失败**。

3. **[绿] 改 `create_chapter_version`**：加 keyword-only `idempotency_key: str | None = None`；非 None 时先查 `WHERE idempotency_key=K` 命中即返回其 version_number；写入时带 idempotency_key。

4. **[绿] 加 `finalize_chapter_version`**：单事务 `with_for_update` 锁 Chapter + 所有版本 → 校验当前活跃版本==expected_active_version（不符抛 StaleChapterVersionError）→ 激活 selected + 清零其余 + 写回 Chapter.content/word_count/quality_status。
   - **协调正文质量任务**：若正文质量 Task 7 已落地 `finalize_quality_result`，则复用其激活逻辑；否则本任务实现。检查 `git log`/代码确认后决定复用或新建（避免重复实现）。

5. **[绿] 跑测试确认通过**。

6. **[重构]** 幂等键构造统一 `chapter_idem_key(operation_id, kind, chapter_number)`。

**验收**：重放同键不增版本；每章单活跃；stale 版本被拒。

---

## Task 6：generate_volume_chapters 接入检查点阶段

**目标**：单章 6 阶段状态机 + lease 复查 + 跳过已完成章节（R2/R3），worker_id 全链路传递（B1）。

**文件**：
- Modify: `src/api/services/tasks/task_dispatcher.py`（注入 worker_id）
- Modify: `src/api/services/tasks/task_worker.py`（claim dict 带 worker_id）
- Modify: `src/api/services/generation/long_form_generation_helpers.py`
- Modify: `tests/api/test_change044_long_form_api.py` + 新增聚焦测试

**步骤**：

1. **[红] 写测试**：
   - claim 后 checkpoint `last_completed_chapter=5`，`generate_volume_chapters` 从第 6 章开始（前 5 章跳过，不重新生成）。
   - 每章推进 6 阶段，checkpoint 记录正确 stage。
   - 循环开头 `assert_lease_held` 抛 LeaseLost 时干净退出。
   - worker_id 从 claim 一路传到 advance_checkpoint。

2. **[红] 跑测试确认失败**。

3. **[绿] 改 worker_id 注入链**：
   - `task_worker._run_claim`：`claim["worker_id"] = self.worker_id` 后传给 dispatcher。
   - `task_dispatcher.dispatch_task`：从 `task["worker_id"]` 取出，传给各 `generate_*` 函数（加 `worker_id` 形参）。
   - `generate_long_form_background`/`generate_volume_background`/`generate_chapters_background`/`generate_volume_chapters` 加 `worker_id: str` 形参。

4. **[绿] 改 `generate_volume_chapters`**：
   - 入口 `ensure_checkpoint`（若无）。
   - 卷/章循环开头：`if checkpoint.last_completed_chapter >= global_ch_num: continue`（跳过已完成）。
   - 每章按设计 §持久化伪代码组织 6 阶段，每阶段前 `assert_lease_held(task_id, worker_id)`，每阶段后 `advance_checkpoint(...)`（本地维护 expected_checkpoint_version）。
   - baseline 用 `create_chapter_version(is_active=False, idempotency_key=...)`；gate 后（若非恢复跳过）调 `finalize_chapter_version`。

5. **[绿] 跑测试确认通过**。

6. **[重构]** 抽 `_run_chapter_stages(...)` 单章阶段执行器，降低循环体复杂度。

**验收**：崩溃恢复从断点续；已完成章跳过；lease 丢失停写。

---

## Task 7：暂停/resume 跨进程化

**目标**：pause_requested 与 status 分离（B14），resume 重入队（B5），recover 处理 paused，volume pause 统一（B15）。

**文件**：
- Modify: `src/api/services/generation/pause_state_store.py`
- Modify: `src/api/services/tasks/task_manager.py`（`requeue_paused_task`、`mark_paused`、recover 扩展）
- Modify: `src/api/services/generation/novel_generator.py`（resume_task 重写）
- Modify: `src/api/services/generation/long_form_generation_helpers.py`（协作式暂停）
- Modify: `src/api/routes/novels.py`（pause/resume 路由前置条件）
- Modify: 相关测试

**步骤**：

1. **[红] 写测试**：
   - `set_paused` 只设 checkpoint `pause_requested=True`，不改 status。
   - `is_pause_requested` / `is_paused_confirmed` 语义正确。
   - `requeue_paused_task`：paused+pause_requested → 重入队；第二次调用 no-op（幂等）。
   - `recover_interrupted_tasks`：paused+pause_requested=False → 重入队；pause_requested=True → 保持 paused。
   - worker 到 `chapter_completed` 后检测 pause_requested → mark_paused + PausedExit，worker 不阻塞。

2. **[红] 跑测试确认失败**。

3. **[绿] 改 `pause_state_store`**：`set_paused` 设 checkpoint pause_requested + Redis 通知；拆 `is_pause_requested`/`is_paused_confirmed`；`clear_paused` 废弃或改为调 requeue。

4. **[绿] 改 `task_manager`**：加 `mark_paused(task_id, worker_id)`（行锁+owner 校验，queue_state='idle'+清 lease）、`requeue_paused_task(task_id)`（前置校验+重入队，返回 RequeueResult）；`recover_interrupted_tasks` join checkpoint 处理 paused。

5. **[绿] 改 `novel_generator.resume_task`**：调 `requeue_paused_task`，不再 clear_paused 硬切。`is_task_paused` 映射到 `is_pause_requested`。

6. **[绿] 改 `generate_volume_chapters`**：循环开头 `is_pause_requested` 为真且当前章已 `chapter_completed` → `advance_checkpoint(status='paused')` → `mark_paused` → raise `PausedExit`（worker `_run_claim` 识别后跳过 release）。删除 `while is_paused: sleep(1)` 阻塞。

7. **[绿] 改 `novels.py`** pause/resume 路由前置条件按设计 §API 契约（含 HITL/短篇无 checkpoint 降级）。

8. **[绿] 跑测试确认通过**。

9. **[重构]** PausedExit 与 LeaseLost 在 `_run_claim` 共用"跳过 release"分支。

**验收**：暂停跨重启有效；resume 幂等；暂停期间 worker 不独占。

---

## Task 8：进度单调 + 事件序列号

**目标**：last_event_sequence（B8），进度事件失败不判失败（R7），percentage 基于持久值单调（R9）。

**文件**：
- Modify: `src/api/services/generation/chapter_generation_utils.py`（_emit_progress）
- Modify: `src/api/services/generation/long_form_generation_helpers.py`
- Modify: `src/api/services/tasks/task_manager.py`（complete_task 不强制 100%）
- Modify: 相关测试

**步骤**：

1. **[红] 写测试**：
   - `_emit_progress` 内部抛异常时被吞掉，章节流程继续，checkpoint seq 不推进。
   - percentage 基于 `last_completed_chapter`，失败章不计入，不回退。
   - `complete_task(status='partially_completed')` 写真实 percentage 而非 100。

2. **[红] 跑测试确认失败**。

3. **[绿] 改 `_emit_progress`**：包 try/except，失败仅 log + 记 failure_detail，不抛。事件带 `sequence=checkpoint.last_event_sequence+1`，成功后 advance_checkpoint 推进 seq。

4. **[绿] 改进度计算**：用 checkpoint `last_completed_chapter` 算 completed/percentage，删除 `len(generated_chapters)`（含失败章）路径。

5. **[绿] 改 `complete_task`**：非 completed 状态写 result 的真实 percentage。

6. **[绿] 跑测试确认通过**。

7. **[重构]** 进度 payload 构造集中到一处。

**验收**：进度事件失败不阻断；percentage 单调。

---

## Task 9：三层进度一致性

**目标**：checkpoint 为单一真相源，LFP 派生，长篇补 Novel.status（R9），卷失败 Volume/LFP 一并 failed（B8）。

**文件**：
- Modify: `src/api/services/generation/long_form_progress_service.py`
- Modify: `src/api/services/generation/long_form_generation_helpers.py`
- Modify: 相关测试

**步骤**：

1. **[红] 写测试**：
   - 卷完成推进 `last_completed_volume` + Volume.status='completed' + LFP.status='completed'。
   - 全书完成 Novel.status='completed'。
   - 卷失败时 Volume.status 和 LFP.status 一并 'failed'（不停在 generating）。
   - LFP.chapters_completed 由 checkpoint 派生（不含失败章）。

2. **[红] 跑测试确认失败**。

3. **[绿] 改卷/任务级推进**：按设计 §卷切换伪代码——`volume_start`/`volume_end`/`task_end` 阶段推进，每步 lease 守卫；LFP.chapters_completed 从 `last_completed_chapter - chapter_start + 1` 派生；`generate_long_form_background` 全部卷完成调 `update_novel(status='completed')`，异常时 'failed' + Volume/LFP failed。

4. **[绿] 跑测试确认通过**。

5. **[重构]** 卷失败处理抽 `_mark_volume_failed(...)`。

**验收**：三层进度一致且单调；长篇更新 Novel.status。

---

## Task 10：错误分类 + /retry /abort /checkpoint 接口

**目标**：failure_category 三类 + 4 个 API 接口（B6/B9）。

**文件**：
- Modify: `src/api/routes/novels.py`
- Modify: `src/api/services/tasks/task_manager.py`（retry/abort 逻辑）
- Modify: `src/api/services/tasks/checkpoint_store.py`（分类写入）
- Create/Modify: 路由测试

**步骤**：

1. **[红] 写测试**：
   - `GET /checkpoint` 返回公开字段，不含 failure_detail；无 checkpoint 404。
   - `POST /retry`：recoverable/needs_human(+confirm) 从断点重入队，attempt_number 归零，进度保留；unrecoverable 返回 409。
   - `POST /abort`：置 failed + 保留 checkpoint。
   - 错误分类：注入 consistency_blocked → needs_human（status='paused'），非 failed。
   - 所有接口 owner 校验。

2. **[红] 跑测试确认失败**。

3. **[绿] 实现分类**：checkpoint_store 提供 `mark_failed(task_id, worker_id, category, detail, recoverable)`；业务层根据异常类型（复用 `should_retry`）决定 category。

4. **[绿] 实现路由**：`/checkpoint`（GET）、`/retry`（POST，复用 enqueue 机制但不改 operation_id/进度）、`/abort`（POST，Task.status='failed'）。按设计 §API 契约的前置/后置/响应码。

5. **[绿] 跑测试确认通过**。

6. **[重构]** owner 校验复用现有 `_require_task_owner`。

**验收**：可恢复错误有重试入口；不可恢复保留诊断不伪造完成。

---

## Task 11：副作用幂等 + 长篇补接 KG

**目标**：StoryBible/KG 加 applied_version 幂等（B19/B20），长篇路径补接 KG，只消费最终活跃版本。

**文件**：
- Modify: `src/api/services/content/story_bible_service.py`（update_bible_after_generation 加 applied_version）
- Modify: `src/api/services/knowledge/knowledge_graph_service.py`（幂等判定用 KnowledgeExtractionLog）
- Modify: `src/api/services/generation/chapter_persistence_service.py`（record_chapter_artifacts 传 applied_version + 读最终活跃版本）
- Modify: `src/api/services/generation/long_form_generation_helpers.py`（side_effects_recorded 阶段调 KG）
- Modify: 相关测试

**步骤**：

1. **[红] 写测试**：
   - `update_bible_after_generation(..., applied_version=N)`：Chapter.bible_applied_version>=N 则 skip（不调 LLM/不 append）。
   - 成功后写 bible_applied_version=N。
   - `extract_from_chapter` 幂等：KnowledgeExtractionLog.status=='completed' 则跳过。
   - 长篇路径 side_effects 阶段调 KG，正文取自 `ChapterVersion(is_active=True)`（不依赖 chapter_result["content"]）。

2. **[红] 跑测试确认失败**。

3. **[绿] 改 `update_bible_after_generation`**：加 keyword-only `applied_version: int`；开头查 Chapter.bible_applied_version 幂等跳过；成功后写标记（同事务）。

4. **[绿] 改 `extract_from_chapter` 调用点**：side_effects 阶段前查 KnowledgeExtractionLog 幂等；成功后写 kg_applied_version。

5. **[绿] 改 `record_chapter_artifacts`**：传 `applied_version=final_version_number`；正文从最终活跃版本读取。

6. **[绿] 跑测试确认通过**。

7. **[重构]** 副作用幂等判定统一 helper。

**验收**：副作用幂等重放不重复 append；长篇有 KG；只消费最终版本。

---

## Task 12：故障注入测试套件 + 回归验证

**目标**：13 场景故障注入（设计 §故障注入场景覆盖）+ 全回归。

**文件**：
- Create: `tests/integration/test_long_form_fault_injection.py`
- 运行全部现有测试

**步骤**：

1. **[绿] 写故障注入测试**（13 场景，DB 状态断言，不真实 kill 进程）：
   1. 检查点恢复（mock dispatcher 在指定阶段抛 LeaseLost，重 claim 从断点续）。
   2. 幂等重试不产生重复版本。
   3. lease 丢失停写（旧 worker complete_task/advance_checkpoint 抛 LeaseLost，DB 未写）。
   4. 暂停跨重启（pause → worker stop → 新 worker start → 从 checkpoint 续）。
   5. resume 幂等（连调两次，第二次 no-op）。
   6. 已完成章跳过（last_completed_chapter=5，从第 6 章开始）。
   7. 重复投递去重（同 operation_id 返回同 task_id）。
   8. 单活跃版本（并发创建，DB 索引拒第二 active）。
   9. 进度单调（失败章不计入，percentage 不回退）。
   10. 错误分类（consistency_blocked → needs_human）。
   11. HITL resume 后崩溃（走 LangGraph checkpointer，task_checkpoints 不介入）。
   12. abort 后 retry（从断点续，不新建 task）。
   13. baseline/quality_finalized 各阶段崩溃恢复。

2. **[绿] 跑故障注入测试**：`poetry run pytest tests/integration/test_long_form_fault_injection.py -q`。

3. **[绿] 全回归**：
   - `make test-backend`（unit + api + integration）。
   - `poetry run pytest tests/api/test_task_manager.py tests/api/test_task_worker.py tests/api/test_chapter_persistence_service.py tests/api/test_change044_long_form_api.py -q`。
   - 短篇路径不受影响：`poetry run pytest tests/api/test_full_generate_api.py -q`（若存在）。
   - `make ruff`、`make check-structure`。
   - 前端相关（若改了 API 契约）：`make build-frontend`。

4. **[重构]** 清理临时文件；确认无回归。

**验收**：13 场景全通过；`make verify` 全绿。

---

## 运维说明

1. **迁移窗口**：迁移 2（ChapterVersion 部分唯一索引）**要求停 worker**（`TASK_WORKER_ENABLED=false` 或维护窗口），避免清理与建索引之间产生新多活跃行导致 `CREATE UNIQUE INDEX` 失败。
2. **配置项**：新增 `LONG_FORM_MAX_ATTEMPTS`（默认 3）；`TASK_QUEUE_LEASE_SECONDS` 保持现值（长任务需确保 heartbeat 间隔 < lease/4）。
3. **恢复顺序**：应用启动 lifespan 中 `recover_interrupted_tasks` 已在，扩展后自动处理 paused 任务。
4. **历史任务**：迁移 4 把 legacy 任务标 `unrecoverable`，不自动从 checkpoint 恢复；需续作的历史长篇由用户 `/retry`（重建 checkpoint）或重新触发生成。
5. **监控**：关注 `lease_lost_clean_exit`、`checkpoint_conflict`、`persistent_task_lease_lost` 日志频率，异常升高说明 lease 时长配置或 worker 负载需调整。

## 完成检查清单

- [ ] T1 迁移 + 模型 schema 契约测试通过
- [ ] T2 CheckpointStore 乐观锁 + lease 守卫测试通过
- [ ] T3 终态函数 lease 守卫 + LeaseLost 干净退出测试通过
- [ ] T4 operation_id 去重测试通过
- [ ] T5 ChapterVersion 幂等 + finalize 原子激活测试通过
- [ ] T6 generate_volume_chapters 检查点接入 + 跳过已完成章测试通过
- [ ] T7 暂停/resume 跨进程 + 幂等测试通过
- [ ] T8 进度单调 + 事件 seq 测试通过
- [ ] T9 三层进度一致测试通过
- [ ] T10 错误分类 + API 接口测试通过
- [ ] T11 副作用幂等 + 长篇 KG 测试通过
- [ ] T12 13 场景故障注入 + 全回归 `make verify` 全绿
