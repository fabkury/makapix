# Promoted feed order — sort by promotion time

> **Status: LIVE ON PROD (2026-09-12, PR #273).** Migration `e5f6a7b8c9d0`
> ran at deploy: 289 promoted rows grandfathered (`promoted_at := created_at`),
> 0 mismatched, 0 stray stamps, index present; the feed's first page was
> byte-identical before and after the deploy, cursored page 2 and the
> `/post?promoted=true` remap both 200. Dev live check: a Nov-2025 post
> promoted via the API led `/api/feed/promoted`, demote restored the order.
> App FYI pushed as thread `0002-promoted-feed-order` in the app repo
> (`a0f3a3ad`); no app change needed, reply optional.
> Reopen trigger: a promoted surface that still shows upload order, or a
> promoted row with `promoted_at IS NULL` after this migration.

## Problem

Every surface serving the promoted set ordered by **creation date**, so a
freshly promoted older artwork landed deep in the Recommended feed (the
diamond page) instead of at the top. The owner wants promoted surfaces
ordered by the date-time a moderator promoted the post.

## Decisions (owner, 2026-09-12)

| # | Decision | Choice |
|---|---|---|
| D1 | Surfaces | `GET /feed/promoted` (website `/recommended`, permalink prev/next, app Recommended tab), the physical players' `promoted` channel, and `GET /post?promoted=true&sort=created_at`. The Web Player's Promoted channel keeps `sort=random` — untouched. |
| D2 | Backfill | Grandfather: `promoted_at := created_at` for every already-promoted post (289 on prod, 78 on dev). No audit-log replay. |
| D3 | Re-promote | `POST /post/{id}/promote` always stamps `now()`; `DELETE` clears it. Demote → promote bumps the post to the top (a deliberate moderator "bump" lever; it re-sends the owner's promotion notification, as before). |
| D4 | API surface | Internal only: no `promoted_at` in the `Post` schema, no contract change. The only OpenAPI diff is the feed docstring. |
| D5 | Players | Server-side remap: on `channel="promoted"`, `sort="server_order"` and `sort="created_at"` both order by promotion time. No protocol or firmware change; `random` unaffected. Documented in `docs/mqtt-protocol/02-player-protocol.md`. |
| D6 | Keyset | Inlined in `feed_promoted` rather than generalising `api/app/pagination.py` (which only knows plain columns). |
| D7 | Null safety | Every ordering uses `Post.promoted_order_key()` = `coalesce(promoted_at, created_at)` so a promoted row that somehow lacks a stamp can never be dropped by a keyset. |

## Implementation

- `api/app/models.py` — `Post.promoted_at` (timestamptz, nullable), composite
  index `ix_posts_promoted_promoted_at (promoted, promoted_at DESC)`, and the
  shared `Post.promoted_order_key()` classmethod.
- `api/alembic/versions/e5f6a7b8c9d0_posts_promoted_at.py` — column + backfill
  + index; runs in-process at API startup (`app/main.py:run_migrations`).
- `api/app/routers/posts.py` — promote/demote stamp; `list_posts` maps the
  `created_at` / `creation_date` sorts to the promotion key when
  `promoted=true`.
- `api/app/routers/search.py:feed_promoted` — inline keyset on the promotion
  key, tie-broken on `id`. Cursors minted before this change carry a
  `created_at` ISO string; grandfathered rows have `promoted_at == created_at`,
  so those cursors still resume in the right place.
- `api/app/services/player_rpc.py:query_posts` — the D5 remap.
- `api/tests/test_promoted_feed_order.py` — ordering + null fallback, cursor
  continuity, legacy cursor, garbage cursor, promote/demote/re-promote (first
  tests ever for those endpoints), the `/post` remap, the player channel.

## Verification

- Dev: migration ran at startup (`alembic current` = `e5f6a7b8c9d0`); 78
  promoted rows, 0 with `promoted_at IS DISTINCT FROM created_at`, 0 stray
  stamps on unpromoted rows; index present. New tests + full suite green.
- Live: promote an old post via the API → it leads `/api/feed/promoted`;
  demote → it leaves; cursored second page 200.
- Prod (after `make deploy`): same three checks, plus the first page of the
  feed is byte-for-byte the same as before deploy (grandfathering).

## Messages

- `messages/0001-server-promoted-feed-order-fyi.md` — FYI to the app team
  (their copy: `makapix-app/messages/0002-promoted-feed-order/`). Reply
  optional.
