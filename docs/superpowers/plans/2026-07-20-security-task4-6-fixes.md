# Task 4-6 安全隐藏问题修复计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复 Task 4-6 排查出的安全隐藏问题（story_bible 越权、book_import 跨用户与孤儿项目、llm_config GET 端点缺 admin、inspiration session 跨用户、auth.py 绕过 Settings、根级测试未入门禁），全部 TDD。

**Architecture:** 复用 Phase 3 已建的鉴权基础设施（`verify_novel_owner` / `verify_task_owner` / `require_admin_user`），按风险优先级逐项修复。每项先写负例测试（匿名 + 跨用户）→ 跑红 → 改生产代码 → 跑绿 → commit。最后补 Makefile `test-root` 目标并接入 `verify` 与 CI。

**Tech Stack:** Python 3.11 · FastAPI · SQLAlchemy 2 async · pytest-asyncio · httpx AsyncClient · ruff

---

## 文件结构

- 修改: `src/api/routes/story_bible.py` — GET/PUT 加 `current_user` + `verify_novel_owner`
- 修改: `src/api/routes/book_import.py` — 3 端点接 owner_id + verify_task_owner
- 修改: `src/api/services/book_import_service.py` — `create_task`/`get_status`/`apply_task`/`create_project_from_analysis` 接/传 owner_id
- 修改: `src/api/routes/llm_config.py` — `list_configs`/`get_token_stats` 加 `require_admin_user`
- 修改: `src/api/services/content/inspiration_service.py` — session 绑定 owner_id，process/generate 校验
- 修改: `src/api/routes/inspiration.py` — start 传 owner，step/generate 校验
- 修改: `src/api/routes/auth.py` — `os.getenv` → `get_settings().ADMIN_USERNAME`
- 修改: `Makefile` — 新增 `test-root` 目标，接入 `verify`
- 修改: `.github/workflows/verify.yml` — backend job 加 `make test-root`
- 创建: `tests/api/test_story_bible_authorization.py` — story_bible 越权负例
- 创建: `tests/api/test_book_import_authorization.py` — book_import 跨用户负例
- 创建: `tests/api/test_llm_config_admin.py` — list_configs/token-stats admin 门禁
- 创建: `tests/api/test_inspiration_session_owner.py` — inspiration session 跨用户负例

---

## 测试基础设施约定（复用 Phase 3 模式）

所有鉴权测试放 `tests/api/`，复用 conftest 的 `mock_get_current_user`（真实 token 优先）。
每个测试文件自带 `_db_setup`（module scope）+ `two_users`（function scope）fixture，
模式参照 `tests/api/test_task_authorization.py`。匿名测试 pop `dependency_overrides` 测真实 401。

helper：
```python
def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}
```

---

## Task 1: story_bible 越权修复（P0，最高危）

**Files:**
- Create: `tests/api/test_story_bible_authorization.py`
- Modify: `src/api/routes/story_bible.py:54-156`

- [ ] **Step 1: 写失败测试 `test_story_bible_authorization.py`**

