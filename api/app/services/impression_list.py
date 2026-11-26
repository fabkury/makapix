"""The "Displayed on" list behind the 📺 number (docs/impression-list/).

One row per (artwork, member) in ``post_impression_users``, written for every
accepted Impression that has a member behind it and read by
``GET /post/{id}/impression-users``. Privacy rules live here: calendar days
only, device models only, and the per-account switch is applied on read.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, or_, text
from sqlalchemy.orm import Session

from .. import models, schemas
from ..pagination import decode_cursor, encode_cursor
from ..utils.blocks import apply_block_filter

# A member is forgotten this long after their last showing (L4).
RETENTION_DAYS = 90

_WEB_DEVICE_TYPES = {"desktop", "mobile", "tablet"}

_UPSERT_SQL = text("""
INSERT INTO post_impression_users
    (post_id, user_id, shown_count, first_shown_on, last_shown_on,
     device_models, web_player, app)
VALUES
    (:post_id, :user_id, 1, :day, :day,
     CAST(:models AS jsonb), :web_player, :app)
ON CONFLICT (post_id, user_id) DO UPDATE SET
    shown_count = post_impression_users.shown_count + 1,
    last_shown_on = GREATEST(post_impression_users.last_shown_on,
                             EXCLUDED.last_shown_on),
    web_player = post_impression_users.web_player OR EXCLUDED.web_player,
    app = post_impression_users.app OR EXCLUDED.app,
    device_models = CASE
        WHEN post_impression_users.device_models @> EXCLUDED.device_models
            THEN post_impression_users.device_models
        ELSE post_impression_users.device_models || EXCLUDED.device_models
    END
""")


def record_showing(
    db: Session,
    *,
    post_id: int,
    user_id: int,
    shown_at: datetime,
    device_type: str,
    player_id: UUID | None,
) -> None:
    """Count one Impression toward the member's row for this artwork.

    Called inside ``write_view_event``'s transaction; the caller commits. The
    upsert is a single statement, so concurrent workers cannot lose a count.
    """
    device_model = None
    if player_id is not None:
        device_model = (
            db.query(models.Player.device_model)
            .filter(models.Player.id == player_id)
            .scalar()
        )
    db.execute(
        _UPSERT_SQL,
        {
            "post_id": post_id,
            "user_id": user_id,
            "day": shown_at.astimezone(timezone.utc).date(),
            "models": json.dumps([device_model] if device_model else []),
            "web_player": player_id is None and device_type in _WEB_DEVICE_TYPES,
            "app": player_id is None and device_type.startswith("app"),
        },
    )


def list_impression_users(
    db: Session,
    post: models.Post,
    viewer: models.User,
    cursor: str | None,
    limit: int,
) -> schemas.Page[schemas.ImpressionUserItem]:
    """The members to show a signed-in viewer, most recently shown first.

    Leaves out members who opted out (from everyone, moderators and the
    artwork's author included — L6), members the viewer blocked, and hidden,
    banned or deactivated accounts.
    """
    piu = models.PostImpressionUser
    now = datetime.now(timezone.utc)
    query = (
        db.query(piu, models.User)
        .join(models.User, models.User.id == piu.user_id)
        .filter(
            piu.post_id == post.id,
            piu.user_id != post.owner_id,
            piu.last_shown_on >= now.date() - timedelta(days=RETENTION_DAYS),
            models.User.show_in_impression_lists == True,  # noqa: E712
            models.User.public_sqid.isnot(None),
            models.User.hidden_by_user == False,  # noqa: E712
            models.User.hidden_by_mod == False,  # noqa: E712
            models.User.non_conformant == False,  # noqa: E712
            models.User.deactivated == False,  # noqa: E712
            or_(models.User.banned_until.is_(None), models.User.banned_until <= now),
        )
    )
    query = apply_block_filter(query, piu.user_id, viewer.id)

    after = _parse_cursor(cursor)
    if after is not None:
        day, row_id = after
        query = query.filter(
            or_(
                piu.last_shown_on < day,
                and_(piu.last_shown_on == day, piu.id < row_id),
            )
        )

    rows = (
        query.order_by(piu.last_shown_on.desc(), piu.id.desc()).limit(limit + 1).all()
    )
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = page[-1][0]
        next_cursor = encode_cursor(str(last.id), last.last_shown_on.isoformat())

    return schemas.Page(
        items=[
            schemas.ImpressionUserItem(
                user_handle=user.handle,
                user_avatar_url=user.avatar_url,
                user_public_sqid=user.public_sqid,
                device_models=list(row.device_models or []),
                web_player=row.web_player,
                app=row.app,
                count=row.shown_count,
                last_shown_on=row.last_shown_on,
            )
            for row, user in page
        ],
        next_cursor=next_cursor,
    )


def _parse_cursor(cursor: str | None) -> tuple[date, int] | None:
    decoded = decode_cursor(cursor)
    if decoded is None:
        return None
    try:
        return date.fromisoformat(str(decoded[1])), int(decoded[0])
    except (TypeError, ValueError):
        return None


def delete_expired(db: Session, today: date | None = None) -> int:
    """Forget rows whose last showing is older than the retention window."""
    today = today or datetime.now(timezone.utc).date()
    return (
        db.query(models.PostImpressionUser)
        .filter(
            models.PostImpressionUser.last_shown_on
            < today - timedelta(days=RETENTION_DAYS)
        )
        .delete(synchronize_session=False)
    )
