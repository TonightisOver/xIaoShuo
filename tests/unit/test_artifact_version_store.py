"""ArtifactVersionStore 单元测试。

覆盖非正文产物的版本快照：save_version（旧 active 置 false + 新 active 插入）、
list_versions、compare_versions、rollback_to、蓝图复用 is_active+version_number。
"""

from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.creative_control.artifact_version_store import ArtifactVersionStore


def _version_row(
    *, version_number=1, is_active=True, artifact_id="w1",
    content_snapshot=None, source="generation",
):
    return SimpleNamespace(
        id=version_number,
        novel_id="novel-1",
        artifact_type="world",
        artifact_id=artifact_id,
        version_number=version_number,
        content_snapshot=content_snapshot or {"rules": f"v{version_number}"},
        source=source,
        model=None,
        operator_id=None,
        task_id=None,
        operation_id=None,
        is_active=is_active,
        created_at=None,
    )


def _session_with(rows, *, old_active=None, scalar_result=None):
    """mock session：execute 返回可控结果。"""
    session = AsyncMock()
    # 第一个 execute：select active -> 返回 old_active（或 None）
    # 第二个 execute：select versions list -> 返回 rows
    active_result = MagicMock()
    active_result.scalar_one_or_none.return_value = old_active
    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = rows
    single_result = MagicMock()
    single_result.scalar_one_or_none.return_value = scalar_result

    session.execute = AsyncMock(
        side_effect=[active_result, list_result] if scalar_result is None
        else [active_result, single_result, list_result]
    )
    session.flush = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session

    return fake_session, session


# ---------------------------------------------------------------- save_version


@pytest.mark.asyncio
async def test_save_version_deactivates_old_and_inserts_new():
    old_active = _version_row(version_number=1, is_active=True)
    fake_session, session = _make_session([_result_with(old_active, scalar=True)])
    store = ArtifactVersionStore()
    with patch(
        "src.core.creative_control.artifact_version_store.get_db_session",
        new=fake_session,
    ):
        vn = await store.save_version(
            "novel-1", "world", "w1",
            content_snapshot={"rules": "v2"},
            source="generation", model="deepseek",
        )
    assert vn == 2
    assert old_active.is_active is False
    added = session.add.call_args_list[-1].args[0]
    assert added.version_number == 2
    assert added.is_active is True


@pytest.mark.asyncio
async def test_save_version_first_version_is_one():
    fake_session, _ = _make_session([_result_with(None, scalar=True)])
    store = ArtifactVersionStore()
    with patch(
        "src.core.creative_control.artifact_version_store.get_db_session",
        new=fake_session,
    ):
        vn = await store.save_version(
            "novel-1", "world", "w1",
            content_snapshot={"rules": "v1"},
            source="manual",
        )
    assert vn == 1


# ---------------------------------------------------------------- list/get


@pytest.mark.asyncio
async def test_list_versions_desc_by_number():
    rows = [
        _version_row(version_number=3, is_active=True),
        _version_row(version_number=1, is_active=False),
        _version_row(version_number=2, is_active=False),
    ]
    fake_session, _ = _make_session([_result_with(rows, is_list=True)])
    store = ArtifactVersionStore()
    with patch(
        "src.core.creative_control.artifact_version_store.get_db_session",
        new=fake_session,
    ):
        result = await store.list_versions("novel-1", "world", "w1")
    numbers = [r["version_number"] for r in result]
    assert numbers == [3, 2, 1]


def _make_session(execute_results):
    """execute 按顺序返回 execute_results 中的 MagicMock；add/flush 可调用。"""
    session = AsyncMock()
    session.execute = AsyncMock(side_effect=list(execute_results))
    session.add = MagicMock()  # 同步 mock，避免协程警告
    session.flush = AsyncMock()

    @asynccontextmanager
    async def fake_session():
        yield session

    return fake_session, session


def _result_with(rows_or_scalar, *, scalar=False, is_list=False):
    r = MagicMock()
    if scalar:
        r.scalar_one_or_none.return_value = rows_or_scalar
    if is_list:
        r.scalars.return_value.all.return_value = rows_or_scalar
    return r


@pytest.mark.asyncio
async def test_get_version_returns_snapshot():
    row = _version_row(version_number=2, content_snapshot={"rules": "v2"})
    fake_session, _ = _make_session([_result_with(row, scalar=True)])
    store = ArtifactVersionStore()
    with patch(
        "src.core.creative_control.artifact_version_store.get_db_session",
        new=fake_session,
    ):
        result = await store.get_version("novel-1", "world", "w1", 2)
    assert result is not None
    assert result["version_number"] == 2
    assert result["content_snapshot"] == {"rules": "v2"}


# ---------------------------------------------------------------- compare


@pytest.mark.asyncio
async def test_compare_versions_returns_field_diff():
    row_a = _version_row(version_number=1, content_snapshot={"rules": "a", "geo": "x"})
    row_b = _version_row(version_number=2, content_snapshot={"rules": "b", "geo": "x"})
    # get_version 被调两次，每次开一个 session、1 次 execute
    fake_session, _ = _make_session([
        _result_with(row_a, scalar=True),
        _result_with(row_b, scalar=True),
    ])
    store = ArtifactVersionStore()
    with patch(
        "src.core.creative_control.artifact_version_store.get_db_session",
        new=fake_session,
    ):
        diff = await store.compare_versions("novel-1", "world", "w1", 1, 2)
    assert diff["changed"] == ["rules"]
    assert diff["unchanged"] == ["geo"]


# ---------------------------------------------------------------- rollback


@pytest.mark.asyncio
async def test_rollback_to_restores_content_and_activates(monkeypatch):
    target = _version_row(
        version_number=2, is_active=False,
        content_snapshot={"rules": "v2-rolled"},
    )
    restored: dict = {}

    async def fake_restore(novel_id, artifact_type, artifact_id, content):
        restored["content"] = content

    # rollback_to 先调 get_version（1 个 session/1 execute），
    # 再开自己的 session（select target for update + select actives，2 execute）
    fake_session, session = _make_session([
        _result_with(target, scalar=True),   # get_version
        _result_with(target, scalar=True),   # select target for update
        _result_with([], is_list=True),      # select actives（空，无其他 active）
    ])
    session.add = MagicMock()

    store = ArtifactVersionStore()
    monkeypatch.setattr(store, "_restore_content_to_product", fake_restore)
    with patch(
        "src.core.creative_control.artifact_version_store.get_db_session",
        new=fake_session,
    ):
        result = await store.rollback_to("novel-1", "world", "w1", 2, operator_id=7)

    assert restored["content"] == {"rules": "v2-rolled"}
    assert target.is_active is True
    assert result["activated_version"] == 2
