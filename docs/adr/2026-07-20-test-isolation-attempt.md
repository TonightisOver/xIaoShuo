# 测试隔离修复尝试（A2 阶段，搁置）

**日期**：2026-07-20
**状态**：搁置（patch 另存为 `2026-07-20-test-isolation-attempt.md.patch`）

## 背景

`make test-backend` 一次跑 `tests/unit tests/api tests/integration` 时报 12 failed + 35 errors。
根因：9 个文件的 `scope="module"` `_db_setup` fixture 各自 `create_all` + 退出时 `drop_all`，
在同一 PostgreSQL 上交错，某模块退出 drop_all 删表，破坏其它模块 → 表不存在错误。
当前 workaround：Makefile `test-backend` 改为分目录跑（test-unit / test-api / test-integration 各自绿）。

## A2 尝试做了什么

- 根 `tests/conftest.py` 新增 session 级共享建表 fixture `_session_tables`（create_all 进程开始、drop_all 进程结束）
- 各模块 `_db_setup` 去掉 create/drop，依赖 `_session_tables`，只 seed 数据
- `test_llm_config_auth.py` 的 `secure_env` 从 drop+create 改为 `DELETE FROM llm_configs`

## 为何搁置

pytest-asyncio 0.23 的 session-scope async fixture 与 module/function-scope async fixture 用**不同的 event loop**，
导致 session fixture 建表用的 engine 连接绑在 loop A，module fixture 在 loop B 用同一 engine 时报
`attached to a different loop`。尝试过 `asyncio_default_fixture_loop_scope = "session"` 与 `@pytest_asyncio.fixture`
均未根治。强修需重构整个测试 event loop 管理，风险大于收益。

## 何时重拾

升级 pytest-asyncio 到 1.0+（统一 event loop scope 后），或在 test_langgraph 子 conftest 之外
统一改用同步入口 + `asyncio.run` 的建表路径。届时 `git apply docs/adr/2026-07-20-test-isolation-attempt.md.patch`
作为起点。

## 当前影响

`make verify` 仍全绿（分目录 workaround），CI 的 backend job 也是三个独立 step。
不影响正确性，只是 `test-backend` 不能单条命令一次跑完——已知局限，记入 MEMORY。
