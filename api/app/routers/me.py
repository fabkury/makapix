"""Self-service endpoints under /me.

Formerly also carried the push-token and notification-preference endpoints
(native-app change-request §4); the FCM server half was deleted 2026-08-11 at
the app team's request (docs/notification-architecture/messages/0002) — the
app never built the client half. If push returns, both halves get built
together in a fresh exchange.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db

router = APIRouter(prefix="/me", tags=["Me"])


@router.get("/blocks", response_model=schemas.Page[schemas.BlockedUserEntry])
def list_my_blocks(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Page[schemas.BlockedUserEntry]:
    """The caller's blocked-users list (docs/ugc-safety/API-CONTRACT.md §4)."""
    from ..pagination import apply_cursor_filter, create_page_response

    query = db.query(models.UserBlock).filter(
        models.UserBlock.blocker_id == current_user.id
    )
    query = apply_cursor_filter(
        query, models.UserBlock, cursor, "created_at", sort_desc=True
    )
    query = query.order_by(models.UserBlock.created_at.desc()).limit(limit + 1)
    blocks = query.all()

    page_data = create_page_response(blocks, limit, cursor)

    blocked_ids = [b.blocked_id for b in page_data["items"]]
    users_by_id: dict[int, models.User] = {}
    if blocked_ids:
        users_by_id = {
            u.id: u
            for u in db.query(models.User).filter(models.User.id.in_(blocked_ids)).all()
        }

    items = []
    for b in page_data["items"]:
        u = users_by_id.get(b.blocked_id)
        if not u:
            continue
        items.append(
            schemas.BlockedUserEntry(
                public_sqid=u.public_sqid or "",
                handle=u.handle,
                avatar_url=u.avatar_url,
                blocked_at=b.created_at,
            )
        )

    return schemas.Page(items=items, next_cursor=page_data["next_cursor"])


@router.get("/remixes", response_model=schemas.Page[schemas.RemixReceivedItem])
def list_remixes_of_my_works(
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Page[schemas.RemixReceivedItem]:
    """Aggregate "Remixes of my works" view, newest first (PLAN.md L12/§5.5).

    Lists viewer-visible Children of any post the caller owns; each item names
    which of the caller's works it declares as Parents. Standard visibility
    rules apply — a remixer who hides their Remix drops out of this list.
    """
    from sqlalchemy import and_, or_
    from ..pagination import apply_cursor_filter, create_page_response
    from ..services.post_stats import annotate_posts_with_counts
    from sqlalchemy.orm import aliased

    parent_post = aliased(models.Post)
    query = (
        db.query(models.Post)
        .join(models.PostLineage, models.PostLineage.child_post_id == models.Post.id)
        .join(parent_post, parent_post.id == models.PostLineage.parent_post_id)
        .filter(
            parent_post.owner_id == current_user.id,
            models.Post.deleted_by_user == False,
            or_(
                models.Post.owner_id == current_user.id,
                and_(
                    models.Post.visible == True,
                    models.Post.hidden_by_user == False,
                    models.Post.hidden_by_mod == False,
                    or_(
                        models.Post.public_visibility == True,
                        models.Post.promoted == True,
                    ),
                ),
            ),
        )
        # One Remix may declare several of the caller's works as Parents.
        .distinct()
    )
    query = apply_cursor_filter(
        query, models.Post, cursor, "created_at", sort_desc=True
    )
    query = query.order_by(models.Post.created_at.desc()).limit(limit + 1)
    children = query.all()
    page_data = create_page_response(children, limit, cursor)
    annotate_posts_with_counts(db, page_data["items"], current_user.id)

    # Which of MY works does each Remix declare? (batch, declaration order)
    child_ids = [p.id for p in page_data["items"]]
    my_sqids_by_child: dict[int, list[str]] = {}
    if child_ids:
        rows = (
            db.query(models.PostLineage.child_post_id, models.PostLineage.parent_sqid)
            .join(parent_post, parent_post.id == models.PostLineage.parent_post_id)
            .filter(
                models.PostLineage.child_post_id.in_(child_ids),
                parent_post.owner_id == current_user.id,
            )
            .order_by(models.PostLineage.position)
            .all()
        )
        for child_id, parent_sqid in rows:
            my_sqids_by_child.setdefault(child_id, []).append(parent_sqid)

    return schemas.Page(
        items=[
            schemas.RemixReceivedItem(
                post=schemas.Post.model_validate(p),
                my_parent_sqids=my_sqids_by_child.get(p.id, []),
            )
            for p in page_data["items"]
        ],
        next_cursor=page_data["next_cursor"],
    )
