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
    """结构化输出：LLM 返回 {reply, suggestions}，上下文逐步累积传给 LLM。"""
    llm = Mock()
    llm.generate = AsyncMock(side_effect=[
        '{"reply": "好创意！我们来起个书名吧。", "suggestions": ["《梦境编译器》", "《现实调试员》", "《编译人生》"]}',
        '{"reply": "书名很棒！接下来写一句话简介。", "suggestions": ["程序员用代码改写梦境", "梦里的 bug 会变成现实", "他能调试所有人的梦"]}',
    ])

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
    first_data = first.json()
    assert first_data["next_step"] == "title"
    # LLM 生成的具体候选透出为 options
    assert first_data["options"] == ["《梦境编译器》", "《现实调试员》", "《编译人生》"]
    assert first_data["ai_reply"] == "好创意！我们来起个书名吧。"

    assert second.status_code == 200
    assert second.json()["next_step"] == "description"

    # 第二步的 prompt 应包含之前收集的全部上下文
    second_prompt = llm.generate.call_args_list[1].args[0]
    assert "一个程序员发现梦境能编译现实" in second_prompt
    assert "梦境编译器" in second_prompt


async def test_process_step_falls_back_on_malformed_llm_output(client):
    """LLM 返回非 JSON 时降级：静态建议 + 通用回复，服务不 500。"""
    llm = Mock()
    llm.generate = AsyncMock(return_value="这不是 JSON 格式的回复")

    with patch("src.api.services.inspiration_service.get_llm_client", return_value=llm):
        start = await client.post("/api/v1/inspiration/start")
        session_id = start.json()["session_id"]
        response = await client.post(
            f"/api/v1/inspiration/{session_id}/step",
            json={"step": "idea", "user_input": "主角能与旧物对话"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["next_step"] == "title"
    assert data["ai_reply"]  # 降级回复非空
    assert data["options"]   # 静态建议非空


async def test_genre_step_uses_fixed_type_list(client):
    """theme→genre 步骤：候选固定为标准类型表，不由 LLM 生成。"""
    llm = Mock()
    llm.generate = AsyncMock(return_value="很好，请选择类型。")

    with patch("src.api.services.inspiration_service.get_llm_client", return_value=llm):
        start = await client.post("/api/v1/inspiration/start")
        session_id = start.json()["session_id"]
        wizard = get_inspiration_wizard()
        wizard._sessions[session_id]["current_step"] = "theme"
        wizard._sessions[session_id]["collected"] = {
            "idea": "x", "title": "y", "description": "z",
        }

        response = await client.post(
            f"/api/v1/inspiration/{session_id}/step",
            json={"step": "theme", "user_input": "成长与代价"},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["next_step"] == "genre"
    assert "玄幻" in data["options"]
    assert "都市" in data["options"]


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
