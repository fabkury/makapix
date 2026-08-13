"""Canonical view/impression vocabulary and shared view-pipeline helpers.

Single home for the redesigned artwork-views model (docs/artwork-views/
DECISIONS.md): the canonical view_type values, the read-time mapping for
legacy data, the rollup watermark, the posts.view_count recompute, and the
lightweight Redis observability counters.

Glossary (repo-root CONTEXT.md): an **Artwork View** is a deliberate look
(>=2s dwell, non-author Visitor, deduped once per Visitor per artwork per
UTC day); an **Impression** is passive playback exposure. Never summed.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Canonical ViewEvent.view_type values (post-redesign).
VIEW = "view"
IMPRESSION = "impression"

# rollup_watermarks.name for the artwork view-events pipeline.
VIEW_EVENTS_WATERMARK = "view_events"

# Pre-redesign view_type values, mapped at read/rollup time. Raw rows are
# never rewritten; they age out of view_events within the 7-day retention.
LEGACY_VIEW_TYPE_MAP = {
    "intentional": VIEW,
    "listing": IMPRESSION,
    "search": IMPRESSION,
    "widget": IMPRESSION,
}


def canonical_view_type(raw: str | None) -> str:
    """Map any stored view_type (canonical or legacy) to VIEW or IMPRESSION."""
    if raw == VIEW:
        return VIEW
    if raw == IMPRESSION:
        return IMPRESSION
    return LEGACY_VIEW_TYPE_MAP.get(raw or "", IMPRESSION)


def views_from_breakdown(views_by_type: dict | None) -> int:
    """Artwork Views in a post_stats_daily views_by_type JSON, any era."""
    vbt = views_by_type or {}
    return int(vbt.get(VIEW, 0) or 0) + int(vbt.get("intentional", 0) or 0)


def impressions_from_breakdown(views_by_type: dict | None) -> int:
    """Impressions in a post_stats_daily views_by_type JSON, any era."""
    vbt = views_by_type or {}
    return sum(
        int(count or 0)
        for key, count in vbt.items()
        if key not in (VIEW, "intentional")
    )


def normalize_breakdown(views_by_type: dict | None) -> dict[str, int]:
    """Collapse a views_by_type JSON of any era to canonical keys.

    API responses always emit {'view': n, 'impression': m}; historical rows
    keep their legacy keys in the DB (never rewritten).
    """
    return {
        VIEW: views_from_breakdown(views_by_type),
        IMPRESSION: impressions_from_breakdown(views_by_type),
    }


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


# ---------------------------------------------------------------------------
# Rollup watermark
# ---------------------------------------------------------------------------


def get_view_watermark(db: Session) -> date | None:
    """Last UTC day fully rolled into post_stats_daily, or None if unseeded."""
    from .. import models

    row = db.get(models.RollupWatermark, VIEW_EVENTS_WATERMARK)
    return row.value_date if row else None


def set_view_watermark(db: Session, value: date) -> None:
    """Advance (or create) the view-events watermark. Caller owns the commit."""
    from .. import models

    row = db.get(models.RollupWatermark, VIEW_EVENTS_WATERMARK)
    if row is None:
        db.add(models.RollupWatermark(name=VIEW_EVENTS_WATERMARK, value_date=value))
    else:
        row.value_date = value


def seed_view_watermark(conn) -> date:
    """Seed the watermark for a DB migrated from the pre-watermark pipeline.

    The old rollup's `now - 7d` cutoff rolled *partial* UTC days, so the
    oldest surviving raw-event day is partially rolled; seeding one day
    before it lets the new rollup MERGE the un-rolled remainder into the
    existing daily row. (Already-rolled player events older than 7 days are
    deleted by the migration before this runs, so they cannot re-roll.)
    Seeds only when no watermark exists (ON CONFLICT DO NOTHING): rewinding a
    live watermark would re-roll already-aggregated days into the daily rows —
    a double count. Accepts a Session or Connection; caller owns the commit.
    Returns the effective watermark (existing or newly seeded).
    """
    yesterday = utc_today() - timedelta(days=1)
    min_day = conn.execute(
        text("SELECT min((created_at AT TIME ZONE 'UTC')::date) FROM view_events")
    ).scalar()
    seed = yesterday if min_day is None else min(min_day - timedelta(days=1), yesterday)
    conn.execute(
        text(
            "INSERT INTO rollup_watermarks (name, value_date) "
            "VALUES (:name, :value) "
            "ON CONFLICT (name) DO NOTHING"
        ),
        {"name": VIEW_EVENTS_WATERMARK, "value": seed},
    )
    effective = conn.execute(
        text("SELECT value_date FROM rollup_watermarks WHERE name = :name"),
        {"name": VIEW_EVENTS_WATERMARK},
    ).scalar()
    return effective if effective is not None else seed


# ---------------------------------------------------------------------------
# posts.view_count recompute (D11/D12)
# ---------------------------------------------------------------------------

_RECOMPUTE_SQL = """
UPDATE posts SET view_count =
  COALESCE((
    SELECT SUM(
      COALESCE((views_by_type->>'view')::int, 0)
      + COALESCE((views_by_type->>'intentional')::int, 0))
    FROM post_stats_daily WHERE post_stats_daily.post_id = posts.id
  ), 0)
  + COALESCE((
    SELECT COUNT(*) FROM view_events
    WHERE view_events.post_id = posts.id
      AND view_events.view_type IN ('view', 'intentional')
      {raw_filter}
  ), 0)
