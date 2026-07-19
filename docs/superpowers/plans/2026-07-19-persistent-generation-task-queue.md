# Persistent Generation Task Queue Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 用 PostgreSQL 租约队列替代小说生成路径的 FastAPI `BackgroundTasks`，保证 queued 任务跨重启持久化，并在多进程下避免重复领取。

**Architecture:** `Task.status` 保留业务状态，新增 `queue_state` 和租约字段管理执行状态。TaskManager 负责原子领取和恢复，dispatcher 负责 JSON payload 到现有生成函数的映射，`PersistentTaskWorker` 在 FastAPI lifespan 内轮询、续租和执行。

**Tech Stack:** Python 3.11、FastAPI、asyncio、SQLAlchemy 2 async、PostgreSQL `FOR UPDATE SKIP LOCKED`、Alembic、Pydantic、pytest

---

## 执行约束

- 不引入 Celery、Redis 或新网络依赖。
- 不修改生成内容、LLM、质量门禁和章节算法。
- 当前任务类型 `max_attempts=1`，不自动重放可能产生部分写入的生成任务。
- 不迁移书籍导入和读者模拟后台作业。
- 不修改安全配置。
- 不执行 Git 暂存、提交、分支或推送。
- 不触碰 `.claude/worktrees/*` 和无关归档改动。

## File Structure

**Create:**

- `alembic/versions/d7e4f9a2c1b0_add_task_queue_fields.py` — tasks 队列字段和索引迁移。
- `src/api/services/task_dispatcher.py` — 固定 TaskType 与 payload 调度。
- `src/api/services/task_worker.py` — 轮询、心跳、执行、停机生命周期。
- `tests/unit/test_task_queue_model_and_migration.py` — ORM 与迁移结构测试。
- `tests/unit/test_task_dispatcher.py` — 六种生成任务和 resume 调度测试。
- `tests/unit/test_task_worker.py` — worker 生命周期和异常路径测试。
- `tests/unit/test_task_queue_routes.py` — 路由入队契约和 BackgroundTasks 清理测试。

**Modify:**

- `src/api/models/db_models.py` — Task 队列字段。
- `src/api/services/task_manager.py` — 创建、重新入队、领取、续租、释放、失败重试、恢复。
- `tests/unit/test_task_manager.py` — 队列状态机单元测试。
- `src/core/config.py`、`.env.example` — 队列配置。
- `src/api/main.py`、`src/core/database.py` — worker 启停顺序与说明。
- `src/api/routes/novels.py`、`src/api/routes/projects.py`、`src/api/routes/review.py` — Task-backed 路由改为持久化入队。
- `docs/DEPLOYMENT.md` — 新任务恢复语义和运维查询。

### Task 1: Add Task queue schema with TDD

**Files:**

- Create: `tests/unit/test_task_queue_model_and_migration.py`
- Modify: `src/api/models/db_models.py`
- Create: `alembic/versions/d7e4f9a2c1b0_add_task_queue_fields.py`

- [x] **Step 1: Write failing ORM field tests**

Create tests that require the exact columns and composite index:

```python
def test_task_model_has_internal_queue_fields():
    from src.api.models.db_models import Task

    columns = Task.__table__.c
    assert columns.task_type.nullable is True
    assert columns.task_payload.nullable is True
    assert columns.queue_state.nullable is True
    assert columns.attempt_count.default.arg == 0
    assert columns.max_attempts.default.arg == 1
    assert columns.available_at.nullable is True
    assert columns.lease_owner.nullable is True
    assert columns.lease_expires_at.nullable is True
    assert columns.heartbeat_at.nullable is True


def test_task_queue_ready_index_exists():
    from src.api.models.db_models import Task

    indexes = {idx.name: tuple(col.name for col in idx.columns) for idx in Task.__table__.indexes}
    assert indexes["ix_tasks_queue_ready"] == ("queue_state", "available_at")
```

- [x] **Step 2: Run ORM tests and verify RED**

Run:

```bash
poetry run pytest tests/unit/test_task_queue_model_and_migration.py -q
```

Expected: FAIL because queue columns do not exist.

