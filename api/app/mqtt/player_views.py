"""MQTT subscriber for player view events (fire-and-forget).

Transport adapter over ``app.services.player_views.record_view_event``: this
module owns MQTT concerns (topic parsing, broker auth by player_key, acks,
subscriber lifecycle); the ingestion logic is shared with the HTTPS backend.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any
from uuid import UUID

from paho.mqtt import client as mqtt_client
from sqlalchemy.orm import Session

from ..db import get_session
from .. import models
from ..services.player_views import (
    DUPLICATE,
    POST_NOT_FOUND,
    RATE_LIMITED,
    record_view_event,
)
from .schemas import P3AViewEvent

logger = logging.getLogger(__name__)

# Subscriber client instance
_view_client: mqtt_client.Client | None = None
_view_client_lock = threading.Lock()


def _on_view_message(
    client: mqtt_client.Client, userdata: Any, msg: mqtt_client.MQTTMessage
) -> None:
    """
    Handle incoming player view event messages.

    Topic pattern: makapix/player/{player_key}/view
    Optional acknowledgment sent to: makapix/player/{player_key}/view/ack
    """
    view_event = None
    player_key = None
    try:
        # Parse topic to extract player_key
        parts = msg.topic.split("/")
        if (
            len(parts) != 4
            or parts[0] != "makapix"
            or parts[1] != "player"
            or parts[3] != "view"
        ):
            logger.warning(f"Invalid view topic format: {msg.topic}")
            return

        player_key_str = parts[2]

        try:
            player_key = UUID(player_key_str)
        except ValueError:
            logger.warning(f"Invalid player_key in topic: {player_key_str}")
            return

        # Parse payload
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse view event payload: {e}")
            return

        # Validate payload with Pydantic schema
        try:
            view_event = P3AViewEvent(**payload)
        except Exception as e:
            logger.error(f"Invalid view event payload: {e}")
            return

        # Verify player_key in payload matches topic
        if str(player_key) != view_event.player_key:
            logger.warning(
                f"player_key mismatch: topic={player_key}, payload={view_event.player_key}"
            )
            if view_event.request_ack:
                ack_topic = f"makapix/player/{player_key}/view/ack"
                ack_payload = json.dumps(
                    {
                        "success": False,
                        "error": "player_key mismatch between topic and payload",
                        "error_code": "player_key_mismatch",
                    }
                )
                client.publish(ack_topic, ack_payload, qos=1)
            return

        # Get database session
        db: Session = next(get_session())
        try:
            # Authenticate player
            player = (
                db.query(models.Player)
                .filter(
                    models.Player.player_key == player_key,
                    models.Player.registration_status == "registered",
                )
                .first()
            )

            if not player:
                logger.warning(f"View event from unregistered player: {player_key}")
                if view_event.request_ack:
                    ack_topic = f"makapix/player/{player_key}/view/ack"
                    ack_payload = json.dumps(
                        {
                            "success": False,
                            "error": "Player not registered",
                            "error_code": "player_not_registered",
                        }
                    )
                    client.publish(ack_topic, ack_payload, qos=1)
                return

            if not player.owner_id:
                logger.warning(f"Player {player_key} has no owner")
                if view_event.request_ack:
                    ack_topic = f"makapix/player/{player_key}/view/ack"
                    ack_payload = json.dumps(
                        {
                            "success": False,
                            "error": "Player has no owner",
                            "error_code": "player_no_owner",
                        }
                    )
                    client.publish(ack_topic, ack_payload, qos=1)
                return

            # Record the view via the shared ingestion service (dedup, rate
            # limit, post/self-view checks, async dispatch).
            result = record_view_event(player, view_event, db)

            if view_event.request_ack:
                ack_topic = f"makapix/player/{player_key}/view/ack"
                if result.status == DUPLICATE:
                    ack_payload = json.dumps(
                        {
                            "success": False,
                            "error": "Duplicate view event",
                            "error_code": "duplicate",
                        }
                    )
                elif result.status == RATE_LIMITED:
                    ack_payload = json.dumps(
                        {
                            "success": False,
                            "error": f"Rate limited, retry after {result.retry_after}s",
                            "error_code": "rate_limited",
                        }
                    )
                elif result.status == POST_NOT_FOUND:
                    ack_payload = json.dumps(
                        {
                            "success": False,
                            "error": "Post not found",
                            "error_code": "post_not_found",
                        }
                    )
                else:
                    # RECORDED or SELF_VIEW -> success
                    ack_payload = json.dumps({"success": True})
                client.publish(ack_topic, ack_payload, qos=1)
                logger.debug(f"Sent view ack to {ack_topic}")

        except Exception as e:
            logger.error(f"Error processing view event: {e}", exc_info=True)
            # Send error ack if requested
            if view_event and view_event.request_ack:
                ack_topic = f"makapix/player/{player_key}/view/ack"
                ack_payload = json.dumps(
                    {
                        "success": False,
                        "error": str(e),
                        "error_code": "processing_error",
                    }
                )
                client.publish(ack_topic, ack_payload, qos=1)
                logger.debug(f"Sent error ack to {ack_topic}")
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Unexpected error in view event handler: {e}", exc_info=True)


def start_view_subscriber() -> None:
    """Start MQTT subscriber for player view events (fire-and-forget)."""
    global _view_client

    with _view_client_lock:
        if _view_client is not None and _view_client.is_connected():
            logger.info("View event subscriber already running")
            return

        try:
            client = mqtt_client.Client(
                callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2,
                client_id=f"player-view-subscriber-{os.getpid()}",
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
                    logger.info("Player view event subscriber connected to MQTT broker")
                    # Subscribe to all player view topics
                    client.subscribe("makapix/player/+/view", qos=1)
                    logger.info("Subscribed to makapix/player/+/view")
                else:
                    logger.error(
                        f"View event subscriber connection failed: {reason_code}"
                    )

            def on_disconnect(
                client, userdata, disconnect_flags, reason_code, properties
            ):
                logger.warning(f"View event subscriber disconnected: {reason_code}")

            client.on_connect = on_connect
            client.on_disconnect = on_disconnect
            client.on_message = _on_view_message

            # Connect to MQTT broker
            broker_host = os.getenv("MQTT_BROKER_HOST", "mqtt")
            broker_port = int(os.getenv("MQTT_BROKER_PORT", "1883"))

            client.connect(broker_host, broker_port, keepalive=60)

            # Start network loop in background thread
            client.loop_start()

            _view_client = client
            logger.info(
                f"Player view event subscriber started (broker: {broker_host}:{broker_port})"
            )

        except Exception as e:
            logger.error(f"Failed to start view event subscriber: {e}", exc_info=True)
            raise


def stop_view_subscriber() -> None:
    """Stop MQTT subscriber for player view events."""
    global _view_client

    with _view_client_lock:
        if _view_client is not None:
            try:
                _view_client.loop_stop()
                _view_client.disconnect()
                _view_client = None
                logger.info("Player view event subscriber stopped")
            except Exception as e:
                logger.error(f"Error stopping view event subscriber: {e}")
