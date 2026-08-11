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
