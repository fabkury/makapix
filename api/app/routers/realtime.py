"""Authenticated real-time stream for app clients (SSE) — change-request §5.

A single bearer-authenticated Server-Sent Events stream that pushes the user's
social notifications as they arrive. Decoupled from the hardware-player MQTT
(which stays mTLS); no broker credentials reach the client. If the socket drops,
the client falls back to polling `GET /api/v1/social-notifications/unread-count`.

Implementation mirrors the proven polling-SSE pattern used by `/bdr/sse`: poll
the notifications table on a short interval, emit new rows, send keepalives, and
close after a bounded lifetime so clients reconnect.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db
from ..services.social_notifications import SocialNotificationService

router = APIRouter(prefix="/realtime", tags=["Realtime"])

_STREAM_TIMEOUT_SECONDS = 300  # client reconnects after this
_POLL_INTERVAL_SECONDS = 3


def _sse(event: str, data: object) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def _notification_payload(n: models.SocialNotification) -> dict:
    return schemas.SocialNotification.model_validate(n).model_dump(mode="json")


@router.get("/notifications")
async def stream_notifications(
    request: Request,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> StreamingResponse:
    """Bearer-authenticated SSE stream of the current user's social notifications."""
    user_id = current_user.id

    async def event_generator() -> AsyncGenerator[str, None]:
        # Greet with the current unread count so the client can sync its badge.
        unread = SocialNotificationService.get_unread_count(db, user_id)
        yield _sse("connected", {"unread_count": unread})

        # Only stream notifications created after the connection opens; the client
        # backfills history via the paginated list endpoint.
        last_seen = datetime.now(timezone.utc)
        deadline = datetime.now(timezone.utc).timestamp() + _STREAM_TIMEOUT_SECONDS

        while datetime.now(timezone.utc).timestamp() < deadline:
            if await request.is_disconnected():
                break
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)
            db.expire_all()

            new_rows = (
                db.query(models.SocialNotification)
                .filter(
                    models.SocialNotification.user_id == user_id,
                    models.SocialNotification.created_at > last_seen,
                )
                .order_by(models.SocialNotification.created_at.asc())
                .all()
            )
            for n in new_rows:
                if n.created_at:
                    last_seen = n.created_at
                yield _sse("notification", _notification_payload(n))

            yield ": keepalive\n\n"

        yield _sse("timeout", {"message": "Connection timeout, please reconnect"})

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
