"""Task-backed 路由的持久化入队契约。"""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.api.models.requests import CreateNovelRequest, LongFormNovelRequest
from src.api.services.tasks.task_dispatcher import TaskType

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TASK_ROUTE_FILES = (
    PROJECT_ROOT / "src/api/routes/novels.py",
    PROJECT_ROOT / "src/api/routes/projects.py",
    PROJECT_ROOT / "src/api/routes/review.py",
)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_task_backed_routes_do_not_use_fastapi_background_tasks():
    for path in TASK_ROUTE_FILES:
        tree = _parse(path)
        background_annotations = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and node.id == "BackgroundTasks"
        ]
        add_task_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add_task"
        ]

        assert not background_annotations, f"{path.name} still uses BackgroundTasks"
        assert not add_task_calls, f"{path.name} still schedules add_task()"


def test_every_route_create_task_call_persists_queue_metadata():
    required = {"task_type", "task_payload", "max_attempts"}
    create_calls = []

    for path in TASK_ROUTE_FILES:
        for node in ast.walk(_parse(path)):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "create_task"
            ):
                create_calls.append((path, node))

    assert create_calls
    for path, call in create_calls:
        keywords = {keyword.arg for keyword in call.keywords}
        assert required <= keywords, (
            f"{path.name}:{call.lineno} missing queue metadata: "
            f"{sorted(required - keywords)}"
        )


@pytest.mark.asyncio
async def test_create_novel_persists_standard_generation_payload(monkeypatch):
    import src.api.routes.novels as novels_route

    request = CreateNovelRequest(
        idea="一个程序员穿越到修仙世界并重建宗门的故事",
        novel_type="玄幻",
        target_words=100000,
    )
    manager = SimpleNamespace(create_task=AsyncMock(return_value="task-1"))
    monkeypatch.setattr(novels_route, "get_task_manager", lambda: manager)

    response = await novels_route.create_novel(
        request,
        current_user=SimpleNamespace(id="user-1"),
    )

    assert response.task_id == "task-1"
    manager.create_task.assert_awaited_once_with(
        idea=request.idea,
        novel_type=request.novel_type,
        target_words=request.target_words,
        owner_id="user-1",
        task_type=TaskType.NOVEL_GENERATE.value,
        task_payload={"request": request.model_dump(mode="json")},
        max_attempts=1,
    )


@pytest.mark.asyncio
async def test_long_form_creates_novel_before_linked_queue_task(monkeypatch):
    import src.api.routes.novels as novels_route
    import src.api.services.content.novel_manager as novel_manager_module

    request = LongFormNovelRequest(
        idea="一个程序员穿越到修仙世界并写下百万字传奇的故事",
        novel_type="玄幻",
        target_words=1_000_000,
        volumes=10,
        chapters_per_volume=40,
        words_per_chapter=3000,
    )
    events: list[str] = []

    async def create_novel(**_kwargs):
        events.append("novel")
        return "novel-long"

    async def create_task(**_kwargs):
        events.append("task")
        return "task-long"

    novel_manager = SimpleNamespace(create_novel=AsyncMock(side_effect=create_novel))
    task_manager = SimpleNamespace(create_task=AsyncMock(side_effect=create_task))
    monkeypatch.setattr(
        novel_manager_module,
        "get_novel_manager",
        lambda: novel_manager,
    )
    monkeypatch.setattr(novels_route, "get_task_manager", lambda: task_manager)
    monkeypatch.setattr(
        novels_route,
        "calculate_long_form_chapter_plan",
        lambda _request: {"total_chapters": 400},
    )

    response = await novels_route.create_long_form_novel(
        request,
        current_user=SimpleNamespace(id="user-1"),
    )

    assert response.novel_id == "novel-long"
    assert events == ["novel", "task"]
    task_manager.create_task.assert_awaited_once_with(
        idea=request.idea,
        novel_type=request.novel_type,
        target_words=request.target_words,
        novel_id="novel-long",
        owner_id="user-1",
        task_type=TaskType.NOVEL_LONG_FORM.value,
        task_payload={
            "novel_id": "novel-long",
            "request": request.model_dump(mode="json"),
        },
        max_attempts=3,
        operation_id=f"novel-long:{TaskType.NOVEL_LONG_FORM.value}",
    )


