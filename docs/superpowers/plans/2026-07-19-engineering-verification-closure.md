# 工程验证收口 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把项目从"目录整理完成"推进到"结构长期可维护"——打通 PostgreSQL 集成测试、清理 Ruff 历史基线、并把现有验证流程固化为可重复运行的统一工程门禁（Makefile 目标 + 可选 CI）。

**Architecture:** 三阶段串联。阶段 1 修复测试 DB 配置（conftest 的 URL 选择 bug + 探测可达性），让 977 个测试中真正连 DB 的部分在本机跑通。阶段 2 用 `ruff check --fix` 机械清理 81 个可自动修复问题，剩余手动修，基线归零。阶段 3 新增一个 Makefile，把"结构测试 / 单元测试 / 集成测试 / ruff / 前端测试 / 前端构建 / 旧路径残留检查"统一为 `make` 目标，并附一个 `make verify` 聚合门禁。

**Tech Stack:** Python 3.11 · pytest/pytest-asyncio · SQLAlchemy(async) + asyncpg · Ruff · Vitest · Make · (可选) GitHub Actions

---

## 现状事实清单（计划依据）

1. **977 个测试**全部成功收集（`pytest --co` 输出 `977 tests collected`），其中真正连 DB 的集成/api 测试因 DB 配置问题跑不起来。
2. **localhost:5432 在跑本机 PostgreSQL**，已存在 `xiaoshuo` 与 `xiaoshuo_test` 两个库，owner 是本机用户 `a1`（无密码）。
3. **conftest bug**：`tests/conftest.py` 的 `_TEST_DB_URLS` 循环用 `if url: ... break`，导致环境变量 `TEST_DATABASE_URL` 不生效——`os.environ.get` 未设时返回 `None` 被 `if url` 跳过，立刻落到第一条写死的 `xiaoshuo:xiaoshuo2026@...` URL。该角色/密码在本机 pg 不存在 → 连接失败。
4. **集成/api 测试自带建表**：如 `tests/api/test_routes.py` 有 session 级 `_db_setup` fixture 用 `Base.metadata.create_all` 建表，不依赖 alembic 迁移；只要 URL 可达就能跑。
5. **Ruff 基线**：`ruff check .` 输出 `Found 89 errors. [*] 81 fixable with --fix`，主要 I001（导入未排序）、F401（未用导入）、少量 UP/N。
6. **无 Makefile**（项目根无 `Makefile`），无 `.github/workflows`（无 CI）。
7. **前端**：`frontend/package.json` 提供 `npm run test`（vitest run，47 项）与 `npm run build`（vite build）。
8. **旧路径残留检查脚本不存在**，需新建；"服务目录结构测试"也不存在，需新建一个 pytest 测试断言目录约束。
9. **本机无 docker 命令**（`command not found: docker`），但本机 pg 已可直接用；计划以本机 pg 为测试 DB，不强依赖 docker。

---

## File Structure

### 新建

- **`Makefile`**（项目根）：统一验证门禁入口。各目标：`test-unit`、`test-integration`、`test-frontend`、`ruff`、`ruff-fix`、`build-frontend`、`check-structure`、`check-legacy-paths`、`verify`（聚合）。
- **`scripts/check_legacy_paths.py`**：扫描仓库，断言不存在已废弃的旧服务路径（旧入口/旧模块路径）。
- **`tests/unit/test_project_structure.py`**：用 pytest 断言关键目录结构约束（`src/api/routes/` 按资源拆分、`src/core/` 分包存在、`archive/` 不被 `src/` 引用等）。
- **`.github/workflows/verify.yml`**（可选/最后任务）：CI 版的 `make verify`。

### 修改

- **`tests/conftest.py`**：重写 `TEST_DATABASE_URL` 选择逻辑——先取 `TEST_DATABASE_URL` 环境变量；否则按候选列表**逐一探测连通性**（TCP 连通 + asyncpg 连接），选中第一个能连上的；全部失败时抛清晰错误并提示如何准备测试 DB（而不是静默落到一条必然失败的 URL）。
- **`.env.example`**：补充 `TEST_DATABASE_URL` 注释示例。
- **`README.md`**：在"验证/测试"小节写入 `make verify` 用法与准备测试 DB 的步骤。

---

## Task 1: 修复 conftest 的测试 DB URL 选择逻辑

**Files:**
- Modify: `tests/conftest.py`（重写 `TEST_DATABASE_URL` 选择段）
- Modify: `.env.example`（补 `TEST_DATABASE_URL` 示例）

