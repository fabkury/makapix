"""HTTPS player RPC backend.

The request/response sibling of the MQTT player protocol
(``app.mqtt.player_requests``). A single envelope endpoint, ``POST
/player/rpc``, dispatches on ``request_type`` to the shared, transport-agnostic
handlers in ``app.services.player_rpc`` — so a request issued here returns the
same result as the equivalent MQTT request. Devices authenticate with an opaque
bearer token (see ``auth.get_current_player``).

For parity with MQTT, error responses use the protocol envelope
(``{request_id, success, error, error_code}``) and additionally carry an
accurate HTTP status.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Body, Depends
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from .. import models
from ..auth import get_current_player
from ..deps import get_db
from ..player_protocol.schemas import (
    EchoRequest,
    GetCommentsRequest,
    GetPlaysetRequest,
    GetPostRequest,
    P3AViewEvent,
    QueryPostsRequest,
    RevokeReactionRequest,
    SubmitReactionRequest,
)
from ..services import player_rpc, player_views
from ..services.player_rpc import PlayerRpcError
from ..services.rate_limit import check_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Player RPC"])

# request_type -> (request model, handler)
_DISPATCH = {
    "query_posts": (QueryPostsRequest, player_rpc.query_posts),
    "get_post": (GetPostRequest, player_rpc.get_post),
    "submit_reaction": (SubmitReactionRequest, player_rpc.submit_reaction),
    "revoke_reaction": (RevokeReactionRequest, player_rpc.revoke_reaction),
    "get_comments": (GetCommentsRequest, player_rpc.get_comments),
    "get_playset": (GetPlaysetRequest, player_rpc.get_playset),
    "echo": (EchoRequest, player_rpc.echo),
}

# request_type -> (rate-limit bucket, per-minute limit). echo is limited inside
# the service handler (10/60s), so it is intentionally absent here.
_RATE_LIMITS = {
    "query_posts": ("read", 60),
    "get_post": ("read", 60),
    "get_comments": ("read", 60),
    "get_playset": ("read", 60),
    "submit_reaction": ("react", 30),
    "revoke_reaction": ("react", 30),
}

# error_code -> HTTP status. Codes come from app.services.player_rpc and this
# router; anything unmapped is treated as a 400.
_ERROR_STATUS = {
    "invalid_request": 400,
    "invalid_json": 400,
    "unknown_request_type": 400,
    "invalid_emoji": 400,
    "missing_user_identifier": 400,
    "missing_hashtag": 400,
    "invalid_hashtag": 400,
    "invalid_criteria": 400,
    "player_key_mismatch": 403,
    "not_visible": 403,
    "not_available": 403,
    "content_not_approved": 403,
    "not_found": 404,
    "deleted": 404,
    "user_not_found": 404,
    "playset_not_found": 404,
    "unsupported_kind": 422,
    "reaction_limit_exceeded": 409,
    "rate_limited": 429,
    "rate_limit_exceeded": 429,
    "internal_error": 500,
}
_DEFAULT_ERROR_STATUS = 400


def _status_for(error_code: str | None) -> int:
    return _ERROR_STATUS.get(error_code or "", _DEFAULT_ERROR_STATUS)


def _error(
    request_id: str | None, message: str, error_code: str, status_code: int
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "request_id": request_id,
            "success": False,
            "error": message,
            "error_code": error_code,
        },
    )


@router.post("/player/rpc")
def player_rpc_endpoint(
    body: dict[str, Any] = Body(...),
    player: models.Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Dispatch a player RPC request over HTTPS.

    The body is the same object a device builds for MQTT, minus the transport
    framing: ``request_type`` selects the handler, ``request_id`` is optional
    (echoed back), and ``player_key`` — if present — must match the
    authenticated player.
    """
    request_type = body.get("request_type")
    raw_request_id = body.get("request_id")
    request_id = str(raw_request_id) if raw_request_id is not None else None

    entry = _DISPATCH.get(request_type)
    if entry is None:
        return _error(
            request_id,
            f"Unknown request type: {request_type}",
            "unknown_request_type",
            400,
        )

    # Defense in depth: a body player_key, if sent, must match the token.
    body_key = body.get("player_key")
    if body_key is not None and str(body_key) != str(player.player_key):
        return _error(
            request_id,
            "player_key does not match the authenticated player",
            "player_key_mismatch",
            403,
        )

    # Per-request-type rate limiting (echo is limited inside its handler).
    limit_cfg = _RATE_LIMITS.get(request_type)
    if limit_cfg is not None:
        bucket, limit = limit_cfg
        allowed, _ = check_rate_limit(
            f"ratelimit:player:{player.id}:rpc:{bucket}",
            limit=limit,
            window_seconds=60,
        )
        if not allowed:
            return _error(request_id, "Rate limit exceeded", "rate_limited", 429)

    model_cls, handler = entry

    # Build the typed request, injecting identity + correlation id. Identity
    # always comes from the token, never the body.
    data = dict(body)
    data["request_type"] = request_type
    data["player_key"] = player.player_key
    data["request_id"] = request_id or ""
    try:
        request_obj = model_cls(**data)
    except ValidationError as e:
        logger.info(f"Invalid {request_type} request from player {player.id}: {e}")
        return _error(request_id, "Invalid request payload", "invalid_request", 400)

    try:
        response = handler(player, request_obj, db)
    except PlayerRpcError as e:
        return _error(request_id, e.message, e.error_code, _status_for(e.error_code))
    except Exception as e:  # noqa: BLE001 - convert any failure into an envelope
        logger.error(f"Error handling {request_type}: {e}", exc_info=True)
        db.rollback()
        return _error(request_id, "Internal error", "internal_error", 500)

    content = response.model_dump(mode="json", exclude_none=True)
    # Echo the client's request_id (null when not supplied) rather than the ""
    # placeholder used to satisfy the shared request model.
    content["request_id"] = request_id

    # get_playset signals an unknown playset via success=False (not an
    # exception); map that to the appropriate status.
    if content.get("success") is False:
        return JSONResponse(
            status_code=_status_for(content.get("error_code")), content=content
        )

    return JSONResponse(status_code=200, content=content)