@pytest.mark.asyncio
async def test_full_generate_persists_rebuilt_request_payload(monkeypatch):
    import src.api.routes.projects as projects_route

    request = projects_route.FullGenerateRequest(
        idea="一个程序员穿越到修仙世界并重建宗门的故事",
        novel_type="玄幻",
        target_words=120000,
        writing_style="简洁冷峻",
        writing_style_prompt="减少修饰语",
    )
    novel_manager = SimpleNamespace(
        create_novel=AsyncMock(return_value="novel-full"),
        update_novel=AsyncMock(return_value=True),
    )
    task_manager = SimpleNamespace(create_task=AsyncMock(return_value="task-full"))
    monkeypatch.setattr(projects_route, "get_novel_manager", lambda: novel_manager)
    monkeypatch.setattr(projects_route, "get_task_manager", lambda: task_manager)

    response = await projects_route.full_generate_project(
        request,
        current_user=SimpleNamespace(id="user-1"),
    )

    expected_request = CreateNovelRequest(
        idea=request.idea,
        novel_type=request.novel_type,
        target_words=request.target_words,
        writing_style=request.writing_style,
        writing_style_prompt=request.writing_style_prompt or "",
    )
    assert response["task_id"] == "task-full"
    task_manager.create_task.assert_awaited_once_with(
        idea=request.idea,
        novel_type=request.novel_type,
        target_words=request.target_words,
        novel_id="novel-full",
        owner_id="user-1",
        task_type=TaskType.NOVEL_FULL_GENERATE.value,
        task_payload={"request": expected_request.model_dump(mode="json")},
        max_attempts=1,
    )


def _project() -> dict[str, object]:
    return {
        "idea": "一个程序员穿越到修仙世界并重建宗门的故事",
        "novel_type": "玄幻",
        "target_words": 100000,
        "writing_style": "现代白话",
        "writing_style_prompt": "",
    }


def _idle_task_manager(task_id: str):
    return SimpleNamespace(
        expire_stale_tasks=AsyncMock(return_value=0),
        list_tasks=AsyncMock(return_value=([], 0)),
        create_task=AsyncMock(return_value=task_id),
    )


@pytest.mark.asyncio
async def test_generate_volume_persists_volume_payload(monkeypatch):
    import src.api.routes.projects as projects_route

    task_manager = _idle_task_manager("task-volume")
    volume_service = SimpleNamespace(
        get_volume=AsyncMock(return_value={"volume_number": 3}),
        update_volume=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        projects_route,
        "_get_project_and_verify_owner",
        AsyncMock(return_value=_project()),
    )
    monkeypatch.setattr(projects_route, "get_task_manager", lambda: task_manager)
    monkeypatch.setattr(projects_route, "get_volume_service", lambda: volume_service)

    response = await projects_route.generate_volume(
        "novel-1",
        projects_route.GenerateVolumeRequest(volume_number=3),
        current_user=SimpleNamespace(id="user-1"),
    )

    assert response["task_id"] == "task-volume"
    task_manager.create_task.assert_awaited_once_with(
        idea=_project()["idea"],
        novel_type=_project()["novel_type"],
        target_words=_project()["target_words"],
        novel_id="novel-1",
        owner_id="user-1",
        task_type=TaskType.NOVEL_VOLUME.value,
        task_payload={"novel_id": "novel-1", "volume_number": 3},
        max_attempts=3,
        operation_id="novel-1:volume:3",
    )


@pytest.mark.asyncio
async def test_generate_chapters_persists_range_payload(monkeypatch):
    import src.api.routes.projects as projects_route

    task_manager = _idle_task_manager("task-chapters")
    monkeypatch.setattr(
        projects_route,
        "_get_project_and_verify_owner",
        AsyncMock(return_value=_project()),
    )
    monkeypatch.setattr(projects_route, "get_task_manager", lambda: task_manager)

    response = await projects_route.generate_chapters(
        "novel-1",
        projects_route.GenerateChaptersRequest(chapter_start=11, chapter_end=20),
        current_user=SimpleNamespace(id="user-1"),
    )

    assert response["task_id"] == "task-chapters"
    task_manager.create_task.assert_awaited_once_with(
        idea=_project()["idea"],
        novel_type=_project()["novel_type"],
        target_words=_project()["target_words"],
        novel_id="novel-1",
        owner_id="user-1",
        task_type=TaskType.NOVEL_CHAPTERS.value,
        task_payload={
            "novel_id": "novel-1",
            "chapter_start": 11,
            "chapter_end": 20,
        },
        max_attempts=3,
        operation_id="novel-1:chapters:11-20",
    )