- [x] **Step 3: Add ORM columns**

Add to `Task`:

```python
task_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
task_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
queue_state: Mapped[str | None] = mapped_column(String(20), nullable=True)
attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
lease_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

__table_args__ = (
    Index("ix_tasks_queue_ready", "queue_state", "available_at"),
)
```

Keep internal fields out of `to_dict()` so public Task responses remain unchanged.

- [x] **Step 4: Add migration and migration structure test**

Migration requirements:

```python
revision = "d7e4f9a2c1b0"
down_revision = "c3d8e1f7a2b4"
```

`upgrade()` adds all nine columns and `ix_tasks_queue_ready`; `downgrade()` drops the index and columns in reverse order. Test imports the migration module and patches `op.add_column/create_index/drop_*` to assert exact operations.

- [x] **Step 5: Run model and migration tests**

Run:

```bash
poetry run pytest tests/unit/test_task_queue_model_and_migration.py -q
poetry run alembic heads
```

Expected: tests pass and only `d7e4f9a2c1b0` is head.

### Task 2: Extend TaskManager queue state machine with TDD

**Files:**

- Modify: `tests/unit/test_task_manager.py`
- Modify: `src/api/services/task_manager.py`

- [x] **Step 1: Extend task mock with queue fields**

Add all queue attributes to `_make_task_mock()` with defaults matching legacy rows (`task_type=None`, `queue_state=None`, attempt defaults).

- [x] **Step 2: Write failing create/enqueue tests**

Required assertions:

```python
task_id = await manager.create_task(
    "idea", "玄幻", 10000,
    task_type="novel.generate",
    task_payload={"request": {"idea": "idea"}},
)
added = session.add.call_args.args[0]
assert added.task_type == "novel.generate"
assert added.task_payload == {"request": {"idea": "idea"}}
assert added.queue_state == "queued"
assert added.attempt_count == 0
assert added.max_attempts == 1
assert added.available_at is not None
```

`enqueue_existing_task()` must lock the row, replace type/payload, reset attempt count, clear lease and set queued.

- [x] **Step 3: Write failing claim/lease tests**

Capture the SQL Select and assert:

```python
assert query._for_update_arg is not None
assert query._for_update_arg.skip_locked is True
assert query._limit_clause.value == 1
```

After claim:

```python
assert task.queue_state == "leased"
assert task.status == "running"
assert task.attempt_count == 1
assert task.lease_owner == "worker-1"
assert task.lease_expires_at > task.heartbeat_at
```

No row returns `None`.

- [x] **Step 4: Write failing renew/release/retry tests**

Cover:

- owner match renews heartbeat and lease;
- owner mismatch returns False and changes nothing;
- HITL progress or paused status releases to idle without failing;
- terminal Task already cleared by `complete_task/fail_task` is tolerated;
- ordinary running handler return becomes failed;
- unhandled exception requeues only when attempts remain;
- attempts exhausted marks failed and appends error.

- [x] **Step 5: Replace startup recovery tests**

Use a `RecoverySummary` dataclass and cover:

```python
assert summary.queued_preserved == 1
assert summary.stale_requeued == 1
assert summary.stale_failed == 1
assert summary.legacy_failed == 1
assert summary.total_changed == 3
```

Future leased rows, idle rows and waiting-review rows remain unchanged.

- [x] **Step 6: Implement TaskManager methods**

Add:

```python
@dataclass(frozen=True)
class RecoverySummary:
    queued_preserved: int = 0
    stale_requeued: int = 0
    stale_failed: int = 0
    legacy_failed: int = 0

    @property
    def total_changed(self) -> int:
        return self.stale_requeued + self.stale_failed + self.legacy_failed
```

Methods:

```python
enqueue_existing_task(...)
claim_next_task(worker_id: str, lease_seconds: int) -> dict[str, Any] | None
renew_lease(task_id: str, worker_id: str, lease_seconds: int) -> bool
release_claim(task_id: str, worker_id: str) -> bool
retry_or_fail_claim(task_id: str, worker_id: str, error: str, retry_delay_seconds: int) -> bool
recover_interrupted_tasks() -> RecoverySummary
```

