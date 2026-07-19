# Security and Core Bug Remediation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 封堵仓库凭据泄露、任务与小说资源越权访问，并修复 WebSocket、拆书导入和管理员初始化的已确认缺陷。

**Architecture:** 以数据库中的 `owner_id` 作为唯一授权事实来源。小说资源继续通过 `verify_novel_owner` 校验；异步任务新增持久化 `owner_id`，所有 HTTP、HITL 与 WebSocket 入口统一校验任务所有者。内存态的拆书任务和灵感会话显式绑定用户 ID。安全回归测试使用两个用户构造负例，禁止依赖全局 admin mock 掩盖越权。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy 2、Alembic、PostgreSQL、Vue 3、Vitest、pytest、Ruff、mypy

---

## Confirmed findings covered by this plan

- P0：Git 跟踪的归档文档中存在形似真实的 DeepSeek API Key；当前树可清理，但历史提交中的密钥必须在供应商侧吊销/轮换。
- P0：`/api/v1/novels` 与 `/api/v1/tasks` 的任务查询、列表、取消、暂停、恢复和部分长篇接口缺少认证/所有权校验。
- P0：`/api/v1/projects/{novel_id}/story-bible` 可匿名读取和修改任意小说的故事圣经。
- P1：HITL 审核接口只验证“已登录”，未验证任务归属，可替他人批准、驳回或读取生成结果。
- P1：WebSocket 未校验任务归属；浏览器客户端又无法发送当前后端要求的认证头，因此真实登录环境下连接会失败。
- P1：拆书导入任务未绑定用户，任意登录用户可读取/应用他人的任务；应用后创建的小说未写入 `owner_id`，会形成孤儿项目。
- P1：灵感向导的内存 session 未绑定用户，知道 session ID 的其他用户可继续操作。
- P1：注册接口直接读取 `os.getenv("ADMIN_USERNAME")`，与项目通过 Pydantic `.env` 加载配置的方式不一致，导致 `.env` 中的管理员用户名可能不生效。
- P1：现有测试全局把 `get_current_user` 覆盖成 admin，且缺少双用户负例，无法发现上述越权。

## Explicitly out of scope for this first remediation batch

- 不自动重写 Git 历史；历史清理会改变提交哈希，需要单独授权和协作窗口。
- 不在本批次把 session 从 `localStorage` 迁移到 HttpOnly Cookie；本批次先保证所有入口实际认证并实施对象级授权。
- 不在本批次引入登录限流依赖；后续工程加固计划会把限流、CSP、密码哈希升级和依赖漏洞扫描纳入。

### Task 1: Redact tracked credentials and add a repository secret gate

**Files:**
- Modify: `archive/changes/CHANGE-002-deepseek-api集成/01-需求分析.md`
- Modify: `archive/changes/CHANGE-002-deepseek-api集成/02-技术设计.md`
- Modify: `archive/changes/CHANGE-002-deepseek-api集成/03-编码计划.md`
- Modify: `archive/changes/CHANGE-009-修复云服务器问题/02-技术设计.md`
- Modify: `archive/changes/CHANGE-026-小说全功能生成/01-需求分析.md`
- Create: `scripts/check_secrets.py`
- Create: `tests/unit/test_check_secrets.py`
- Modify: `Makefile`
- Modify: `.github/workflows/verify.yml`

- [ ] **Step 1: Write the failing scanner tests**

```python
from pathlib import Path

from scripts.check_secrets import find_secret_candidates


def test_detects_provider_key(tmp_path: Path) -> None:
    sample = tmp_path / "leak.md"
    sample.write_text("DEEPSEEK_API_KEY=sk-" + "a" * 32, encoding="utf-8")
    assert find_secret_candidates(tmp_path) == [sample]


def test_allows_documented_placeholders(tmp_path: Path) -> None:
    sample = tmp_path / "example.md"
    sample.write_text("DEEPSEEK_API_KEY=sk-your-key", encoding="utf-8")
    assert find_secret_candidates(tmp_path) == []
```

- [ ] **Step 2: Run the scanner tests and verify failure**

Run: `poetry run pytest tests/unit/test_check_secrets.py -q`

Expected: FAIL because `scripts.check_secrets` does not exist.

- [ ] **Step 3: Implement the scanner**