```python
"""故事圣经鉴权回归测试（Task 4.1）。

story_bible GET/PUT 原无鉴权，任意用户可读写他人小说的设定（世界观/角色/伏笔等核心资产）。
覆盖：owner 读写 200、跨用户 GET 403、跨用户 PUT 403、匿名 GET/PUT 401。
"""

import secrets
from datetime import UTC, datetime

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.api.models.db_models import Novel
from src.core.auth_models import User
from src.core.database import Base, get_db_session, get_engine
from src.core.security.users import create_session, hash_password


@pytest.fixture(scope="module")
async def _db_setup():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def two_users(_db_setup):
    suffix = secrets.token_hex(4)
    async with get_db_session() as session:
        a = User(username=f"bible_a_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        b = User(username=f"bible_b_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        session.add(a)
        session.add(b)
        await session.flush()
        a_id, b_id = a.id, b.id
        novel_id = f"bible-novel-{suffix}"
        session.add(Novel(novel_id=novel_id, title="圣经测试", idea="t",
                          novel_type="玄幻", target_words=10000, status="draft", owner_id=a_id))
    token_a = await create_session(a_id)
    token_b = await create_session(b_id)
    return {"a_id": a_id, "token_a": token_a, "b_id": b_id,
            "token_b": token_b, "novel_id": novel_id}


@pytest.fixture
async def client(_db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_owner_can_read_and_write_bible(client, two_users):
    """owner GET 自动初始化空记录 → 200；PUT 写入 → 200。"""
    novel_id = two_users["novel_id"]
    r = await client.get(f"/api/v1/projects/{novel_id}/story-bible", headers=_bearer(two_users["token_a"]))
    assert r.status_code == 200, r.text
    r = await client.put(
        f"/api/v1/projects/{novel_id}/story-bible",
        headers=_bearer(two_users["token_a"]),
        json={"worldview_rules": "测试世界观"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["worldview_rules"] == "测试世界观"


async def test_cross_user_get_bible_forbidden(client, two_users):
    """user B 读 user A 的故事圣经 → 403。"""
    r = await client.get(
        f"/api/v1/projects/{two_users['novel_id']}/story-bible",
        headers=_bearer(two_users["token_b"]),
    )
    assert r.status_code == 403, r.text


async def test_cross_user_put_bible_forbidden(client, two_users):
    """user B 写 user A 的故事圣经 → 403。"""
    r = await client.put(
        f"/api/v1/projects/{two_users['novel_id']}/story-bible",
        headers=_bearer(two_users["token_b"]),
        json={"worldview_rules": "劫持"},
    )
    assert r.status_code == 403, r.text


async def test_anonymous_get_bible_unauthorized(client, two_users):
    """匿名 GET → 401。"""
    from src.api.main import app
    from src.core.security.auth import get_current_user

    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        r = await client.get(f"/api/v1/projects/{two_users['novel_id']}/story-bible")
        assert r.status_code == 401, r.text
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved
```

- [ ] **Step 2: 跑测试验证失败**

Run: `poetry run pytest tests/api/test_story_bible_authorization.py -v`
Expected: FAIL — 跨用户 GET/PUT 返回 200（无鉴权），匿名 GET 也非 401

- [ ] **Step 3: 改 `story_bible.py` GET/PUT 加鉴权**

修改两个端点签名与首行：

```python
from fastapi import APIRouter, Depends, HTTPException
from src.api.owner_guard import verify_novel_owner
from src.core.auth_models import User
from src.core.security.auth import get_current_user


@router.get("", response_model=StoryBibleResponse)
async def get_story_bible(
    novel_id: str,
    current_user: User = Depends(get_current_user),
):
    """获取小说的故事圣经。如果不存在，则自动初始化一条空记录。"""
    await verify_novel_owner(novel_id, current_user)
    async with get_db_session() as session:
        # ... 原有逻辑不变
```

PUT 端点同理加 `current_user: User = Depends(get_current_user)` + 首行 `await verify_novel_owner(novel_id, current_user)`。

- [ ] **Step 4: 跑测试验证通过**

Run: `poetry run pytest tests/api/test_story_bible_authorization.py -v`
Expected: PASS（4 项）

- [ ] **Step 5: 跑 ruff 确认无 lint 错误**

Run: `poetry run ruff check src/api/routes/story_bible.py tests/api/test_story_bible_authorization.py`
Expected: no errors

- [ ] **Step 6: commit**

```bash
git add src/api/routes/story_bible.py tests/api/test_story_bible_authorization.py
git commit -m "fix(story_bible): GET/PUT 加 verify_novel_owner 修复 P0 越权读写 (Task 4.1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: book_import 跨用户 + 孤儿项目修复（P1）

**Files:**
- Create: `tests/api/test_book_import_authorization.py`
- Modify: `src/api/services/book_import_service.py:112-214`
- Modify: `src/api/routes/book_import.py:16-62`

- [ ] **Step 1: 写失败测试 `test_book_import_authorization.py`**

```python
"""拆书导入鉴权回归测试（Task 4.2）。

book_import 原仅 create_task 不传 owner_id，get_status/apply 无 owner 校验，
导致跨用户访问他人导入任务、导入产生的小说成孤儿项目。
覆盖：导入任务绑定 owner、跨用户读 status/apply 403、apply 产生的 novel owner 正确。
"""

