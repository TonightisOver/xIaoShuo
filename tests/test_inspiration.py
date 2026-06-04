from unittest.mock import AsyncMock, Mock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.main import app
from src.api.services.inspiration_service import get_inspiration_wizard


@pytest.fixture(autouse=True)
def clear_inspiration_sessions():
    get_inspiration_wizard().clear()


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_start_inspiration_session(client):
    response = await client.post("/api/v1/inspiration/start")

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"].startswith("inspiration-")
    assert data["step"] == "idea"
    assert data["next_step"] == "idea"
    assert data["options"]


async def test_process_step_sends_previous_context_to_llm(client):
    llm = Mock()
    llm.generate = AsyncMock(side_effect=["标题回复", "简介回复"])

    with patch("src.api.services.inspiration_service.get_llm_client", return_value=llm):
        start = await client.post("/api/v1/inspiration/start")
        session_id = start.json()["session_id"]

        first = await client.post(
            f"/api/v1/inspiration/{session_id}/step",
            json={"step": "idea", "user_input": "一个程序员发现梦境能编译现实"},
        )
        second = await client.post(
            f"/api/v1/inspiration/{session_id}/step",
            json={"step": "title", "user_input": "梦境编译器"},
        )

    assert first.status_code == 200
    assert first.json()["next_step"] == "title"
    assert first.json()["options"]
    assert second.status_code == 200
    assert second.json()["next_step"] == "description"

    second_prompt = llm.generate.call_args_list[1].args[0]
    assert "一个程序员发现梦境能编译现实" in second_prompt
    assert "梦境编译器" in second_prompt


async def test_generate_outline_stores_collected_data(client):
    llm = Mock()
    llm.generate = AsyncMock(return_value="大纲内容")

    with patch("src.api.services.inspiration_service.get_llm_client", return_value=llm):
        start = await client.post("/api/v1/inspiration/start")
        session_id = start.json()["session_id"]
        await client.post(
            f"/api/v1/inspiration/{session_id}/step",
            json={"step": "idea", "user_input": "主角能听见城市的心跳"},
        )
        response = await client.post(f"/api/v1/inspiration/{session_id}/generate")

    assert response.status_code == 200
    data = response.json()
    assert data["outline"] == "大纲内容"
    assert data["collected"]["idea"] == "主角能听见城市的心跳"
    prompt = llm.generate.call_args_list[-1].args[0]
    assert "主角能听见城市的心跳" in prompt


async def test_create_project_uses_novel_manager(client):
    manager = Mock()
    manager.create_novel = AsyncMock(return_value="novel-123")

    with patch(
        "src.api.services.inspiration_service.get_novel_manager",
        return_value=manager,
    ):
        start = await client.post("/api/v1/inspiration/start")
        session_id = start.json()["session_id"]
        wizard = get_inspiration_wizard()
        wizard._sessions[session_id]["collected"] = {
            "idea": "被放逐的将军在废土重建文明",
            "title": "废土王令",
            "genre": "科幻",
        }

        response = await client.post(f"/api/v1/inspiration/{session_id}/create")

    assert response.status_code == 200
    assert response.json()["novel_id"] == "novel-123"
    manager.create_novel.assert_awaited_once()
    kwargs = manager.create_novel.await_args.kwargs
    assert kwargs["title"] == "废土王令"
    assert kwargs["novel_type"] == "科幻"
