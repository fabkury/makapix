"""Device bearer token service for the HTTPS player API.

Player device tokens are high-entropy random secrets stored only as a SHA-256
hash (same approach as ``RefreshToken`` / ``EmailVerificationToken``). The
plaintext is returned exactly once, at issuance or rotation. A token resolves
directly to a registered ``Player``; the auth dependency layers on the
``registration_status`` / owner checks.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from .. import models

logger = logging.getLogger(__name__)

# Wire prefix for player device tokens, e.g. "mpx_live_8sK2f9Qd...".
TOKEN_PREFIX = "mpx_live_"
# Bytes of entropy in the random component.
TOKEN_ENTROPY_BYTES = 32


def _hash_token(token: str) -> str:
    """Hash a token using SHA-256 for secure storage and lookup."""
    return hashlib.sha256(token.encode()).hexdigest()


def issue_token(db: Session, player: models.Player) -> str:
    """Mint a fresh device token for a player and return the plaintext (once).

    Any existing active tokens for the player are revoked first, so a player
    has at most one usable token at a time.
    """
    db.query(models.PlayerToken).filter(
        models.PlayerToken.player_id == player.id,
        models.PlayerToken.revoked.is_(False),
    ).update({"revoked": True})

    token = f"{TOKEN_PREFIX}{secrets.token_urlsafe(TOKEN_ENTROPY_BYTES)}"
    db.add(
        models.PlayerToken(
            player_id=player.id,
            token_hash=_hash_token(token),
            prefix=token[:16],
        )
    )
    db.commit()

    logger.info(f"Issued device token for player {player.id}")
    return token


def get_active_token(db: Session, player_id: UUID) -> models.PlayerToken | None:
    """Return the player's active (non-revoked, non-expired) token, if any."""
    now = datetime.now(timezone.utc)
    return (
        db.query(models.PlayerToken)
        .filter(
            models.PlayerToken.player_id == player_id,
            models.PlayerToken.revoked.is_(False),
        )
        .filter(
            (models.PlayerToken.expires_at.is_(None))
            | (models.PlayerToken.expires_at > now)
        )
        .first()
    )


def resolve_player(db: Session, token: str) -> models.Player | None:
    """Resolve a bearer token to its ``Player``, or None if invalid.

    A token is invalid if it is unknown, revoked, or expired. The matched
    token's ``last_used_at`` is refreshed on success. Note: this does not check
    ``registration_status`` or owner state — the auth dependency does.
    """
    if not token:
        return None

    record = (
        db.query(models.PlayerToken)
        .filter(
            models.PlayerToken.token_hash == _hash_token(token),
            models.PlayerToken.revoked.is_(False),
        )
        .first()
    )
    if record is None:
        return None

    now = datetime.now(timezone.utc)
    if record.expires_at is not None and record.expires_at < now:
        return None

    record.last_used_at = now
    db.commit()
    return record.player


def revoke_all(db: Session, player_id: UUID) -> int:
    """Revoke all active tokens for a player. Returns the number revoked."""
    count = (
        db.query(models.PlayerToken)
        .filter(
            models.PlayerToken.player_id == player_id,
            models.PlayerToken.revoked.is_(False),
        )
        .update({"revoked": True})
    )
    db.commit()
    logger.info(f"Revoked {count} device token(s) for player {player_id}")
    return count
