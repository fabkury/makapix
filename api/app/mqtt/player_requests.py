"""MQTT subscriber for player requests (transport adapter).

The business logic for every request type lives in
``app.services.player_rpc``; this module owns only MQTT concerns: topic
parsing, broker-side authentication by ``player_key``, the 128 KiB inbound
payload cap, response publishing, and the subscriber lifecycle. The HTTPS
backend (``app.routers.player_rpc``) is a sibling adapter over the same
service, which is what keeps the two transports behaviourally identical.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from typing import Any
from uuid import UUID

from paho.mqtt import client as mqtt_client
from pydantic import BaseModel
from sqlalchemy.orm import Session, joinedload

from .. import models
from ..db import get_session
from ..player_protocol.schemas import (
    EchoRequest,
    ErrorResponse,
    GetCommentsRequest,
    GetPlaysetRequest,
    GetPostRequest,
    QueryPostsRequest,
    RevokeReactionRequest,
    SubmitReactionRequest,
)
from ..services import player_rpc
from ..services.player_rpc import PlayerRpcError
from .publisher import publish

logger = logging.getLogger(__name__)

# Subscriber client instance
_request_client: mqtt_client.Client | None = None
_request_client_lock = threading.Lock()


def _authenticate_player(player_key: UUID, db: Session) -> models.Player | None:
    """
    Authenticate player and return player record with owner relationship.

    Args:
        player_key: Player's unique key
        db: Database session

    Returns:
        Player instance if authenticated and registered, None otherwise
    """
    player = (
        db.query(models.Player)
        .options(joinedload(models.Player.owner))
        .filter(
            models.Player.player_key == player_key,
            models.Player.registration_status == "registered",
        )
        .first()
    )

    if not player:
        logger.warning(f"Player authentication failed for key: {player_key}")
        return None

    if not player.owner:
        logger.warning(f"Player {player_key} has no owner")
        return None

    # Match the HTTP path (get_current_player -> check_user_can_authenticate):
    # a banned/deactivated owner's device must not keep operating over MQTT.
    from ..auth import user_can_authenticate

    if not user_can_authenticate(player.owner):
        logger.warning(f"Player {player_key} rejected: owner banned or deactivated")
        return None

    return player


def _send_error_response(
    player_key: UUID,
    request_id: str,
    error_message: str,
    error_code: str | None = None,
) -> None:
    """
    Send error response to player via MQTT.

    Args:
        player_key: Player's unique key
        request_id: Request ID for correlation
        error_message: Human-readable error message
        error_code: Optional error code
    """
    response_topic = f"makapix/player/{player_key}/response/{request_id}"

    error_response = ErrorResponse(
        request_id=request_id,
        error=error_message,
        error_code=error_code,
    )

    publish(
        topic=response_topic,
        payload=error_response.model_dump(mode="json"),
        qos=1,
        retain=False,
    )


MAX_MQTT_PAYLOAD_BYTES = 131072  # 128 KiB hard limit (p3a inbound buffer)


def _payload_size_bytes(payload: dict[str, Any]) -> int:
    # Minified JSON to better match the real on-wire size.
    return len(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )


def _trim_posts_payload_to_limit(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Enforce MAX_MQTT_PAYLOAD_BYTES by trimming posts from the end if needed.
    """
    if _payload_size_bytes(payload) <= MAX_MQTT_PAYLOAD_BYTES:
        return payload

    posts = payload.get("posts")
    if not isinstance(posts, list) or not posts:
        return payload

    # Binary search to find the largest prefix of posts that fits.
    low, high = 0, len(posts)
    while low < high:
        mid = (low + high + 1) // 2
        candidate = dict(payload)
        candidate["posts"] = posts[:mid]
        if _payload_size_bytes(candidate) <= MAX_MQTT_PAYLOAD_BYTES:
            low = mid
        else:
            high = mid - 1

    trimmed = dict(payload)
    trimmed["posts"] = posts[:low]
    return trimmed