```python
#!/usr/bin/env python3
from __future__ import annotations

import re
import sys
from pathlib import Path

KEY_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_-]{24,}\b")
IGNORED_DIRS = {".git", ".claude", "node_modules", "dist", ".venv"}
ALLOWED_VALUES = {
    "sk-your-key",
    "sk-placeholder",
    "sk-redacted-example",
}


def find_secret_candidates(root: Path) -> list[Path]:
    matches: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in IGNORED_DIRS for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        candidates = KEY_PATTERN.findall(text)
        if any(candidate not in ALLOWED_VALUES for candidate in candidates):
            matches.append(path)
    return sorted(matches)


def main() -> int:
    matches = find_secret_candidates(Path.cwd())
    for path in matches:
        print(path)
    return 1 if matches else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Replace every tracked real-looking key with `sk-redacted-example`**

Only replace the key values. Preserve the surrounding historical explanation.

- [ ] **Step 5: Add the gate to local and CI verification**

Add to `Makefile`:

```make
.PHONY: check-secrets

check-secrets:
	$(PY) python scripts/check_secrets.py
```

Append `check-secrets` to the `verify` prerequisites and add this backend CI step:

```yaml
      - run: make check-secrets
```

- [ ] **Step 6: Verify the scanner**

Run: `poetry run pytest tests/unit/test_check_secrets.py -q && poetry run python scripts/check_secrets.py`

Expected: tests PASS and scanner exits 0 with no output.

### Task 2: Add persistent task ownership

**Files:**
- Create: `alembic/versions/20260720_add_task_owner.py`
- Modify: `src/api/models/db_models.py`
- Modify: `src/api/services/tasks/task_manager.py`
- Modify: `src/api/owner_guard.py`
- Modify: `tests/unit/test_task_queue_model_and_migration.py`
- Modify: `tests/unit/test_task_manager.py`

- [ ] **Step 1: Write failing model and manager tests**

Add assertions that `Task` has an indexed nullable `owner_id`, `Task.to_dict()` includes it, `create_task(..., owner_id=7)` persists it, and `list_tasks_for_owner(7)` never returns owner 8 tasks.

```python
async def test_list_tasks_for_owner_isolated(manager) -> None:
    first = await manager.create_task("a", "玄幻", 10000, owner_id=7)
    await manager.create_task("b", "玄幻", 10000, owner_id=8)
    tasks, total = await manager.list_tasks_for_owner(owner_id=7)
    assert total == 1
    assert [task["task_id"] for task in tasks] == [first]
