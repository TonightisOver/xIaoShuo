"""Progress event bus for real-time task updates.

In-process pub/sub using asyncio.Queue — one queue per subscriber.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    STAGE_START = "stage_start"
    STAGE_COMPLETE = "stage_complete"
    CHAPTER_PROGRESS = "chapter_progress"
    SUB_FEATURE_START = "sub_feature_start"
    SUB_FEATURE_COMPLETE = "sub_feature_complete"
    ERROR = "error"
    COMPLETED = "completed"


@dataclass
class ProgressEvent:
    task_id: str
    event_type: EventType
    data: dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)


class ProgressEventBus:

    def __init__(self):
        self._subscribers: dict[str, list[asyncio.Queue[ProgressEvent]]] = {}

    def subscribe(self, task_id: str) -> asyncio.Queue[ProgressEvent]:
        queue: asyncio.Queue[ProgressEvent] = asyncio.Queue()
        self._subscribers.setdefault(task_id, []).append(queue)
        return queue

    def unsubscribe(self, task_id: str, queue: asyncio.Queue[ProgressEvent]) -> None:
        if task_id in self._subscribers:
            self._subscribers[task_id] = [
                q for q in self._subscribers[task_id] if q is not queue
            ]
            if not self._subscribers[task_id]:
                del self._subscribers[task_id]

    async def publish(self, event: ProgressEvent) -> None:
        for queue in self._subscribers.get(event.task_id, []):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def has_subscribers(self, task_id: str) -> bool:
        return bool(self._subscribers.get(task_id))


_event_bus: ProgressEventBus | None = None


def get_event_bus() -> ProgressEventBus:
    global _event_bus
    if _event_bus is None:
        _event_bus = ProgressEventBus()
    return _event_bus


# Callback registry for chapter-level progress (keyed by task_id)
_progress_callbacks: dict[str, Any] = {}


def register_progress_callback(task_id: str, callback: Any) -> None:
    _progress_callbacks[task_id] = callback


def get_progress_callback(task_id: str) -> Any | None:
    return _progress_callbacks.get(task_id)


def unregister_progress_callback(task_id: str) -> None:
    _progress_callbacks.pop(task_id, None)
