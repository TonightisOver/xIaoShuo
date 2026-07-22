"""章节蓝图工作台路由契约测试。

直调路由 async 函数 + mock service，断言 HTTPException。
禁止真实调用 LLM。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes import chapters as chapters_mod


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
