"""Player management and control endpoints."""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user, require_ownership
from ..deps import get_db
from ..sqids_config import decode_user_sqid


def get_user_by_sqid(sqid: str, db: Session) -> models.User:
    """
    Look up a user by their public sqid.

    Raises 404 if user not found or sqid invalid.
    """
    user_id = decode_user_sqid(sqid)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    user = db.query(models.User).filter(models.User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user


from ..mqtt.cert_generator import (
    disconnect_mqtt_client,
    generate_client_certificate,
    load_ca_certificate,
    revoke_certificate,
)
from ..mqtt.player_commands import log_command, publish_player_command
from ..services.playset import PlaysetService
from ..services.rate_limit import check_rate_limit
from ..utils.registration import generate_registration_code


def get_client_ip(request: Request) -> str:
    """
    Extract client IP address from request, handling proxies.

    Checks X-Forwarded-For header first (for reverse proxy setups),
    then falls back to direct client IP.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host
    return "unknown"


router = APIRouter(tags=["Players"])

# Constants
MAX_PLAYERS_PER_USER = 128
REGISTRATION_CODE_EXPIRY_MINUTES = 15
CERT_VALIDITY_DAYS = 365
CERT_RENEWAL_THRESHOLD_DAYS = 30


@router.post(
    "/player/provision",
    response_model=schemas.PlayerProvisionResponse,
    status_code=status.HTTP_201_CREATED,
)
def provision_player(
    payload: schemas.PlayerProvisionRequest,
    db: Session = Depends(get_db),
) -> schemas.PlayerProvisionResponse:
    """
    Provision a new player (device calls this).

    Returns player_key and 6-character registration code that expires in 15 minutes.
    """
    from uuid import uuid4

    player_key = uuid4()
    registration_code = generate_registration_code()
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=REGISTRATION_CODE_EXPIRY_MINUTES
    )

    # Create player record
    player = models.Player(
        player_key=player_key,
        device_model=payload.device_model,
        firmware_version=payload.firmware_version,
        registration_status="pending",
        registration_code=registration_code,
        registration_code_expires_at=expires_at,
    )
    db.add(player)
    db.commit()
    db.refresh(player)

    # Get MQTT broker info
    broker_host = os.getenv("MQTT_PUBLIC_HOST", "development.makapix.club")
    broker_port = int(os.getenv("MQTT_PUBLIC_PORT", "8884"))

    return schemas.PlayerProvisionResponse(
        player_key=player_key,
        registration_code=registration_code,
        registration_code_expires_at=expires_at,
        mqtt_broker={"host": broker_host, "port": broker_port},
    )


@router.post(
    "/player/register",
    response_model=schemas.PlayerPublic,
    status_code=status.HTTP_201_CREATED,
)
def register_player(
    payload: schemas.PlayerRegisterRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.PlayerPublic:
    """
    Register a player to the current user's account.

    Validates registration code and assigns ownership.
    Enforces 128 player limit per user.
    """
    # Check player limit
    player_count = (
        db.query(models.Player)
        .filter(models.Player.owner_id == current_user.id)
        .count()
    )
    if player_count >= MAX_PLAYERS_PER_USER:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_PLAYERS_PER_USER} players allowed per user",
        )

    # Find player by registration code
    now = datetime.now(timezone.utc)
    player = (
        db.query(models.Player)
        .filter(
            models.Player.registration_code == payload.registration_code.upper(),
            models.Player.registration_status == "pending",
            models.Player.registration_code_expires_at > now,
        )
        .first()
    )

    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Invalid or expired registration code",
        )

    # Check if already registered
    if player.owner_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Player already registered",
        )

    # Register player
    player.owner_id = current_user.id
    player.name = payload.name
    player.registration_status = "registered"
    player.registered_at = now
    player.registration_code = None  # Clear code after registration
    player.registration_code_expires_at = None

    # Add player_key to MQTT password file (empty password for username-only auth)
    passwd_file = os.getenv("MQTT_PASSWD_FILE", "/mqtt-config/passwords")

    # Validate password file path to prevent path traversal
    # Use pathlib to resolve the path and ensure it's within allowed directories
    from pathlib import Path

    try:
        passwd_file_path = Path(passwd_file).resolve()
        allowed_passwd_dirs = [
            Path("/mqtt-config").resolve(),
            Path("/mosquitto/config").resolve(),
        ]

        # Check if resolved path is within any allowed directory
        is_valid = any(
            passwd_file_path.is_relative_to(allowed_dir)
            for allowed_dir in allowed_passwd_dirs
        )

        if not is_valid:
            import logging

            logger = logging.getLogger(__name__)
            logger.error(f"Invalid MQTT password file path: {passwd_file_path}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Invalid MQTT configuration",
            )

        # Use the validated resolved path
        passwd_file = str(passwd_file_path)
    except (ValueError, OSError) as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"Path validation error for MQTT password file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid MQTT configuration",
        )

    # Validate player_key is a valid UUID (additional safety check)
    try:
        str(player.player_key)
    except (ValueError, AttributeError):
        import logging

        logger = logging.getLogger(__name__)
        logger.error("Invalid player_key format")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Invalid player configuration",
        )

    try:
        subprocess.run(
            ["mosquitto_passwd", "-b", passwd_file, str(player.player_key), ""],
            check=True,
            capture_output=True,
            timeout=5,  # Add timeout to prevent hanging
        )
    except subprocess.CalledProcessError as e:
        # Log error but don't fail registration - password file might not exist yet
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to add player_key to MQTT password file: {e}")
    except FileNotFoundError:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning("mosquitto_passwd not found - ensure MQTT broker is configured")

    # Generate and store TLS certificates (CN = player_key for mTLS)
    ca_cert_path = os.getenv("MQTT_CA_FILE", "/certs/ca.crt")
    ca_key_path = os.getenv("MQTT_CA_KEY_FILE", "/certs/ca.key")
    try:
        cert_pem, key_pem, serial_number = generate_client_certificate(
            player_key=player.player_key,
            ca_cert_path=ca_cert_path,
            ca_key_path=ca_key_path,
            cert_validity_days=CERT_VALIDITY_DAYS,
        )
        player.cert_pem = cert_pem
        player.key_pem = key_pem
        player.cert_serial_number = serial_number
        player.cert_issued_at = now
        player.cert_expires_at = now + timedelta(days=CERT_VALIDITY_DAYS)
    except FileNotFoundError as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.error(f"CA certificate files not found: {e}")
        # Don't fail registration if certs can't be generated
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Failed to generate player certificate")
        # Don't fail registration if certs can't be generated

    db.commit()
    db.refresh(player)

    # Log the device registration as a special "add_device" command
    log_command(
        db=db,
        player_id=player.id,
        command_type="add_device",
        payload={
            "player_key": str(player.player_key),
            "owner_id": str(current_user.id),
            "owner_handle": current_user.handle,
            "device_name": player.name,
            "device_model": player.device_model,
            "firmware_version": player.firmware_version,
        },
    )

    return schemas.PlayerPublic.model_validate(player)


@router.get("/player/{player_key}/credentials", response_model=schemas.TLSCertBundle)
def get_player_credentials(
    player_key: UUID,
    request: Request,
    db: Session = Depends(get_db),
) -> schemas.TLSCertBundle:
    """
    Device calls this to get credentials after registration completes.

    No authentication required - player_key serves as authentication.
    """
    # Rate limiting: 20 credential requests per minute per IP
    client_ip = get_client_ip(request)
    rate_limit_key = f"ratelimit:player_creds:{client_ip}"
    allowed, _ = check_rate_limit(rate_limit_key, limit=20, window_seconds=60)

    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many credential requests. Please try again later.",
        )

    player = (
        db.query(models.Player)
        .filter(
            models.Player.player_key == player_key,
            models.Player.registration_status == "registered",
        )
        .first()
    )

    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found or not registered",
        )

    if not player.cert_pem or not player.key_pem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificates not available for this player",
        )

    # Load CA certificate
    ca_cert_path = os.getenv("MQTT_CA_FILE", "/certs/ca.crt")
    try:
        ca_pem = load_ca_certificate(ca_cert_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CA certificate not found",
        )

    # Get MQTT broker info
    broker_host = os.getenv("MQTT_PUBLIC_HOST", "development.makapix.club")
    broker_port = int(os.getenv("MQTT_PUBLIC_PORT", "8884"))

    return schemas.TLSCertBundle(
        ca_pem=ca_pem,
        cert_pem=player.cert_pem,
        key_pem=player.key_pem,
        broker={"host": broker_host, "port": broker_port},
    )


@router.get("/u/{sqid}/player", response_model=dict[str, list[schemas.PlayerPublic]])
def list_players(
    sqid: str,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> dict[str, list[schemas.PlayerPublic]]:
    """List all players for a user."""
    user = get_user_by_sqid(sqid, db)
    require_ownership(user.id, current_user)

    players = db.query(models.Player).filter(models.Player.owner_id == user.id).all()

    return {"items": [schemas.PlayerPublic.model_validate(p) for p in players]}


@router.get("/u/{sqid}/player/{player_id}", response_model=schemas.PlayerPublic)
def get_player(
    sqid: str,
    player_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.PlayerPublic:
    """Get a single player."""
    user = get_user_by_sqid(sqid, db)
    require_ownership(user.id, current_user)

    player = (
        db.query(models.Player)
        .filter(models.Player.id == player_id, models.Player.owner_id == user.id)
        .first()
    )

    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found",
        )

    return schemas.PlayerPublic.model_validate(player)


@router.patch("/u/{sqid}/player/{player_id}", response_model=schemas.PlayerPublic)
def update_player(
    sqid: str,
    player_id: UUID,
    payload: schemas.PlayerUpdateRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.PlayerPublic:
    """Update player name."""
    user = get_user_by_sqid(sqid, db)
    require_ownership(user.id, current_user)

    player = (
        db.query(models.Player)
        .filter(models.Player.id == player_id, models.Player.owner_id == user.id)
        .first()
    )

    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found",
        )

    if payload.name is not None:
        player.name = payload.name

    db.commit()
    db.refresh(player)

    return schemas.PlayerPublic.model_validate(player)


@router.get("/u/{sqid}/player/{player_id}/certs", response_model=schemas.TLSCertBundle)
def download_player_certs(
    sqid: str,
    player_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.TLSCertBundle:
    """Authenticated user downloads certificates for their player."""
    user = get_user_by_sqid(sqid, db)
    require_ownership(user.id, current_user)

    player = (
        db.query(models.Player)
        .filter(models.Player.id == player_id, models.Player.owner_id == user.id)
        .first()
    )

    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found",
        )

    if not player.cert_pem or not player.key_pem:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificates not available for this player",
        )

    # Load CA certificate
    ca_cert_path = os.getenv("MQTT_CA_FILE", "/certs/ca.crt")
    try:
        ca_pem = load_ca_certificate(ca_cert_path)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CA certificate not found",
        )

    # Get MQTT broker info
    broker_host = os.getenv("MQTT_PUBLIC_HOST", "development.makapix.club")
    broker_port = int(os.getenv("MQTT_PUBLIC_PORT", "8884"))

    return schemas.TLSCertBundle(
        ca_pem=ca_pem,
        cert_pem=player.cert_pem,
        key_pem=player.key_pem,
        broker={"host": broker_host, "port": broker_port},
    )


@router.delete("/u/{sqid}/player/{player_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_player(
    sqid: str,
    player_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> None:
    """Remove player registration. Preserves command logs for audit trail."""
    user = get_user_by_sqid(sqid, db)
    require_ownership(user.id, current_user)

    player = (
        db.query(models.Player)
        .filter(models.Player.id == player_id, models.Player.owner_id == user.id)
        .first()
    )

    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found",
        )

    # Store player info before deletion for logging and cleanup
    player_key_str = str(player.player_key)
    player_name = player.name
    device_model = player.device_model
    firmware_version = player.firmware_version
    cert_serial = player.cert_serial_number

    # Log the device removal as a special "remove_device" command BEFORE deletion
    # This log entry will have player_id set to NULL after the player is deleted
    log_command(
        db=db,
        player_id=player.id,
        command_type="remove_device",
        payload={
            "player_key": player_key_str,
            "owner_id": str(current_user.id),
            "owner_handle": current_user.handle,
            "device_name": player_name,
            "device_model": device_model,
            "firmware_version": firmware_version,
            "removed_by": str(current_user.id),
        },
    )

    # Revoke TLS certificate to prevent reconnection via mTLS
    if cert_serial:
        ca_cert_path = os.getenv("MQTT_CA_FILE", "/certs/ca.crt")
        ca_key_path = os.getenv("MQTT_CA_KEY_FILE", "/certs/ca.key")
        crl_path = os.getenv("MQTT_CRL_FILE", "/certs/crl.pem")

        try:
            import logging

            logger = logging.getLogger(__name__)

            revoked = revoke_certificate(
                serial_number=cert_serial,
                ca_cert_path=ca_cert_path,
                ca_key_path=ca_key_path,
                crl_path=crl_path,
            )
            if revoked:
                logger.info(
                    f"Revoked certificate {cert_serial} for player {player_key_str}"
                )
            else:
                logger.warning(
                    f"Failed to revoke certificate {cert_serial} for player {player_key_str}"
                )
        except Exception as e:
            logger.exception(
                f"Error revoking certificate for player {player_key_str}: {e}"
            )

    # Disconnect active MQTT connection (best effort)
    disconnect_mqtt_client(player.player_key)

    # Delete player from database (command logs preserved with player_id = NULL)
    db.delete(player)
    db.commit()

    # Remove player_key from MQTT password file
    passwd_file = os.getenv("MQTT_PASSWD_FILE", "/mqtt-config/passwords")
    try:
        subprocess.run(
            ["mosquitto_passwd", "-D", passwd_file, player_key_str],
            check=True,
            capture_output=True,
        )
    except subprocess.CalledProcessError as e:
        # Log error but don't fail - player is already deleted from DB
        import logging

        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to remove player_key from MQTT password file: {e}")
    except FileNotFoundError:
        import logging

        logger = logging.getLogger(__name__)
        logger.warning("mosquitto_passwd not found - MQTT password not cleaned up")


@router.post(
    "/u/{sqid}/player/{player_id}/command", response_model=schemas.PlayerCommandResponse
)
def send_player_command(
    sqid: str,
    player_id: UUID,
    payload: schemas.PlayerCommandRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.PlayerCommandResponse:
    """Send command to a player."""
    user = get_user_by_sqid(sqid, db)
    require_ownership(user.id, current_user)

    player = (
        db.query(models.Player)
        .filter(models.Player.id == player_id, models.Player.owner_id == user.id)
        .first()
    )

    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found",
        )

    # Check rate limits
    player_key = f"ratelimit:player:{player_id}:cmd"
    user_key = f"ratelimit:user:{user.id}:cmd"

    allowed_player, remaining_player = check_rate_limit(
        player_key, limit=300, window_seconds=60
    )
    allowed_user, remaining_user = check_rate_limit(
        user_key, limit=1000, window_seconds=60
    )

    if not allowed_player:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for player (300 commands/minute)",
        )

    if not allowed_user:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for user (1000 commands/minute)",
        )

    # Prepare command payload
    command_payload: dict[str, Any] = {}

    if payload.command_type == "show_artwork":
        if not payload.post_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="post_id is required for show_artwork command",
            )

        # Fetch post details
        post = db.query(models.Post).filter(models.Post.id == payload.post_id).first()
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found",
            )

        # Check visibility
        if not post.visible or post.hidden_by_mod or post.non_conformant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Post is not visible",
            )

        command_payload = {
            "post_id": post.id,
            "storage_key": str(post.storage_key),
            "art_url": post.art_url,
        }

    elif payload.command_type == "play_channel":
        # Validate channel parameters
        if not any([payload.channel_name, payload.hashtag, payload.user_sqid]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="play_channel requires one of: channel_name, hashtag, or user_sqid",
            )

        # Build channel payload - check user_sqid first since it may come with
        # channel_name="by_user" and we need to include user_sqid/user_handle
        if payload.user_sqid:
            # Validate that the user exists
            target_user = get_user_by_sqid(payload.user_sqid, db)
            if not target_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )
            command_payload = {
                "channel_name": "by_user",
                "user_sqid": payload.user_sqid,
                "user_handle": payload.user_handle or target_user.handle,
            }
        elif payload.hashtag:
            command_payload = {"channel_name": "hashtag", "hashtag": payload.hashtag}
        elif payload.channel_name:
            command_payload = {"channel_name": payload.channel_name}

    elif payload.command_type == "play_playset":
        if not payload.playset_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="playset_name is required for play_playset command",
            )

        # Get playset from service
        playset = PlaysetService.get_playset(db, user, payload.playset_name)
        if not playset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Playset '{payload.playset_name}' not found",
            )

        # Build command payload from playset
        command_payload = playset.to_dict()

    # Publish command via MQTT
    command_id = publish_player_command(
        player_key=player.player_key,
        command_type=payload.command_type,
        payload=command_payload if command_payload else None,
    )

    # Log command
    log_command(
        db=db,
        player_id=player_id,
        command_type=payload.command_type,
        payload=command_payload if command_payload else None,
    )

    return schemas.PlayerCommandResponse(command_id=command_id, status="sent")


@router.post(
    "/u/{sqid}/player/command/all", response_model=schemas.PlayerCommandAllResponse
)
def send_command_to_all_players(
    sqid: str,
    payload: schemas.PlayerCommandRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.PlayerCommandAllResponse:
    """Send command to all user's registered players."""
    user = get_user_by_sqid(sqid, db)
    require_ownership(user.id, current_user)

    # Get all registered players
    players = (
        db.query(models.Player)
        .filter(
            models.Player.owner_id == user.id,
            models.Player.registration_status == "registered",
        )
        .all()
    )

    if not players:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered players found",
        )

    # Check user rate limit
    user_key = f"ratelimit:user:{user.id}:cmd"
    allowed_user, remaining_user = check_rate_limit(
        user_key, limit=1000, window_seconds=60
    )

    if not allowed_user:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded for user (1000 commands/minute)",
        )

    # Prepare command payload
    command_payload: dict[str, Any] = {}

    if payload.command_type == "show_artwork":
        if not payload.post_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="post_id is required for show_artwork command",
            )

        post = db.query(models.Post).filter(models.Post.id == payload.post_id).first()
        if not post:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Post not found",
            )

        if not post.visible or post.hidden_by_mod or post.non_conformant:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Post is not visible",
            )

        command_payload = {
            "post_id": post.id,
            "storage_key": str(post.storage_key),
            "art_url": post.art_url,
        }

    elif payload.command_type == "play_channel":
        # Validate channel parameters
        if not any([payload.channel_name, payload.hashtag, payload.user_sqid]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="play_channel requires one of: channel_name, hashtag, or user_sqid",
            )

        # Build channel payload - check user_sqid first since it may come with
        # channel_name="by_user" and we need to include user_sqid/user_handle
        if payload.user_sqid:
            # Validate that the user exists
            target_user = get_user_by_sqid(payload.user_sqid, db)
            if not target_user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="User not found",
                )
            command_payload = {
                "channel_name": "by_user",
                "user_sqid": payload.user_sqid,
                "user_handle": payload.user_handle or target_user.handle,
            }
        elif payload.hashtag:
            command_payload = {"channel_name": "hashtag", "hashtag": payload.hashtag}
        elif payload.channel_name:
            command_payload = {"channel_name": payload.channel_name}

    elif payload.command_type == "play_playset":
        if not payload.playset_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="playset_name is required for play_playset command",
            )

        # Get playset from service
        playset = PlaysetService.get_playset(db, user, payload.playset_name)
        if not playset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Playset '{payload.playset_name}' not found",
            )

        # Build command payload from playset
        command_payload = playset.to_dict()

    # Send to all players
    commands = []
    for player in players:
        # Check per-player rate limit
        player_key = f"ratelimit:player:{player.id}:cmd"
        allowed_player, _ = check_rate_limit(player_key, limit=300, window_seconds=60)

        if allowed_player:
            command_id = publish_player_command(
                player_key=player.player_key,
                command_type=payload.command_type,
                payload=command_payload if command_payload else None,
            )

            log_command(
                db=db,
                player_id=player.id,
                command_type=payload.command_type,
                payload=command_payload if command_payload else None,
            )

            commands.append(
                schemas.PlayerCommandResponse(command_id=command_id, status="sent")
            )

    return schemas.PlayerCommandAllResponse(sent_count=len(commands), commands=commands)


