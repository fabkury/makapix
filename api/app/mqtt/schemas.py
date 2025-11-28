"""MQTT notification payload schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, HttpUrl


class PostNotificationPayload(BaseModel):
    """MQTT notification payload for new posts."""

    post_id: int  # Changed from UUID to int
    owner_id: UUID
    owner_handle: str
    title: str
    art_url: HttpUrl
    canvas: str
    promoted_category: str | None = None
    created_at: datetime

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}

