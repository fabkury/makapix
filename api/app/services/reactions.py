"""Reaction writes — the single implementation behind every transport.

The REST endpoints (`app.routers.reactions`) and the player request protocol
(`app.services.player_rpc`, reached over MQTT and the HTTPS player RPC) both
add and remove reactions through this module, so the rules cannot drift apart
again: post visibility, the block guard, idempotency, the per-post cap and the
social notification to the post owner apply whatever the source of the
reaction.

Nothing here knows about HTTP or MQTT. Refusals are raised as
``ReactionError`` carrying a ``code``; each transport maps it onto its own
error representation.
"""

from __future__ import annotations

import logging

from sqlalchemy import func
from sqlalchemy.orm import Session

from .. import models
from ..constants import NotificationType
from ..utils.blocks import block_exists_between
from ..utils.visibility import can_access_post
from .social_notifications import SocialNotificationService

logger = logging.getLogger(__name__)

MAX_EMOJI_LENGTH = 20
MAX_REACTIONS_PER_POST = 5

# ReactionError codes
INVALID_EMOJI = "invalid_emoji"
POST_NOT_FOUND = "post_not_found"  # missing, or not visible to the reactor
POST_DELETED = "post_deleted"
BLOCKED = "blocked"
CAP_REACHED = "cap_reached"


class ReactionError(Exception):
    """A refused reaction write. ``code`` is one of the module constants."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _actor_filter(user: models.User | None, ip: str | None):
    """Reactions belong to a user, or — for anonymous visitors — to an IP."""
    if user is not None:
        return models.Reaction.user_id == user.id
    return models.Reaction.user_ip == ip


def add_reaction(
    db: Session,
    *,
    post_id: int,
    emoji: str,
    user: models.User | None = None,
    ip: str | None = None,
) -> bool:
    """Add a reaction to a post on behalf of ``user`` (or anonymous ``ip``).

    Idempotent: returns False when the reaction already existed, True when it
    was created. A created reaction by an authenticated user notifies the
    post owner (self-reactions and rate limiting are handled by the
    notification service).

    Raises:
        ReactionError: invalid emoji, post missing / deleted / not visible to
            the reactor, a block between reactor and post owner, or the
            per-post cap reached.
    """
    if not emoji or len(emoji) > MAX_EMOJI_LENGTH:
        raise ReactionError(INVALID_EMOJI, "Invalid emoji format")

    # You cannot react to a post you cannot see. Missing and not-visible are
    # deliberately indistinguishable (post ids are sequential — see
    # utils.visibility.get_accessible_post_or_404).
    post = db.query(models.Post).filter(models.Post.id == post_id).first()
    if post is None:
        raise ReactionError(POST_NOT_FOUND, "Post not found")
    if post.deleted_by_user:
        raise ReactionError(POST_DELETED, "Post has been deleted")
    if not can_access_post(post, user):
        raise ReactionError(POST_NOT_FOUND, "Post not found")

    # Interaction guard (docs/ugc-safety/ D11): a block in either direction
    # between the reactor and the post owner refuses the reaction. Anonymous
    # reactors have no identity to check (D16).
    if (
        user is not None
        and user.id != post.owner_id
        and block_exists_between(db, user.id, post.owner_id)
    ):
        raise ReactionError(BLOCKED, "You cannot interact with this user.")

    mine = _actor_filter(user, ip)

    existing = (
        db.query(models.Reaction.id)
        .filter(
            models.Reaction.post_id == post_id,
            mine,
            models.Reaction.emoji == emoji,
        )
        .first()
    )
    if existing:
        return False

    reaction_count = (
        db.query(func.count(models.Reaction.id))
        .filter(models.Reaction.post_id == post_id, mine)
        .scalar()
    )
    if reaction_count >= MAX_REACTIONS_PER_POST:
        raise ReactionError(
            CAP_REACHED,
            f"Maximum reactions per user per post ({MAX_REACTIONS_PER_POST}) reached.",
        )

    db.add(
        models.Reaction(
            post_id=post_id,
            user_id=user.id if user is not None else None,
            user_ip=ip if user is None else None,
            emoji=emoji,
        )
    )
    db.commit()

    # Notify the post owner (authenticated reactors only). The reaction is
    # already committed: a notification failure must not fail the request.
    if user is not None:
        try:
            SocialNotificationService.create_notification(
                db=db,
                user_id=post.owner_id,
                notification_type=NotificationType.REACTION,
                post=post,
                actor=user,
                emoji=emoji,
            )
        except Exception:  # noqa: BLE001
            logger.exception(
                "Failed to create reaction notification for post %s", post_id
            )
            db.rollback()

    return True


def remove_reaction(
    db: Session,
    *,
    post_id: int,
    emoji: str,
    user: models.User | None = None,
    ip: str | None = None,
) -> bool:
    """Remove a reaction (idempotent). Returns True if a row was deleted."""
    deleted = (
        db.query(models.Reaction)
        .filter(
            models.Reaction.post_id == post_id,
            _actor_filter(user, ip),
            models.Reaction.emoji == emoji,
        )
        .delete()
    )
    db.commit()
    return bool(deleted)
