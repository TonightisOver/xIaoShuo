import sys
import types
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

fernet_module = types.ModuleType("cryptography.fernet")
fernet_module.Fernet = Mock()
fernet_module.InvalidToken = RuntimeError
cryptography_module = types.ModuleType("cryptography")
cryptography_module.fernet = fernet_module
sys.modules.setdefault("cryptography", cryptography_module)
sys.modules.setdefault("cryptography.fernet", fernet_module)

def get_book_import_service():
    from src.api.services.book_import_service import get_book_import_service

    return get_book_import_service()


@pytest.fixture(autouse=True)
def clear_book_import_tasks():
    get_book_import_service().clear()


@pytest.fixture
async def client():
    from src.api.routes.book_import import router
    from src.core.auth_models import User
    from src.core.security.auth import get_current_user

    test_app = FastAPI()
    test_app.include_router(router)
    # 独立 app 不经 conftest 的 dependency_overrides；mock 一个固定用户让鉴权放行
    test_app.dependency_overrides[get_current_user] = lambda: User(
        id=1, username="test_user", hashed_password="x", is_admin=True
    )
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


def test_upload_and_parse_splits_chinese_and_english_chapters():
    text = "序言\n第1章 开端\n主角出现\nChapter 2 Crossroad\n新的冲突"

    chapters = get_book_import_service().upload_and_parse(text)

    assert len(chapters) == 3
    assert chapters[0]["title"] == "序章"
    assert chapters[1]["title"] == "第1章 开端"
    assert chapters[2]["title"] == "Chapter 2 Crossroad"
    assert "新的冲突" in chapters[2]["content"]


async def test_import_book_runs_background_analysis(client):
    llm = Mock()
    llm.generate = AsyncMock(return_value="""{
        "title": "雾城来信",
        "genre": "悬疑",
        "summary": "一封信引出旧案。",
        "characters": [{"name": "林舟", "personality": "冷静", "background": "记者"}],
        "worldview": {
            "background": "近未来城市",
            "rules": "线索交易",
            "geography": "雾城",
        },
        "foreshadows": [{"name": "旧信", "description": "开篇信件", "chapter": 1}],
        "writing_style": {
            "narrative_perspective": "第三人称",
            "language_features": "短句密集",
            "pacing_preference": "快节奏"
        }
    }""")

    with patch("src.api.routes.book_import.get_llm_client", return_value=llm):
        response = await client.post(
            "/api/v1/projects/import-book",
            files={"file": ("novel.txt", "第1章 开端\n林舟收到一封信。", "text/plain")},
        )

    assert response.status_code == 202
    task_id = response.json()["task_id"]
    status = await client.get(f"/api/v1/projects/import-book/{task_id}/status")

    assert status.status_code == 200
    data = status.json()
    assert data["status"] == "completed"
    assert data["analysis"]["title"] == "雾城来信"
    assert data["analysis"]["characters"][0]["name"] == "林舟"


async def test_apply_import_creates_project_from_analysis(client):
    service = get_book_import_service()
    task_id = service.create_task([
        {"index": 1, "title": "第1章", "content": "正文"}
    ], owner_id=1)
    service._tasks[task_id]["status"] = "completed"
    service._tasks[task_id]["analysis"] = {
        "title": "雾城来信",
        "genre": "悬疑",
        "summary": "一封信引出旧案。",
        "characters": [{"name": "林舟", "personality": "冷静", "background": "记者"}],
        "worldview": {
            "background": "近未来城市",
            "rules": "线索交易",
            "geography": "雾城",
        },
        "foreshadows": [{"name": "旧信", "description": "开篇信件", "chapter": 1}],
        "writing_style": {
            "narrative_perspective": "第三人称",
            "language_features": "短句密集",
            "pacing_preference": "快节奏",
        },
    }

    manager = Mock()
    manager.create_novel = AsyncMock(return_value="novel-created")
    manager.upsert_world_setting = AsyncMock()

    character_service = Mock()
    character_service.create_character = AsyncMock(return_value=101)

    with patch(
        "src.api.services.book_import_service.get_novel_manager",
        return_value=manager,
    ), patch(
        "src.api.services.book_import_service.get_character_service",
        return_value=character_service,
    ):
        response = await client.post(f"/api/v1/projects/import-book/{task_id}/apply")

    assert response.status_code == 200
    assert response.json()["novel_id"] == "novel-created"
    manager.create_novel.assert_awaited_once()
    create_kwargs = manager.create_novel.await_args.kwargs
    assert create_kwargs["title"] == "雾城来信"
    assert create_kwargs["novel_type"] == "悬疑"
    manager.upsert_world_setting.assert_awaited_once()
    character_service.create_character.assert_awaited_once()
