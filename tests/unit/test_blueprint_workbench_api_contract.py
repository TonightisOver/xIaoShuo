"""章节蓝图工作台路由契约测试。

直调路由 async 函数 + mock service，断言 HTTPException。
禁止真实调用 LLM。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.routes import chapters as chapters_mod
from src.core.exceptions import ArtifactConflictError


def _user():
    u = MagicMock()
    u.id = 1
    return u


@pytest.mark.asyncio
async def test_generate_blueprint_route_dispatches_background_task():
    """POST /chapters/{n}/blueprint/generate 改为投递后台 NOVEL_BLUEPRINT 任务,
    不再同步直写,返回 task_id + status=generating(URL 保留,行为异步)。"""
    novel = {"novel_id": "novel-1", "title": "T", "owner_id": 1}
    with (
        patch.object(chapters_mod, "verify_novel_owner", new=AsyncMock(return_value=novel)),
        patch.object(chapters_mod, "get_current_user", new=MagicMock()),
        patch("src.api.routes.chapters.verify_novel_owner", new=AsyncMock(return_value=novel)),
    ):
        # 路由内部应构造 ScopePlan 并 dispatch;mock dispatcher
        fake_dispatched = MagicMock()
        fake_dispatched.task_id = "task-1"
        fake_dispatched.task_ids = ["task-1"]
        fake_dispatched.task_type = "novel_blueprint"
        fake_dispatched.target_chapters = [5]
        fake_dispatched.accepted = [{"chapter_number": 5, "task_id": "task-1"}]
        fake_dispatched.skipped_locked = []
        fake_dispatched.skipped_confirmed = []
        fake_dispatched.already_generating = []
        fake_dispatched.failed_to_enqueue = []
        with (
            patch("src.api.services.creative_control.generation_dispatch.CreativeGenerationDispatcher") as disp_cls,
            patch("src.api.routes.chapters.get_novel_manager") as mgr,
            patch("src.core.database.get_db_session") as dbctx,
        ):
            disp_cls.return_value.dispatch_scope = AsyncMock(return_value=fake_dispatched)
            mgr.return_value.get_novel = AsyncMock(return_value=novel)
            # mock 一个 async context manager 返回带 outline 的 session
            session = AsyncMock()
            res = MagicMock()
            res.scalar_one_or_none.return_value = MagicMock(content={"chapter": 5})
            session.execute = AsyncMock(return_value=res)

            class _Ctx:
                async def __aenter__(self):
                    return session

                async def __aexit__(self, *a):
                    return False

            dbctx.return_value = _Ctx()
            result = await chapters_mod.generate_blueprint("novel-1", 5, _user())

    assert result["status"] == "generating"
    assert result["task_id"] == "task-1"
    assert result["task_type"] == "novel_blueprint"


@pytest.mark.asyncio
async def test_list_blueprints_route_returns_summaries():
    from src.api.routes import blueprint_workbench as wb

    novel = {"novel_id": "novel-1", "owner_id": 1}
    fake_service = MagicMock()
    fake_service.list_chapter_summaries = AsyncMock(return_value={
        "items": [{"chapter_number": 1, "has_blueprint": False, "control_status": "not_generated"}],
        "total": 1, "page": 1, "page_size": 50, "status_counts": {"not_generated": 1},
    })
    with (
        patch("src.api.routes.blueprint_workbench.verify_novel_owner", new=AsyncMock(return_value=novel)),
        patch("src.api.routes.blueprint_workbench.BlueprintWorkbenchService", return_value=fake_service),
    ):
        result = await wb.list_blueprints("novel-1", _user())
    assert result["total"] == 1
    assert result["items"][0]["control_status"] == "not_generated"


@pytest.mark.asyncio
async def test_list_blueprints_route_owner_check_404():
    from src.api.routes import blueprint_workbench as wb

    async def _deny(*a, **kw):
        raise HTTPException(status_code=404, detail="Novel not found")

    with patch("src.api.routes.blueprint_workbench.verify_novel_owner", new=_deny):
        with pytest.raises(HTTPException) as exc:
            await wb.list_blueprints("missing", _user())
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_workspace_route_aggregates():
    from src.api.routes import blueprint_workbench as wb

    novel = {"novel_id": "novel-1", "owner_id": 1}
    fake_service = MagicMock()
    fake_service.get_workspace = AsyncMock(return_value={
        "blueprint": {"chapter_type": "climax"}, "control": {"version": 1},
        "versions": [], "outline": None, "previous_state_delta": None,
        "chapter_summary": None, "quality_status": None, "available_characters": [],
    })
    with (
        patch("src.api.routes.blueprint_workbench.verify_novel_owner", new=AsyncMock(return_value=novel)),
        patch("src.api.routes.blueprint_workbench.BlueprintWorkbenchService", return_value=fake_service),
    ):
        result = await wb.get_workspace_route("novel-1", 5, _user())
    assert result["blueprint"]["chapter_type"] == "climax"


@pytest.mark.asyncio
async def test_options_route_returns_enums():
    from src.api.routes import blueprint_workbench as wb

    novel = {"novel_id": "novel-1", "owner_id": 1}
    fake_service = MagicMock()
    fake_service.get_options = MagicMock(return_value={
        "chapter_type": ["main_advance", "climax"],
        "pacing_target": ["fast", "medium", "slow"],
        "foreshadow_action": ["plant", "callback", "advance"],
    })
    with (
        patch("src.api.routes.blueprint_workbench.verify_novel_owner", new=AsyncMock(return_value=novel)),
        patch("src.api.routes.blueprint_workbench.BlueprintWorkbenchService", return_value=fake_service),
    ):
        result = await wb.get_options("novel-1", _user())
    assert "main_advance" in result["chapter_type"]


@pytest.mark.asyncio
async def test_batch_lock_returns_per_chapter_results():
    from src.api.routes import blueprint_workbench as wb
    from src.api.models.creative_control import LockRequest  # noqa: F401  (确保模型已 import)

    novel = {"novel_id": "novel-1", "owner_id": 1}
    fake_control = MagicMock()
    fake_control.lock = AsyncMock(side_effect=[3, ArtifactConflictError("novel-1", "blueprint", "13", 1, 2)])
    # 构造 batch 请求体 dict（路由用 pydantic 模型解析）
    with (
        patch("src.api.routes.blueprint_workbench.verify_novel_owner", new=AsyncMock(return_value=novel)),
        patch("src.api.routes.blueprint_workbench.CreativeControlService", return_value=fake_control),
    ):
        body = wb.BatchControlRequest(
            action="lock", artifact_type="blueprint",
            chapter_numbers=[12, 13], expected_versions={"12": 2, "13": 1},
        )
        result = await wb.batch_control("novel-1", body, _user())
    assert len(result["results"]) == 2
    by_ch = {r["chapter_number"]: r for r in result["results"]}
    assert by_ch[12]["status"] == "ok"
    assert by_ch[13]["status"] == "conflict"
    assert by_ch[13]["current_version"] == 2


@pytest.mark.asyncio
async def test_batch_rejects_over_50():
    from src.api.routes import blueprint_workbench as wb

    novel = {"novel_id": "novel-1", "owner_id": 1}
    with patch("src.api.routes.blueprint_workbench.verify_novel_owner", new=AsyncMock(return_value=novel)):
        with pytest.raises(HTTPException) as exc:
            body = wb.BatchControlRequest(
                action="lock", artifact_type="blueprint",
                chapter_numbers=list(range(1, 52)), expected_versions={},
            )
            await wb.batch_control("novel-1", body, _user())
    assert exc.value.status_code == 422
