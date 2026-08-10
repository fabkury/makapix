"""In-process per-user pub/sub buses for live SSE delivery.

Two isolated buses share one implementation:
- ``player_bus`` — player capability/state events (MQTT subscriber threads
  publish; the player SSE endpoint forwards to the browser).
- ``notification_bus`` — social notifications (request handlers publish
  post-commit; the /realtime/notifications SSE endpoint forwards).

They must stay separate instances: the player SSE re-emits raw bus events,
so notification events on the same queues would leak into player streams.

Single-process only. If we ever scale to multiple API workers, this
needs to move to Redis pub/sub.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Capture the loop the buses live on so threaded callers (MQTT callbacks,
# threadpool-run sync request handlers) can publish into it.
_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


class UserEventBus:
    def __init__(self, name: str) -> None:
        self._name = name
        # user_id -> set of asyncio.Queue
        self._subscribers: dict[int, set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, user_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        async with self._lock:
            self._subscribers.setdefault(user_id, set()).add(queue)
        return queue

    async def unsubscribe(self, user_id: int, queue: asyncio.Queue) -> None:
        async with self._lock:
            subs = self._subscribers.get(user_id)
            if subs is None:
                return
            subs.discard(queue)
            if not subs:
                self._subscribers.pop(user_id, None)

    def publish_threadsafe(self, user_id: int, event: dict[str, Any]) -> None:
        """Publish from a non-asyncio thread (MQTT callback, request handler)."""
        loop = _loop
        if loop is None or loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self._publish(user_id, event), loop)

    async def _publish(self, user_id: int, event: dict[str, Any]) -> None:
        subs = self._subscribers.get(user_id)
        if not subs:
            return
        # Snapshot to avoid mutation during iteration
        for queue in list(subs):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "SSE queue full (%s) for user %s; dropping event",
                    self._name,
                    user_id,
                )


player_bus = UserEventBus("player")
notification_bus = UserEventBus("notifications")