Use timezone-aware `datetime.now(UTC)`. Create a private `_clear_lease(task)` helper. `complete_task()` and `fail_task()` call it and set `queue_state="idle"` when queue metadata exists.

- [x] **Step 7: Run TaskManager tests**

Run:

```bash
poetry run pytest tests/unit/test_task_manager.py tests/unit/test_change060_task_status.py -q
```

Expected: all lifecycle and queue tests pass.

### Task 3: Build strict task dispatcher with TDD

**Files:**

- Create: `tests/unit/test_task_dispatcher.py`
- Create: `src/api/services/task_dispatcher.py`

- [x] **Step 1: Write failing dispatch tests**

Each test patches the real target function and calls:

```python
await dispatch_task({
    "task_id": "task-1",
    "task_type": TaskType.NOVEL_GENERATE.value,
    "task_payload": {"request": request.model_dump(mode="json")},
})
```

Assert exact reconstructed arguments for:

- `NOVEL_GENERATE`
- `NOVEL_FULL_GENERATE`
- `NOVEL_LONG_FORM`
- `NOVEL_VOLUME`
- `NOVEL_CHAPTERS`
- `PIPELINE_RESUME`

Unknown type raises `ValueError("Unsupported task type")`; malformed payload raises Pydantic/KeyError and never calls a handler.

- [x] **Step 2: Verify RED**

Run:

```bash
poetry run pytest tests/unit/test_task_dispatcher.py -q
```

Expected: module missing.

- [x] **Step 3: Implement TaskType and dispatch_task**

Use:

```python
class TaskType(StrEnum):
    NOVEL_GENERATE = "novel.generate"
    NOVEL_FULL_GENERATE = "novel.full_generate"
    NOVEL_LONG_FORM = "novel.long_form"
    NOVEL_VOLUME = "novel.volume"
    NOVEL_CHAPTERS = "novel.chapters"
    PIPELINE_RESUME = "pipeline.resume"
```

Imports of `novel_generator` functions stay inside the selected branch to avoid startup cycles. Rebuild request models with `CreateNovelRequest.model_validate()` and `LongFormNovelRequest.model_validate()`.

- [x] **Step 4: Run dispatcher tests**

Run:

```bash
poetry run pytest tests/unit/test_task_dispatcher.py -q
```

Expected: all pass.

### Task 4: Build PersistentTaskWorker with TDD

**Files:**

- Create: `tests/unit/test_task_worker.py`
- Create: `src/api/services/task_worker.py`

- [x] **Step 1: Write failing execution tests**

Inject an AsyncMock manager and dispatcher into the worker. Cover:

- no claim waits and polls again;
- claimed task calls dispatcher once;
- heartbeat calls `renew_lease` while dispatcher is blocked;
- successful terminal handler calls `release_claim` safely;
- dispatcher exception calls `retry_or_fail_claim`;
- `CancelledError` during shutdown does not call retry/fail/release;
- `start()` and `stop()` are idempotent;
- stop prevents later claims.

- [x] **Step 2: Verify RED**

Run:

```bash
poetry run pytest tests/unit/test_task_worker.py -q
```

Expected: module missing.

- [x] **Step 3: Implement worker**

Constructor accepts dependencies and timing values for tests:

```python
class PersistentTaskWorker:
    def __init__(
        self,
        manager: TaskManager,
        dispatcher: Callable[[dict[str, Any]], Awaitable[None]] = dispatch_task,
        *,
        poll_seconds: float = 1.0,
        lease_seconds: int = 120,
        retry_delay_seconds: int = 5,
        worker_id: str | None = None,
    ): ...
```

Worker id contains hostname, pid and random suffix. `_run_claim()` starts heartbeat, dispatches, and handles success/exception/cancellation exactly as the design specifies. `get_task_worker()` builds a singleton from Settings.

- [x] **Step 4: Run worker tests**

Run:

```bash
poetry run pytest tests/unit/test_task_worker.py -q
```

Expected: all pass without database or sleeps longer than milliseconds.

### Task 5: Integrate worker into application lifecycle

**Files:**

