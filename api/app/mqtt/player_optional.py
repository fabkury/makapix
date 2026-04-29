"""MQTT subscribers for optional player features.

Three topics handled here:
  - makapix/player/{key}/capabilities  (retained, player declares features)
  - makapix/player/{key}/state         (retained, player reports current state)
  - makapix/player/{key}/command/ack   (per-command acknowledgement)
"""

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

from .. import models
from ..db import get_session
from ..services import player_events

logger = logging.getLogger(__name__)

# Whitelist of feature names we recognise. Unknown keys are ignored.
KNOWN_FEATURES = {"pause", "brightness", "rotation", "mirror"}

_client: mqtt_client.Client | None = None
_client_lock = threading.Lock()


# ---------------------------------------------------------------------------
# Capability validation
# ---------------------------------------------------------------------------


def _sanitize_capabilities(raw: Any) -> dict[str, Any] | None:
    """Pull out the recognised features from the player's manifest."""
    if not isinstance(raw, dict):
        return None
    features = raw.get("features")
    if not isinstance(features, dict):
        return None

    cleaned: dict[str, Any] = {}
    for name, spec in features.items():
        if name not in KNOWN_FEATURES:
            continue
        if not isinstance(spec, dict):
            continue
        if name == "brightness":
            try:
                bmin = int(spec.get("min", 0))
                bmax = int(spec.get("max", 100))
                step = int(spec.get("step", 1))
            except (TypeError, ValueError):
                continue
            if bmin >= bmax or step <= 0:
                continue
            cleaned[name] = {"min": bmin, "max": bmax, "step": step}
        elif name == "rotation":
            values = spec.get("values")
            if not isinstance(values, list):
                continue
            try:
                vals = [int(v) for v in values]
            except (TypeError, ValueError):
                continue
            cleaned[name] = {"values": vals}
        elif name == "mirror":
            values = spec.get("values")
            if not isinstance(values, list):
                continue
            vals = [str(v) for v in values if isinstance(v, str)]
            if not vals:
                continue
            cleaned[name] = {"values": vals}
        elif name == "pause":
            cleaned[name] = {}

    return cleaned


def _sanitize_state(
    raw: dict[str, Any], capabilities: dict[str, Any] | None
) -> dict[str, Any]:
    """Filter the reported state to only fields the player advertises."""
    out: dict[str, Any] = {}
    caps = capabilities or {}

    if "pause" in caps and "is_paused" in raw:
        out["is_paused"] = bool(raw.get("is_paused"))

    if "brightness" in caps and "brightness" in raw:
        try:
            v = int(raw["brightness"])
        except (TypeError, ValueError):
            v = None
        spec = caps["brightness"]
        if v is not None and spec["min"] <= v <= spec["max"]:
            out["brightness"] = v

    if "rotation" in caps and "rotation" in raw:
        try:
            v = int(raw["rotation"])
        except (TypeError, ValueError):
            v = None
        if v is not None and v in caps["rotation"]["values"]:
            out["rotation"] = v

    if "mirror" in caps and "mirror" in raw:
        v = raw.get("mirror")
        if isinstance(v, str) and v in caps["mirror"]["values"]:
            out["mirror"] = v

    return out


# ---------------------------------------------------------------------------
# Message handlers
# ---------------------------------------------------------------------------


def _player_key_from_topic(topic: str) -> UUID | None:
    parts = topic.split("/")
    # makapix/player/{key}/...
    if len(parts) < 4:
        return None
    try:
        return UUID(parts[2])
    except ValueError:
        return None


def _handle_capabilities(player_key: UUID, payload: dict[str, Any]) -> None:
    cleaned = _sanitize_capabilities(payload)
    db: Session = next(get_session())
    try:
        player = (
            db.query(models.Player)
            .filter(models.Player.player_key == player_key)
            .first()
        )
        if player is None:
            logger.warning("Capabilities for unknown player_key %s", player_key)
            return

        # Empty payload (or "{}") means: player declares no optional support.
        # Treat falsy cleaned as empty dict.
        capabilities = cleaned or {}

        firmware_version = payload.get("firmware_version")
        if isinstance(firmware_version, str):
            player.firmware_version = firmware_version

        player.capabilities = capabilities
        player.capabilities_updated_at = datetime.now(timezone.utc)

        # Drop any reported state that is no longer supported.
        if "pause" not in capabilities:
            player.is_paused = None
        if "brightness" not in capabilities:
            player.brightness = None
        if "rotation" not in capabilities:
            player.rotation = None
        if "mirror" not in capabilities:
            player.mirror = None

        db.commit()

        if player.owner_id is not None:
            player_events.publish_threadsafe(
                player.owner_id,
                {
                    "type": "capabilities",
                    "player_id": str(player.id),
                    "capabilities": capabilities,
                    "firmware_version": player.firmware_version,
                },
            )
    except Exception:
        logger.exception("Error handling capabilities for %s", player_key)
        db.rollback()
    finally:
        db.close()


