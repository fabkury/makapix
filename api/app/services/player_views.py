"""Shared player view-event ingestion (MQTT + HTTPS).

The post-authentication core of recording a player view: deduplication, rate
limiting, post-existence and self-view checks, and async dispatch to the
``write_view_event`` Celery task. Both transports call :func:`record_view_event`
with an authenticated ``Player`` and a validated ``P3AViewEvent`` and translate
the returned status into their own response (an MQTT ack or an HTTP status).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from .. import models
from ..player_protocol.schemas import P3AViewEvent

logger = logging.getLogger(__name__)

# Timestamp that indicates unsynced time on p3a devices.
UNSYNC_TIMESTAMP = "1970-01-01T00:00:00Z"

# Ingestion result statuses.
RECORDED = "recorded"
DUPLICATE = "duplicate"
RATE_LIMITED = "rate_limited"
POST_NOT_FOUND = "post_not_found"
SELF_VIEW = "self_view"  # accepted, but intentionally not recorded


@dataclass
class ViewIngestResult:
    """Outcome of ingesting a single player view event."""

    status: str
    retry_after: float | None = None


def record_view_event(
    player: models.Player, event: P3AViewEvent, db: Session
) -> ViewIngestResult:
    """Ingest a fire-and-forget view event for an authenticated player.

    Deduplication is checked before rate limiting, matching the MQTT path.
    Returns a :class:`ViewIngestResult` whose ``status`` is one of
    ``RECORDED``, ``DUPLICATE``, ``RATE_LIMITED``, ``POST_NOT_FOUND``, or
    ``SELF_VIEW``. Recorded events are dispatched to Celery; this function never
    blocks on the write.
    """
    from .rate_limit import check_player_view_rate_limit, check_view_duplicate

    player_key = str(player.player_key)

    # Discard duplicates (e.g. MQTT QoS 1 retransmissions, client retries).
    if check_view_duplicate(player_key, event.post_id, event.timestamp):
        logger.debug(
            f"Discarded duplicate view: player={player_key}, post={event.post_id}"
        )
        return ViewIngestResult(DUPLICATE)

    # Rate limit (1 view per 5 seconds per player).
    allowed, retry_after = check_player_view_rate_limit(player_key)
    if not allowed:
        logger.debug(
            f"Rate limited view from player {player_key}, retry after {retry_after}s"
        )
        return ViewIngestResult(RATE_LIMITED, retry_after)

    post = db.query(models.Post).filter(models.Post.id == event.post_id).first()
    if not post:
        logger.warning(f"View event for non-existent post: {event.post_id}")
        return ViewIngestResult(POST_NOT_FOUND)

    # Don't record a view if the player's owner is the post's owner.
    if player.owner_id == post.owner_id:
        logger.debug(
            f"Skipped self-view for post {event.post_id} by player {player_key}"
        )
        return ViewIngestResult(SELF_VIEW)

    from ..tasks import write_view_event
    from ..utils.view_tracking import ViewSource, ViewType, hash_ip

    # Map p3a's intent to our view_type.
    if event.intent == "artwork":
        view_type = ViewType.INTENTIONAL
    elif event.intent == "channel":
        view_type = ViewType.LISTING
    else:
        logger.warning(
            f"Unexpected intent value: {event.intent}, defaulting to LISTING"
        )
        view_type = ViewType.LISTING

    # Reject "1970-01-01T00:00:00Z" (unsynced device) -> store NULL local time.
    local_datetime = event.timestamp if event.timestamp != UNSYNC_TIMESTAMP else None

    # Build channel_context from channel-specific fields.
    channel_context = None
    if event.channel in ("by_user", "reactions") and event.channel_user_sqid:
        channel_context = event.channel_user_sqid
    elif event.channel == "hashtag" and event.channel_hashtag:
        channel_context = event.channel_hashtag

    # Players use a synthetic IP hash derived from their key.
    player_ip_hash = hash_ip(f"player:{player_key}")

    event_data = {
        "post_id": str(event.post_id),
        "viewer_user_id": str(player.owner_id),
        "viewer_ip_hash": player_ip_hash,
        "country_code": None,  # Players don't have geographic info
        "device_type": "player",
        "view_source": ViewSource.PLAYER.value,
        "view_type": view_type.value,
        "user_agent_hash": None,
        "referrer_domain": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        # Player-specific fields
        "player_id": str(player.id),
        "local_datetime": local_datetime,
        "local_timezone": event.timezone if event.timezone else None,
        "play_order": event.play_order,
        "channel": event.channel,
        "channel_context": channel_context,
    }

    write_view_event.delay(event_data)
    logger.info(f"Recorded view for post {event.post_id} from player {player_key}")
    return ViewIngestResult(RECORDED)