- Modify: `src/core/config.py`
- Modify: `.env.example`
- Modify: `src/api/main.py`
- Modify: `src/core/database.py`
- Test: `tests/unit/test_task_worker.py`

- [x] **Step 1: Add settings tests**

Assert defaults:

```python
assert settings.TASK_QUEUE_ENABLED is True
assert settings.TASK_QUEUE_POLL_SECONDS == 1.0
assert settings.TASK_QUEUE_LEASE_SECONDS == 120
assert settings.TASK_QUEUE_RETRY_DELAY_SECONDS == 5
```

- [x] **Step 2: Add lifecycle helper test**

Factor startup/shutdown into small functions if needed. Test that enabled mode calls recover → worker.start and shutdown calls worker.stop before checkpointer/database teardown. Disabled mode does not start a worker.

- [x] **Step 3: Implement lifespan wiring**

After LLM initialization and startup validation:

```python
task_worker = None
if settings.TASK_QUEUE_ENABLED:
    task_worker = get_task_worker()
    await task_worker.start()
```

Use `try: yield finally:` and stop worker first in finally. Log `RecoverySummary` fields instead of a single recovered count. Update `close_db()` documentation to describe the explicit worker shutdown order.

- [x] **Step 4: Run lifecycle and import tests**

Run:

```bash
poetry run pytest tests/unit/test_task_worker.py -q
poetry run python -c "from src.api.main import app; print(app.title)"
```

Expected: tests pass and app imports.

### Task 6: Migrate Task-backed routes to durable enqueue

**Files:**

- Create: `tests/unit/test_task_queue_routes.py`
- Modify: `src/api/routes/novels.py`
- Modify: `src/api/routes/projects.py`
- Modify: `src/api/routes/review.py`

- [x] **Step 1: Write static route guard test**

Parse the three modules with AST and assert they contain no `BackgroundTasks` annotation and no `.add_task()` call. Book import and reader simulation are explicitly excluded.

- [x] **Step 2: Write representative route contract tests**

Patch `get_task_manager()` and required services, call route functions directly, and assert `create_task()` receives exact type/payload for ordinary, full, long-form, volume and chapter-range tasks. Review route asserts `enqueue_existing_task()` receives `pipeline.resume` and the decision payload.

- [x] **Step 3: Verify RED**

Run:

```bash
poetry run pytest tests/unit/test_task_queue_routes.py -q
```

Expected: failures because routes still use BackgroundTasks and omit queue metadata.

- [x] **Step 4: Migrate novels routes**

Remove `BackgroundTasks` from Task-backed endpoint signatures. For each `create_task()` add:

```python
task_type=TaskType.<TYPE>.value,
task_payload={... JSON-only payload ...},
max_attempts=1,
```

For long-form creation, create the Novel first, then create the linked Task with `novel_id` and request payload. Per-volume tasks must also store `novel_id`.

- [x] **Step 5: Migrate projects routes**

Map generate/full/volume/chapters to the corresponding TaskType and remove direct generation-function imports.

- [x] **Step 6: Migrate review resume**

Replace BackgroundTasks scheduling with:

```python
await task_manager.enqueue_existing_task(
    task_id,
    task_type=TaskType.PIPELINE_RESUME.value,
    task_payload={"decision": decision},
    max_attempts=1,
)
```

- [x] **Step 7: Run route tests and source search**

Run:

```bash
poetry run pytest tests/unit/test_task_queue_routes.py -q
rg -n "background_tasks\.add_task" src/api/routes
```

Expected: only book import and reader simulation remain.

### Task 7: Document deployment and verify focused suite

**Files:**

- Modify: `.env.example`
- Modify: `docs/DEPLOYMENT.md`

- [x] **Step 1: Document settings and operational semantics**

Explain queued vs leased vs legacy recovery, current no-replay policy for started generation, multi-worker `SKIP LOCKED`, and SQL diagnostics:

```sql
SELECT task_id, status, queue_state, task_type, attempt_count,
       lease_owner, lease_expires_at
FROM tasks
WHERE queue_state IN ('queued', 'leased')
ORDER BY created_at;
```

- [x] **Step 2: Run focused backend suite**

Run:

