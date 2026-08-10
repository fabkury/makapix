"""Unit tests for the in-process per-user event buses (services/event_bus.py).

The plane-separation invariant matters most here: notification events must
never reach player-bus queues (the player SSE re-emits raw bus events).
"""

from __future__ import annotations

import asyncio

from app.services import event_bus
from app.services.event_bus import UserEventBus


def test_subscribe_publish_receive():
    async def scenario():
        bus = UserEventBus("test")
        queue = await bus.subscribe(1)
        await bus._publish(1, {"hello": "world"})
        assert queue.get_nowait() == {"hello": "world"}
        await bus.unsubscribe(1, queue)
        # After unsubscribe the user key is gone; publishing is a no-op.
        await bus._publish(1, {"again": True})
        assert bus._subscribers == {}

    asyncio.run(scenario())


def test_publish_only_reaches_target_user():
    async def scenario():
        bus = UserEventBus("test")
        q1 = await bus.subscribe(1)
        q2 = await bus.subscribe(2)
        await bus._publish(1, {"n": 1})
        assert q1.get_nowait() == {"n": 1}
        assert q2.empty()

    asyncio.run(scenario())


def test_queue_full_drops_without_raising():
    async def scenario():
        bus = UserEventBus("test")
        queue = await bus.subscribe(1)
        for i in range(64):
            await bus._publish(1, {"i": i})
        # 65th is dropped, not raised.
        await bus._publish(1, {"i": 64})
        assert queue.qsize() == 64

    asyncio.run(scenario())


def test_publish_threadsafe_noops_without_loop(monkeypatch):
    monkeypatch.setattr(event_bus, "_loop", None)
    bus = UserEventBus("test")
    # Must not raise even though no loop was registered.
    bus.publish_threadsafe(1, {"x": 1})


def test_bus_instances_are_isolated():
    """Plane separation: an event on the notification bus never lands on a
    player-bus queue for the same user."""

    async def scenario():
        player_q = await event_bus.player_bus.subscribe(42)
        notif_q = await event_bus.notification_bus.subscribe(42)
        try:
            await event_bus.notification_bus._publish(42, {"kind": "notif"})
            assert notif_q.get_nowait() == {"kind": "notif"}
            assert player_q.empty()
        finally:
            await event_bus.player_bus.unsubscribe(42, player_q)
            await event_bus.notification_bus.unsubscribe(42, notif_q)

    asyncio.run(scenario())