@router.post(
    "/u/{sqid}/player/{player_id}/renew-cert",
    response_model=schemas.PlayerRenewCertResponse,
)
def renew_player_certificate(
    sqid: str,
    player_id: UUID,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.PlayerRenewCertResponse:
    """
    Renew player certificate.

    Only available if certificate is within 30 days of expiry or already expired.
    """
    user = get_user_by_sqid(sqid, db)
    require_ownership(user.id, current_user)

    player = (
        db.query(models.Player)
        .filter(models.Player.id == player_id, models.Player.owner_id == user.id)
        .first()
    )

    if not player:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Player not found",
        )

    # Check if renewal is needed
    now = datetime.now(timezone.utc)
    if player.cert_expires_at:
        days_until_expiry = (player.cert_expires_at - now).days
        if days_until_expiry > CERT_RENEWAL_THRESHOLD_DAYS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Certificate is still valid for {days_until_expiry} days. Renewal only available within {CERT_RENEWAL_THRESHOLD_DAYS} days of expiry.",
            )

    # Get CA certificate and key paths
    ca_cert_path = os.getenv("MQTT_CA_FILE", "/certs/ca.crt")
    ca_key_path = os.getenv("MQTT_CA_KEY_FILE", "/certs/ca.key")

    # Generate new certificate (CN = player_key for mTLS)
    try:
        cert_pem, key_pem, serial_number = generate_client_certificate(
            player_key=player.player_key,
            ca_cert_path=ca_cert_path,
            ca_key_path=ca_key_path,
            cert_validity_days=CERT_VALIDITY_DAYS,
        )

        # Update player certificate info
        player.cert_pem = cert_pem
        player.key_pem = key_pem
        player.cert_serial_number = serial_number
        player.cert_issued_at = now
        player.cert_expires_at = now + timedelta(days=CERT_VALIDITY_DAYS)

        db.commit()
        db.refresh(player)

        return schemas.PlayerRenewCertResponse(
            cert_expires_at=player.cert_expires_at,
            message="Certificate renewed successfully",
        )
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"CA certificate files not found: {e}",
        )
    except Exception as e:
        import logging

        logger = logging.getLogger(__name__)
        logger.exception("Failed to generate player certificate")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate certificate: {str(e)}",
        )