```bash
poetry run pytest tests/unit/test_task_queue_model_and_migration.py tests/unit/test_task_manager.py tests/unit/test_change060_task_status.py tests/unit/test_task_dispatcher.py tests/unit/test_task_worker.py tests/unit/test_task_queue_routes.py -q
```

Expected: zero failures.

- [x] **Step 3: Run migration and static checks**

Run:

```bash
poetry run alembic heads
poetry run ruff check src/api/models/db_models.py src/api/services/task_manager.py src/api/services/task_dispatcher.py src/api/services/task_worker.py src/api/main.py src/core/config.py src/core/database.py src/api/routes/novels.py src/api/routes/projects.py src/api/routes/review.py tests/unit/test_task_queue_model_and_migration.py tests/unit/test_task_manager.py tests/unit/test_task_dispatcher.py tests/unit/test_task_worker.py tests/unit/test_task_queue_routes.py
git diff --check
```

Expected: one Alembic head, Ruff and diff checks pass.

### Task 8: Full verification and review

**Files:** No additional production changes expected.

- [x] **Step 1: Run complete backend unit suite**

Run:

```bash
poetry run pytest tests/unit -q
```

Expected: zero failures; existing warnings/skips recorded separately.

- [x] **Step 2: Run database-backed tests when available**

Run:

```bash
poetry run pytest tests/api/test_routes.py tests/integration/test_full_generate_api.py tests/integration/test_change044_long_form_api.py -q
```

If PostgreSQL remains unavailable in the sandbox, record the exact connection blocker and do not claim integration success.

- [x] **Step 3: Run frontend regression**

Run from `frontend/`:

```bash
npm test
npm run build
```

Expected: 47 tests pass and build exits 0.

- [x] **Step 4: Review final diff**

Check schema compatibility, no arbitrary payload execution, no duplicate route scheduling, worker cancellation safety, current `max_attempts=1`, and excluded BackgroundTasks unchanged.

- [x] **Step 5: Record exact evidence**

Append pass/fail/skip counts, Alembic head, Ruff/build results, database integration status and code review resolution to this plan. Do not perform Git operations.

## Completion Evidence — 2026-07-19

- 聚焦队列套件：`84 passed`。
- 完整后端单元测试：`839 passed, 1 skipped, 6 warnings, 0 failed`。
- 前端回归：`47 passed`；Vite production build 退出码 `0`。
- Alembic：唯一 head 为 `d7e4f9a2c1b0`。
- 变更范围 Ruff：`All checks passed!`。
- `git diff --check`：退出码 `0`，无输出。
- FastAPI 导入：`from src.api.main import app` 成功，应用标题为 `xIaoShuo API`。
- 路由后台任务搜索：仅剩明确排除的 `book_import.py` 与
  `reader_simulation.py`；Task-backed 小说生成和 HITL 路由无
  `BackgroundTasks`/`add_task()`。
- 四个数据库集成文件可正常收集：`66 tests collected`；已移除迁移后失效的
  BackgroundTasks patch。
- 实际数据库测试命令已执行，但 49 项均在 fixture 连接
  `localhost:5432`（`::1:5432`）时被沙箱阻止：
  `PermissionError: [Errno 1] Operation not permitted`。申请放开本机 PostgreSQL
  连接时审批服务返回 `503 Service Unavailable`，因此数据库集成状态记录为
  **环境未验证**，没有声称通过。
- 独立代码审查最终结论：`Ready: Yes`，无 Critical、Important 或 Minor 遗留。
  审查期间已修复：
  - legacy stale 清理误伤 queued/leased 任务；
  - worker 单次数据库异常导致 runner 永久退出；
  - heartbeat 丢失后旧 dispatcher 继续执行；
  - 次数耗尽的过期 lease 在运行期永久滞留；
  - recovery 与续租并发缺少行锁，以及 idle 全表扫描；
  - startup/shutdown 异常路径资源清理不完整；
  - approved/revision/rejected 审核并发重入缺少行锁 CAS；
  - 数据库集成测试仍 patch 已删除的路由后台函数。
- 未执行 Git 暂存、提交、分支、推送或其他 Git 写操作。
