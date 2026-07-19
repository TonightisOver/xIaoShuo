"""WebSocket 路由鉴权测试（Task 3）。

通过 Sec-WebSocket-Protocol 子协议传 session token：
- 无 token → 4401
- 无效 token → 4401
- 其他用户的 task → 4403
- task 不存在 → 4404
- owner → 连接成功收到 connected
"""

import secrets
from datetime import UTC, datetime

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from src.api.main import app
from src.api.models.db_models import Novel, Task
from src.core.auth_models import User
from src.core.database import Base, get_db_session, get_engine
from src.core.security.users import create_session, hash_password


async def _drop_all():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


async def _seed():
    suffix = secrets.token_hex(4)
    async with get_db_session() as session:
        a = User(username=f"ws_a_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        b = User(username=f"ws_b_{suffix}", hashed_password=hash_password("pass1234"), is_admin=False)
        session.add(a)
        session.add(b)
        await session.flush()
        a_id, b_id = a.id, b.id
        novel_id = f"ws-novel-{suffix}"
        task_id = f"ws-task-{suffix}"
        session.add(Novel(novel_id=novel_id, title="ws测试", idea="t",
                         novel_type="玄幻", target_words=10000, status="draft", owner_id=a_id))
        await session.flush()
        session.add(Task(task_id=task_id, novel_id=novel_id, owner_id=a_id,
                         status="pending", idea="t", novel_type="玄幻",
                         target_words=10000, created_at=datetime.now(UTC)))
    token_a = await create_session(a_id)
    token_b = await create_session(b_id)
    return {"task_id": task_id, "token_a": token_a, "token_b": token_b}


@pytest.fixture
def ws_client_seed():
    """启动 TestClient（lifespan 自动建表），在其 portal loop 内 seed 用户/task。

    单 fixture 供单个测试函数复用，避免多个 TestClient portal 复用全局 engine
    导致的跨 event loop 问题。
    """
    with TestClient(app) as client:
        seed = client.portal.call(_seed)
        yield client, seed
        client.portal.call(_drop_all)


def test_websocket_auth_matrix(ws_client_seed):
    """WebSocket 鉴权全矩阵（单 portal 内跑，避免跨 loop）：
    无 token→4401、无效 token→4401、跨用户→4403、task 不存在→4404、owner→connected。
    """
    client, seed = ws_client_seed
    task_id = seed["task_id"]
    token_a = seed["token_a"]
    token_b = seed["token_b"]

    # 无 token → 4401
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/tasks/{task_id}"):
            pass
    assert exc.value.code == 4401

    # 无效 token → 4401
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/tasks/{task_id}", subprotocols=["xiaoshuo", "invalid"]):
            pass
    assert exc.value.code == 4401

    # 跨用户 → 4403
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect(f"/ws/tasks/{task_id}", subprotocols=["xiaoshuo", token_b]):
            pass
    assert exc.value.code == 4403

    # task 不存在 → 4404
    with pytest.raises(WebSocketDisconnect) as exc:
        with client.websocket_connect("/ws/tasks/no-such-task", subprotocols=["xiaoshuo", token_a]):
            pass
    assert exc.value.code == 4404

    # owner → connected
    try:
        with client.websocket_connect(f"/ws/tasks/{task_id}", subprotocols=["xiaoshuo", token_a]) as ws:
            data = ws.receive_json()
            assert data["type"] == "connected"
            assert data["task_id"] == task_id
    except WebSocketDisconnect as exc:
        if exc.code != 1000:
            raise


# --- 事件总线单元测试（与鉴权无关，保留）---


def test_event_bus_publish_subscribe():
    """事件总线 publish/subscribe 基本功能"""
    import asyncio

    from src.api.services.generation.progress_event_bus import (
        EventType,
        ProgressEvent,
        get_event_bus,
    )

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
    from src.api.services.generation.progress_event_bus import get_event_bus

    event_bus = get_event_bus()
    task_id = "test-unsub"
    queue = event_bus.subscribe(task_id)
    event_bus.unsubscribe(task_id, queue)
    assert not event_bus.has_subscribers(task_id)