def _publish_response(
    player_key: UUID,
    request_id: str,
    response: BaseModel,
    *,
    exclude_none: bool,
    trim: bool = False,
) -> None:
    """Serialize a response model and publish it to the player's response topic."""
    payload = response.model_dump(mode="json", exclude_none=exclude_none)
    if trim:
        payload = _trim_posts_payload_to_limit(payload)

    response_topic = f"makapix/player/{player_key}/response/{request_id}"
    publish(topic=response_topic, payload=payload, qos=1, retain=False)


def _run_handler(
    handler,
    player: models.Player,
    request: BaseModel,
    db: Session,
    *,
    exclude_none: bool,
    trim: bool = False,
    write: bool = False,
    err_prefix: str = "Internal error",
) -> None:
    """Invoke a player_rpc handler and publish its result over MQTT.

    Translates ``PlayerRpcError`` into an MQTT error response and falls back to
    an ``internal_error`` response for unexpected exceptions (rolling back the
    session for write operations), preserving the prior per-handler behaviour.
    """
    try:
        response = handler(player, request, db)
    except PlayerRpcError as e:
        _send_error_response(
            player.player_key, request.request_id, e.message, e.error_code
        )
        return
    except Exception as e:  # noqa: BLE001 - convert any failure into an error response
        logger.error(
            f"Error handling {getattr(request, 'request_type', '?')}: {e}",
            exc_info=True,
        )
        if write:
            db.rollback()
        _send_error_response(
            player.player_key,
            request.request_id,
            f"{err_prefix}: {e}",
            "internal_error",
        )
        return

    _publish_response(
        player.player_key,
        request.request_id,
        response,
        exclude_none=exclude_none,
        trim=trim,
    )


def _handle_query_posts(
    player: models.Player, request: QueryPostsRequest, db: Session
) -> None:
    """Handle query_posts request (MQTT adapter)."""
    _run_handler(
        player_rpc.query_posts,
        player,
        request,
        db,
        exclude_none=True,
        trim=True,
        err_prefix="Internal error processing query",
    )


def _handle_get_post(
    player: models.Player, request: GetPostRequest, db: Session
) -> None:
    """Handle get_post request (MQTT adapter)."""
    _run_handler(
        player_rpc.get_post,
        player,
        request,
        db,
        exclude_none=True,
        err_prefix="Internal error fetching post",
    )


def _handle_submit_reaction(
    player: models.Player, request: SubmitReactionRequest, db: Session
) -> None:
    """Handle submit_reaction request (MQTT adapter)."""
    _run_handler(
        player_rpc.submit_reaction,
        player,
        request,
        db,
        exclude_none=False,
        write=True,
        err_prefix="Internal error adding reaction",
    )


def _handle_revoke_reaction(
    player: models.Player, request: RevokeReactionRequest, db: Session
) -> None:
    """Handle revoke_reaction request (MQTT adapter)."""
    _run_handler(
        player_rpc.revoke_reaction,
        player,
        request,
        db,
        exclude_none=False,
        write=True,
        err_prefix="Internal error revoking reaction",
    )


def _handle_get_comments(
    player: models.Player, request: GetCommentsRequest, db: Session
) -> None:
    """Handle get_comments request (MQTT adapter)."""
    _run_handler(
        player_rpc.get_comments,
        player,
        request,
        db,
        exclude_none=False,
        err_prefix="Internal error fetching comments",
    )


def _handle_get_playset(
    player: models.Player, request: GetPlaysetRequest, db: Session
) -> None:
    """Handle get_playset request (MQTT adapter)."""
    _run_handler(
        player_rpc.get_playset,
        player,
        request,
        db,
        exclude_none=True,
        err_prefix="Internal error fetching playset",
    )


def _handle_echo(player: models.Player, request: EchoRequest, db: Session) -> None:
    """Handle echo request (MQTT adapter)."""
    _run_handler(
        player_rpc.echo,
        player,
        request,
        db,
        exclude_none=False,
        err_prefix="Internal error",
    )


