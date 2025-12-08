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
    PostSummary,
    SubmitViewRequest,
    SubmitViewResponse,
    RevokeReactionRequest,
    RevokeReactionResponse,
    SubmitReactionRequest,
    SubmitReactionResponse,
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
        # Build base query
        query = db.query(models.Post).options(joinedload(models.Post.owner))
        
        # Apply channel filter
        if request.channel == "promoted":
            query = query.filter(models.Post.promoted == True)
        elif request.channel == "user":
            # Only query player owner's posts
            query = query.filter(models.Post.owner_id == player.owner_id)
        # "all" requires no additional filter
        
        # Apply visibility filters (respect user privileges)
        is_moderator = "moderator" in player.owner.roles or "owner" in player.owner.roles
        
        if not is_moderator:
            query = query.filter(
                models.Post.visible == True,
                models.Post.hidden_by_mod == False,
                models.Post.non_conformant == False,
            )
        else:
            # Moderators see everything except non-visible
            query = query.filter(models.Post.visible == True)
        
        # Apply sorting
        if request.sort == "created_at":
            query = query.order_by(models.Post.created_at.desc())
        elif request.sort == "random":
            # Use random seed if provided for reproducible ordering
            if request.random_seed is not None:
                # PostgreSQL-specific random ordering with seed
                # Note: This is not truly reproducible across different dataset sizes
                seed_value = (request.random_seed % 1000000) / 1000000.0
                query = query.order_by(func.random())
                # Execute seed setting in a separate statement
                db.execute(f"SELECT setseed({seed_value})")
            else:
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
        
        # Build response
        post_summaries = [
            PostSummary(
                post_id=post.id,
                storage_key=post.storage_key,
                title=post.title,
                art_url=post.art_url,
                canvas=post.canvas,
                width=post.width,
                height=post.height,
                frame_count=post.frame_count,
                has_transparency=post.has_transparency,
                owner_handle=post.owner.handle,
                created_at=post.created_at,
            )
            for post in posts
        ]
        
        response = QueryPostsResponse(
            request_id=request.request_id,
            posts=post_summaries,
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
        
        logger.info(f"Sent query_posts response to player {player.player_key}: {len(post_summaries)} posts")
        
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
        view_type = ViewType.INTENTIONAL if request.view_intent == "intentional" else ViewType.LISTING
        
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
            query = query.filter(models.Comment.hidden_by_mod == False)
        
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
        comment_summaries = []
        for comment in comments:
            # Skip deleted comments without children
            # (simplified - full logic would require checking for children)
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