@pytest.mark.asyncio
async def test_review_requeues_same_task_for_pipeline_resume(monkeypatch):
    import src.api.routes.review as review_route

    manager = SimpleNamespace(
        get_task=AsyncMock(
            return_value={
                "task_id": "task-review",
                "status": "running",
                "owner_id": "user-1",
                "progress": {
                    "current_stage": "human_review",
                    "waiting_for_review": True,
                    "review_decision": "pending",
                },
            }
        ),
        set_review_decision=AsyncMock(),
        enqueue_existing_task=AsyncMock(return_value=True),
        fail_task=AsyncMock(),
    )
    monkeypatch.setattr(review_route, "get_task_manager", lambda: manager)
    monkeypatch.setattr(
        "src.api.services.tasks.task_manager.get_task_manager", lambda: manager
    )
    request = review_route.ReviewRequest(
        approval_status="revision",
        revision_instructions="加强主角冲突",
    )

    response = await review_route.submit_review(
        "task-review",
        request,
        current_user=SimpleNamespace(id="user-1"),
    )

    assert response.approval_status == "revision"
    manager.set_review_decision.assert_not_awaited()
    manager.enqueue_existing_task.assert_awaited_once_with(
        "task-review",
        task_type=TaskType.PIPELINE_RESUME.value,
        task_payload={
            "decision": {
                "approval_status": "revision",
                "revision_instructions": "加强主角冲突",
            }
        },
        max_attempts=1,
    )
    manager.fail_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_rejects_running_task_outside_human_review(monkeypatch):
    import src.api.routes.review as review_route

    manager = SimpleNamespace(
        get_task=AsyncMock(
            return_value={
                "task_id": "task-running",
                "status": "running",
                "owner_id": "user-1",
                "progress": {"current_stage": "chapter_generation"},
            }
        ),
        enqueue_existing_task=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(review_route, "get_task_manager", lambda: manager)
    monkeypatch.setattr(
        "src.api.services.tasks.task_manager.get_task_manager", lambda: manager
    )

    with pytest.raises(review_route.HTTPException) as exc_info:
        await review_route.submit_review(
            "task-running",
            review_route.ReviewRequest(approval_status="approved"),
            current_user=SimpleNamespace(id="user-1"),
        )

    assert exc_info.value.status_code == 400
    manager.enqueue_existing_task.assert_not_awaited()


@pytest.mark.asyncio
async def test_review_returns_conflict_when_locked_resume_precondition_fails(
    monkeypatch,
):
    import src.api.routes.review as review_route

    manager = SimpleNamespace(
        get_task=AsyncMock(
            return_value={
                "task_id": "task-review",
                "status": "running",
                "owner_id": "user-1",
                "progress": {
                    "current_stage": "human_review",
                    "waiting_for_review": True,
                    "review_decision": "pending",
                },
            }
        ),
        set_review_decision=AsyncMock(),
        enqueue_existing_task=AsyncMock(return_value=False),
        fail_task=AsyncMock(),
    )
    monkeypatch.setattr(review_route, "get_task_manager", lambda: manager)
    monkeypatch.setattr(
        "src.api.services.tasks.task_manager.get_task_manager", lambda: manager
    )

    with pytest.raises(review_route.HTTPException) as exc_info:
        await review_route.submit_review(
            "task-review",
            review_route.ReviewRequest(approval_status="approved"),
            current_user=SimpleNamespace(id="user-1"),
        )

    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_rejected_review_uses_atomic_cas(monkeypatch):
    import src.api.routes.review as review_route

    manager = SimpleNamespace(
        get_task=AsyncMock(
            return_value={
                "task_id": "task-review",
                "status": "running",
                "owner_id": "user-1",
                "progress": {
                    "current_stage": "human_review",
                    "waiting_for_review": True,
                    "review_decision": "pending",
                },
            }
        ),
        reject_review_task=AsyncMock(return_value=True),
    )
    monkeypatch.setattr(review_route, "get_task_manager", lambda: manager)
    monkeypatch.setattr(
        "src.api.services.tasks.task_manager.get_task_manager", lambda: manager
    )

    response = await review_route.submit_review(
        "task-review",
        review_route.ReviewRequest(
            approval_status="rejected",
            revision_instructions="主线方向错误",
        ),
        current_user=SimpleNamespace(id="user-1"),
    )

    assert response.approval_status == "rejected"
    manager.reject_review_task.assert_awaited_once_with(
        "task-review",
        instructions="主线方向错误",
    )


@pytest.mark.asyncio
async def test_rejected_review_returns_conflict_when_cas_fails(monkeypatch):
    import src.api.routes.review as review_route

    manager = SimpleNamespace(
        get_task=AsyncMock(
            return_value={
                "task_id": "task-review",
                "status": "running",
                "owner_id": "user-1",
                "progress": {
                    "current_stage": "human_review",
                    "waiting_for_review": True,
                    "review_decision": "pending",
                },
            }
        ),
        reject_review_task=AsyncMock(return_value=False),
    )
    monkeypatch.setattr(review_route, "get_task_manager", lambda: manager)
    monkeypatch.setattr(
        "src.api.services.tasks.task_manager.get_task_manager", lambda: manager
    )

    with pytest.raises(review_route.HTTPException) as exc_info:
        await review_route.submit_review(
            "task-review",
            review_route.ReviewRequest(
                approval_status="rejected",
                revision_instructions="主线方向错误",
            ),
            current_user=SimpleNamespace(id="user-1"),
        )

    assert exc_info.value.status_code == 409
