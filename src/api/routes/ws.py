"""WebSocket route for real-time task progress."""

import asyncio
import logging
from datetime import datetime

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from src.api.services.progress_event_bus import EventType, get_event_bus
from src.api.services.task_manager import get_task_manager

logger = logging.getLogger(__name__)
router = APIRouter()

HEARTBEAT_INTERVAL = 30.0


@router.websocket("/ws/tasks/{task_id}")
async def task_progress_ws(websocket: WebSocket, task_id: str):
    task_manager = get_task_manager()
    task = await task_manager.get_task(task_id)

    if not task:
        await websocket.close(code=4004, reason="Task not found")
        return

    await websocket.accept()

    await websocket.send_json({
        "type": "connected",
        "task_id": task_id,
        "current_status": task["status"],
        "progress": task.get("progress"),
        "timestamp": datetime.now().isoformat(),
    })

    if task["status"] in ("completed", "failed"):
        await websocket.send_json({
            "type": task["status"],
            "task_id": task_id,
            "data": task.get("result") if task["status"] == "completed" else {"errors": task.get("errors", [])},
            "timestamp": datetime.now().isoformat(),
        })
        await websocket.close(code=1000)
        return

    event_bus = get_event_bus()
    queue = event_bus.subscribe(task_id)

    try:
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=HEARTBEAT_INTERVAL)
                await websocket.send_json({
                    "type": event.event_type.value,
                    "task_id": event.task_id,
                    "data": event.data,
                    "timestamp": event.timestamp.isoformat(),
                })
                if event.event_type == EventType.COMPLETED:
                    await websocket.close(code=1000)
                    break
                if event.event_type == EventType.ERROR and not event.data.get("non_blocking"):
                    await websocket.close(code=1000)
                    break
            except TimeoutError:
                await websocket.send_json({
                    "type": "heartbeat",
                    "timestamp": datetime.now().isoformat(),
                })
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for task {task_id}")
    except Exception as e:
        logger.error(f"WebSocket error for task {task_id}: {e}")
    finally:
        event_bus.unsubscribe(task_id, queue)