"""


def recompute_post_view_counts(conn, post_ids: list[int] | None = None) -> int:
    """Rebuild posts.view_count from daily aggregates + raw view events.

    The D12 recompute: Views = the intentional/view slice of the stored
    daily breakdowns plus raw view rows AFTER the watermark (rolled days'
    raw rows are retained up to 7 days and already live in the daily rows —
    counting them again would double count). With no watermark, all raw
    rows count (only reachable pre-seed / in tests). Historical daily rows
    were never deduped (accepted approximation); post-redesign raw rows are
    dedup-gated at ingestion. Accepts a Session or Connection; caller owns
    the commit. Returns the number of posts updated.
    """
    watermark = conn.execute(
        text("SELECT value_date FROM rollup_watermarks WHERE name = :name"),
        {"name": VIEW_EVENTS_WATERMARK},
    ).scalar()
    raw_filter = (
        "AND (view_events.created_at AT TIME ZONE 'UTC')::date > :watermark"
        if watermark is not None
        else ""
    )
    sql = _RECOMPUTE_SQL.format(raw_filter=raw_filter)
    params: dict = {}
    if watermark is not None:
        params["watermark"] = watermark
    if post_ids is not None:
        if not post_ids:
            return 0
        sql += " WHERE posts.id = ANY(:post_ids)"
        params["post_ids"] = post_ids
    result = conn.execute(text(sql), params)
    return result.rowcount or 0


# ---------------------------------------------------------------------------
# Observability counters (D15) — day-keyed, fail-open
# ---------------------------------------------------------------------------

_COUNTER_TTL_SECONDS = 2 * 86400  # yesterday's counters must survive for the
# 02:30 ET health check; two days is plenty.


def _counter_key(name: str, day: date) -> str:
    return f"viewobs:{name}:{day.strftime('%Y%m%d')}"


def incr_view_counter(name: str) -> None:
    """Increment today's (UTC) counter for `name`. Never raises."""
    try:
        from ..cache import get_redis_client

        client = get_redis_client()
        if not client:
            return
        key = _counter_key(name, utc_today())
        pipe = client.pipeline()
        pipe.incr(key)
        pipe.expire(key, _COUNTER_TTL_SECONDS)
        pipe.execute()
    except Exception:  # pragma: no cover - defensive
        logger.debug(f"Failed to increment view counter {name}", exc_info=True)


def get_view_counter(name: str, day: date | None = None) -> int:
    """Read a day's counter (default: today UTC). 0 when absent/unavailable."""
    try:
        from ..cache import get_redis_client

        client = get_redis_client()
        if not client:
            return 0
        raw = client.get(_counter_key(name, day or utc_today()))
        return int(raw) if raw else 0
    except Exception:  # pragma: no cover - defensive
        return 0