def _on_request_message(
    client: mqtt_client.Client, userdata: Any, msg: mqtt_client.MQTTMessage
) -> None:
    """
    Handle incoming player request messages.

    Topic pattern: makapix/player/{player_key}/request/{request_id}
    """
    try:
        # Parse topic to extract player_key
        parts = msg.topic.split("/")
        if (
            len(parts) != 5
            or parts[0] != "makapix"
            or parts[1] != "player"
            or parts[3] != "request"
        ):
            logger.warning(f"Invalid request topic format: {msg.topic}")
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
            logger.error(f"Failed to parse request payload: {e}")
            # Try to extract player_key from topic for error response
            _send_error_response(
                player_key,
                "unknown",
                "Invalid JSON in request payload",
                "invalid_json",
            )
            return

        request_type = payload.get("request_type")
        request_id = payload.get("request_id", "unknown")

        if not request_type:
            logger.warning("Request missing request_type")
            _send_error_response(
                player_key, request_id, "Missing request_type", "invalid_request"
            )
            return

        # Authenticate player
        db: Session = next(get_session())
        try:
            player = _authenticate_player(player_key, db)

            if not player:
                _send_error_response(
                    player_key,
                    request_id,
                    "Player not authenticated or not registered",
                    "authentication_failed",
                )
                return

            # Route request to appropriate handler
            if request_type == "query_posts":
                request_obj = QueryPostsRequest(**payload)
                _handle_query_posts(player, request_obj, db)
            elif request_type == "get_post":
                request_obj = GetPostRequest(**payload)
                _handle_get_post(player, request_obj, db)
            elif request_type == "submit_reaction":
                request_obj = SubmitReactionRequest(**payload)
                _handle_submit_reaction(player, request_obj, db)
            elif request_type == "revoke_reaction":
                request_obj = RevokeReactionRequest(**payload)
                _handle_revoke_reaction(player, request_obj, db)
            elif request_type == "get_comments":
                request_obj = GetCommentsRequest(**payload)
                _handle_get_comments(player, request_obj, db)
            elif request_type == "get_playset":
                request_obj = GetPlaysetRequest(**payload)
                _handle_get_playset(player, request_obj, db)
            elif request_type == "echo":
                request_obj = EchoRequest(**payload)
                _handle_echo(player, request_obj, db)
            else:
                logger.warning(f"Unknown request_type: {request_type}")
                _send_error_response(
                    player_key,
                    request_id,
                    f"Unknown request type: {request_type}",
                    "unknown_request_type",
                )

        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            _send_error_response(
                player_key,
                request_id,
                f"Internal error: {str(e)}",
                "internal_error",
            )
        finally:
            db.close()

    except Exception as e:
        logger.error(f"Unexpected error in request handler: {e}", exc_info=True)


def start_request_subscriber() -> None:
    """Start MQTT subscriber for player requests."""
    global _request_client

    with _request_client_lock:
        if _request_client is not None and _request_client.is_connected():
            logger.info("Request subscriber already running")
            return

        try:
            client = mqtt_client.Client(
                callback_api_version=mqtt_client.CallbackAPIVersion.VERSION2,
                client_id=f"player-request-subscriber-{os.getpid()}",
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
                    logger.info("Player request subscriber connected to MQTT broker")
                    # Subscribe to all player request topics
                    client.subscribe("makapix/player/+/request/+", qos=1)
                    logger.info("Subscribed to makapix/player/+/request/+")
                else:
                    logger.error(f"Request subscriber connection failed: {reason_code}")

            def on_disconnect(
                client, userdata, disconnect_flags, reason_code, properties
            ):
                logger.warning(f"Request subscriber disconnected: {reason_code}")

            client.on_connect = on_connect
            client.on_disconnect = on_disconnect
            client.on_message = _on_request_message

            # Use internal port 1883
            host = os.getenv("MQTT_BROKER_HOST", "mqtt")
            port = int(os.getenv("MQTT_BROKER_PORT", "1883"))

            logger.info(f"Connecting request subscriber to {host}:{port}")
            client.connect(host, port, keepalive=60)
            client.loop_start()

            _request_client = client
            logger.info("Player request subscriber started")

        except Exception as e:
            logger.error(f"Failed to start request subscriber: {e}", exc_info=True)


def stop_request_subscriber() -> None:
    """Stop MQTT subscriber for player requests."""
    global _request_client

    with _request_client_lock:
        if _request_client:
            _request_client.loop_stop()
            _request_client.disconnect()
            _request_client = None
            logger.info("Player request subscriber stopped")
