"""MQTT subscriber for player requests and request handlers."""

from __future__ import annotations

import json
import logging
import os
import random
import threading
from typing import Any
from uuid import UUID

from paho.mqtt import client as mqtt_client
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..db import get_session
from .. import models
from .publisher import publish
from .schemas import (
    QueryPostsRequest,
    QueryPostsResponse,
    ArtworkPostPayload,
    PlaylistArtworkPayload,
    PlaylistPostPayload,
    PlayerPostPayload,
    SubmitViewRequest,
    SubmitViewResponse,
    RevokeReactionRequest,
    RevokeReactionResponse,
    SubmitReactionRequest,
    SubmitReactionResponse,
    GetPostRequest,
    GetPostResponse,
    GetCommentsRequest,
    GetCommentsResponse,
    CommentSummary,
    ErrorResponse,
)

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
MAX_PLAYLIST_ARTWORKS = 1024
DEFAULT_DWELL_MS = 30000


def _payload_size_bytes(payload: dict[str, Any]) -> int:
    # Minified JSON to better match the real on-wire size.
    return len(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8"))


def _build_artwork_payload(post: models.Post) -> ArtworkPostPayload:
    return ArtworkPostPayload(
        post_id=post.id,
        kind="artwork",
        owner_handle=post.owner.handle,
        created_at=post.created_at,
        metadata_modified_at=post.metadata_modified_at,
        storage_key=str(post.storage_key),
        art_url=post.art_url or "",
        canvas=post.canvas or "",
        width=int(post.width or 0),
        height=int(post.height or 0),
        frame_count=int(post.frame_count or 1),
        # NOTE: Player firmware protocol currently expects `has_transparency`.
        # We map it from the new backend metadata field for backward compatibility.
        has_transparency=bool(getattr(post, "uses_transparency", False)),
        artwork_modified_at=post.artwork_modified_at,
        dwell_time_ms=int(getattr(post, "dwell_time_ms", DEFAULT_DWELL_MS) or DEFAULT_DWELL_MS),
    )


def _build_playlist_payload(
    playlist_post: models.Post,
    db: Session,
    pe: int,
) -> PlaylistPostPayload:
    # Total artworks is the full playlist size, irrespective of truncation.
    total_artworks = (
        db.query(func.count(models.PlaylistItem.id))
        .filter(models.PlaylistItem.playlist_post_id == playlist_post.id)
        .scalar()
        or 0
    )

    # Determine how many items to include for this request.
    if pe == 0:
        include_limit = MAX_PLAYLIST_ARTWORKS
    else:
        include_limit = max(0, min(int(pe), MAX_PLAYLIST_ARTWORKS))

    item_rows = (
        db.query(models.PlaylistItem.artwork_post_id, models.PlaylistItem.dwell_time_ms)
        .filter(models.PlaylistItem.playlist_post_id == playlist_post.id)
        .order_by(models.PlaylistItem.position.asc())
        .limit(include_limit)
        .all()
    )
    artwork_ids_in_order = [pid for (pid, _d) in item_rows]
    dwell_by_post_id: dict[int, int] = {
        int(pid): int(d or DEFAULT_DWELL_MS) for (pid, d) in item_rows
    }

    artworks: list[PlaylistArtworkPayload] = []
    if artwork_ids_in_order:
        artwork_posts = (
            db.query(models.Post)
            .options(joinedload(models.Post.owner))
            .filter(models.Post.id.in_(artwork_ids_in_order))
            .all()
        )
        by_id: dict[int, models.Post] = {p.id: p for p in artwork_posts}

        for pid in artwork_ids_in_order:
            p = by_id.get(pid)
            if not p:
                continue
            # Apply the same visibility constraints as for top-level posts later.
            if not p.visible or p.hidden_by_user or p.hidden_by_mod or p.non_conformant:
                continue
            if p.kind != "artwork":
                continue

            artworks.append(
                PlaylistArtworkPayload(
                    post_id=p.id,
                    storage_key=str(p.storage_key),
                    art_url=p.art_url or "",
                    canvas=p.canvas or "",
                    width=int(p.width or 0),
                    height=int(p.height or 0),
                    frame_count=int(p.frame_count or 1),
                    # NOTE: Player firmware protocol currently expects `has_transparency`.
                    # We map it from the new backend metadata field for backward compatibility.
                    has_transparency=bool(getattr(p, "uses_transparency", False)),
                    owner_handle=p.owner.handle,
                    created_at=p.created_at,
                    metadata_modified_at=p.metadata_modified_at,
                    artwork_modified_at=p.artwork_modified_at,
                    dwell_time_ms=dwell_by_post_id.get(p.id, int(getattr(p, "dwell_time_ms", DEFAULT_DWELL_MS) or DEFAULT_DWELL_MS)),
                )
            )

    return PlaylistPostPayload(
        post_id=playlist_post.id,
        kind="playlist",
        owner_handle=playlist_post.owner.handle,
        created_at=playlist_post.created_at,
        metadata_modified_at=playlist_post.metadata_modified_at,
        total_artworks=int(total_artworks),
        dwell_time_ms=int(getattr(playlist_post, "dwell_time_ms", DEFAULT_DWELL_MS) or DEFAULT_DWELL_MS),
        artworks=artworks,
    )


def _trim_posts_payload_to_limit(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Enforce MAX_MQTT_PAYLOAD_BYTES.

    Primary trimming mechanism (per requirements):
    - Only trim by removing individual artworks from playlist posts (preserving play order),
      using binary search to find the largest prefix of playlist artworks that fits.

    Fallback:
    - If payload is still too large even with 0 playlist artworks, trim posts from the end.
    """
    if _payload_size_bytes(payload) <= MAX_MQTT_PAYLOAD_BYTES:
        return payload

    posts = payload.get("posts")
    if isinstance(posts, list):
        # Build flattened playlist-artwork index in play order (posts order, then playlist order).
        flat: list[tuple[int, int]] = []
        for pi, post in enumerate(posts):
            if isinstance(post, dict) and post.get("kind") == "playlist":
                artworks = post.get("artworks") or []
                if isinstance(artworks, list):
                    for ai in range(len(artworks)):
                        flat.append((pi, ai))

        if flat:
            original_artworks_by_post: dict[int, list[Any]] = {}
            for pi, post in enumerate(posts):
                if isinstance(post, dict) and post.get("kind") == "playlist":
                    artworks = post.get("artworks") or []
                    if isinstance(artworks, list):
                        original_artworks_by_post[pi] = artworks

            def build_with_prefix(n: int) -> dict[str, Any]:
                keep_counts: dict[int, int] = {}
                for (pi, ai) in flat[:n]:
                    keep_counts[pi] = max(keep_counts.get(pi, 0), ai + 1)

                new_posts: list[Any] = []
                for pi, post in enumerate(posts):
                    if isinstance(post, dict) and post.get("kind") == "playlist":
                        new_post = dict(post)
                        orig_artworks = original_artworks_by_post.get(pi, [])
                        k = keep_counts.get(pi, 0)
                        new_post["artworks"] = orig_artworks[:k]
                        new_posts.append(new_post)
                    else:
                        new_posts.append(post)

                new_payload = dict(payload)
                new_payload["posts"] = new_posts
                return new_payload

            low, high = 0, len(flat)
            while low < high:
                mid = (low + high + 1) // 2
                candidate = build_with_prefix(mid)
                if _payload_size_bytes(candidate) <= MAX_MQTT_PAYLOAD_BYTES:
                    low = mid
                else:
                    high = mid - 1

            payload = build_with_prefix(low)

    # Fallback: if still too large, drop posts from the end (best effort).
    if _payload_size_bytes(payload) <= MAX_MQTT_PAYLOAD_BYTES:
        return payload

    posts = payload.get("posts")
    if not isinstance(posts, list) or not posts:
        return payload

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


def _handle_query_posts(
    player: models.Player,
    request: QueryPostsRequest,
    db: Session,
) -> None:
    """
    Handle query_posts request.
    
    Args:
        player: Authenticated player instance
        request: Parsed request
        db: Database session
    """
    try:
        pe = request.PE if request.PE is not None else 1

        # Build base query (include both artwork and playlist posts)
        query = db.query(models.Post).options(joinedload(models.Post.owner)).filter(
            models.Post.kind.in_(["artwork", "playlist"])
        )
        
        # Apply channel filter
        if request.channel == "promoted":
            query = query.filter(models.Post.promoted.is_(True))
        elif request.channel == "user":
            # Only query player owner's posts
            query = query.filter(models.Post.owner_id == player.owner_id)
        elif request.channel == "by_user":
            # Query arbitrary user's posts by handle or sqid
            target_user = None
            if request.user_handle:
                target_user = db.query(models.User).filter(models.User.handle == request.user_handle).first()
            elif request.user_sqid:
                target_user = db.query(models.User).filter(models.User.public_sqid == request.user_sqid).first()
            else:
                _send_error_response(
                    player.player_key,
                    request.request_id,
                    "user_handle or user_sqid is required when channel='by_user'",
                    "missing_user_identifier",
                )
                return
            
            if not target_user:
                identifier = request.user_handle or request.user_sqid
                _send_error_response(
                    player.player_key,
                    request.request_id,
                    f"User '{identifier}' not found",
                    "user_not_found",
                )
                return
            
            query = query.filter(models.Post.owner_id == target_user.id)
        elif request.channel == "hashtag":
            # Query posts by hashtag
            if not request.hashtag:
                _send_error_response(
                    player.player_key,
                    request.request_id,
                    "hashtag is required when channel='hashtag'",
                    "missing_hashtag",
                )
                return
            
            # Normalize hashtag (lowercase, strip) to match how they're stored
            hashtag_normalized = request.hashtag.strip().lower()
            if not hashtag_normalized:
                _send_error_response(
                    player.player_key,
                    request.request_id,
                    "hashtag cannot be empty",
                    "invalid_hashtag",
                )
                return
            
            query = query.filter(models.Post.hashtags.contains([hashtag_normalized]))
        elif request.channel == "artwork":
            # Protocol compatibility: do not exclude playlists (per server policy).
            pass
        # "all" requires no additional filter
        
        # Apply visibility filters (respect user privileges)
        is_moderator = "moderator" in player.owner.roles or "owner" in player.owner.roles
        
        if not is_moderator:
            query = query.filter(
                models.Post.visible,
                ~models.Post.hidden_by_user,
                ~models.Post.hidden_by_mod,
                ~models.Post.non_conformant,
            )
        else:
            # Moderators see everything except non-visible
            query = query.filter(models.Post.visible, ~models.Post.hidden_by_user)
        
        # Apply sorting
        if request.sort == "created_at":
            query = query.order_by(models.Post.created_at.desc())
        elif request.sort == "random":
            # Use random seed if provided for reproducible ordering
            if request.random_seed is not None:
                # PostgreSQL-specific random ordering with seed
                # Use parameterized query to prevent SQL injection
                from sqlalchemy import text
                seed_value = (request.random_seed % 1000000) / 1000000.0
                db.execute(text("SELECT setseed(:seed)"), {"seed": seed_value})
            query = query.order_by(func.random())
        else:
            # "server_order" - use id order (insertion order)
            query = query.order_by(models.Post.id.desc())
        
        # Apply cursor pagination if provided
        # For simplicity, using offset-based pagination encoded as cursor
        offset = 0
        if request.cursor:
            try:
                offset = int(request.cursor)
            except ValueError:
                logger.warning(f"Invalid cursor: {request.cursor}")
        
        query = query.offset(offset).limit(request.limit + 1)  # +1 to check if more
        
        # Execute query
        posts = query.all()
        
        # Check if there are more results
        has_more = len(posts) > request.limit
        if has_more:
            posts = posts[:request.limit]
        
        # Calculate next cursor
        next_cursor = None
        if has_more:
            next_cursor = str(offset + request.limit)
        
        # Build response payload posts
        payload_posts: list[PlayerPostPayload] = []
        for post in posts:
            if post.kind == "artwork":
                payload_posts.append(_build_artwork_payload(post))
            elif post.kind == "playlist":
                payload_posts.append(_build_playlist_payload(post, db, pe))
        
        response = QueryPostsResponse(
            request_id=request.request_id,
            posts=payload_posts,
            next_cursor=next_cursor,
            has_more=has_more,
        )
        
        # Enforce payload size limit (128KiB)
        response_dict = response.model_dump(mode="json")
        response_dict = _trim_posts_payload_to_limit(response_dict)

        # Send response
        response_topic = f"makapix/player/{player.player_key}/response/{request.request_id}"
        publish(
            topic=response_topic,
            payload=response_dict,
            qos=1,
            retain=False,
        )
        
        logger.info(f"Sent query_posts response to player {player.player_key}: {len(payload_posts)} posts")
        
    except Exception as e:
        logger.error(f"Error handling query_posts: {e}", exc_info=True)
        _send_error_response(
            player.player_key,
            request.request_id,
            f"Internal error processing query: {str(e)}",
            "internal_error",
        )


def _handle_submit_view(
    player: models.Player,
    request: SubmitViewRequest,
    db: Session,
) -> None:
    """
    Handle submit_view request.
    
    Args:
        player: Authenticated player instance
        request: Parsed request
        db: Database session
    """
    try:
        # Check if post exists
        post = db.query(models.Post).filter(models.Post.id == request.post_id).first()
        
        if not post:
            _send_error_response(
                player.player_key,
                request.request_id,
                f"Post {request.post_id} not found",
                "not_found",
            )
            return
        
        # Don't record view if player owner is the post owner
        if player.owner_id == post.owner_id:
            # Still send success response, but don't record
            response = SubmitViewResponse(request_id=request.request_id)
            response_topic = f"makapix/player/{player.player_key}/response/{request.request_id}"
            publish(
                topic=response_topic,
                payload=response.model_dump(mode="json"),
                qos=1,
                retain=False,
            )
            logger.debug(f"Skipped view recording for post {request.post_id} - player owner is post owner")
            return
        
        # Import view tracking utilities
        from ..utils.view_tracking import ViewType, ViewSource, hash_ip
        from ..geoip import get_country_code
        from ..tasks import write_view_event
        from datetime import datetime, timezone
        
        # Map view_intent to view_type
        if request.view_intent == "intentional":
            view_type = ViewType.INTENTIONAL
        elif request.view_intent == "automated":
            view_type = ViewType.LISTING
        else:
            # Default to LISTING for unexpected values
            logger.warning(f"Unexpected view_intent value: {request.view_intent}, defaulting to LISTING")
            view_type = ViewType.LISTING
        
        # Create view event data
        # For player views, we use a synthetic IP hash based on player_key
        player_ip_hash = hash_ip(f"player:{player.player_key}")
        
        event_data = {
            "post_id": str(request.post_id),
            "viewer_user_id": str(player.owner_id),
            "viewer_ip_hash": player_ip_hash,
            "country_code": None,  # Players don't have geographic info
            "device_type": "player",
            "view_source": ViewSource.PLAYER.value,
            "view_type": view_type.value,
            "user_agent_hash": None,  # Players don't have user agents
            "referrer_domain": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Dispatch to Celery for async write
        write_view_event.delay(event_data)
        
        # Send success response
        response = SubmitViewResponse(request_id=request.request_id)
        response_topic = f"makapix/player/{player.player_key}/response/{request.request_id}"
        publish(
            topic=response_topic,
            payload=response.model_dump(mode="json"),
            qos=1,
            retain=False,
        )
        
        logger.info(f"Recorded view for post {request.post_id} from player {player.player_key}")
        
    except Exception as e:
        logger.error(f"Error handling submit_view: {e}", exc_info=True)
        _send_error_response(
            player.player_key,
            request.request_id,
            f"Internal error recording view: {str(e)}",
            "internal_error",
        )


def _handle_get_post(
    player: models.Player,
    request: GetPostRequest,
    db: Session,
) -> None:
    """Handle get_post request."""
    try:
        pe = request.PE if request.PE is not None else 1

        post = (
            db.query(models.Post)
            .options(joinedload(models.Post.owner))
            .filter(models.Post.id == request.post_id)
            .first()
        )
        if not post:
            _send_error_response(
                player.player_key,
                request.request_id,
                f"Post {request.post_id} not found",
                "not_found",
            )
            return

        # Visibility (same logic as query_posts)
        is_moderator = "moderator" in player.owner.roles or "owner" in player.owner.roles
        if not post.visible:
            _send_error_response(
                player.player_key,
                request.request_id,
                "Post is not visible",
                "not_visible",
            )
            return
        if post.hidden_by_user:
            _send_error_response(
                player.player_key,
                request.request_id,
                "Post is not available",
                "not_available",
            )
            return
        if not is_moderator and (post.hidden_by_mod or post.non_conformant):
            _send_error_response(
                player.player_key,
                request.request_id,
                "Post is not available",
                "not_available",
            )
            return

        if post.kind == "artwork":
            payload_post: PlayerPostPayload = _build_artwork_payload(post)
        elif post.kind == "playlist":
            payload_post = _build_playlist_payload(post, db, pe)
        else:
            _send_error_response(
                player.player_key,
                request.request_id,
                f"Unsupported post kind: {post.kind}",
                "unsupported_kind",
            )
            return

        response = GetPostResponse(
            request_id=request.request_id,
            success=True,
            post=payload_post,
        )

        response_dict = response.model_dump(mode="json")

        # Enforce payload size limit. For get_post, only playlist artworks can be trimmed.
        if _payload_size_bytes(response_dict) > MAX_MQTT_PAYLOAD_BYTES and isinstance(response_dict.get("post"), dict):
            post_dict = response_dict["post"]
            if post_dict.get("kind") == "playlist":
                # Reuse the same trimming logic by wrapping in posts list.
                wrapped = {"posts": [post_dict]}
                wrapped = _trim_posts_payload_to_limit(wrapped)
                response_dict["post"] = wrapped["posts"][0]

        response_topic = f"makapix/player/{player.player_key}/response/{request.request_id}"
        publish(
            topic=response_topic,
            payload=response_dict,
            qos=1,
            retain=False,
        )
    except Exception as e:
        logger.error(f"Error handling get_post: {e}", exc_info=True)
        _send_error_response(
            player.player_key,
            request.request_id,
            f"Internal error fetching post: {str(e)}",
            "internal_error",
        )

def _handle_submit_reaction(
    player: models.Player,
    request: SubmitReactionRequest,
    db: Session,
) -> None:
    """
    Handle submit_reaction request.
    
    Args:
        player: Authenticated player instance
        request: Parsed request
        db: Database session
    """
    try:
        # Validate emoji (basic validation)
        emoji = request.emoji.strip()
        if not emoji or len(emoji) > 20:
            _send_error_response(
                player.player_key,
                request.request_id,
                "Invalid emoji format",
                "invalid_emoji",
            )
            return
        
        # Check if post exists
        post = db.query(models.Post).filter(models.Post.id == request.post_id).first()
        
        if not post:
            _send_error_response(
                player.player_key,
                request.request_id,
                f"Post {request.post_id} not found",
                "not_found",
            )
            return
        
        # Check if reaction already exists (idempotent)
        existing = (
            db.query(models.Reaction)
            .filter(
                models.Reaction.post_id == request.post_id,
                models.Reaction.user_id == player.owner_id,
                models.Reaction.emoji == emoji,
            )
            .first()
        )
        
        if existing:
            # Already exists, return success
            response = SubmitReactionResponse(request_id=request.request_id)
            response_topic = f"makapix/player/{player.player_key}/response/{request.request_id}"
            publish(
                topic=response_topic,
                payload=response.model_dump(mode="json"),
                qos=1,
                retain=False,
            )
            logger.debug(f"Reaction already exists for post {request.post_id}")
            return
        
        # Check reaction limit (max 5 per user per post)
        reaction_count = (
            db.query(func.count(models.Reaction.id))
            .filter(
                models.Reaction.post_id == request.post_id,
                models.Reaction.user_id == player.owner_id,
            )
            .scalar()
        )
        
        if reaction_count >= 5:
            _send_error_response(
                player.player_key,
                request.request_id,
                "Maximum 5 reactions per post exceeded",
                "reaction_limit_exceeded",
            )
            return
        
        # Create reaction
        reaction = models.Reaction(
            post_id=request.post_id,
            user_id=player.owner_id,
            emoji=emoji,
        )
        db.add(reaction)
        db.commit()
        
        # Send success response
        response = SubmitReactionResponse(request_id=request.request_id)
        response_topic = f"makapix/player/{player.player_key}/response/{request.request_id}"
        publish(
            topic=response_topic,
            payload=response.model_dump(mode="json"),
            qos=1,
            retain=False,
        )
        
        logger.info(f"Added reaction '{emoji}' to post {request.post_id} from player {player.player_key}")
        
    except Exception as e:
        logger.error(f"Error handling submit_reaction: {e}", exc_info=True)
        db.rollback()
        _send_error_response(
            player.player_key,
            request.request_id,
            f"Internal error adding reaction: {str(e)}",
            "internal_error",
        )


def _handle_revoke_reaction(
    player: models.Player,
    request: RevokeReactionRequest,
    db: Session,
) -> None:
    """
    Handle revoke_reaction request.
    
    Args:
        player: Authenticated player instance
        request: Parsed request
        db: Database session
    """
    try:
        # Find and delete reaction
        reaction = (
            db.query(models.Reaction)
            .filter(
                models.Reaction.post_id == request.post_id,
                models.Reaction.user_id == player.owner_id,
                models.Reaction.emoji == request.emoji.strip(),
            )
            .first()
        )
        
        if reaction:
            db.delete(reaction)
            db.commit()
            logger.info(f"Revoked reaction '{request.emoji}' from post {request.post_id} for player {player.player_key}")
        else:
            # Idempotent - return success even if reaction didn't exist
            logger.debug(f"No reaction to revoke for post {request.post_id}")
        
        # Send success response
        response = RevokeReactionResponse(request_id=request.request_id)
        response_topic = f"makapix/player/{player.player_key}/response/{request.request_id}"
        publish(
            topic=response_topic,
            payload=response.model_dump(mode="json"),
            qos=1,
            retain=False,
        )
        
    except Exception as e:
        logger.error(f"Error handling revoke_reaction: {e}", exc_info=True)
        db.rollback()
        _send_error_response(
            player.player_key,
            request.request_id,
            f"Internal error revoking reaction: {str(e)}",
            "internal_error",
        )


def _handle_get_comments(
    player: models.Player,
    request: GetCommentsRequest,
    db: Session,
) -> None:
    """
    Handle get_comments request.
    
    Args:
        player: Authenticated player instance
        request: Parsed request
        db: Database session
    """
    try:
        # Build query
        query = (
            db.query(models.Comment)
            .options(joinedload(models.Comment.author))
            .filter(models.Comment.post_id == request.post_id)
        )
        
        # Filter by moderation status
        is_moderator = "moderator" in player.owner.roles or "owner" in player.owner.roles
        if not is_moderator:
            query = query.filter(~models.Comment.hidden_by_mod)
        
        # Filter by depth (max 2)
        query = query.filter(models.Comment.depth <= 2)
        
        # Order by creation time
        query = query.order_by(models.Comment.created_at.asc())
        
        # Apply cursor pagination
        offset = 0
        if request.cursor:
            try:
                offset = int(request.cursor)
            except ValueError:
                logger.warning(f"Invalid cursor: {request.cursor}")
        
        query = query.offset(offset).limit(request.limit + 1)  # +1 to check if more
        
        # Execute query
        comments = query.all()
        
        # Check if there are more results
        has_more = len(comments) > request.limit
        if has_more:
            comments = comments[:request.limit]
        
        # Calculate next cursor
        next_cursor = None
        if has_more:
            next_cursor = str(offset + request.limit)
        
        # Build comment summaries
        # Note: Deleted comments are filtered in a simplified way here.
        # A full implementation would require checking if deleted comments have children
        # and preserving them in the tree structure with modified content.
        comment_summaries = []
        for comment in comments:
            # Skip deleted comments (simplified filtering)
            # In a full implementation, we would:
            # 1. Build a parent-child map
            # 2. Keep deleted comments that have non-deleted children
            # 3. Mark deleted comments with a placeholder message
            if comment.deleted_by_owner:
                continue
            
            comment_summaries.append(
                CommentSummary(
                    comment_id=comment.id,
                    post_id=comment.post_id,
                    author_handle=comment.author.handle if comment.author else None,
                    body=comment.body,
                    depth=comment.depth,
                    parent_id=comment.parent_id,
                    created_at=comment.created_at,
                    deleted=comment.deleted_by_owner,
                )
            )
        
        # Build response
        response = GetCommentsResponse(
            request_id=request.request_id,
            comments=comment_summaries,
            next_cursor=next_cursor,
            has_more=has_more,
        )
        
        # Send response
        response_topic = f"makapix/player/{player.player_key}/response/{request.request_id}"
        publish(
            topic=response_topic,
            payload=response.model_dump(mode="json"),
            qos=1,
            retain=False,
        )
        
        logger.info(f"Sent comments response to player {player.player_key}: {len(comment_summaries)} comments")
        
    except Exception as e:
        logger.error(f"Error handling get_comments: {e}", exc_info=True)
        _send_error_response(
            player.player_key,
            request.request_id,
            f"Internal error fetching comments: {str(e)}",
            "internal_error",
        )


def _on_request_message(client: mqtt_client.Client, userdata: Any, msg: mqtt_client.MQTTMessage) -> None:
    """
    Handle incoming player request messages.
    
    Topic pattern: makapix/player/{player_key}/request/{request_id}
    """
    try:
        # Parse topic to extract player_key
        parts = msg.topic.split("/")
        if len(parts) != 5 or parts[0] != "makapix" or parts[1] != "player" or parts[3] != "request":
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
            _send_error_response(player_key, request_id, "Missing request_type", "invalid_request")
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
            elif request_type == "submit_view":
                request_obj = SubmitViewRequest(**payload)
                _handle_submit_view(player, request_obj, db)
            elif request_type == "submit_reaction":
                request_obj = SubmitReactionRequest(**payload)
                _handle_submit_reaction(player, request_obj, db)
            elif request_type == "revoke_reaction":
                request_obj = RevokeReactionRequest(**payload)
                _handle_revoke_reaction(player, request_obj, db)
            elif request_type == "get_comments":
                request_obj = GetCommentsRequest(**payload)
                _handle_get_comments(player, request_obj, db)
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
            
            def on_disconnect(client, userdata, disconnect_flags, reason_code, properties):
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
