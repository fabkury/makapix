"""Authenticated real-time stream for web and app clients (SSE).

A single bearer-authenticated Server-Sent Events stream that pushes the user's
social notifications as they arrive. This is the human plane's live channel
(docs/notification-architecture/): browsers and apps consume it over HTTPS via
fetch-streaming (EventSource cannot send an Authorization header); the MQTT
broker is the device plane and carries no social notifications.

Delivery is push-based: `SocialNotificationService._dispatch_notification`
publishes each committed row onto the in-process `notification_bus`
(services/event_bus.py) and this endpoint forwards it. No polling, and the
pooled DB connection is released right after the greeting — the stream itself
never touches the database. Missed events (disconnects, multi-worker futures)
are reconciled by the `connected` greeting's unread_count and the paginated
list endpoint; clients dedupe by notification id.

Events: `connected` {"unread_count": N} → `notification` (full REST item
shape) → `: keepalive` comments → `timeout` then close at the bounded
lifetime (clients reconnect; the bound re-gates auth and reaps dead streams).
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from .. import models
from ..auth import get_current_user
from ..deps import get_db
from ..services.event_bus import notification_bus
from ..services.social_notifications import SocialNotificationService

router = APIRouter(prefix="/realtime", tags=["Realtime"])

_STREAM_TIMEOUT_SECONDS = 300  # client reconnects after this
_KEEPALIVE_SECONDS = 15.0


def _sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


@router.get("/notifications")
async def stream_notifications(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> StreamingResponse:
    """Bearer-authenticated SSE stream of the current user's social notifications."""
    user_id = current_user.id

    async def event_generator() -> AsyncGenerator[str, None]:
        # Subscribe BEFORE reading the count: an event landing in between is
        # delivered AND counted (clients dedupe by id) — never missed.
        queue = await notification_bus.subscribe(user_id)
        try:
            # Greet with the current unread count so the client can sync its
            # badge on every (re)connect.
            unread = await run_in_threadpool(
                SocialNotificationService.get_unread_count, db, user_id
            )
            # Release the pooled DB connection for the stream's lifetime; the
            # push loop below never touches the database. (get_db's teardown
            # close() after the response is idempotent.)
            await run_in_threadpool(db.close)
            yield _sse("connected", {"unread_count": unread})

            deadline = time.monotonic() + _STREAM_TIMEOUT_SECONDS
            while (remaining := deadline - time.monotonic()) > 0:
                if await request.is_disconnected():
                    return
                try:
                    event = await asyncio.wait_for(
                        queue.get(), timeout=min(_KEEPALIVE_SECONDS, remaining)
                    )
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
                    continue
                yield _sse("notification", event)

            yield _sse("timeout", {"message": "Connection timeout, please reconnect"})
        finally:
            await notification_bus.unsubscribe(user_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