**背景**：当前 conftest 的 URL 选择有 bug，且失败时静默落到一条必然连不上的写死 URL。本任务改成"环境变量优先 + 逐一探测可达性 + 失败时清晰报错"。

- [ ] **Step 1: 先写一个探测函数的失败测试**

创建 `tests/unit/test_conftest_db_url.py`：

```python
"""验证 tests/conftest.py 的 DB URL 选择逻辑：环境变量优先、探测可达性、失败清晰报错。"""

import importlib
import os


def _reload_conftest_with_env(monkeypatch, env: dict):
    for k in list(os.environ):
        if k in {"TEST_DATABASE_URL", "DATABASE_URL", "LLM_ENCRYPTION_KEY"}:
            monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import tests.conftest as conf
    return importlib.reload(conf)


def test_env_var_takes_priority(monkeypatch):
    """设了 TEST_DATABASE_URL 就必须用它，不能落到写死 fallback。"""
    conf = _reload_conftest_with_env(monkeypatch, {"TEST_DATABASE_URL": "postgresql+asyncpg://x:x@nonexistent:5432/db"})
    assert conf.TEST_DATABASE_URL == "postgresql+asyncpg://x:x@nonexistent:5432/db"
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /Users/a1/Developer/projects/xIaoShuo && poetry run pytest tests/unit/test_conftest_db_url.py -v
```

Expected: FAIL —— 当前逻辑因 `nonexistent` 不可达会被探测函数改写或报错，且未设环境变量时 `os.environ.get` 返回 None 被跳过。测试断言"环境变量优先"，当前实现不满足。

- [ ] **Step 3: 重写 conftest 的 URL 选择逻辑**

把 `tests/conftest.py` 顶部到 `pytest_configure` 之前替换为：

```python
"""Pytest configuration and fixtures"""

import asyncio
import os
import socket

import asyncpg
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

# Test Fernet key for LLM_ENCRYPTION_KEY
TEST_FERNET_KEY = "8bj5PGK84njNhOHlIV64dHHMh7QGgdrNKm5eozsXDKY="

# 候选测试 DB URL：环境变量优先；其后按本机常见配置逐一探测。
# 注意：写死条目仅为兼容多种本机/容器环境，不可在"环境变量已设"时被覆盖。
_CANDIDATE_DB_URLS = [
    os.environ.get("TEST_DATABASE_URL"),
    "postgresql+asyncpg://a1@localhost:5432/xiaoshuo_test",
    "postgresql+asyncpg://xiaoshuo:xiaoshuo2026@localhost:5432/xiaoshuo_test",
    "postgresql+asyncpg://xiaoshuo:xiaoshuo2026@localhost:5433/xiaoshuo_test",
    "postgresql+asyncpg://postgres:postgres@localhost:5432/postgres",
]


def _host_port_from_pg_url(url: str) -> tuple[str, int] | None:
    """从 postgresql+asyncpg://user:pwd@host:port/db 抽取 host/port。"""
    try:
        rest = url.split("://", 1)[1]
        authority = rest.split("/", 1)[0]
        host, _, port = authority.rpartition(":")
        port = port.split("?")[0]
        return host, int(port)
    except (IndexError, ValueError):
        return None


def _tcp_reachable(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _pg_login_ok(url: str) -> bool:
    """用 asyncpg 直接连一次确认登录/库存在。url 须是 asyncpg 可用的。"""
    pg_url = url.replace("postgresql+asyncpg://", "postgresql://")
    async def _check() -> bool:
        try:
            conn = await asyncpg.connect(pg_url, timeout=2)
            await conn.close()
            return True
        except Exception:
            return False
    try:
        return asyncio.run(_check())
    except RuntimeError:
        return False


def _resolve_test_db_url() -> str:
    # 1) 环境变量优先（用户显式指定，不探测、不覆盖）
    env_url = os.environ.get("TEST_DATABASE_URL")
    if env_url:
        return env_url
    # 2) 逐一探测候选 URL：TCP 可达 + 登录成功
    for url in _CANDIDATE_DB_URLS:
        if not url:
            continue
        hp = _host_port_from_pg_url(url)
        if not hp or not _tcp_reachable(*hp):
            continue
        if _pg_login_ok(url):
            return url
    # 3) 全部不可达：给出可操作的报错，不要静默跑测试
    raise RuntimeError(
        "未找到可用的测试数据库。请二选一：\n"
        "  (a) export TEST_DATABASE_URL='postgresql+asyncpg://<user>@localhost:5432/xiaoshuo_test'\n"
        "  (b) 在本机 PostgreSQL 建库：createdb xiaoshuo_test\n"
        "确认 PostgreSQL 已启动且用户对该库有建表权限。"
    )


TEST_DATABASE_URL = _resolve_test_db_url()
```

