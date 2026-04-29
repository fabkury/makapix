"""MQTT player command publishing and logging."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from .. import models
from .publisher import publish

logger = logging.getLogger(__name__)


def publish_player_command(
    player_key: UUID,
    command_type: str,
    payload: dict[str, Any] | None = None,
    command_id: UUID | None = None,
) -> UUID:
    """
    Publish command to player via MQTT.

    If command_id is supplied it is used as-is (so it can match an existing
    PlayerCommandLog row, enabling ack tracking).
    """
    from uuid import uuid4

    if command_id is None:
        command_id = uuid4()
    topic = f"makapix/player/{player_key}/command"

    message = {
        "command_id": str(command_id),
        "command_type": command_type,
        "payload": payload or {},
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    success = publish(topic, message, qos=1, retain=False)

    if success:
        logger.info(
            f"Published command {command_id} to player {player_key}: {command_type}"
        )
    else:
        logger.error(f"Failed to publish command {command_id} to player {player_key}")

    return command_id


def log_command(
    db: Session,
    player_id: UUID,
    command_type: str,
    payload: dict[str, Any] | None = None,
    command_id: UUID | None = None,
) -> models.PlayerCommandLog:
    """
    Log command to database for auditing.

    Args:
        db: Database session
        player_id: Player ID
        command_type: Command type
        payload: Command payload

    Returns:
        Created PlayerCommandLog instance
    """
    kwargs: dict[str, Any] = {
        "player_id": player_id,
        "command_type": command_type,
        "payload": payload,
    }
    if command_id is not None:
        kwargs["id"] = command_id
    command_log = models.PlayerCommandLog(**kwargs)
    db.add(command_log)
    db.commit()
    db.refresh(command_log)

    return command_log
