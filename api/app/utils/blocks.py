"""User-block helpers (docs/ugc-safety/ D10/D11).

All block SQL lives here:
- `apply_block_filter` — one-way visibility: hide blocked users' content from
  the blocker on list surfaces (feeds, search, comments, notifications, ...).
- `block_exists_between` / `ensure_not_blocked` — symmetric interaction
  prevention: any block between two users refuses comment/reaction/like/follow
  in both directions with 403 `blocked`.
"""

from __future__ import annotations

from fastapi import status
from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import Query, Session

from .. import models
from ..errors import AppError, ErrorCode

# Per-user block cap (D19); advertised in /config as max_blocks_per_user.
MAX_BLOCKS_PER_USER = 1000


def apply_block_filter(query: Query, author_col, viewer_id: int | None) -> Query:
    """Exclude rows authored by users the viewer has blocked (D10).

    `author_col` is the column holding the row author's user id (e.g.
    `Post.owner_id`, `Comment.author_id`). No-op for anonymous viewers.
    Uses NOT EXISTS against the (blocker_id, blocked_id) unique index.
    """
    if viewer_id is None:
        return query
    return query.filter(
        ~exists().where(
            and_(
                models.UserBlock.blocker_id == viewer_id,
                models.UserBlock.blocked_id == author_col,
            )
        )
    )


def blocked_ids_for(db: Session, viewer_id: int | None) -> set[int]:
    """The set of user ids the viewer has blocked (for Python-side filtering,
    e.g. the comment-tree pass where SQL filtering would orphan replies)."""
    if viewer_id is None:
        return set()
    rows = (
        db.query(models.UserBlock.blocked_id)
        .filter(models.UserBlock.blocker_id == viewer_id)
        .all()
    )
    return {row[0] for row in rows}


def filter_items_by_blocks(items: list, db: Session, viewer_id: int | None) -> list:
    """In-memory variant of `apply_block_filter` for cached list surfaces
    (e.g. the shared /posts/recent cache, where user-specific filtering runs
    after cache retrieval). Items must expose an `owner_id` attribute."""
    if viewer_id is None or not items:
        return items
    blocked = blocked_ids_for(db, viewer_id)
    if not blocked:
        return items
    return [item for item in items if item.owner_id not in blocked]


def block_exists_between(db: Session, a_id: int, b_id: int) -> bool:
    """True if a block exists between the two users in either direction (D11)."""
    return db.query(
        db.query(models.UserBlock)
        .filter(
            or_(
                and_(
                    models.UserBlock.blocker_id == a_id,
                    models.UserBlock.blocked_id == b_id,
                ),
                and_(
                    models.UserBlock.blocker_id == b_id,
                    models.UserBlock.blocked_id == a_id,
                ),
            )
        )
        .exists()
    ).scalar()


def ensure_not_blocked(db: Session, actor_id: int, other_id: int) -> None:
    """Refuse an interaction between two users when a block exists between
    them in either direction (D11/D20). Self-interactions are never blocked."""
    if actor_id == other_id:
        return
    if block_exists_between(db, actor_id, other_id):
        raise AppError(
            ErrorCode.blocked,
            "You cannot interact with this user.",
            status.HTTP_403_FORBIDDEN,
        )
