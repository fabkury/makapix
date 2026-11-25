"""Public Pulse: the community-activity timeline (docs/pulse/)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from .. import models, schemas
from ..auth import get_current_user
from ..deps import get_db
from ..services.pulse import build_pulse_page

router = APIRouter(prefix="/pulse", tags=["Pulse"])


@router.get("", response_model=schemas.Page[schemas.PulseCard])
def get_pulse(
    cursor: str | None = None,
    limit: int = Query(20, ge=1, le=50),
    kinds: str | None = Query(
        None,
        description=(
            "Comma-separated subset of likes, posts, remixes, comments, player, "
            "badge, reputation, promoted (default: all). Unknown values are "
            "ignored."
        ),
    ),
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
) -> schemas.Page[schemas.PulseCard]:
    """
    Timeline of public member activity from the last 30 days, newest first
    (signed-in members only).

    Activity is grouped into cards: one member + one kind + one burst, where
    each event comes within 6 hours of the previous one. Only what the Recent
    feed would show the caller is included (approval, hiding, deletion,
    blocks, monitored hashtags); anonymous activity never is.
    """
    requested = (
        {k.strip() for k in kinds.split(",") if k.strip()}
        if kinds is not None
        else None
    )
    return build_pulse_page(
        db, current_user, cursor=cursor, limit=limit, kinds=requested
    )