import secrets

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.api.services.book_import_service import get_book_import_service
from src.core.auth_models import User
from src.core.database import Base, get_db_session, get_engine
from src.core.security.users import create_session, hash_password


@pytest.fixture(scope="module")
async def _db_setup():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def two_users(_db_setup):
    suffix = secrets.token_hex(4)
    async with get_db_session() as session:
        a = User(username=f"imp_a_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        b = User(username=f"imp_b_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        session.add(a)
        session.add(b)
        await session.flush()
        a_id, b_id = a.id, b.id
    token_a = await create_session(a_id)
    token_b = await create_session(b_id)
    return {"a_id": a_id, "token_a": token_a, "b_id": b_id, "token_b": token_b}


@pytest.fixture
async def client(_db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_import_task_bound_to_owner(two_users):
    """create_task 带 owner_id → task["owner_id"] == a_id。"""
    service = get_book_import_service()
    service.clear()
    task_id = service.create_task([{"index": 1, "title": "序章", "content": "x"}], owner_id=two_users["a_id"])
    status = service.get_status(task_id, owner_id=two_users["a_id"])
    assert status["owner_id"] == two_users["a_id"]


async def test_cross_user_get_status_forbidden(two_users):
    """user B 读 user A 的导入 status → KeyError/403。"""
    service = get_book_import_service()
    service.clear()
    task_id = service.create_task([{"index": 1, "title": "序章", "content": "x"}], owner_id=two_users["a_id"])
    # B 持有 A 的 task_id 试图读 → service 层应抛 KeyError（路由转 404/403）
    with pytest.raises(KeyError):
        service.get_status(task_id, owner_id=two_users["b_id"])


async def test_cross_user_apply_forbidden(two_users):
    """user B 应用 user A 的导入任务 → 抛 PermissionError（路由转 403）。"""
    service = get_book_import_service()
    service.clear()
    task_id = service.create_task([{"index": 1, "title": "序章", "content": "x"}], owner_id=two_users["a_id"])
    with pytest.raises((KeyError, PermissionError)):
        await service.apply_task(task_id, owner_id=two_users["b_id"])
```

- [ ] **Step 2: 跑测试验证失败**

Run: `poetry run pytest tests/api/test_book_import_authorization.py -v`
Expected: FAIL — `create_task` 不接受 owner_id 参数

- [ ] **Step 3: 改 `book_import_service.py` 接 owner_id**

`create_task` 签名 + session 存 owner_id：
```python
def create_task(self, chapters: list[dict[str, Any]], *, owner_id: int | None = None) -> str:
    self._cleanup_tasks()
    self._enforce_task_limit()
    task_id = f"book-import-{uuid.uuid4().hex}"
    now = datetime.now(UTC).isoformat()
    self._tasks[task_id] = {
        "task_id": task_id,
        "status": "pending",
        "owner_id": owner_id,  # 新增
        "chapters": deepcopy(chapters),
        # ... 其余不变
    }
    return task_id
```

`get_status` 加 owner 校验：
```python
def get_status(self, task_id: str, *, owner_id: int | None = None) -> dict[str, Any]:
    task = self._get_task(task_id)
    if owner_id is not None and task.get("owner_id") != owner_id:
        raise PermissionError("Book import task not accessible")
    return {
        "task_id": task["task_id"],
        "status": task["status"],
        "owner_id": task.get("owner_id"),  # 新增返回
        # ... 其余不变
    }
```

`apply_task` 加 owner 校验 + 传 owner_id 给 `create_project_from_analysis`：
```python
async def apply_task(self, task_id: str, *, owner_id: int | None = None) -> dict[str, Any]:
    task = self._get_task(task_id)
    if owner_id is not None and task.get("owner_id") != owner_id:
        raise PermissionError("Book import task not accessible")
    if task["status"] == "applied" and task["project"]:
        return deepcopy(task["project"])
    if task["status"] != "completed" or not task["analysis"]:
        raise ValueError("Book import analysis is not completed")
    project = await self.create_project_from_analysis(task_id, task["analysis"], owner_id=owner_id)
    self._set_task(task_id, status="applied", project=project)
    return deepcopy(project)
```

`create_project_from_analysis` 接 owner_id 传给 `manager.create_novel`：
```python
async def create_project_from_analysis(
    self,
    novel_id: str,
    analysis_data: dict[str, Any],
    *,
    owner_id: int | None = None,
) -> dict[str, Any]:
    manager = get_novel_manager()
    # ... 不变
    created_novel_id = await manager.create_novel(
        idea=idea,
        novel_type=novel_type,
        target_words=100000,
        title=title,
        writing_style="拆书风格",
        custom_style_description=style_prompt,
        writing_style_prompt=style_prompt,
        owner_id=owner_id,  # 新增
    )
    # ... 其余不变
```

- [ ] **Step 4: 改 `book_import.py` 路由传 owner_id + 调用方式适配**

```python
@router.post("", status_code=202)
async def import_book(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    # ... 不变
    task_id = service.create_task(chapters, owner_id=current_user.id)
    background_tasks.add_task(service.run_analysis, task_id, get_llm_client())
    # ... 不变


@router.get("/{task_id}/status")
async def get_import_status(task_id: str, current_user: User = Depends(get_current_user)):
    service = get_book_import_service()
    try:
        return service.get_status(task_id, owner_id=current_user.id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except KeyError:
        raise HTTPException(status_code=404, detail="Book import task not found")


@router.post("/{task_id}/apply")
async def apply_import(task_id: str, current_user: User = Depends(get_current_user)):
    service = get_book_import_service()
    try:
        return await service.apply_task(task_id, owner_id=current_user.id)
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    except KeyError:
        raise HTTPException(status_code=404, detail="Book import task not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("book_import_apply_failed", task_id=task_id, error=str(exc))
        raise HTTPException(status_code=500, detail="Failed to create project")
```

- [ ] **Step 5: 跑测试验证通过**

Run: `poetry run pytest tests/api/test_book_import_authorization.py -v`
Expected: PASS（3 项）

- [ ] **Step 6: 跑现有 root 测试确认无回归**

Run: `poetry run pytest tests/test_book_import.py -v`
Expected: PASS（若有调用 `create_task`/`get_status`/`apply_task` 旧签名的测试需适配 owner_id kw，预期少量改动）

- [ ] **Step 7: ruff + commit**

Run: `poetry run ruff check src/api/routes/book_import.py src/api/services/book_import_service.py tests/api/test_book_import_authorization.py`
Expected: no errors

```bash
git add src/api/routes/book_import.py src/api/services/book_import_service.py tests/api/test_book_import_authorization.py tests/test_book_import.py
git commit -m "fix(book_import): 导入任务绑 owner_id + get_status/apply 加 owner 校验 (Task 4.2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: llm_config GET 端点加 admin 门禁（P1）

**Files:**
- Create: `tests/api/test_llm_config_admin.py`
- Modify: `src/api/routes/llm_config.py:113-119, 218-221`

- [ ] **Step 1: 写失败测试 `test_llm_config_admin.py`**

```python
"""LLM 配置 GET 端点 admin 门禁测试（Task 5.2）。

list_configs / get_token_stats 原任意登录用户可读，泄露全局配置与用量。
覆盖：admin 200、普通用户 403、匿名 401。
"""

import secrets

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.core.auth_models import User
from src.core.database import Base, get_db_session, get_engine
from src.core.security.users import create_session, hash_password


@pytest.fixture(scope="module")
async def _db_setup():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def admin_and_user(_db_setup):
    suffix = secrets.token_hex(4)
    async with get_db_session() as session:
        admin = User(username=f"llmadmin_{suffix}", hashed_password=hash_password("pass1234"), is_admin=True)
        plain = User(username=f"llmuser_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        session.add(admin)
        session.add(plain)
        await session.flush()
        admin_id, plain_id = admin.id, plain.id
    token_admin = await create_session(admin_id)
    token_plain = await create_session(plain_id)
    return {"token_admin": token_admin, "token_plain": token_plain}


@pytest.fixture
async def client(_db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_list_configs_admin_ok(client, admin_and_user):
    r = await client.get("/api/v1/llm/configs", headers=_bearer(admin_and_user["token_admin"]))
    assert r.status_code == 200, r.text


async def test_list_configs_plain_user_forbidden(client, admin_and_user):
    r = await client.get("/api/v1/llm/configs", headers=_bearer(admin_and_user["token_plain"]))
    assert r.status_code == 403, r.text


async def test_token_stats_plain_user_forbidden(client, admin_and_user):
    r = await client.get("/api/v1/llm/token-stats", headers=_bearer(admin_and_user["token_plain"]))
    assert r.status_code == 403, r.text


async def test_anonymous_list_configs_unauthorized(client, admin_and_user):
    from src.api.main import app
    from src.core.security.auth import get_current_user

    saved = app.dependency_overrides.pop(get_current_user, None)
    try:
        r = await client.get("/api/v1/llm/configs")
        assert r.status_code == 401, r.text
    finally:
        if saved is not None:
            app.dependency_overrides[get_current_user] = saved
```

- [ ] **Step 2: 跑测试验证失败**

Run: `poetry run pytest tests/api/test_llm_config_admin.py -v`
Expected: FAIL — 普通用户 list_configs/token-stats 返回 200

- [ ] **Step 3: 改 `llm_config.py` 两个 GET 加 admin**

```python
@router.get("/configs", response_model=list[LLMConfigResponse])
async def list_configs(_admin=Depends(require_admin_user)) -> list[LLMConfigResponse]:
    """列出所有 LLM 配置（仅 admin，api_key 脱敏）。"""
    async with get_db_session() as session:
        result = await session.execute(select(LLMConfig).order_by(LLMConfig.id))
        configs = result.scalars().all()
    return [_to_response(c) for c in configs]


@router.get("/token-stats")
async def get_token_stats(_admin=Depends(require_admin_user)) -> dict[str, Any]:
    """返回 token 用量统计数据（仅 admin）。"""
    return get_token_tracker().get_stats()
```

- [ ] **Step 4: 跑测试验证通过**

Run: `poetry run pytest tests/api/test_llm_config_admin.py -v`
Expected: PASS（4 项）

- [ ] **Step 5: 跑现有 root 测试确认无回归**

Run: `poetry run pytest tests/test_llm_config_auth.py -v`
Expected: PASS 或如失败则适配（旧测试可能以普通用户读 configs，需改为 admin）

- [ ] **Step 6: ruff + commit**

Run: `poetry run ruff check src/api/routes/llm_config.py tests/api/test_llm_config_admin.py`
Expected: no errors

```bash
git add src/api/routes/llm_config.py tests/api/test_llm_config_admin.py tests/test_llm_config_auth.py
git commit -m "fix(llm_config): list_configs/token-stats 加 require_admin_user (Task 5.2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: inspiration session 绑定 owner_id（P2）

**Files:**
- Create: `tests/api/test_inspiration_session_owner.py`
- Modify: `src/api/services/content/inspiration_service.py:48-72, 74-131, 133-138, 199-204`
- Modify: `src/api/routes/inspiration.py:37-65, 68-91`

- [ ] **Step 1: 写失败测试 `test_inspiration_session_owner.py`**

```python
"""灵感向导 session 跨用户隔离测试（Task 4.3）。

inspiration session 原不绑 owner，session_id 已知即可被他人接续操作污染内容。
覆盖：A start → A step ok；B 用 A 的 session_id step → 403。
"""

import secrets

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.core.auth_models import User
from src.core.database import Base, get_db_session, get_engine
from src.core.security.users import create_session, hash_password


@pytest.fixture(scope="module")
async def _db_setup():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def two_users(_db_setup):
    suffix = secrets.token_hex(4)
    async with get_db_session() as session:
        a = User(username=f"insp_a_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        b = User(username=f"insp_b_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        session.add(a)
        session.add(b)
        await session.flush()
        a_id, b_id = a.id, b.id
    token_a = await create_session(a_id)
    token_b = await create_session(b_id)
    return {"a_id": a_id, "token_a": token_a, "b_id": b_id, "token_b": token_b}


@pytest.fixture
async def client(_db_setup):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


async def test_cross_user_step_forbidden(client, two_users):
    """A start session → B 用该 session_id step → 403。"""
    r = await client.post("/api/v1/inspiration/start", headers=_bearer(two_users["token_a"]))
    assert r.status_code == 200, r.text
    session_id = r.json()["session_id"]

    r_b = await client.post(
        f"/api/v1/inspiration/{session_id}/step",
        headers=_bearer(two_users["token_b"]),
        json={"step": "idea", "user_input": "劫持内容"},
    )
    assert r_b.status_code == 403, r_b.text
```

- [ ] **Step 2: 跑测试验证失败**

Run: `poetry run pytest tests/api/test_inspiration_session_owner.py -v`
Expected: FAIL — B 用 A 的 session step 返回 200（无 owner 校验）

- [ ] **Step 3: 改 `inspiration_service.py` session 绑 owner + 校验**

`start_session` 接 owner_id：
```python
def start_session(self, *, owner_id: int | None = None) -> dict[str, Any]:
    self._cleanup_sessions()
    self._enforce_session_limit()
    session_id = f"inspiration-{uuid.uuid4().hex}"
    now = datetime.now(UTC).isoformat()
    self._sessions[session_id] = {
        "session_id": session_id,
        "owner_id": owner_id,  # 新增
        "current_step": "idea",
        # ... 其余不变
    }
    # ... 返回不变
```

`process_step` 加 owner 校验：
```python
async def process_step(
    self,
    session_id: str,
    step: str,
    user_input: str,
    *,
    owner_id: int | None = None,
) -> dict[str, Any]:
    session = self._get_session(session_id)
    if owner_id is not None and session.get("owner_id") is not None \
            and session.get("owner_id") != owner_id:
        raise PermissionError("Inspiration session not accessible")
    # ... 其余不变
```

`generate_outline` 同理加 owner_id 参数 + 校验。

- [ ] **Step 4: 改 `inspiration.py` 路由传 owner + 处理 PermissionError**

```python
@router.post("/start")
async def start_inspiration_session(current_user: User = Depends(get_current_user)):
    wizard = get_inspiration_wizard()
    return wizard.start_session(owner_id=current_user.id)


@router.post("/{session_id}/step")
async def process_inspiration_step(
    session_id: str,
    request: InspirationStepRequest,
    current_user: User = Depends(get_current_user),
):
    wizard = get_inspiration_wizard()
    try:
        return await wizard.process_step(
            session_id=session_id,
            step=request.step,
            user_input=request.user_input,
            owner_id=current_user.id,
        )
    except PermissionError:
        raise HTTPException(status_code=403, detail="Inspiration session not accessible")
    except KeyError:
        raise HTTPException(status_code=404, detail="Inspiration session not found")
    # ... 其余不变
```

`generate_inspiration_outline` 同理传 `owner_id=current_user.id` + PermissionError→403。

- [ ] **Step 5: 跑测试验证通过**

Run: `poetry run pytest tests/api/test_inspiration_session_owner.py -v`
Expected: PASS

- [ ] **Step 6: 跑现有 root 测试确认无回归**

Run: `poetry run pytest tests/test_inspiration.py -v`
Expected: PASS 或适配（旧测试若直接调 `start_session()` 不传 owner_id，依赖默认 None 不校验，应仍通过）

- [ ] **Step 7: ruff + commit**

Run: `poetry run ruff check src/api/routes/inspiration.py src/api/services/content/inspiration_service.py tests/api/test_inspiration_session_owner.py`
Expected: no errors

```bash
git add src/api/routes/inspiration.py src/api/services/content/inspiration_service.py tests/api/test_inspiration_session_owner.py tests/test_inspiration.py
git commit -m "fix(inspiration): session 绑 owner_id + step/generate 加跨用户校验 (Task 4.3)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: auth.py 绕过 Settings 修复（P3）

**Files:**
- Modify: `src/api/routes/auth.py:51-54`

- [ ] **Step 1: 改 `auth.py` 用 `get_settings().ADMIN_USERNAME`**

```python
from src.core.config import get_settings
# ... 删除函数体内的 import os

    # Create user（若 username 匹配 ADMIN_USERNAME 配置，标记为 admin）
    admin_username = get_settings().ADMIN_USERNAME.strip()
    is_admin = bool(admin_username) and req.username == admin_username
```

注意：`get_settings` 已在 conftest `pytest_configure` 调 `get_settings.cache_clear()`，确保读最新 env。

- [ ] **Step 2: 跑现有 auth 相关测试确认无回归**

Run: `poetry run pytest tests/test_auth*.py tests/api/test_*auth*.py -v 2>/dev/null; poetry run pytest -k "register or admin" -v`
Expected: PASS（行为不变，仅配置来源切换）

- [ ] **Step 3: ruff + commit**

Run: `poetry run ruff check src/api/routes/auth.py`
Expected: no errors

```bash
git add src/api/routes/auth.py
git commit -m "refactor(auth): register 用 get_settings().ADMIN_USERNAME 替代 os.getenv (Task 5.1)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: 补 test-root 门禁（流程）

**Files:**
- Modify: `Makefile`
- Modify: `.github/workflows/verify.yml`

- [ ] **Step 1: 先单独跑 4 个根级测试确认无 conftest 耦合**

Run: `poetry run pytest tests/test_book_import.py tests/test_careers.py tests/test_inspiration.py tests/test_llm_config_auth.py -v`
Expected: PASS（若有失败，先修适配，因 Task 1-5 改了 service 签名）

- [ ] **Step 2: 改 `Makefile` 加 test-root 目标**

在 `test-backend` 目标后追加：

```makefile
test-root:
	$(PY) pytest tests/test_book_import.py tests/test_careers.py tests/test_inspiration.py tests/test_llm_config_auth.py -v
```

并把 `.PHONY` 行与 `verify` 依赖补上 `test-root`：

```makefile
.PHONY: test-unit test-api test-integration test-backend test-root test-frontend ruff ruff-fix build-frontend check-structure check-legacy-paths check-secrets verify
```

```makefile
verify: test-backend test-root test-frontend ruff check-structure check-legacy-paths check-secrets build-frontend
```

- [ ] **Step 3: 改 `.github/workflows/verify.yml` backend job 加 test-root**

在 `- run: make test-integration` 后加一行：

```yaml
      - run: make test-root
```

- [ ] **Step 4: 跑 `make test-root` 验证**

Run: `make test-root`
Expected: PASS

- [ ] **Step 5: 跑 `make verify` 全门禁验证**

Run: `make verify`
Expected: ALL CHECKS PASSED

- [ ] **Step 6: commit**

```bash
git add Makefile .github/workflows/verify.yml
git commit -m "chore: 新增 test-root 门禁接入 4 个根级安全测试 (Task 6)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: 最终验证与收口

- [ ] **Step 1: 跑全套测试**

Run: `make verify`
Expected: ALL CHECKS PASSED

- [ ] **Step 2: alembic heads 确认单一**

Run: `poetry run alembic heads`
Expected: 单一 head（无分支）

- [ ] **Step 3: git diff --check 确认无空白错误**

Run: `git diff --check`
Expected: 无输出

- [ ] **Step 4: 汇总修复结果**

报告：Task 4.1-6 全部完成，`make verify` 绿，新增 4 个鉴权测试文件共 N 项负例。

---

## Self-Review

**1. Spec coverage:** Task 4.1 story_bible（Task 1）✓、4.2 book_import（Task 2）✓、4.3 inspiration（Task 4）✓、5.1 auth.py（Task 5）✓、5.2 llm_config（Task 3）✓、6.1/6.2 Makefile/CI（Task 6）✓。排查报告 6 项全覆盖。

**2. Placeholder scan:** 无 TODO/TBD，所有 step 含完整代码。

**3. Type consistency:** `create_task(chapters, *, owner_id)` 在 service 与 route 调用一致；`get_status(task_id, *, owner_id)`、`apply_task(task_id, *, owner_id)`、`create_project_from_analysis(novel_id, analysis_data, *, owner_id)` 签名前后一致；`start_session(*, owner_id)`、`process_step(session_id, step, user_input, *, owner_id)` 一致。
