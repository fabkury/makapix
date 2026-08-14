"""Lineage Links: parent resolution, permission enforcement, link creation.

Source of truth: docs/artwork-provenance/PLAN.md (§3.2, §4, §5) and ADR 0002.

Normative rules enforced here:
- Publish-time permission: a declared parent must resolve to an existing
  artwork post (soft-deleted rows still count; hard-deleted don't) with
  ``remixable = true`` — else the whole request fails 422 (fail closed;
  silently dropping an edge would create exactly the unattributed remix the
  owner opted out of). Owners always pass for their own posts.
- Parents are Club artworks only; duplicates collapse; ≤ MAX_PARENTS after
  dedup; declaration order is preserved (position).
- Links are append-only: replace-artwork may add parents, never removes.
- Cycle rejection keeps Lineage a DAG (only reachable at replace time —
  a fresh upload can't be anyone's ancestor yet).
"""

from __future__ import annotations

import logging

from fastapi import status
from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session

from .. import models
from ..constants import NotificationType
from ..errors import AppError, ErrorCode
from ..services.social_notifications import SocialNotificationService

logger = logging.getLogger(__name__)

MAX_PARENTS = 8

_DESCENDANT_CHECK_SQL = sa_text("""
    WITH RECURSIVE descendants AS (
        SELECT child_post_id FROM post_lineage WHERE parent_post_id = :root_id
        UNION
        SELECT pl.child_post_id
        FROM post_lineage pl
        JOIN descendants d ON pl.parent_post_id = d.child_post_id
    )
    SELECT 1 FROM descendants WHERE child_post_id = :candidate_id LIMIT 1
    """)


def parse_remixed_from(raw: str | None) -> list[str]:
    """Split the comma-separated ``remixed_from`` field, deduped, order kept."""
    if not raw:
        return []
    seen: set[str] = set()
    sqids: list[str] = []
    for token in raw.split(","):
        sqid = token.strip()
        if sqid and sqid not in seen:
            seen.add(sqid)
            sqids.append(sqid)
    if len(sqids) > MAX_PARENTS:
        raise AppError(
            ErrorCode.too_many_parents,
            f"At most {MAX_PARENTS} parents may be declared.",
            status.HTTP_422_UNPROCESSABLE_ENTITY,
        )
    return sqids


def resolve_declared_parents(
    db: Session,
    remixed_from: str | None,
    *,
    actor_id: int,
    child: models.Post | None = None,
) -> list[models.Post]:
    """Resolve + permission-check declared parent sqids (declaration order).

    ``child`` is the existing post when called from replace-artwork; the
    cycle check only applies then.
    """
    sqids = parse_remixed_from(remixed_from)
    parents: list[models.Post] = []
    for sqid in sqids:
        parent = (
            db.query(models.Post)
            .filter(
                models.Post.public_sqid == sqid,
                models.Post.kind == "artwork",
            )
            .first()
        )
        if parent is None:
            raise AppError(
                ErrorCode.parent_not_found,
                f"Declared parent {sqid!r} does not resolve to an artwork.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"parent": sqid},
            )
        if not parent.remixable and parent.owner_id != actor_id:
            raise AppError(
                ErrorCode.remix_not_allowed,
                f"The artist of {sqid!r} does not allow remixes.",
                status.HTTP_422_UNPROCESSABLE_ENTITY,
                details={"parent": sqid},
            )
        if child is not None:
            if parent.id == child.id:
                raise AppError(
                    ErrorCode.lineage_cycle,
                    "A post cannot be its own parent.",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    details={"parent": sqid},
                )
            is_descendant = db.execute(
                _DESCENDANT_CHECK_SQL,
                {"root_id": child.id, "candidate_id": parent.id},
            ).first()
            if is_descendant:
                raise AppError(
                    ErrorCode.lineage_cycle,
                    f"Declared parent {sqid!r} is a descendant of this post.",
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    details={"parent": sqid},
                )
        parents.append(parent)
    return parents


def create_lineage_links(
    db: Session, child: models.Post, parents: list[models.Post]
) -> list[models.PostLineage]:
    """Create links child→parents, appending after any existing links.

    Parents already linked (by sqid snapshot) are skipped — replace-artwork
    re-declaring an existing parent is a no-op, not an error.
    """
    existing = (
        db.query(models.PostLineage)
        .filter(models.PostLineage.child_post_id == child.id)
        .all()
    )
    existing_sqids = {link.parent_sqid for link in existing}
    next_position = max((link.position for link in existing), default=-1) + 1

    created: list[models.PostLineage] = []
    for parent in parents:
        if parent.public_sqid in existing_sqids:
            continue
        link = models.PostLineage(
            child_post_id=child.id,
            parent_post_id=parent.id,
            parent_sqid=parent.public_sqid,
            position=next_position,
        )
        next_position += 1
        db.add(link)
        created.append(link)
    if created:
        db.flush()
    return created


def notify_remix_published(
    db: Session,
    child: models.Post,
    actor: models.User,
    parents: list[models.Post],
) -> None:
    """One ``remix`` notification per distinct parent owner (L12).

    Content denormalizes from the *child*, so the notification leads to the
    new Remix. Self-remixes are skipped by the service's self-action guard.
    """
    notified: set[int] = set()
    for parent in parents:
        if parent.owner_id in notified:
            continue
        notified.add(parent.owner_id)
        SocialNotificationService.create_notification(
            db=db,
            user_id=parent.owner_id,
            notification_type=NotificationType.REMIX,
            post=child,
            actor=actor,
        )
