"""Mentions — the `<@SQID>` markup in comment bodies and post descriptions.

Design: docs/mentions/ (server decisions S1–S12) on top of the app repo's
docs/mentions/ (D1–D21); contract thread messages/0004-mentions.

Storage is markup only (S6): `comments.body` / `posts.description` hold the
text with `<@SQID>` inline, where SQID is the target's `users.public_sqid`.
Every read resolves each sqid to the target's *current* handle, so renames
never leave stale text:

- `render()` → (plain rendering, mentions refs). The plain rendering is what
  `body` / `description` carry on the wire and what every legacy reader
  (notification previews, player RPC, exports) sees.
- Resolution goes through a per-session cache in `Session.info`, which list
  endpoints fill in one batch with `prime()`; anything unprimed resolves
  lazily, so no serializer can ever leak raw markup.

Writes go through `sanitize()`: a mention survives only when its target is
mentionable for the writer (`mentionable_users_query`, the one function the
candidates endpoint also uses), up to MAX_MENTIONS_PER_TEXT; everything else
is flattened to plain `@handle` text, silently (never an error, so blocks and
policies cannot be probed).

Notifications: `notify_mentions()` (one row per recipient per text, held while
the post awaits approval) and `release_held_mentions()` at approval (S3).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import and_, exists, or_
from sqlalchemy.orm import Query, Session, joinedload, object_session

from .. import models

logger = logging.getLogger(__name__)

# Grammar (S1): "<@" + 1–32 base62 characters + ">". Anything else starting
# with "<@" is literal text. No word-boundary rule: "a<@t5>b" is a mention.
MENTION_RE = re.compile(r"<@([A-Za-z0-9]{1,32})>")

# D5: per-text cap (advertised on /config as max_mentions_per_text, the
# clients' launch signal) and the per-writer hourly notification budget.
MAX_MENTIONS_PER_TEXT = 16
MAX_NOTIFIED_MENTIONS_PER_HOUR = 256

# S2: shown for a sqid that resolves to no account.
UNKNOWN_HANDLE = "user"

# users.mention_policy values (D11).
MENTION_POLICY_EVERYONE = "everyone"
MENTION_POLICY_FOLLOWING = "following"
MENTION_POLICY_NOBODY = "nobody"
MENTION_POLICIES = (
    MENTION_POLICY_EVERYONE,
    MENTION_POLICY_FOLLOWING,
    MENTION_POLICY_NOBODY,
)

_PREVIEW_LENGTH = 100
_CACHE_KEY = "mention_refs"


@dataclass(frozen=True)
class MentionTarget:
    """A resolved sqid: the account it points at, as of this read."""

    id: int
    public_sqid: str
    handle: str
    avatar_url: str | None

    def as_ref(self) -> dict:
        return {
            "public_sqid": self.public_sqid,
            "handle": self.handle,
            "avatar_url": self.avatar_url,
        }


# ---------------------------------------------------------------------------
# Parsing and read-time resolution
# ---------------------------------------------------------------------------


def has_markup(text: str | None) -> bool:
    """True when `text` contains at least one syntactically valid mention."""
    return bool(text) and MENTION_RE.search(text) is not None


def extract_sqids(text: str | None) -> list[str]:
    """Distinct sqids in `text`, in order of first appearance."""
    if not text:
        return []
    return list(dict.fromkeys(m.group(1) for m in MENTION_RE.finditer(text)))


def resolve_sqids(db: Session | None, sqids: Iterable[str]) -> dict[str, MentionTarget]:
    """Map each sqid that belongs to an existing account to its target.

    Results (including misses) are cached for the session's lifetime — one
    request — so a page of comments costs one `IN (...)` lookup however many
    serializers ask. Without a session nothing resolves (renders `@user`).
    """
    sqids = list(dict.fromkeys(sqids))
    if not sqids or db is None:
        return {}
    cache: dict[str, MentionTarget | None] = db.info.setdefault(_CACHE_KEY, {})
    missing = [s for s in sqids if s not in cache]
    if missing:
        rows = (
            db.query(
                models.User.id,
                models.User.public_sqid,
                models.User.handle,
                models.User.avatar_url,
            )
            .filter(models.User.public_sqid.in_(missing))
            .all()
        )
        found = {
            row.public_sqid: MentionTarget(
                id=row.id,
                public_sqid=row.public_sqid,
                handle=row.handle,
                avatar_url=row.avatar_url,
            )
            for row in rows
        }
        for sqid in missing:
            cache[sqid] = found.get(sqid)
    return {s: cache[s] for s in sqids if cache.get(s) is not None}


def clear_cache(db: Session) -> None:
    """Forget cached resolutions (e.g. after a handle change in this session)."""
    db.info.pop(_CACHE_KEY, None)


def prime(db: Session, texts: Iterable[str | None]) -> None:
    """Resolve every sqid in `texts` in one query, ahead of serialization."""
    sqids: list[str] = []
    for text in texts:
        sqids.extend(extract_sqids(text))
    if sqids:
        resolve_sqids(db, sqids)


def render(db: Session | None, text: str | None) -> tuple[str | None, list[dict]]:
    """(plain rendering, mentions refs) for stored markup.

    The plain rendering replaces each `<@SQID>` with `@handle`, or `@user`
    when the sqid resolves to no account (S2). Refs list the resolved sqids in
    order of first appearance: `{public_sqid, handle, avatar_url}`.
    """
    if not has_markup(text):
        return text, []
    sqids = extract_sqids(text)
    resolved = resolve_sqids(db, sqids)

    def _plain(match: re.Match) -> str:
        target = resolved.get(match.group(1))
        return "@" + (target.handle if target is not None else UNKNOWN_HANDLE)

    plain = MENTION_RE.sub(_plain, text)
    refs = [resolved[s].as_ref() for s in sqids if s in resolved]
    return plain, refs


def render_orm(obj: object, text: str | None) -> tuple[str | None, list[dict]]:
    """`render()` for a text read off an ORM instance, using its own session."""
    if not has_markup(text):
        return text, []
    return render(object_session(obj), text)


def plain_text(db: Session | None, text: str | None) -> str | None:
    """The plain rendering only (for previews, exports, legacy readers)."""
    return render(db, text)[0]


def preview(db: Session | None, text: str | None) -> str | None:
    """First 100 characters of the plain rendering, `...` when truncated."""
    plain = plain_text(db, text)
    if not plain:
        return None
    if len(plain) > _PREVIEW_LENGTH:
        return plain[:_PREVIEW_LENGTH] + "..."
    return plain


def strip_markup(text: str | None) -> str | None:
    """`text` with every mention removed (for content checks like profanity)."""
    if not has_markup(text):
        return text
    return MENTION_RE.sub(" ", text)


# SQL twin of MENTION_RE for Postgres `regexp_replace` (search) and `~`.
MENTION_SQL_PATTERN = r"<@[A-Za-z0-9]{1,32}>"


# ---------------------------------------------------------------------------
# Mentionability (D3, D11, S7) — the one function
# ---------------------------------------------------------------------------


def mentionable_users_query(db: Session, writer: models.User) -> Query:
    """Users `writer` may mention. Used by the write path AND the candidates
    endpoint, so the two can never disagree.

    A target is mentionable when it:
    1. would appear in /user/browse (email-verified; not hidden by user or
       moderator; not non-conformant, deactivated or banned) — except that the
       site owner is not excluded, although browse hides them;
    2. has no block with the writer in either direction;
    3. has a mention_policy that admits the writer: `everyone`, or
       `following` when the target follows the writer.

    The rules are the same for every writer, moderators included (S7). The
    writer themself is not special-cased here: callers decide (self-mentions
    are kept on write but never notify; candidates exclude the caller).
    """
    User = models.User
    block = models.UserBlock
    return db.query(User).filter(
        User.email_verified == True,  # noqa: E712
        User.hidden_by_user == False,  # noqa: E712
        User.hidden_by_mod == False,  # noqa: E712
        User.non_conformant == False,  # noqa: E712
        User.deactivated == False,  # noqa: E712
        User.banned_until.is_(None),
        ~exists().where(
            or_(
                and_(block.blocker_id == writer.id, block.blocked_id == User.id),
                and_(block.blocker_id == User.id, block.blocked_id == writer.id),
            )
        ),
        or_(
            User.mention_policy == MENTION_POLICY_EVERYONE,
            and_(
                User.mention_policy == MENTION_POLICY_FOLLOWING,
                exists().where(
                    and_(
                        models.Follow.follower_id == User.id,
                        models.Follow.following_id == writer.id,
                    )
                ),
            ),
        ),
    )


def mentionable_ids(
    db: Session, writer: models.User, candidate_ids: Iterable[int]
) -> set[int]:
    """The subset of `candidate_ids` that `writer` may mention."""
    ids = list(set(candidate_ids))
    if not ids:
        return set()
    rows = (
        mentionable_users_query(db, writer)
        .with_entities(models.User.id)
        .filter(models.User.id.in_(ids))
        .all()
    )
    return {row[0] for row in rows}


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


@dataclass
class SanitizedText:
    """Result of `sanitize()`: the text to store and whom it mentions."""

    text: str | None
    # Distinct user ids of the mentions that survived, first appearance first
    # (includes the writer on a self-mention; notify_mentions skips it).
    mentioned_ids: list[int] = field(default_factory=list)


def sanitize(
    db: Session, writer: models.User | None, text: str | None
) -> SanitizedText:
    """Rewrite submitted text into the markup to store.

    Each `<@SQID>` is kept only when its target is mentionable for `writer`
    (or is the writer themself), up to MAX_MENTIONS_PER_TEXT occurrences.
    Everything else is flattened: `@handle` for an existing account, `@user`
    for a sqid that resolves to none. An anonymous writer (None) cannot
    mention (D4), so all of their markup is flattened.
    """
    if not has_markup(text):
        return SanitizedText(text=text)

    resolved = resolve_sqids(db, extract_sqids(text))
    allowed: set[int] = set()
    if writer is not None and resolved:
        target_ids = {t.id for t in resolved.values()}
        allowed = mentionable_ids(db, writer, target_ids)
        if writer.id in target_ids:
            allowed.add(writer.id)

    kept = 0
    mentioned: list[int] = []

    def _rewrite(match: re.Match) -> str:
        nonlocal kept
        target = resolved.get(match.group(1))
        if target is None:
            return "@" + UNKNOWN_HANDLE
        if target.id not in allowed or kept >= MAX_MENTIONS_PER_TEXT:
            return "@" + target.handle
        kept += 1
        if target.id not in mentioned:
            mentioned.append(target.id)
        return match.group(0)

    return SanitizedText(text=MENTION_RE.sub(_rewrite, text), mentioned_ids=mentioned)


def mentioned_user_ids(db: Session, text: str | None) -> list[int]:
    """User ids mentioned by already-stored markup (for edit diffs)."""
    resolved = resolve_sqids(db, extract_sqids(text))
    return list(dict.fromkeys(t.id for t in resolved.values()))


# ---------------------------------------------------------------------------
# Notifications (N1–N6 as amended by S3)
# ---------------------------------------------------------------------------


def _writer_can_notify(writer: models.User) -> bool:
    if writer.deactivated:
        return False
    if writer.banned_until is not None:
        banned_until = writer.banned_until
        if banned_until.tzinfo is None:
            banned_until = banned_until.replace(tzinfo=timezone.utc)
        if banned_until > datetime.now(timezone.utc):
            return False
    return True


def notify_mentions(
    db: Session,
    *,
    writer: models.User,
    post: models.Post,
    recipient_ids: Iterable[int],
    comment: models.Comment | None = None,
) -> int:
    """Send `mention` notifications for one text; returns how many were sent.

    `comment` set → a comment mention (comment_id = the comment); None → a
    mention in the post's description. Skipped per recipient when: it is the
    writer; the post is still awaiting approval (held, S3 — released by
    `release_held_mentions`) or is hidden/deleted; the target is no longer
    mentionable; they
    cannot access the post or it carries a monitored hashtag they have not
    opted into (N2); they already hold a comment/comment_reply/mention row
    for this comment, or a mention row for this description (N1 precedence
    and never-re-notify on edits); the writer's hourly budget is spent (D5).
    """
    from ..constants import NotificationType
    from ..services.rate_limit import check_rate_limit
    from ..services.social_notifications import SocialNotificationService
    from .monitored_hashtags import post_has_unapproved_monitored_hashtags
    from .visibility import can_access_post

    if not post.public_visibility:
        return 0
    # A hidden or deleted post notifies nobody — not even moderator
    # recipients, whom can_access_post would otherwise admit.
    if (
        not post.visible
        or post.hidden_by_user
        or post.hidden_by_mod
        or post.deleted_by_user
    ):
        return 0
    if comment is not None and (
        comment.deleted_by_owner or comment.deleted_by_mod or comment.hidden_by_mod
    ):
        return 0
    if not _writer_can_notify(writer):
        return 0

    ids = [i for i in dict.fromkeys(recipient_ids) if i != writer.id]
    if not ids:
        return 0

    eligible = mentionable_ids(db, writer, ids)
    if not eligible:
        return 0

    SN = models.SocialNotification
    existing_q = db.query(SN.user_id).filter(SN.user_id.in_(eligible))
    if comment is not None:
        existing_q = existing_q.filter(
            SN.comment_id == comment.id,
            SN.notification_type.in_(
                [
                    NotificationType.COMMENT,
                    NotificationType.COMMENT_REPLY,
                    NotificationType.MENTION,
                ]
            ),
        )
    else:
        existing_q = existing_q.filter(
            SN.post_id == post.id,
            SN.comment_id.is_(None),
            SN.notification_type == NotificationType.MENTION,
        )
    already = {row[0] for row in existing_q.all()}

    recipients = {
        u.id: u
        for u in db.query(models.User).filter(models.User.id.in_(eligible)).all()
    }
    description_preview = preview(db, post.description) if comment is None else None

    sent = 0
    for uid in ids:
        recipient = recipients.get(uid)
        if recipient is None or uid in already:
            continue
        if not can_access_post(post, recipient):
            continue
        if post_has_unapproved_monitored_hashtags(post, recipient):
            continue
        allowed, _ = check_rate_limit(
            f"ratelimit:mention_notif:{writer.id}",
            limit=MAX_NOTIFIED_MENTIONS_PER_HOUR,
            window_seconds=3600,
        )
        if not allowed:
            logger.info(
                "Mention notification budget spent for writer %s; "
                "remaining mentions link but do not notify",
                writer.id,
            )
            break
        created = SocialNotificationService.create_notification(
            db=db,
            user_id=uid,
            notification_type=NotificationType.MENTION,
            post=post,
            actor=writer,
            comment=comment,
            extra_preview=description_preview,
        )
        if created is not None:
            sent += 1
    return sent


def release_held_mentions(db: Session, post: models.Post) -> int:
    """Notify mentions held while `post` awaited approval (S3).

    Called when a moderator approves the post: re-evaluates the description
    (writer = the post owner, S8) and every live comment on the post. Rows
    already sent are skipped by `notify_mentions`' de-duplication, so this is
    idempotent (re-approval after a revoke sends only what is new).
    """
    if not post.public_visibility:
        return 0

    sent = 0
    if has_markup(post.description):
        owner = post.owner or db.get(models.User, post.owner_id)
        if owner is not None:
            sent += notify_mentions(
                db,
                writer=owner,
                post=post,
                recipient_ids=mentioned_user_ids(db, post.description),
            )

    comments = (
        db.query(models.Comment)
        .options(joinedload(models.Comment.author))
        .filter(
            models.Comment.post_id == post.id,
            models.Comment.author_id.isnot(None),
            models.Comment.deleted_by_owner == False,  # noqa: E712
            models.Comment.deleted_by_mod == False,  # noqa: E712
            models.Comment.hidden_by_mod == False,  # noqa: E712
            models.Comment.body.op("~")(MENTION_SQL_PATTERN),
        )
        .order_by(models.Comment.created_at.asc())
        .all()
    )
    for comment in comments:
        if comment.author is None:
            continue
        sent += notify_mentions(
            db,
            writer=comment.author,
            post=post,
            recipient_ids=mentioned_user_ids(db, comment.body),
            comment=comment,
        )
    return sent