> 说明：`pytest_configure` 内的 `os.environ["DATABASE_URL"] = TEST_DATABASE_URL` 保持不变即可。

- [ ] **Step 4: 运行测试确认通过**

```bash
poetry run pytest tests/unit/test_conftest_db_url.py -v
```

Expected: PASS —— 环境变量优先得到满足（未探测、直接返回）。

- [ ] **Step 5: 确认探测逻辑在本机能选出可达 URL（未设环境变量时）**

```bash
poetry run python -c "import os; os.environ.pop('TEST_DATABASE_URL', None); import tests.conftest as c; print('SELECTED:', c.TEST_DATABASE_URL)"
```

Expected: 输出 `SELECTED: postgresql+asyncpg://a1@localhost:5432/xiaoshuo_test`（本机 owner 为 a1、库已存在、可达且可登录）。

- [ ] **Step 6: 更新 .env.example 补充测试 DB 说明**

在 `.env.example` 的 Database configuration 段后追加：

```
# 测试用数据库（pytest 自动探测；如需强制指定可在此设置）
# TEST_DATABASE_URL=postgresql+asyncpg://a1@localhost:5432/xiaoshuo_test
```

- [ ] **Step 7: Commit**

```bash
git add tests/conftest.py tests/unit/test_conftest_db_url.py .env.example
git commit -m "fix(test): 修复 conftest DB URL 选择逻辑——环境变量优先+探测可达性+失败清晰报错"
```

---

## Task 2: 打通 PostgreSQL 集成测试（端到端跑通 api + integration）

**Files:**
- 无新建/修改源码文件（仅运行验证 + 必要时补 fixture 复用）

**背景**：`tests/api/test_routes.py` 等各自定义了 session 级 `_db_setup` fixture 用 `Base.metadata.create_all` 建表。Task 1 修好 URL 后，本任务验证集成/api 测试能真正跑通，并把任何遗漏的建表依赖补齐。

- [ ] **Step 1: 跑 api 测试目录**

```bash
poetry run pytest tests/api -v 2>&1 | tail -40
```

Expected: 全绿（或暴露具体失败）。若失败属"表不存在/关系不存在"，检查对应测试是否缺 `_db_setup` 依赖，而非改源码。

- [ ] **Step 2: 跑 integration 测试目录**

```bash
poetry run pytest tests/integration -v 2>&1 | tail -40
```

Expected: 全绿。同样，失败先判定是"测试 DB 配置"还是"测试本身缺建表 fixture"。

- [ ] **Step 3: 如有测试缺建表 fixture，统一为复用 test_routes 的 _db_setup 模式**

若 Step 1/2 出现"relation does not exist"类错误，定位缺 fixture 的测试文件，在其顶部补：

```python
import pytest
from src.core.database import Base, get_engine


@pytest.fixture(scope="session")
async def _db_setup():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

并在用到 DB 的测试函数加 `async def test_x(client, _db_setup):` 让 fixture 生效。

> 注意：若多个文件各自定义同名 session 级 fixture，pytest 会按文件隔离，不会冲突；保持现状即可，不要为"统一"而过度抽象（YAGNI）。

- [ ] **Step 4: 跑完整测试套件确认总数**

```bash
poetry run pytest 2>&1 | tail -15
```

Expected: `977 passed`（或接近，个别可能因环境差异 skip）。记录实际通过数。

- [ ] **Step 5: Commit（仅当 Step 3 有改动时）**

```bash
git add tests/
git commit -m "test: 补齐集成测试建表 fixture，确保连 DB 测试端到端跑通"
```

若 Step 3 无改动则跳过 commit，直接进入下一任务。

---

## Task 3: 清理 Ruff 历史基线（机械清理 + 手动收尾，归零）

**Files:**
- 修改：`tests/` 与 `src/` 下被 ruff 标记的文件（自动 fix 涉及多文件）

**背景**：`ruff check .` 报 89 errors，81 可 `--fix`。本任务先自动修复，再手动清剩余 8 个（含 6 个 unsafe-fix，逐个判定）。

- [ ] **Step 1: 先看完整问题清单**

```bash
poetry run ruff check . 2>&1 | tee /tmp/ruff_before.txt | tail -5
```

记录 `Found N errors`。

- [ ] **Step 2: 自动修复**

```bash
poetry run ruff check . --fix 2>&1 | tail -10
```

Expected: 输出 `Fixed N errors`，剩余约 8 个。

- [ ] **Step 3: 再跑一次确认剩余**

```bash
poetry run ruff check . 2>&1 | tail -15
```

Expected: 剩余问题逐条列出（多为 unsafe-fix 或需人工判断的）。

- [ ] **Step 4: 逐个手动修剩余问题**

对每一条剩余 ruff 报错，打开对应文件手动修复（删未用导入、重排导入块、修命名/旧语法）。**不要**用 `--unsafe-fixes` 批量跑——逐条确认语义不变。

修复后单文件验证：

```bash
poetry run ruff check <文件路径> 2>&1
```

- [ ] **Step 5: 确认全量归零**

```bash
poetry run ruff check . 2>&1 | tail -5
```

Expected: `All checks passed!`

- [ ] **Step 6: 确认测试未被 ruff fix 破坏**

```bash
poetry run pytest -q 2>&1 | tail -10
```

Expected: 通过数与 Task 2 Step 4 一致（ruff 只改导入/格式，不应改变行为）。

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "chore(ruff): 清理历史静态检查基线——导入排序/未用导入/旧语法，全量归零"
```

