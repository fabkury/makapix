"""MQTT notification payloads + re-export of the shared player protocol.

The player request/response/view schemas now live in
``app.player_protocol.schemas`` so they can be shared by the HTTPS player
backend. They are re-exported here unchanged for backward compatibility with
existing ``from app.mqtt.schemas import ...`` call sites. Only genuinely
MQTT-specific payloads (post notifications) are defined in this module.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, HttpUrl

# Re-export the transport-agnostic player protocol schemas (backward compat).
from ..player_protocol.schemas import *  # noqa: F401,F403
from ..player_protocol.schemas import __all__ as _player_protocol_all


class PostNotificationPayload(BaseModel):
    """MQTT notification payload for new posts."""

    post_id: int  # Changed from UUID to int
    owner_id: UUID
    owner_handle: str
    title: str
    art_url: HttpUrl
    width: int
    height: int
    promoted_category: str | None = None
    created_at: datetime

    model_config = {"json_encoders": {datetime: lambda v: v.isoformat()}}


__all__ = [*_player_protocol_all, "PostNotificationPayload"]
