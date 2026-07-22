"""Creative Control API 契约测试。

直接调路由函数 + patch core 服务，验证 owner 校验、409 映射、422 校验。
不连真实 DB / 不起 httpx app。
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from src.api.models.creative_control import (
    EditArtifactRequest,
    GenerateScopeRequest,
    LockRequest,
    RegenerateRequest,
    SetModeRequest,
    SetStatusRequest,
)
from src.api.routes.creative_control import (
    approve_artifact,
    edit_artifact,
    get_artifact,
    get_impact,
    get_stage,
    list_operations,
    lock_artifact,
    mark_stale,
    plan_generate_scope,
    preview_generate_scope,
    regenerate_artifact,
    rollback_version,
    set_creation_mode,
)
from src.core.exceptions import (
    ArtifactBusyError,
    ArtifactConflictError,
    ArtifactLockedError,
)


def _user():
    return SimpleNamespace(id=7)


def _ol():
    """返回 patch 对象；在 with 块内用 `as ol` 拿到 mock 后调 _cfg(ol)。"""
    return patch("src.api.routes.creative_control.OperationLogService")


def _cfg(ol):
    ol.return_value.record = AsyncMock(return_value={"id": 1})
    ol.return_value.list = AsyncMock(return_value=[])


# ----------------------------------------------------------- owner 校验


@pytest.mark.asyncio
async def test_get_stage_verifies_owner():
    user = _user()
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()) as verify, \
         patch("src.api.routes.creative_control.get_novel_manager") as gm, \
         patch("src.api.routes.creative_control.CreativeControlService") as cs, \
         patch("src.api.routes.creative_control.ArtifactAdapterRegistry") as adapters:
        gm.return_value.get_novel = AsyncMock(return_value={"creation_mode": "auto", "creative_stage": 1})
        cs.return_value.get_or_create = AsyncMock(return_value={"control_status": "generated", "version": 1})
        adapters.return_value.list_artifacts = AsyncMock(
            side_effect=lambda _novel_id, artifact_type: (
                [{"artifact_id": "42", "label": "林舟"}]
                if artifact_type == "character"
                else []
            )
        )
        result = await get_stage("novel-1", current_user=user)
    verify.assert_awaited_once_with("novel-1", user)
    assert result["creation_mode"] == "auto"
    assert len(result["stages"]) == 10
    character_stage = next(
        stage for stage in result["stages"] if stage["artifact_type"] == "character"
    )
    assert character_stage["artifacts"][0]["artifact_id"] == "42"


@pytest.mark.asyncio
async def test_get_artifact_returns_real_content():
    user = _user()
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.CreativeControlService") as cs, \
         patch("src.api.routes.creative_control.ArtifactVersionStore") as vs, \
         patch("src.api.routes.creative_control.ArtifactAdapterRegistry") as adapters:
        cs.return_value.get_or_create = AsyncMock(
            return_value={"control_status": "generated", "version": 1}
        )
        vs.return_value.list_versions = AsyncMock(return_value=[])
        adapters.return_value.load = AsyncMock(
            return_value={"name": "林舟", "role": "主角"}
        )
        result = await get_artifact(
            "novel-1", "character", "42", current_user=user
        )

    assert result["content"]["name"] == "林舟"


# ----------------------------------------------------------- edit 409


@pytest.mark.asyncio
async def test_edit_returns_409_on_stale_version():
    user = _user()
    req = EditArtifactRequest(content={"rules": "x"}, expected_version=1)
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.CreativeArtifactWriteService") as writes:
        writes.return_value.edit_artifact = AsyncMock(
            side_effect=ArtifactConflictError("novel-1", "world", "w1", 1, 3)
        )
        with pytest.raises(HTTPException) as exc:
            await edit_artifact("novel-1", "world", "w1", req, current_user=user)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "stale_version"
    assert exc.value.detail["current_version"] == 3


@pytest.mark.asyncio
async def test_edit_returns_409_on_locked():
    user = _user()
    req = EditArtifactRequest(content={"rules": "x"}, expected_version=1)
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.CreativeArtifactWriteService") as writes:
        writes.return_value.edit_artifact = AsyncMock(
            side_effect=ArtifactLockedError("novel-1", "world", "w1")
        )
        with pytest.raises(HTTPException) as exc:
            await edit_artifact("novel-1", "world", "w1", req, current_user=user)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "locked"


@pytest.mark.asyncio
async def test_edit_success_returns_edited():
    user = _user()
    req = EditArtifactRequest(content={"rules": "x"}, expected_version=1)
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.CreativeArtifactWriteService") as writes, \
         _ol() as ol:
        _cfg(ol)
        writes.return_value.edit_artifact = AsyncMock(
            return_value=SimpleNamespace(control_version=2, artifact_version=3)
        )
        result = await edit_artifact("novel-1", "world", "w1", req, current_user=user)
    assert result["status"] == "edited"
    assert result["version"] == 2
    assert result["artifact_version"] == 3


@pytest.mark.asyncio
async def test_edit_chapter_creates_version_and_marks_unverified():
    """手动编辑正文：建 ChapterVersion（激活）+ 置 quality_status=unverified +
    control -> edited + op_log。验收 §8：旧质量分数不当作新正文的当前分数。"""
    user = _user()
    req = EditArtifactRequest(
        content="修改后的正文纯文本",
        expected_version=3,
        expected_active_version=4,
    )
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.CreativeArtifactWriteService") as writes, \
         _ol() as ol:
        _cfg(ol)
        writes.return_value.edit_artifact = AsyncMock(
            return_value=SimpleNamespace(control_version=4, artifact_version=5)
        )
        result = await edit_artifact("novel-1", "chapter", "7", req, current_user=user)

    kwargs = writes.return_value.edit_artifact.await_args.kwargs
    assert kwargs["expected_active_version"] == 4
    assert kwargs["content"] == "修改后的正文纯文本"
    # control service 是唯一审计写入者，路由不重复记录
    ol.return_value.record.assert_not_awaited()
    assert result["status"] == "edited"
    assert result["version"] == 4
    assert result["artifact_version"] == 5


@pytest.mark.asyncio
async def test_edit_chapter_conflict_maps_409():
    """正文编辑遇到过期版本（create_chapter_version 抛 ArtifactConflictError）映射 409。"""
    from src.core.exceptions import ArtifactConflictError

    user = _user()
    req = EditArtifactRequest(
        content="正文", expected_version=2, expected_active_version=1
    )
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.CreativeArtifactWriteService") as writes, \
         _ol() as ol:
        _cfg(ol)
        writes.return_value.edit_artifact = AsyncMock(
            side_effect=ArtifactConflictError("novel-1", "chapter", "7", 2, 4)
        )
        with pytest.raises(HTTPException) as exc:
            await edit_artifact("novel-1", "chapter", "7", req, current_user=user)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "stale_version"


@pytest.mark.asyncio
async def test_edit_chapter_non_numeric_id_maps_422():
    """正文 artifact_id 语义为 chapter_number；非数字应 422 而非 500。"""
    user = _user()
    req = EditArtifactRequest(content="正文", expected_version=0)
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.CreativeArtifactWriteService") as writes, \
         _ol() as ol:
        _cfg(ol)
        writes.return_value.edit_artifact = AsyncMock(
            side_effect=ValueError("invalid artifact id")
        )
        with pytest.raises(HTTPException) as exc:
            await edit_artifact("novel-1", "chapter", "abc", req, current_user=user)
    assert exc.value.status_code == 422


# ----------------------------------------------------------- lock/approve


@pytest.mark.asyncio
async def test_lock_returns_409_on_illegal_state():
    user = _user()
    req = LockRequest(expected_version=1)
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.CreativeControlService") as cs, \
         _ol() as ol:
        _cfg(ol)
        cs.return_value.lock = AsyncMock(
            side_effect=ValueError("lock requires approved status, got generated")
        )
        with pytest.raises(HTTPException) as exc:
            await lock_artifact("novel-1", "world", "w1", req, current_user=user)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "illegal_state"


@pytest.mark.asyncio
async def test_approve_success():
    user = _user()
    req = LockRequest(expected_version=1)
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.CreativeControlService") as cs, \
         _ol() as ol:
        _cfg(ol)
        cs.return_value.approve = AsyncMock(return_value=2)
        result = await approve_artifact("novel-1", "world", "w1", req, current_user=user)
    assert result == {"status": "approved", "version": 2}


# ----------------------------------------------------------- regenerate


@pytest.mark.asyncio
async def test_regenerate_returns_409_on_busy():
    user = _user()
    req = RegenerateRequest(expected_version=1)
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.CreativeControlService") as cs, \
         _ol() as ol:
        _cfg(ol)
        cs.return_value.assert_writable = AsyncMock(
            side_effect=ArtifactBusyError("novel-1", "chapter", "5")
        )
        with pytest.raises(HTTPException) as exc:
            await regenerate_artifact("novel-1", "chapter", "5", req, current_user=user)
    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "busy"


@pytest.mark.asyncio
async def test_regenerate_chapter_dispatches_persistent_task():
    user = _user()
    req = RegenerateRequest(expected_version=1)
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.CreativeControlService") as cs, \
         patch("src.api.routes.creative_control.get_novel_manager") as manager, \
         patch("src.api.routes.creative_control.CreativeGenerationDispatcher") as dispatcher, \
         _ol() as ol:
        _cfg(ol)
        cs.return_value.assert_writable = AsyncMock()
        cs.return_value.begin_generating = AsyncMock(return_value=2)
        manager.return_value.get_novel = AsyncMock(
            return_value={
                "novel_id": "novel-1",
                "idea": "测试创意",
                "novel_type": "玄幻",
                "target_words": 100000,
            }
        )
        dispatcher.return_value.dispatch_scope = AsyncMock(
            return_value=SimpleNamespace(
                task_id="task-7",
                task_type="novel.chapters",
                target_chapters=[7],
                skipped_locked=[],
                skipped_confirmed=[],
            )
        )
        result = await regenerate_artifact(
            "novel-1", "chapter", "7", req, current_user=user
        )

    assert result["task_id"] == "task-7"
    assert result["status"] == "generating"


@pytest.mark.asyncio
async def test_unsupported_regenerate_does_not_change_control_status():
    user = _user()
    req = RegenerateRequest(expected_version=1)
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.CreativeControlService") as cs:
        with pytest.raises(HTTPException) as exc:
            await regenerate_artifact(
                "novel-1", "world", "novel-1", req, current_user=user
            )

    assert exc.value.status_code == 422
    cs.return_value.begin_generating.assert_not_called()


# ----------------------------------------------------------- impact / stale / versions


@pytest.mark.asyncio
async def test_get_impact_returns_analysis():
    user = _user()
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.ImpactAnalyzer") as ia:
        ia.return_value.analyze = AsyncMock(
            return_value={"regenerable": [{"artifact_type": "character"}], "to_mark_stale": []}
        )
        result = await get_impact("novel-1", "world", "w1", current_user=user)
    assert result["regenerable"][0]["artifact_type"] == "character"


@pytest.mark.asyncio
async def test_mark_stale_returns_split():
    user = _user()
    req = SetStatusRequest(expected_version=1, reason="world changed")
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.CreativeControlService") as cs, \
         _ol() as ol:
        _cfg(ol)
        cs.return_value.mark_stale = AsyncMock(
            return_value={"upstream": {}, "regenerable": [], "to_mark_stale": []}
        )
        result = await mark_stale("novel-1", "world", "w1", req, current_user=user)
    assert "regenerable" in result
    assert "to_mark_stale" in result


@pytest.mark.asyncio
async def test_rollback_returns_404_on_missing_version():
    user = _user()
    req = LockRequest(expected_version=1)
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.CreativeArtifactWriteService") as writes:
        writes.return_value.rollback_artifact = AsyncMock(
            side_effect=ValueError("version not found: 99")
        )
        with pytest.raises(HTTPException) as exc:
            await rollback_version("novel-1", "world", "w1", 99, req, current_user=user)
    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_list_operations_passes_filters():
    user = _user()
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.OperationLogService") as ol:
        ol.return_value.list = AsyncMock(return_value=[{"action": "edit"}])
        result = await list_operations(
            "novel-1", artifact_type="world", action="edit", limit=50,
            current_user=user,
        )
    assert result == [{"action": "edit"}]
    ol.return_value.list.assert_awaited_once_with(
        "novel-1", artifact_type="world", action="edit", limit=50
    )


# ----------------------------------------------------------- generate-scope


@pytest.mark.asyncio
async def test_preview_generate_scope():
    user = _user()
    req = GenerateScopeRequest(mode="volume", volume_number=2)
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.GenerationScopePlanner") as gp:
        from src.core.creative_control.scope_planner import ScopePreview
        gp.return_value.preview = AsyncMock(return_value=ScopePreview(
            estimated_chapters=4, estimated_tokens=18000.0,
            target_chapters=[10, 11, 12, 13],
            skipped_locked=[], skipped_confirmed=[],
            impact={"regenerable": [], "to_mark_stale": []},
        ))
        result = await preview_generate_scope("novel-1", req, current_user=user)
    assert result["estimated_chapters"] == 4
    assert result["estimated_tokens"] == 18000.0
    assert result["target_chapters"] == [10, 11, 12, 13]


@pytest.mark.asyncio
async def test_plan_generate_scope():
    user = _user()
    req = GenerateScopeRequest(mode="chapters", chapter_start=1, chapter_end=3)
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.GenerationScopePlanner") as gp, \
         patch("src.api.routes.creative_control.get_novel_manager") as manager, \
         patch("src.api.routes.creative_control.CreativeGenerationDispatcher") as dispatcher:
        from src.core.creative_control.scope_planner import ScopePlan
        gp.return_value.plan = AsyncMock(return_value=ScopePlan(
            endpoint="generate-chapters",
            payload={"chapter_start": 1, "chapter_end": 3},
            target_chapters=[1, 2, 3], skipped_locked=[], skipped_confirmed=[],
        ))
        manager.return_value.get_novel = AsyncMock(
            return_value={
                "novel_id": "novel-1",
                "idea": "测试创意",
                "novel_type": "玄幻",
                "target_words": 100000,
            }
        )
        dispatcher.return_value.dispatch_scope = AsyncMock(
            return_value=SimpleNamespace(
                task_id="task-1",
                task_type="novel.chapters",
                target_chapters=[1, 2, 3],
                skipped_locked=[],
                skipped_confirmed=[],
            )
        )
        result = await plan_generate_scope("novel-1", req, current_user=user)
    assert result["task_id"] == "task-1"
    assert result["task_type"] == "novel.chapters"
    dispatcher.return_value.dispatch_scope.assert_awaited_once()


# ----------------------------------------------------------- mode


@pytest.mark.asyncio
async def test_set_creation_mode():
    user = _user()
    req = SetModeRequest(creation_mode="assisted")
    with patch("src.api.routes.creative_control.verify_novel_owner", new=AsyncMock()), \
         patch("src.api.routes.creative_control.get_novel_manager") as gm, \
         _ol() as ol:
        _cfg(ol)
        gm.return_value.update_novel = AsyncMock(return_value=None)
        result = await set_creation_mode("novel-1", req, current_user=user)
    assert result == {"status": "updated", "creation_mode": "assisted"}
    gm.return_value.update_novel.assert_awaited_once_with("novel-1", creation_mode="assisted")


def test_request_models_reject_invalid_values():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        GenerateScopeRequest(mode="invalid_mode")
    with pytest.raises(ValidationError):
        SetModeRequest(creation_mode="turbo")
    with pytest.raises(ValidationError):
        EditArtifactRequest(content={}, expected_version=-1)
    with pytest.raises(ValidationError):
        GenerateScopeRequest(mode="chapters", chapter_start=2)
    with pytest.raises(ValidationError):
        GenerateScopeRequest(mode="blueprint_only")
    with pytest.raises(ValidationError):
        GenerateScopeRequest(mode="volume")