---

## Task 4: 新增"旧服务路径残留检查"脚本

**Files:**
- Create: `scripts/check_legacy_paths.py`

**背景**：拆目录后需防止旧路径死灰复燃。本脚本扫描仓库，断言一组已知废弃的旧路径/旧符号不存在或未被 `src/` 引用。

- [ ] **Step 1: 先确认当前已无残留（确定基线"应该通过"）**

```bash
grep -rn "src.api.services.novel_generator\|src.api.routes.old\|src.core.langgraph.nodes.legacy" src/ 2>/dev/null | head
```

记录结果（若无输出，基线干净）。

- [ ] **Step 2: 写脚本**

`scripts/check_legacy_paths.py`：

```python
"""旧服务路径残留检查：断言废弃路径/符号不再出现于 src/ 内。

退出码 0 = 干净；非 0 = 发现残留，需人工清理。
用法：python scripts/check_legacy_paths.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = REPO_ROOT / "src"

# 已废弃的模块路径片段/符号；一旦在 src/ 下命中即视为残留。
LEGACY_MARKERS: list[str] = [
    # 示例占位：按实际拆分历史填入真实废弃路径
    # "src.api.services.novel_generator",   # 已拆分到 long_form_generation_helpers
    # "src.api.routes.old",
]

# 已废弃的顶层文件名；存在即视为残留。
LEGACY_FILES: list[str] = [
    # "src/api/routes/old_routes.py",
]


def _scan_legacy_imports() -> list[str]:
    hits: list[str] = []
    for py in SRC_DIR.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        for marker in LEGACY_MARKERS:
            if marker in text:
                hits.append(f"{py.relative_to(REPO_ROOT)}: 命中废弃标记 {marker!r}")
    return hits


def _scan_legacy_files() -> list[str]:
    hits: list[str] = []
    for f in LEGACY_FILES:
        if (REPO_ROOT / f).exists():
            hits.append(f"废弃文件仍存在: {f}")
    return hits


def main() -> int:
    hits = _scan_legacy_imports() + _scan_legacy_files()
    if not hits:
        print("legacy-paths: OK (无残留)")
        return 0
    print("legacy-paths: FAIL —— 发现旧路径残留：")
    for h in hits:
        print(f"  - {h}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
```

> 注：`LEGACY_MARKERS` / `LEGACY_FILES` 初始留空/占位是**有意**的——本任务先把检查机制立起来（脚本 + 调用点），具体的废弃路径清单由后续按真实拆分历史填入；空清单时脚本通过，表示"当前无已知残留基线"。填清单是持续动作，不是本计划阻塞项。

- [ ] **Step 3: 运行确认通过**

```bash
poetry run python scripts/check_legacy_paths.py
```

Expected: `legacy-paths: OK (无残留)`，退出码 0。

- [ ] **Step 4: Commit**

```bash
git add scripts/check_legacy_paths.py
git commit -m "chore(scripts): 新增旧服务路径残留检查脚本（legacy-paths gate）"
```

---

## Task 5: 新增"服务目录结构测试"

**Files:**
- Create: `tests/unit/test_project_structure.py`

**背景**：把目录约束变成可执行的 pytest 断言，防止后续误拆/误建目录。