def _handle_state(player_key: UUID, payload: dict[str, Any]) -> None:
    db: Session = next(get_session())
    try:
        player = (
            db.query(models.Player)
            .filter(models.Player.player_key == player_key)
            .first()
        )
        if player is None:
            logger.warning("State for unknown player_key %s", player_key)
            return

        clean = _sanitize_state(payload, player.capabilities)
        if "is_paused" in clean:
            player.is_paused = clean["is_paused"]
        if "brightness" in clean:
            player.brightness = clean["brightness"]
        if "rotation" in clean:
            player.rotation = clean["rotation"]
        if "mirror" in clean:
            player.mirror = clean["mirror"]
        player.state_updated_at = datetime.now(timezone.utc)
        db.commit()

        if player.owner_id is not None and clean:
            player_events.publish_threadsafe(
                player.owner_id,
                {
                    "type": "state",
                    "player_id": str(player.id),
                    "state": clean,
                },
            )
    except Exception:
        logger.exception("Error handling state for %s", player_key)
        db.rollback()
    finally:
        db.close()


def _handle_ack(player_key: UUID, payload: dict[str, Any]) -> None:
    command_id_raw = payload.get("command_id")
    if not isinstance(command_id_raw, str):
        return
    try:
        command_id = UUID(command_id_raw)
    except ValueError:
        return

    raw_status = payload.get("status")
    if raw_status not in ("ok", "error", "unsupported"):
        return
    error_msg = payload.get("error") if isinstance(payload.get("error"), str) else None

    db: Session = next(get_session())
    try:
        log = (
            db.query(models.PlayerCommandLog)
            .filter(models.PlayerCommandLog.id == command_id)
            .first()
        )
        if log is None:
            logger.warning("Ack for unknown command_id %s", command_id)
            return
        log.ack_status = raw_status
        log.acked_at = datetime.now(timezone.utc)
        db.commit()

        player = log.player
        owner_id = player.owner_id if player is not None else None
        if owner_id is not None:
            player_events.publish_threadsafe(
                owner_id,
                {
                    "type": "command_ack",
                    "player_id": str(player.id) if player is not None else None,
                    "command_id": str(command_id),
                    "status": raw_status,
                    "error": error_msg,
                },
            )
    except Exception:
        logger.exception("Error handling ack for %s", command_id)
        db.rollback()
    finally:
        db.close()


def _on_message(
    client: mqtt_client.Client, userdata: Any, msg: mqtt_client.MQTTMessage
) -> None:
    try:
        player_key = _player_key_from_topic(msg.topic)
        if player_key is None:
            return
        # Empty retained payload == manifest cleared. Treat as empty dict.
        if not msg.payload:
            payload: dict[str, Any] = {}
        else:
            payload = json.loads(msg.payload.decode("utf-8"))
        if not isinstance(payload, dict):
            return

        if msg.topic.endswith("/capabilities"):
            _handle_capabilities(player_key, payload)
        elif msg.topic.endswith("/state"):
            _handle_state(player_key, payload)
        elif msg.topic.endswith("/command/ack"):
            _handle_ack(player_key, payload)
    except json.JSONDecodeError as e:
        logger.error("Failed to decode optional-feature message: %s", e)
    except Exception:
        logger.exception("Unexpected error in optional-feature handler")


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------


def start_optional_subscriber() -> None:
    global _client
    with _client_lock:
        if _client is not None and _client.is_connected():
            return

        client = mqtt_client.Client(
            callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2,
            client_id=f"player-optional-subscriber-{os.getpid()}",
            protocol=mqtt_client.MQTTv5,
        )

        username = os.getenv("MQTT_USERNAME", "api-server")
        password = os.getenv("MQTT_PASSWORD", "")
        if username:
            client.username_pw_set(username, password)

        use_tls = os.getenv("MQTT_TLS_ENABLED", "false").lower() == "true"
        if use_tls:
            ca_file = os.getenv("MQTT_CA_FILE")
            if ca_file and os.path.exists(ca_file):
                client.tls_set(ca_certs=ca_file)
            else:
                client.tls_set()
                client.tls_insecure_set(True)

        def on_connect(c, userdata, flags, reason_code, properties):
            if reason_code == 0:
                logger.info("Optional-feature subscriber connected")
                c.subscribe("makapix/player/+/capabilities", qos=1)
                c.subscribe("makapix/player/+/state", qos=1)
                c.subscribe("makapix/player/+/command/ack", qos=1)
            else:
                logger.error("Optional-feature subscriber failed: %s", reason_code)

        def on_disconnect(c, userdata, disconnect_flags, reason_code, properties):
            logger.warning("Optional-feature subscriber disconnected: %s", reason_code)

        client.on_connect = on_connect
        client.on_disconnect = on_disconnect
        client.on_message = _on_message

        host = os.getenv("MQTT_BROKER_HOST", "mqtt")
        port = int(os.getenv("MQTT_BROKER_PORT", "1883"))
        client.connect(host, port, keepalive=60)
        client.loop_start()
        _client = client


def stop_optional_subscriber() -> None:
    global _client
    with _client_lock:
        if _client is not None:
            _client.loop_stop()
            _client.disconnect()
            _client = None
