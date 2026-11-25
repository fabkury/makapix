"""Public Pulse: a timeline of what members do, grouped into cards.

Contract: docs/pulse/messages/0002-server-pulse-contract-accepted.md.

One card = one member + one kind of activity + one burst (each event within
`BURST_GAP` of the previous one). Cards are rebuilt from the source tables on
every request over a fixed window, then paged in memory — so a card can never
be split across pages, and nothing has to be kept in sync on the write paths.
That is affordable because the window is short and the Club is small (a few
hundred events a month); if that stops being true, cache the event list or
materialize it, the contract does not change.

Every visibility rule is applied to the *events*, per viewer, before
grouping: a card describes exactly what the viewer may see.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import exists, func, or_
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..pagination import decode_cursor, encode_cursor
from ..utils.blocks import apply_block_filter, blocked_ids_for
from ..utils.mentions import plain_text
from ..utils.monitored_hashtags import apply_monitored_hashtag_filter
from .post_stats import annotate_posts_with_counts

PULSE_KINDS = (
    "likes",
    "posts",
    "remixes",
    "comments",
    "player",
    "badge",
    "reputation",
    "promoted",
)

WINDOW = timedelta(days=30)  # how far back Pulse reaches
BURST_GAP = timedelta(hours=6)  # max silence inside one card
MAX_POSTS_PER_CARD = 6
MAX_COMMENTS_PER_CARD = 3
PREVIEW_LEN = 140

# Kinds whose events never join a card with another event.
_SINGLE_EVENT_KINDS = frozenset({"player"})
_POST_KINDS = frozenset({"likes", "posts", "remixes", "promoted"})


def pulse_preview(body: str | None, db: Session | None = None) -> str | None:
    """Plain-text comment preview: mentions as @handle, cut to PREVIEW_LEN."""
    if body is None:
        return None
    if db is not None:
        body = plain_text(db, body)  # stored mention markup → @handle
    if len(body) <= PREVIEW_LEN:
        return body
    return body[: PREVIEW_LEN - 1] + "…"


@dataclass
class _Event:
    kind: str
    actor_id: int
    at: datetime
    ref: Any = None  # post id, comment id, badge code or device model
    delta: int = 0  # reputation only


@dataclass
class _Card:
    kind: str
    actor_id: int
    events: list[_Event] = field(default_factory=list)  # oldest first
    id: str = ""

    @property
    def started_at(self) -> datetime:
        return self.events[0].at

    @property
    def updated_at(self) -> datetime:
        return self.events[-1].at


def _discoverable_posts(query, viewer: models.User):
    """Restrict a query that involves models.Post to what the Recent feed
    would show this viewer (approval, hiding, deletion, monitored hashtags,
    blocked owners)."""
    query = query.filter(
        models.Post.kind == "artwork",
        models.Post.visible == True,  # noqa: E712
        models.Post.hidden_by_mod == False,  # noqa: E712
        models.Post.hidden_by_user == False,  # noqa: E712
        models.Post.non_conformant == False,  # noqa: E712
        models.Post.public_visibility == True,  # noqa: E712
        models.Post.deleted_by_user == False,  # noqa: E712
    )
    query = apply_monitored_hashtag_filter(query, models.Post, viewer)
    return apply_block_filter(query, models.Post.owner_id, viewer.id)


def _collect_events(
    db: Session, viewer: models.User, kinds: set[str], cutoff: datetime
) -> list[_Event]:
    events: list[_Event] = []

    if "posts" in kinds or "remixes" in kinds:
        is_remix = (
            exists()
            .where(models.PostLineage.child_post_id == models.Post.id)
            .label("is_remix")
        )
        rows = _discoverable_posts(
            db.query(
                models.Post.id, models.Post.owner_id, models.Post.listed_at, is_remix
            ),
            viewer,
        ).filter(models.Post.listed_at >= cutoff)
        for post_id, owner_id, listed_at, remix in rows:
            kind = "remixes" if remix else "posts"
            if kind in kinds:
                events.append(_Event(kind, owner_id, listed_at, post_id))

    if "promoted" in kinds:
        promoted_at = models.Post.promoted_order_key()
        rows = _discoverable_posts(
            db.query(models.Post.id, models.Post.owner_id, promoted_at), viewer
        ).filter(
            models.Post.promoted == True, promoted_at >= cutoff  # noqa: E712
        )
        for post_id, owner_id, at in rows:
            events.append(_Event("promoted", owner_id, at, post_id))

    if "likes" in kinds:
        # One event per (member, post) however many emoji, timed at the first
        # reaction so adding a second emoji later is not fresh activity.
        first_reaction = func.min(models.Reaction.created_at)
        rows = (
            _discoverable_posts(
                db.query(
                    models.Reaction.user_id, models.Reaction.post_id, first_reaction
                ).join(models.Post, models.Post.id == models.Reaction.post_id),
                viewer,
            )
            .filter(
                models.Reaction.user_id.isnot(None),
                models.Reaction.user_id != models.Post.owner_id,
            )
            .group_by(models.Reaction.user_id, models.Reaction.post_id)
            .having(first_reaction >= cutoff)
        )
        for user_id, post_id, at in rows:
            events.append(_Event("likes", user_id, at, post_id))

    if "comments" in kinds:
        rows = _discoverable_posts(
            db.query(
                models.Comment.id, models.Comment.author_id, models.Comment.created_at
            ).join(models.Post, models.Post.id == models.Comment.post_id),
            viewer,
        ).filter(
            models.Comment.author_id.isnot(None),
            models.Comment.hidden_by_mod == False,  # noqa: E712
            models.Comment.deleted_by_owner == False,  # noqa: E712
            models.Comment.deleted_by_mod == False,  # noqa: E712
            models.Comment.created_at >= cutoff,
        )
        for comment_id, author_id, at in rows:
            events.append(_Event("comments", author_id, at, comment_id))

    if "player" in kinds:
        rows = db.query(
            models.Player.owner_id,
            models.Player.registered_at,
            models.Player.device_model,
        ).filter(
            models.Player.registration_status == "registered",
            models.Player.owner_id.isnot(None),
            models.Player.registered_at >= cutoff,
        )
        for owner_id, at, device_model in rows:
            events.append(_Event("player", owner_id, at, device_model))

    if "badge" in kinds:
        rows = db.query(
            models.BadgeGrant.user_id,
            models.BadgeGrant.granted_at,
            models.BadgeGrant.badge,
        ).filter(models.BadgeGrant.granted_at >= cutoff)
        for user_id, at, badge in rows:
            events.append(_Event("badge", user_id, at, badge))

    if "reputation" in kinds:
        rows = db.query(
            models.ReputationHistory.user_id,
            models.ReputationHistory.created_at,
            models.ReputationHistory.delta,
        ).filter(models.ReputationHistory.created_at >= cutoff)
        for user_id, at, delta in rows:
            events.append(_Event("reputation", user_id, at, delta=delta))

    return events


def _load_actors(
    db: Session, viewer: models.User, actor_ids: set[int], now: datetime
) -> dict[int, models.User]:
    """The actors Pulse may show: not hidden, deactivated, banned or blocked
    by the viewer."""
    if not actor_ids:
        return {}
    blocked = blocked_ids_for(db, viewer.id)
    users = (
        db.query(models.User)
        .filter(
            models.User.id.in_(actor_ids - blocked),
            models.User.public_sqid.isnot(None),
            models.User.hidden_by_user == False,  # noqa: E712
            models.User.hidden_by_mod == False,  # noqa: E712
            models.User.non_conformant == False,  # noqa: E712
            models.User.deactivated == False,  # noqa: E712
            or_(models.User.banned_until.is_(None), models.User.banned_until <= now),
        )
        .all()
    )
    return {u.id: u for u in users}


def _group(events: list[_Event], actors: dict[int, models.User]) -> list[_Card]:
    events = [e for e in events if e.actor_id in actors]
    events.sort(key=lambda e: (e.kind, e.actor_id, e.at))

    cards: list[_Card] = []
    current: _Card | None = None
    for event in events:
        joins = (
            current is not None
            and current.kind == event.kind
            and current.actor_id == event.actor_id
            and event.kind not in _SINGLE_EVENT_KINDS
            and event.at - current.updated_at <= BURST_GAP
        )
        if not joins:
            current = _Card(event.kind, event.actor_id)
            cards.append(current)
        current.events.append(event)

    # Pulse celebrates: a reputation burst that nets zero or less is not shown.
    cards = [
        c for c in cards if c.kind != "reputation" or sum(e.delta for e in c.events) > 0
    ]
    for card in cards:
        sqid = actors[card.actor_id].public_sqid
        card.id = f"{card.kind}:{sqid}:{card.started_at.isoformat()}"
    cards.sort(key=lambda c: (c.updated_at, c.id), reverse=True)
    return cards


def _parse_cursor(cursor: str | None) -> tuple[datetime, str] | None:
    decoded = decode_cursor(cursor)
    if not decoded:
        return None
    card_id, sort_value = decoded
    if not isinstance(card_id, str) or not isinstance(sort_value, str):
        return None
    try:
        if sort_value.endswith("Z"):
            sort_value = sort_value[:-1] + "+00:00"
        at = datetime.fromisoformat(sort_value)
    except ValueError:
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return at, card_id


def _hydrate(
    db: Session,
    viewer: models.User,
    cards: list[_Card],
    actors: dict[int, models.User],
    reputation_events: list[_Event],
) -> list[schemas.PulseCard]:
    """Turn the page's cards into response objects, loading only what the
    page shows."""
    shown: dict[str, list[_Event]] = {}
    for card in cards:
        newest_first = card.events[::-1]
        if card.kind in _POST_KINDS:
            newest_first = newest_first[:MAX_POSTS_PER_CARD]
        elif card.kind == "comments":
            newest_first = newest_first[:MAX_COMMENTS_PER_CARD]
        shown[card.id] = newest_first

    comment_ids = [e.ref for c in cards if c.kind == "comments" for e in shown[c.id]]
    comments = (
        {
            c.id: c
            for c in db.query(models.Comment).filter(models.Comment.id.in_(comment_ids))
        }
        if comment_ids
        else {}
    )

    post_ids = {e.ref for c in cards if c.kind in _POST_KINDS for e in shown[c.id]}
    post_ids |= {c.post_id for c in comments.values()}
    posts: dict[int, schemas.Post] = {}
    if post_ids:
        rows = (
            db.query(models.Post)
            .options(joinedload(models.Post.owner), joinedload(models.Post.license))
            .filter(models.Post.id.in_(post_ids))
            .all()
        )
        annotate_posts_with_counts(db, rows, viewer.id)
        posts = {p.id: schemas.Post.model_validate(p) for p in rows}

    badge_codes = {e.ref for c in cards if c.kind == "badge" for e in c.events}
    badge_defs = (
        {
            d.badge: d
            for d in db.query(models.BadgeDefinition).filter(
                models.BadgeDefinition.badge.in_(badge_codes)
            )
        }
        if badge_codes
        else {}
    )

    items: list[schemas.PulseCard] = []
    for card in cards:
        actor = actors[card.actor_id]
        item = schemas.PulseCard(
            id=card.id,
            kind=card.kind,
            actor=schemas.PulseActor(
                public_sqid=actor.public_sqid,
                handle=actor.handle,
                avatar_url=actor.avatar_url,
            ),
            started_at=card.started_at,
            updated_at=card.updated_at,
            count=len(card.events),
        )
        events = shown[card.id]
        if card.kind in _POST_KINDS:
            item.posts = [posts[e.ref] for e in events if e.ref in posts]
        elif card.kind == "comments":
            item.comments = [
                schemas.PulseComment(
                    id=comment.id,
                    preview=pulse_preview(comment.body, db) or "",
                    is_reply=comment.parent_id is not None,
                    created_at=comment.created_at,
                    post=posts[comment.post_id],
                )
                for e in events
                if (comment := comments.get(e.ref)) is not None
                and comment.post_id in posts
            ]
        elif card.kind == "player":
            item.player = schemas.PulsePlayer(device_model=events[0].ref)
        elif card.kind == "badge":
            item.badges = [
                schemas.PulseBadge(
                    badge=e.ref,
                    label=badge_defs[e.ref].label if e.ref in badge_defs else e.ref,
                    icon_url_64=(
                        badge_defs[e.ref].icon_url_64 if e.ref in badge_defs else None
                    ),
                )
                for e in events
            ]
        elif card.kind == "reputation":
            # Total right after this card: today's total minus what came later.
            later = sum(
                e.delta
                for e in reputation_events
                if e.actor_id == card.actor_id and e.at > card.updated_at
            )
            item.reputation = schemas.PulseReputation(
                delta=sum(e.delta for e in card.events),
                total=actor.reputation - later,
            )
        items.append(item)
    return items


def build_pulse_page(
    db: Session,
    viewer: models.User,
    *,
    cursor: str | None,
    limit: int,
    kinds: set[str] | None = None,
) -> schemas.Page[schemas.PulseCard]:
    now = datetime.now(timezone.utc)
    active = set(PULSE_KINDS) if kinds is None else kinds & set(PULSE_KINDS)
    if not active:
        return schemas.Page(items=[], next_cursor=None)

    events = _collect_events(db, viewer, active, now - WINDOW)
    actors = _load_actors(db, viewer, {e.actor_id for e in events}, now)
    cards = _group(events, actors)

    after = _parse_cursor(cursor)
    if after is not None:
        cards = [c for c in cards if (c.updated_at, c.id) < after]

    page = cards[:limit]
    next_cursor = (
        encode_cursor(page[-1].id, page[-1].updated_at.isoformat())
        if len(cards) > limit
        else None
    )
    items = _hydrate(
        db, viewer, page, actors, [e for e in events if e.kind == "reputation"]
    )
    return schemas.Page(items=items, next_cursor=next_cursor)
