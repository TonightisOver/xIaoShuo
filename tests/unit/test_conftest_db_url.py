"""验证 tests/conftest.py 的 DB URL 选择逻辑：环境变量优先、探测可达性、失败清晰报错。"""

import importlib
import os


def _reload_conftest_with_env(monkeypatch, env):
    for k in list(os.environ):
        if k in {"TEST_DATABASE_URL", "DATABASE_URL", "LLM_ENCRYPTION_KEY"}:
            monkeypatch.delenv(k, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    import tests.conftest as conf
    return importlib.reload(conf)


def test_env_var_takes_priority(monkeypatch):
    """设了 TEST_DATABASE_URL 就必须用它，不能落到写死 fallback。"""
    conf = _reload_conftest_with_env(
        monkeypatch, {"TEST_DATABASE_URL": "postgresql+asyncpg://x:x@nonexistent:5432/db"}
    )
    assert conf.TEST_DATABASE_URL == "postgresql+asyncpg://x:x@nonexistent:5432/db"


def test_raises_when_no_env_and_no_reachable_db(monkeypatch):
    """无环境变量、且所有候选 URL 都不可达时，应抛 RuntimeError 而非静默落到坏 URL。"""
    import tests.conftest as conf

    # 候选 URL 全部指向不可达端口，强制探测全失败
    monkeypatch.setattr(conf, "_CANDIDATE_DB_URLS", [
        "postgresql+asyncpg://a1@localhost:1/xiaoshuo_test",
        "postgresql+asyncpg://xiaoshuo:xiaoshuo2026@localhost:1/xiaoshuo_test",
    ])
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    import pytest

    with pytest.raises(RuntimeError, match="未找到可用的测试数据库"):
        conf._resolve_test_db_url()

