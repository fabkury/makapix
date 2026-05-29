"""SEO: an XML sitemap of public, indexable URLs.

Exposed publicly at ``/api/sitemap.xml`` (Caddy strips the ``/api`` prefix via
``handle_path`` before forwarding to this app, and FastAPI has no ``root_path``,
so the in-app route ``/sitemap.xml`` is reached at ``/api/sitemap.xml``).
It is advertised to crawlers from ``web/public/robots.txt``.

The sitemap lists:
  * a small set of public marketing/content pages,
  * every publicly-visible artwork  -> ``/p/{public_sqid}``,
  * every publicly-listable artist profile -> ``/u/{public_sqid}``.

The visibility filters intentionally mirror the public listing endpoints
(``routers/posts.py:list_posts`` with ``visible_only=True`` and
``routers/users.py:browse_users``) so hidden / pending / banned content never
leaks to search engines. If those rules change, update them here too.
"""

from __future__ import annotations

import logging
import os
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from .. import models
from ..deps import get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["SEO"])

# Public site origin (e.g. https://makapix.club). Same env the email service
# uses for verification links; set per-environment via deploy/stack/.env(.dev).
# Default to the canonical prod origin so a misconfigured env never emits
# localhost URLs into a live sitemap.
SITE_URL = os.getenv("BASE_URL", "https://makapix.club").rstrip("/")

# A <urlset> must stay under 50,000 URLs / 50 MB uncompressed. A young site is
# nowhere near this; if either cap is reached we emit a comment (see below) and
# the right follow-up is to split into a <sitemapindex>.
MAX_POSTS = 45_000
MAX_USERS = 5_000

# Public, indexable, non-auth pages worth advertising explicitly.
STATIC_PATHS = ["/", "/about", "/players", "/recommended", "/size_rules"]


def _iso(dt) -> str | None:
    return dt.isoformat() if dt is not None else None


def _abs(path: str) -> str:
    return f"{SITE_URL}{path}"


@router.get("/sitemap.xml")
def sitemap(db: Session = Depends(get_db)) -> Response:
    """Render the public sitemap as XML."""
    rows: list[str] = []

    def add(loc: str, lastmod: str | None = None, priority: str | None = None) -> None:
        parts = [f"<loc>{escape(loc)}</loc>"]
        if lastmod:
            parts.append(f"<lastmod>{escape(lastmod)}</lastmod>")
        if priority:
            parts.append(f"<priority>{priority}</priority>")
        rows.append("<url>" + "".join(parts) + "</url>")

    # 1) Static marketing/content pages.
    for path in STATIC_PATHS:
        add(_abs(path), priority="1.0" if path == "/" else "0.7")

    # 2) Public artworks  ->  /p/{public_sqid}
    post_rows = (
        db.query(
            models.Post.public_sqid,
            models.Post.updated_at,
            models.Post.created_at,
        )
        .filter(
            models.Post.kind == "artwork",
            models.Post.deleted_by_user.is_(False),
            models.Post.public_sqid.isnot(None),
            models.Post.public_sqid != "",
            models.Post.visible.is_(True),
            models.Post.hidden_by_mod.is_(False),
            models.Post.hidden_by_user.is_(False),
            models.Post.non_conformant.is_(False),
            models.Post.public_visibility.is_(True),
        )
        .order_by(models.Post.created_at.desc())
        .limit(MAX_POSTS + 1)
        .all()
    )
    posts_truncated = len(post_rows) > MAX_POSTS
    for sqid, updated_at, created_at in post_rows[:MAX_POSTS]:
        add(_abs(f"/p/{sqid}"), _iso(updated_at) or _iso(created_at), "0.8")

    # 3) Publicly-listable artist profiles  ->  /u/{public_sqid}
    user_rows = (
        db.query(
            models.User.public_sqid,
            models.User.updated_at,
            models.User.created_at,
        )
        .filter(
            models.User.public_sqid.isnot(None),
            models.User.email_verified.is_(True),
            models.User.hidden_by_user.is_(False),
            models.User.hidden_by_mod.is_(False),
            models.User.non_conformant.is_(False),
            models.User.deactivated.is_(False),
            models.User.banned_until.is_(None),
            ~models.User.roles.cast(JSONB).contains(["owner"]),
        )
        .order_by(models.User.created_at.desc())
        .limit(MAX_USERS + 1)
        .all()
    )
    users_truncated = len(user_rows) > MAX_USERS
    for sqid, updated_at, created_at in user_rows[:MAX_USERS]:
        add(_abs(f"/u/{sqid}"), _iso(updated_at) or _iso(created_at), "0.5")

    body = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">',
    ]
    if posts_truncated or users_truncated:
        # Never truncate silently: tell future maintainers a split is overdue.
        body.append(
            f"<!-- NOTE: capped at {MAX_POSTS} posts / {MAX_USERS} users. "
            "Split into a sitemap index to list everything. -->"
        )
    body.extend(rows)
    body.append("</urlset>")

    return Response(
        content="\n".join(body),
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )
