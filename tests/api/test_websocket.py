"""WebSocket 路由测试"""

import asyncio

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.api.main import app
from src.api.services.progress_event_bus import (
    EventType,
    ProgressEvent,
    get_event_bus,
)


@pytest.fixture
def ws_client():
    with TestClient(app) as client:
        yield client


def test_websocket_reject_nonexistent_task(ws_client):
    """连接不存在的任务应被拒绝"""
    with pytest.raises(WebSocketDisconnect) as exc_info:
        with ws_client.websocket_connect("/ws/tasks/nonexistent-id"):
            pass
    assert exc_info.value.code == 4004


def test_websocket_connect_existing_task(ws_client):
    """连接已有任务应收到 connected 消息"""
    response = ws_client.post(
        "/api/v1/novels",
        json={
            "idea": "测试创意：一个程序员的修仙之路",
            "novel_type": "玄幻",
            "target_words": 50000,
        },
    )
    task_id = response.json()["task_id"]

    with ws_client.websocket_connect(f"/ws/tasks/{task_id}") as ws:
        data = ws.receive_json()
        assert data["type"] == "connected"
        assert data["task_id"] == task_id
        assert data["current_status"] in ("pending", "running", "completed", "failed")


def test_event_bus_publish_subscribe():
    """事件总线 publish/subscribe 基本功能"""
    event_bus = get_event_bus()
    task_id = "test-task-ws-pub"

    queue = event_bus.subscribe(task_id)

    async def _run():
        event = ProgressEvent(
            task_id=task_id,
            event_type=EventType.STAGE_COMPLETE,
            data={"stage": "idea_expansion", "percentage": 14},
        )
        await event_bus.publish(event)
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received.event_type == EventType.STAGE_COMPLETE
        assert received.data["stage"] == "idea_expansion"

    asyncio.run(_run())
    event_bus.unsubscribe(task_id, queue)


def test_event_bus_unsubscribe():
    """取消订阅后不再收到事件"""
    event_bus = get_event_bus()
    task_id = "test-unsub"

    queue = event_bus.subscribe(task_id)
    event_bus.unsubscribe(task_id, queue)

    assert not event_bus.has_subscribers(task_id)