- [ ] **Step 1: 先确认当前实际目录结构，把"应该断言什么"写实**

```bash
ls src/api/routes/ && echo "---" && ls src/core/ && echo "---" && ls src/api/services/
```

记录真实子目录，作为断言依据。

- [ ] **Step 2: 写结构测试**

`tests/unit/test_project_structure.py`：

```python
"""服务目录结构约束：断言关键目录/分包存在，且 archive/ 不被 src/ 引用。"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"


def test_routes_split_by_resource():
    """routes 按资源拆分，不再是单文件。"""
    routes_dir = SRC / "api" / "routes"
    assert routes_dir.is_dir(), "src/api/routes/ 应为目录"
    py_files = [p.name for p in routes_dir.glob("*.py") if p.name != "__init__.py"]
    assert len(py_files) >= 3, f"routes 下应至少有 3 个资源模块，实际 {py_files}"


def test_core_subpackages_exist():
    """core 已有合理分包。"""
    for sub in ["database", "config.py", "security"]:
        assert (SRC / "core" / sub).exists(), f"src/core/{sub} 应存在"


def test_archive_not_imported_by_src():
    """archive/ 仅供归档，src/ 内不应 import 它。"""
    archive_marker = "from archive" if (REPO_ROOT / "archive").is_dir() else None
    if not archive_marker:
        return  # 无 archive 目录则跳过
    for py in SRC.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        assert "from archive" not in text and "import archive" not in text, (
            f"{py.relative_to(REPO_ROOT)} 不应 import archive/"
        )


def test_no_top_level_project_dirs_under_root():
    """工作区根不应出现 node_modules/.venv 等被提交的产物目录。"""
    for forbidden in ["node_modules", ".venv", "__pycache__"]:
        assert not (REPO_ROOT / forbidden).is_dir() or forbidden == "__pycache__", (
            f"根目录不应存在 {forbidden}/（应被 gitignore）"
        )
```

- [ ] **Step 3: 运行确认通过**

```bash
poetry run pytest tests/unit/test_project_structure.py -v
```

Expected: 全绿。若某断言与现状不符，**先核对现状**——是断言写错还是真有结构问题，宁可调断言也不要掩盖真问题。

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_project_structure.py
git commit -m "test(structure): 新增服务目录结构约束测试"
```

---

## Task 6: 固化为 Makefile 统一工程门禁

**Files:**
- Create: `Makefile`（项目根）
- Modify: `README.md`（写入 `make verify` 用法）

**背景**：把散在各处的验证统一成 `make` 目标，附一个 `make verify` 聚合门禁。

- [ ] **Step 1: 写 Makefile**

`Makefile`：

```makefile
# xIaoShuo 工程验证门禁
# 用法：make verify 跑全部检查；make <target> 跑单项。

PY := poetry run
FE := cd frontend && npm

.PHONY: test-unit test-integration test-backend test-frontend ruff ruff-fix build-frontend check-structure check-legacy-paths verify clean

## 后端单元测试
test-unit:
	$(PY) pytest tests/unit -q

## 后端 API/集成测试（需可达的 PostgreSQL 测试库）
test-integration:
	$(PY) pytest tests/api tests/integration -q

## 后端全部测试
test-backend:
	$(PY) pytest -q

## 前端单元测试
test-frontend:
	$(FE) run test

## Ruff 静态检查
ruff:
	$(PY) ruff check .

## Ruff 自动修复（谨慎，会改文件）
ruff-fix:
	$(PY) ruff check . --fix

## 前端生产构建
build-frontend:
	$(FE) run build

## 服务目录结构约束测试
check-structure:
	$(PY) pytest tests/unit/test_project_structure.py -q

## 旧服务路径残留检查
check-legacy-paths:
	$(PY) python scripts/check_legacy_paths.py

## 聚合门禁：跑全部验证（任一失败即整体失败）
verify: test-backend test-frontend ruff check-structure check-legacy-paths build-frontend
	@echo "==== ALL CHECKS PASSED ===="
```

> Makefile 缩进必须用 Tab（不是空格）。

- [ ] **Step 2: 验证单项目标可用**

```bash
make check-structure && make check-legacy-paths && make ruff
```

Expected: 三项均通过。

- [ ] **Step 3: 跑聚合门禁**

```bash
make verify 2>&1 | tail -30
```

Expected: 末尾 `==== ALL CHECKS PASSED ====`。若有失败，回到对应 Task 修复后重跑。

- [ ] **Step 4: 更新 README.md 写入用法**

在 `README.md` 的测试/验证相关位置追加小节：

```markdown
## 工程验证