```

- [ ] **Step 2: Run the focused tests and verify failure**

Run: `poetry run pytest tests/unit/test_task_queue_model_and_migration.py tests/unit/test_task_manager.py -q`

Expected: FAIL because `Task.owner_id` and `list_tasks_for_owner` do not exist.

- [ ] **Step 3: Add the Alembic migration**

```python
"""add task owner

Revision ID: 20260720_task_owner
Revises: d7e4f9a2c1b0
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260720_task_owner"
down_revision: str | Sequence[str] | None = "d7e4f9a2c1b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tasks", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_tasks_owner_id", "tasks", "users", ["owner_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_tasks_owner_id", "tasks", ["owner_id"])
    op.execute(
        """
        UPDATE tasks AS t
        SET owner_id = n.owner_id
        FROM novels AS n
        WHERE t.novel_id = n.novel_id
          AND t.owner_id IS NULL
        """
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_owner_id", table_name="tasks")
    op.drop_constraint("fk_tasks_owner_id", "tasks", type_="foreignkey")
    op.drop_column("tasks", "owner_id")
```

- [ ] **Step 4: Add the ORM field and serialization**

Add to `Task`:

```python
owner_id: Mapped[int | None] = mapped_column(
    Integer,
    ForeignKey("users.id", ondelete="SET NULL"),
    nullable=True,
    index=True,
)
```

Add `"owner_id": self.owner_id` to `Task.to_dict()`.

- [ ] **Step 5: Require owner ID for new tasks and add owner-filtered queries**

Use these signatures in `TaskManager`:

```python
async def create_task(
    self,
    idea: str,
    novel_type: str,
    target_words: int,
    novel_id: str | None = None,
    *,
    owner_id: int,
    task_type: str | None = None,
    task_payload: dict[str, Any] | None = None,
    max_attempts: int = 1,
) -> str:
```

```python
async def list_tasks_for_owner(
    self,
    owner_id: int,
    status: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[dict[str, Any]], int]:
    async with get_db_session() as session:
        query = select(Task).where(Task.owner_id == owner_id)
        if status:
            query = query.where(Task.status == status)
        total = (
            await session.execute(
                select(func.count()).select_from(query.subquery())
            )
        ).scalar_one()
        rows = (
            await session.execute(
                query.order_by(Task.created_at.desc()).limit(limit).offset(offset)
            )
        ).scalars().all()
        return [task.to_dict() for task in rows], total
```

- [ ] **Step 6: Add a shared task owner guard**

```python
async def verify_task_owner(task_id: str, current_user: User) -> dict:
    task = await get_task_manager().get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    if task.get("owner_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Permission denied")
    return task
```

- [ ] **Step 7: Run focused tests**

Run: `poetry run pytest tests/unit/test_task_queue_model_and_migration.py tests/unit/test_task_manager.py -q`

Expected: PASS.

### Task 3: Enforce ownership on task, long-form, review, and WebSocket routes

**Files:**
- Modify: `src/api/routes/novels.py`
- Modify: `src/api/routes/projects.py`
- Modify: `src/api/routes/review.py`
- Modify: `src/api/routes/ws.py`
- Modify: `src/core/security/auth.py`
- Modify: `frontend/src/composables/useWebSocket.js`
- Create: `tests/api/test_task_authorization.py`
- Modify: `tests/api/test_websocket.py`
- Modify: `frontend/src/__tests__/useWebSocket.spec.js`

- [ ] **Step 1: Write HTTP cross-user authorization tests**

Create two real users and sessions. Seed one novel and task for user A. Assert user B receives 403 for:

```text
GET  /api/v1/novels/{task_id}
POST /api/v1/novels/{task_id}/cancel
POST /api/v1/tasks/{task_id}/pause
POST /api/v1/tasks/{task_id}/resume
GET  /api/v1/tasks/{task_id}/review
POST /api/v1/tasks/{task_id}/review
GET  /api/v1/novels/{novel_id}/quality-report
GET  /api/v1/novels/{novel_id}/filler-detection
GET  /api/v1/novels/{novel_id}/foreshadow-tracker
GET  /api/v1/novels/{novel_id}/long-form/progress
POST /api/v1/novels/{novel_id}/volumes/1/generate
POST /api/v1/novels/{novel_id}/volumes/1/pause
POST /api/v1/novels/{novel_id}/volumes/1/resume
```

Also assert `GET /api/v1/novels` returns only the caller's tasks and `POST /api/v1/novels/cleanup/stale` returns 403 for a non-admin user.

- [ ] **Step 2: Run the authorization tests and verify failure**

Run: `poetry run pytest tests/api/test_task_authorization.py -q`

Expected: multiple failures showing current anonymous or cross-user access.

- [ ] **Step 3: Protect all task and long-form routes**

Apply these rules in `novels.py`:

- Every non-health endpoint requires `current_user: User = Depends(get_current_user)`.
- Every new task passes `owner_id=current_user.id`.
- Task detail/cancel/pause/resume call `verify_task_owner` before any operation.
- Task list calls `list_tasks_for_owner(current_user.id, ...)`.
- `cleanup/stale` depends on `require_admin_user` because it mutates all users' tasks.
- Every endpoint with `novel_id` calls `verify_novel_owner(novel_id, current_user)` before service access.

Apply `owner_id=current_user.id` to every `create_task` call in `projects.py`.

- [ ] **Step 4: Protect HITL review**

At the start of both review endpoints:

```python
task = await verify_task_owner(task_id, current_user)
```

Reuse the returned task in `submit_review` instead of loading it again.

- [ ] **Step 5: Add WebSocket authentication through subprotocols**

Add to `src/core/security/auth.py`:

```python
async def get_websocket_user(websocket: WebSocket) -> User | None:
    raw = websocket.headers.get("sec-websocket-protocol", "")
    protocols = [item.strip() for item in raw.split(",") if item.strip()]
    if len(protocols) == 2 and protocols[0] == "xiaoshuo":
        return await get_session_user(protocols[1])
    if get_settings().DEV_AUTO_LOGIN:
        return await get_or_create_dev_user()
    return None
```

Update the route flow:

```python
current_user = await get_websocket_user(websocket)
if current_user is None:
    await websocket.close(code=4401, reason="Authentication required")
    return
try:
    task = await verify_task_owner(task_id, current_user)
except HTTPException as exc:
    await websocket.close(
        code=4404 if exc.status_code == 404 else 4403,
        reason=exc.detail,
    )
    return
await websocket.accept(subprotocol="xiaoshuo")
```

- [ ] **Step 6: Send the session token as a WebSocket subprotocol**

Update the frontend connection:

```javascript
const token = localStorage.getItem('session_token')
const socket = token
  ? new WebSocket(url, ['xiaoshuo', token])
  : new WebSocket(url)
```

- [ ] **Step 7: Add WebSocket tests**

Backend assertions:

- no subprotocol token closes with 4401;
- invalid token closes with 4401;
- user B token for user A task closes with 4403;
- user A token connects and receives `connected`.

Frontend assertion:

```javascript
expect(MockWebSocket).toHaveBeenCalledWith(
  expect.stringContaining('/ws/tasks/t1'),
  ['xiaoshuo', 'valid-session'],
)
```

- [ ] **Step 8: Run route and WebSocket tests**

Run: `poetry run pytest tests/api/test_task_authorization.py tests/api/test_websocket.py -q && cd frontend && npm test -- useWebSocket.spec.js --run`

Expected: PASS.

### Task 4: Protect Story Bible, book import, and inspiration sessions

**Files:**
- Modify: `src/api/routes/story_bible.py`
- Modify: `src/api/routes/book_import.py`
- Modify: `src/api/services/book_import_service.py`
- Modify: `src/api/routes/inspiration.py`
- Modify: `src/api/services/content/inspiration_service.py`
- Create: `tests/api/test_secondary_resource_authorization.py`
- Modify: `tests/test_book_import.py`
- Modify: `tests/test_inspiration.py`

- [ ] **Step 1: Write cross-user tests**

For two users A and B, assert:

- B cannot GET or PUT A's Story Bible;
- B cannot read or apply A's book-import task;
- a project created by applying A's import has `owner_id == A.id`;
- B cannot advance or generate from A's stateful inspiration session.

- [ ] **Step 2: Run the tests and verify failure**

Run: `poetry run pytest tests/api/test_secondary_resource_authorization.py -q`

Expected: failures demonstrating missing ownership.

- [ ] **Step 3: Add Story Bible owner verification**

Both handlers receive `current_user: User = Depends(get_current_user)` and call:

```python
await verify_novel_owner(novel_id, current_user)
```

before opening their own database session.

- [ ] **Step 4: Bind book-import tasks to users and preserve ownership on project creation**

Use these method contracts:

```python
def create_task(self, chapters: list[dict[str, Any]], owner_id: int) -> str:
```

```python
def get_status(self, task_id: str, owner_id: int) -> dict[str, Any]:
```

```python
async def apply_task(self, task_id: str, owner_id: int) -> dict[str, Any]:
```

Store `"owner_id": owner_id` in `_tasks`. `_get_owned_task` raises `PermissionError` when IDs differ. Route handlers translate it to HTTP 403. Pass `owner_id` to `create_project_from_analysis`, then to `manager.create_novel(owner_id=owner_id, ...)`.

- [ ] **Step 5: Bind inspiration sessions to users**

Use these method contracts:

```python
def start_session(self, owner_id: int) -> dict[str, Any]:
async def process_step(self, session_id: str, step: str, user_input: str, owner_id: int) -> dict[str, Any]:
async def generate_outline(self, session_id: str, owner_id: int) -> dict[str, Any]:
async def create_project(self, session_id: str, target_words: int, owner_id: int) -> dict[str, Any]:
```

Store `owner_id` in each session and make `_get_session(session_id, owner_id)` raise `PermissionError` on mismatch. Route handlers translate it to HTTP 403. Stateless `collected` requests remain bound to the authenticated caller when creating a project.

- [ ] **Step 6: Run focused tests**

Run: `poetry run pytest tests/api/test_secondary_resource_authorization.py tests/test_book_import.py tests/test_inspiration.py -q`

Expected: PASS.

### Task 5: Correct administrator provisioning and secure LLM metadata endpoints

**Files:**
- Modify: `src/api/routes/auth.py`
- Modify: `src/api/routes/llm_config.py`
- Modify: `tests/test_llm_config_auth.py`
- Modify: `tests/api/routes/test_llm_config.py`

- [ ] **Step 1: Write failing tests**

Add tests proving:

- `ADMIN_USERNAME` loaded through `get_settings()` creates an admin user even when the value exists only in Pydantic settings;
- ordinary users receive 403 from all six LLM config/stat endpoints;
- admin users can list configs, read token stats, and perform all mutations.

- [ ] **Step 2: Run and verify failure**

Run: `poetry run pytest tests/test_llm_config_auth.py tests/api/routes/test_llm_config.py -q`

Expected: admin provisioning and public GET tests fail under the new security expectation.

- [ ] **Step 3: Use the canonical settings source**

Replace the direct environment read in registration with:

```python
admin_username = get_settings().ADMIN_USERNAME.strip()
is_admin = bool(admin_username) and req.username == admin_username
```

- [ ] **Step 4: Require admin for LLM metadata reads**

Add `_admin: User = Depends(require_admin_user)` to `list_configs` and `get_token_stats`, matching the existing mutation policy.

- [ ] **Step 5: Run focused tests**

Run: `poetry run pytest tests/test_llm_config_auth.py tests/api/routes/test_llm_config.py -q`

Expected: PASS.

### Task 6: Remove authentication blind spots from the test suite

**Files:**
- Modify: `tests/conftest.py`
- Modify: `tests/api/test_cross_novel_isolation.py`
- Modify: `Makefile`
- Modify: `.github/workflows/verify.yml`

- [ ] **Step 1: Stop globally overriding every request as admin**

Delete this global override:

```python
app.dependency_overrides[get_current_user] = mock_get_current_user
```

Replace it with explicit fixtures:

```python
@pytest.fixture
async def auth_user_factory():
    async def create(username: str, *, is_admin: bool = False) -> tuple[User, str]:
        async with get_db_session() as session:
            user = User(
                username=username,
                hashed_password=hash_password("pass1234"),
                is_admin=is_admin,
            )
            session.add(user)
            await session.flush()
            user_id = user.id
        token = await create_session(user_id)
        return User(id=user_id, username=username, hashed_password="", is_admin=is_admin), token
    return create
```

Tests send `Authorization: Bearer <token>` explicitly.

- [ ] **Step 2: Ensure root-level tests enter the backend gate**

Add a target:

```make
test-root:
	$(PY) pytest tests/test_book_import.py tests/test_careers.py tests/test_inspiration.py tests/test_llm_config_auth.py -q
```

Make `test-backend` depend on `test-root`, and add `make test-root` to the backend CI job.

- [ ] **Step 3: Add explicit anonymous and cross-user assertions**

For every protected router touched by this plan, assert anonymous requests return 401 and non-owner requests return 403. Do not use dependency overrides in these tests.

- [ ] **Step 4: Run backend authorization suites**

Run: `make test-root && make test-api`

Expected: PASS with a reachable PostgreSQL test database.

### Task 7: Full verification and security review

**Files:**
- Modify only if verification reveals a root-cause defect in files already listed above.

- [ ] **Step 1: Run migrations against the test database**

Run: `TEST_DATABASE_URL="$TEST_DATABASE_URL" DATABASE_URL="$TEST_DATABASE_URL" poetry run alembic upgrade head`

Expected: migration reaches `20260720_task_owner` without errors.

- [ ] **Step 2: Run backend tests in isolated groups**

Run: `make test-unit && make test-root && make test-api && make test-integration`

Expected: all pass; the real-LLM `tests/integration/test_langgraph` remains excluded.

- [ ] **Step 3: Run frontend tests and build**

Run: `make test-frontend && make build-frontend`

Expected: 47 or more tests pass and production build succeeds.

- [ ] **Step 4: Run static and repository gates**

Run: `poetry run ruff check . && poetry run python scripts/check_secrets.py && git diff --check`

Expected: all commands exit 0.

- [ ] **Step 5: Perform a focused authorization review**

Review every route in `src/api/routes/novels.py`, `review.py`, `ws.py`, `story_bible.py`, `book_import.py`, `inspiration.py`, and `llm_config.py`. Confirm each non-public endpoint has both authentication and the correct object-level ownership/admin check.

- [ ] **Step 6: Record the external incident action**

Document in the delivery note that all exposed provider keys must be revoked and replaced. Do not state that repository redaction invalidates credentials or removes them from Git history.

---

## Self-review

- Spec coverage: covers every confirmed P0/P1 issue listed above, including negative authorization tests.
- Placeholder scan: implementation steps contain concrete paths, contracts, code, commands, and expected results.
- Type consistency: `owner_id` is an integer across ORM, manager, route, in-memory task/session, and tests; task guards return the existing task dictionary.
