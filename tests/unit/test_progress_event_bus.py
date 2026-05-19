"""进度事件总线单元测试（CHANGE-027）

覆盖：
- register_progress_callback / unregister_progress_callback
- get_progress_callback
- ProgressEventBus.subscribe / unsubscribe / publish / has_subscribers
"""

import asyncio

import pytest

from src.api.services.progress_event_bus import (
    EventType,
    ProgressEvent,
    ProgressEventBus,
    get_progress_callback,
    register_progress_callback,
    unregister_progress_callback,
)


# ============================================================
#  回调注册 / 注销
# ============================================================

class TestProgressCallbackRegistry:
    """测试回调注册表的增删查"""

    def setup_method(self):
        """每个测试前清理全局注册表"""
        from src.api.services import progress_event_bus
        progress_event_bus._progress_callbacks.clear()

    def test_register_and_get(self):
        """注册后可以通过 get 取回"""
        async def my_callback(data):
            pass

        register_progress_callback("task-1", my_callback)
        result = get_progress_callback("task-1")
        assert result is my_callback

    def test_get_nonexistent_returns_none(self):
        """未注册的 task_id 返回 None"""
        result = get_progress_callback("nonexistent-task")
        assert result is None

    def test_unregister_removes_callback(self):
        """注销后 get 返回 None"""
        async def cb(data):
            pass

        register_progress_callback("task-2", cb)
        assert get_progress_callback("task-2") is not None

        unregister_progress_callback("task-2")
        assert get_progress_callback("task-2") is None

    def test_unregister_nonexistent_is_safe(self):
        """注销不存在的 task_id 不抛出异常"""
        unregister_progress_callback("never-registered")  # should not raise

    def test_register_overwrites_existing(self):
        """重复注册同一 task_id 会覆盖旧回调"""
        async def cb1(data):
            pass

        async def cb2(data):
            pass

        register_progress_callback("task-3", cb1)
        register_progress_callback("task-3", cb2)
        assert get_progress_callback("task-3") is cb2

    def test_multiple_tasks_isolated(self):
        """不同 task_id 的回调互不干扰"""
        async def cb_a(data):
            pass

        async def cb_b(data):
            pass

        register_progress_callback("task-a", cb_a)
        register_progress_callback("task-b", cb_b)

        assert get_progress_callback("task-a") is cb_a
        assert get_progress_callback("task-b") is cb_b

        unregister_progress_callback("task-a")
        assert get_progress_callback("task-a") is None
        assert get_progress_callback("task-b") is cb_b


# ============================================================
#  ProgressEventBus
# ============================================================

class TestProgressEventBus:
    """测试事件总线的订阅/发布/取消订阅"""

    def test_subscribe_returns_queue(self):
        """subscribe 返回 asyncio.Queue"""
        bus = ProgressEventBus()
        queue = bus.subscribe("task-x")
        assert isinstance(queue, asyncio.Queue)

    def test_has_subscribers_after_subscribe(self):
        """订阅后 has_subscribers 返回 True"""
        bus = ProgressEventBus()
        bus.subscribe("task-y")
        assert bus.has_subscribers("task-y") is True

    def test_has_no_subscribers_initially(self):
        """未订阅时 has_subscribers 返回 False"""
        bus = ProgressEventBus()
        assert bus.has_subscribers("task-z") is False

    def test_unsubscribe_removes_queue(self):
        """取消订阅后 has_subscribers 返回 False"""
        bus = ProgressEventBus()
        queue = bus.subscribe("task-u")
        bus.unsubscribe("task-u", queue)
        assert bus.has_subscribers("task-u") is False

    def test_unsubscribe_nonexistent_is_safe(self):
        """取消不存在的订阅不抛出异常"""
        bus = ProgressEventBus()
        queue = asyncio.Queue()
        bus.unsubscribe("never-subscribed", queue)  # should not raise

    def test_multiple_subscribers_same_task(self):
        """同一 task_id 可以有多个订阅者"""
        bus = ProgressEventBus()
        q1 = bus.subscribe("task-multi")
        q2 = bus.subscribe("task-multi")
        assert q1 is not q2
        assert bus.has_subscribers("task-multi") is True

    @pytest.mark.asyncio
    async def test_publish_delivers_to_subscriber(self):
        """publish 将事件投递到订阅队列"""
        bus = ProgressEventBus()
        queue = bus.subscribe("task-pub")

        event = ProgressEvent(
            task_id="task-pub",
            event_type=EventType.STAGE_START,
            data={"stage": "idea_expansion", "percentage": 0},
        )
        await bus.publish(event)

        received = queue.get_nowait()
        assert received is event
        assert received.event_type == EventType.STAGE_START

    @pytest.mark.asyncio
    async def test_publish_delivers_to_all_subscribers(self):
        """publish 将事件投递到所有订阅者"""
        bus = ProgressEventBus()
        q1 = bus.subscribe("task-all")
        q2 = bus.subscribe("task-all")

        event = ProgressEvent(
            task_id="task-all",
            event_type=EventType.COMPLETED,
            data={"percentage": 100},
        )
        await bus.publish(event)

        assert q1.get_nowait() is event
        assert q2.get_nowait() is event

    @pytest.mark.asyncio
    async def test_publish_does_not_deliver_to_other_tasks(self):
        """publish 不会将事件投递到其他 task_id 的队列"""
        bus = ProgressEventBus()
        q_target = bus.subscribe("task-target")
        q_other = bus.subscribe("task-other")

        event = ProgressEvent(
            task_id="task-target",
            event_type=EventType.STAGE_COMPLETE,
            data={"stage": "world_building"},
        )
        await bus.publish(event)

        assert not q_target.empty()
        assert q_other.empty()

    @pytest.mark.asyncio
    async def test_publish_no_subscribers_is_safe(self):
        """没有订阅者时 publish 不抛出异常"""
        bus = ProgressEventBus()
        event = ProgressEvent(
            task_id="task-nobody",
            event_type=EventType.ERROR,
            data={"error": "test"},
        )
        await bus.publish(event)  # should not raise

    @pytest.mark.asyncio
    async def test_publish_full_queue_does_not_raise(self):
        """队列满时 publish 静默丢弃，不抛出异常"""
        bus = ProgressEventBus()
        # 创建容量为 1 的队列并手动注入
        small_queue: asyncio.Queue = asyncio.Queue(maxsize=1)
        bus._subscribers["task-full"] = [small_queue]

        # 填满队列
        event1 = ProgressEvent(
            task_id="task-full",
            event_type=EventType.STAGE_START,
            data={"stage": "s1"},
        )
        event2 = ProgressEvent(
            task_id="task-full",
            event_type=EventType.STAGE_START,
            data={"stage": "s2"},
        )
        await bus.publish(event1)
        await bus.publish(event2)  # 队列满，应静默丢弃

        # 只有第一个事件在队列中
        assert small_queue.qsize() == 1
        assert small_queue.get_nowait() is event1
