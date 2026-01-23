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
) -> UUID:
    """
    Publish command to player via MQTT.

    Args:
        player_key: Player's unique key (UUID)
        command_type: Command type (swap_next, swap_back, show_artwork)
        payload: Command-specific payload data

    Returns:
        Command ID (UUID) for tracking
    """
    from uuid import uuid4

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
    command_log = models.PlayerCommandLog(
        player_id=player_id,
        command_type=command_type,
        payload=payload,
    )
    db.add(command_log)
    db.commit()
    db.refresh(command_log)

    return command_log
