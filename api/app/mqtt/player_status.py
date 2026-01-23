"""MQTT subscriber for player status updates."""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from paho.mqtt import client as mqtt_client
from sqlalchemy.orm import Session

from ..db import get_session
from .. import models

logger = logging.getLogger(__name__)

# Subscriber client instance
_status_client: mqtt_client.Client | None = None
_status_client_lock = threading.Lock()


def _on_status_message(
    client: mqtt_client.Client, userdata: Any, msg: mqtt_client.MQTTMessage
) -> None:
    """Handle incoming player status messages."""
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        player_key_str = payload.get("player_key")

        if not player_key_str:
            logger.warning("Received status message without player_key")
            return

        player_key = UUID(player_key_str)

        # Update database
        db: Session = next(get_session())
        try:
            player = (
                db.query(models.Player)
                .filter(models.Player.player_key == player_key)
                .first()
            )

            if not player:
                logger.warning(
                    f"Received status update for unknown player_key: {player_key}"
                )
                return

            # Update connection status
            connection_status = payload.get("status", "online")
            player.connection_status = connection_status
            player.last_seen_at = datetime.now(timezone.utc)

            # Update current post if provided
            if "current_post_id" in payload:
                current_post_id = payload.get("current_post_id")
                player.current_post_id = current_post_id if current_post_id else None

            # Update firmware version if provided
            if "firmware_version" in payload:
                firmware_version = payload.get("firmware_version")
                if firmware_version:
                    player.firmware_version = firmware_version

            db.commit()
            logger.info(f"Updated status for player {player_key}: {connection_status}")

        except Exception as e:
            logger.error(
                f"Error processing status update for player {player_key}: {e}",
                exc_info=True,
            )
            db.rollback()
        finally:
            db.close()

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse status message: {e}")
    except Exception as e:
        logger.error(f"Unexpected error handling status message: {e}", exc_info=True)


def start_status_subscriber() -> None:
    """Start MQTT subscriber for player status updates."""
    global _status_client

    with _status_client_lock:
        if _status_client is not None and _status_client.is_connected():
            logger.info("Status subscriber already running")
            return

        try:
            client = mqtt_client.Client(
                callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2,
                client_id=f"player-status-subscriber-{os.getpid()}",
                protocol=mqtt_client.MQTTv5,
            )

            # Set username/password for api-server
            username = os.getenv("MQTT_USERNAME", "api-server")
            password = os.getenv("MQTT_PASSWORD", "")
            if username:
                client.username_pw_set(username, password)

            # Internal connection uses port 1883 (no TLS required within Docker network)
            use_tls = os.getenv("MQTT_TLS_ENABLED", "false").lower() == "true"
            if use_tls:
                ca_file = os.getenv("MQTT_CA_FILE")
                if ca_file and os.path.exists(ca_file):
                    client.tls_set(ca_certs=ca_file)
                else:
                    client.tls_set()
                    client.tls_insecure_set(True)
                    logger.warning("MQTT TLS insecure mode enabled (development only)")

            def on_connect(client, userdata, flags, reason_code, properties):
                if reason_code == 0:
                    logger.info("Player status subscriber connected to MQTT broker")
                    # Subscribe to all player status topics
                    client.subscribe("makapix/player/+/status", qos=1)
                    logger.info("Subscribed to makapix/player/+/status")
                else:
                    logger.error(f"Status subscriber connection failed: {reason_code}")

            def on_disconnect(
                client, userdata, disconnect_flags, reason_code, properties
            ):
                logger.warning(f"Status subscriber disconnected: {reason_code}")

            client.on_connect = on_connect
            client.on_disconnect = on_disconnect
            client.on_message = _on_status_message

            # Use internal port 1883 (no mTLS required within Docker network)
            host = os.getenv("MQTT_BROKER_HOST", "mqtt")
            port = int(os.getenv("MQTT_BROKER_PORT", "1883"))

            logger.info(f"Connecting status subscriber to {host}:{port}")
            client.connect(host, port, keepalive=60)
            client.loop_start()

            _status_client = client
            logger.info("Player status subscriber started")

        except Exception as e:
            logger.error(f"Failed to start status subscriber: {e}", exc_info=True)


def stop_status_subscriber() -> None:
    """Stop MQTT subscriber for player status updates."""
    global _status_client

    with _status_client_lock:
        if _status_client:
            _status_client.loop_stop()
            _status_client.disconnect()
            _status_client = None
            logger.info("Player status subscriber stopped")