@router.post("/player/events/view")
def player_view_endpoint(
    body: dict[str, Any] = Body(...),
    player: models.Player = Depends(get_current_player),
    db: Session = Depends(get_db),
) -> JSONResponse:
    """Report a fire-and-forget view event (HTTPS equivalent of the MQTT view topic).

    Identity comes from the bearer token, so ``player_key`` is not part of the
    body; the HTTP status is the acknowledgement (there is no ack channel).
    """
    data = dict(body)
    data["player_key"] = str(player.player_key)
    data.pop("request_ack", None)
    try:
        event = P3AViewEvent(**data)
    except ValidationError as e:
        logger.info(f"Invalid view event from player {player.id}: {e}")
        return _error(None, "Invalid view event payload", "invalid_request", 400)

    result = player_views.record_view_event(player, event, db)

    if result.status in (player_views.RECORDED, player_views.SELF_VIEW):
        return JSONResponse(status_code=202, content={"success": True})
    if result.status == player_views.DUPLICATE:
        return JSONResponse(
            status_code=200, content={"success": True, "deduplicated": True}
        )
    if result.status == player_views.RATE_LIMITED:
        resp = JSONResponse(
            status_code=429,
            content={
                "success": False,
                "error": "Rate limited",
                "error_code": "rate_limited",
            },
        )
        if result.retry_after is not None:
            resp.headers["Retry-After"] = str(int(result.retry_after) + 1)
        return resp
    # POST_NOT_FOUND
    return JSONResponse(
        status_code=404,
        content={
            "success": False,
            "error": "Post not found",
            "error_code": "not_found",
        },
    )
