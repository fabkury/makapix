"""In-process pub/sub bus for live player capability/state events.

MQTT subscribers (running on the API server) push events here; SSE
endpoints subscribe per user and forward events to the browser.

Single-process only. If we ever scale to multiple API workers, this
needs to move to Redis pub/sub.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


# user_id -> set of asyncio.Queue
_subscribers: dict[int, set[asyncio.Queue]] = {}
_lock = asyncio.Lock()
# Capture the loop the bus lives on so threaded MQTT callbacks can publish into it.
_loop: asyncio.AbstractEventLoop | None = None


def set_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _loop
    _loop = loop


async def subscribe(user_id: int) -> asyncio.Queue:
    queue: asyncio.Queue = asyncio.Queue(maxsize=64)
    async with _lock:
        _subscribers.setdefault(user_id, set()).add(queue)
    return queue


async def unsubscribe(user_id: int, queue: asyncio.Queue) -> None:
    async with _lock:
        subs = _subscribers.get(user_id)
        if subs is None:
            return
        subs.discard(queue)
        if not subs:
            _subscribers.pop(user_id, None)


def publish_threadsafe(user_id: int, event: dict[str, Any]) -> None:
    """Publish from a non-asyncio thread (e.g. an MQTT callback)."""
    loop = _loop
    if loop is None or loop.is_closed():
        return
    asyncio.run_coroutine_threadsafe(_publish(user_id, event), loop)


async def _publish(user_id: int, event: dict[str, Any]) -> None:
    subs = _subscribers.get(user_id)
    if not subs:
        return
    # Snapshot to avoid mutation during iteration
    for queue in list(subs):
        try:
            queue.put_nowait(event)
        except asyncio.QueueFull:
            logger.warning("SSE queue full for user %s; dropping event", user_id)


def _serialize_uuid(v: Any) -> Any:
    if isinstance(v, UUID):
        return str(v)
    return v