一键跑全部门禁：

```bash
make verify
```

单项：

- `make test-backend` — 后端全部测试
- `make test-integration` — API/集成测试（需可达 PostgreSQL 测试库）
- `make test-frontend` — 前端 Vitest
- `make ruff` — 静态检查
- `make build-frontend` — 前端生产构建
- `make check-structure` — 目录结构约束
- `make check-legacy-paths` — 旧路径残留检查

### 准备测试数据库

集成测试需可达的 PostgreSQL 测试库。本机已存在时 conftest 会自动探测；也可显式指定：

```bash
export TEST_DATABASE_URL='postgresql+asyncpg://a1@localhost:5432/xiaoshuo_test'
```

若无库，先建：

```bash
createdb xiaoshuo_test
```
```

- [ ] **Step 5: Commit**

```bash
git add Makefile README.md
git commit -m "chore: 新增 Makefile 统一工程门禁（make verify 聚合）"
```

---

## Task 7（可选）: CI 版门禁（GitHub Actions）

**Files:**
- Create: `.github/workflows/verify.yml`

**背景**：把 `make verify` 复刻到 CI，确保 PR 走同一套门禁。本机无 docker，CI 用 GitHub runner 自带 services 起 postgres。

- [ ] **Step 1: 写 workflow**

`.github/workflows/verify.yml`：

```yaml
name: verify

on:
  push:
    branches: [master]
  pull_request:

jobs:
  backend:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:17-alpine
        env:
          POSTGRES_USER: xiaoshuo
          POSTGRES_PASSWORD: xiaoshuo2026
          POSTGRES_DB: xiaoshuo_test
        ports: ["5432:5432"]
        options: >-
          --health-cmd "pg_isready -U xiaoshuo"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5
    env:
      TEST_DATABASE_URL: postgresql+asyncpg://xiaoshuo:xiaoshuo2026@localhost:5432/xiaoshuo_test
      LLM_ENCRYPTION_KEY: 8bj5PGK84njNhOHlIV64dHHMh7QGgdrNKm5eozsXDKY=
      DATABASE_URL: postgresql+asyncpg://xiaoshuo:xiaoshuo2026@localhost:5432/xiaoshuo_test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - run: pip install poetry && poetry install --no-root
      - run: make test-backend
      - run: make ruff
      - run: make check-structure
      - run: make check-legacy-paths

  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - run: cd frontend && npm ci
      - run: make test-frontend
      - run: make build-frontend
```

- [ ] **Step 2: 本地用 act 或直接推到分支触发验证（无法本地验证 YAML 语法时至少做 yamllint / python yaml.safe_load 校验）**

```bash
poetry run python -c "import yaml; yaml.safe_load(open('.github/workflows/verify.yml'))" && echo "YAML OK"
```

Expected: `YAML OK`。

- [ ] **Step 3: Commit（不立即推送，由用户决定何时启用 CI）**

```bash
git add .github/workflows/verify.yml
git commit -m "ci: 新增 verify workflow（make verify 的 CI 版）"
```

---

## Self-Review

**1. Spec coverage（对照用户三优先级）：**
- "打通 PostgreSQL 集成测试" → Task 1（修 conftest）+ Task 2（端到端跑通）✅
- "清理 Ruff 基线" → Task 3 ✅
- "固定持续验证门禁" → Task 4（旧路径检查）+ Task 5（结构测试）+ Task 6（Makefile）+ Task 7（CI，可选）✅
- "暂缓继续拆 models/routes" → 计划全程不拆 ORM/路由，仅触及测试与脚本 ✅

**2. Placeholder scan：**
- Task 4 的 `LEGACY_MARKERS` 留空是有意设计（先立机制），已在文中说明，非占位偷懒。
- 其余步骤均含完整代码/命令/期望输出，无 "TBD/补错误处理" 类占位。

**3. Type/命名一致性：**
- Makefile 目标名（`test-backend`/`test-integration`/`check-structure`/`check-legacy-paths`/`verify`）在 Task 6、Task 7、README 中一致。
- conftest 的 `TEST_DATABASE_URL`/`TEST_FERNET_KEY` 命名与原文件一致；`_resolve_test_db_url` 在 Step 3 定义、Step 1 测试与 Step 5 验证中一致引用。
- `scripts/check_legacy_paths.py` 的 `main()` 退出码语义在 Task 4 与 Task 6 `check-legacy-paths` 目标一致。

无遗留问题。
