"""Re-export of the shared player protocol schemas.

The player request/response/view schemas live in
``app.player_protocol.schemas`` so they can be shared by the HTTPS player
backend. They are re-exported here unchanged for backward compatibility with
existing ``from app.mqtt.schemas import ...`` call sites. MQTT carries only
the device plane (docs/notification-architecture/) — the former
PostNotificationPayload was deleted with the post/new fan-out (2026-08).
"""

from __future__ import annotations

# Re-export the transport-agnostic player protocol schemas (backward compat).
from ..player_protocol.schemas import *  # noqa: F401,F403
from ..player_protocol.schemas import __all__ as _player_protocol_all

__all__ = [*_player_protocol_all]
