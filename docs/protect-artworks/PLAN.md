# PLAN — protect artworks from harvesting

> **Status: PLAN WRITTEN 2026-09-14, AWAITING OWNER REVIEW (D18). No code yet.**
> Folds in every decision in [DECISIONS.md](DECISIONS.md) (D1–D18). Options
> referenced by letter+number are defined in [02-options.md](02-options.md).
> Update [PROGRESS.md](PROGRESS.md) after each step.

## Goal

Meet the bar in D7 — **every artwork byte fetch from the website or the app
is tied to an identity with a posts-per-hour budget, the casual right-click
save is gone, the one sanctioned way to get a file is attributed, and a
harvest shows up on a dashboard with a block button** — without touching
what deployed players do (D3, D9) and without any third party (D4).

## Non-goals

- Making harvesting impossible (screenshots, DevTools — 01 §8).
- Changing the vault URL scheme, headers that players depend on, or the
  player RPC contract.
- Watermarks or any pixel change (D6). File metadata is Phase 2, gated on
  a p3a decode test.
- ToS wording (D17 — deferred). The deprecated Blog subsystem.
- Per-post OG / SSR itself (appraisal F3) — this plan only fixes *how* an
  OG image URL must be served when that effort happens (D13).

## Shape of the end state

```
players ──plain HTTP──▶ vault.makapix.club/{shard}/{key}.{ext}   (unchanged, open)
                         ▲
                         │ storage_key is now a *player secret*
web / app ──identity──▶ makapix.club/api/art/{sqid}/{variant}   (gated, budgeted, same-origin)
                         │   identity = member JWT | app JWT | anonymous viewer cookie | unfurler UA
                         ▼
                      Redis budgets ─▶ harvest signals ─▶ mod-dashboard block
```

Listing endpoints return `art` (sqid + variants + gated URL) instead of
`art_url` + `storage_key`; the frozen player surfaces keep the old shape.

## Phase 0 — no contract change (ship alone, ~1 week)

Everything here is additive on the server and invisible to the app and to
players. Deploys develop → PR → main → `make deploy`; the vault header
change additionally needs `docker restart caddy` on prod.

### 0.1 `<ArtworkImage>` wrapper and DOM deterrents (B1)

- New `web/src/components/kit/ArtworkImage.tsx` (kit/ is the component
  home): renders the `<img>` with `draggable={false}`,
  `onContextMenu={preventDefault}`, class with `-webkit-touch-callout:
  none; user-select: none; -webkit-user-drag: none`, keeps `alt`,
  `loading="lazy"`, `ensureCompatibleArtUrl`, and exposes a `variant`
  prop (`native | upscaled | png | gif | webp`) so Phase 1 can swap the
  source without touching call sites.
- Migrate the human-facing render sites: `CardGrid`, `CardRoller`,
  `SelectedPostOverlay`, `SelectedArtworkOverlay`, `WebPlayer`,
  `p/[sqid]`, `u/[sqid]`, `user/[id]`, `welcome`, `remixes`, `search`,
  `notifications`, `profile/HighlightsGallery`. Leave moderator panels
  (`mod-dashboard`, `umd/*`, `DownloadStatsPanel`, `VaultShardingPanel`,
  `pmd/PostTable`) and own-upload previews (`submit`, `divoom-import`) as
  plain `<img>`.
- Remove any `<a href={art_url}>` (audit; none expected).
- Test: a Playwright check that right-click on a card does not open the
  native menu is flaky by nature — assert the handler/attributes are
  present instead (React Testing Library or a Playwright attribute check).

### 0.2 Read-path budgets (D1, D2, D14)

- New `api/app/services/read_budget.py`:
  - `identity_for(request, user) -> Identity` — `user:{id}` for members
    and the app (JWT), `anon:{hash_ip(ip)}` otherwise (`utils/client_ip.py`,
    `utils/view_tracking.hash_ip`). Moderators/owner → exempt.
  - `consume_posts(identity, n) -> BudgetResult` — Redis `INCRBY` on
    `budget:posts:{identity}:h:{YYYYMMDDHH}` (TTL 2 h) and
    `…:d:{YYYYMMDD}` (TTL 2 d); limits from settings
    `MAKAPIX_BUDGET_ANON_POSTS_HOUR=600`, `…_DAY=2000`,
    `MAKAPIX_BUDGET_MEMBER_POSTS_HOUR=3000` (D14). Redis-down → the
    existing in-memory fallback pattern in `services/rate_limit.py`.
  - `consume_miss(identity)` — `budget:miss:{identity}:h:…`, limit 100/h
    (D2), consumed on sqid/storage-key 404s.
- FastAPI dependency `ReadBudget = Depends(read_budget)` returning a
  `BudgetContext`; endpoints call `ctx.charge(len(items))` after building
  the page and get a `429` (`AppError` code `budget_exceeded`,
  `Retry-After`, `X-Budget-Remaining`) when the *previous* total is already
  over. Charging after the fact keeps the count in posts, not requests.
- Apply to every endpoint in 01 §3: `GET /post`, `/post/recent`,
  `/post/{storage_key}`, `/p/{sqid}`, `/hashtags*`, `/feed/promoted`,
  `/feed/following`, `/search`, `/user/u/{sqid}*`, `/user/{id}`,
  `/u/{sqid}`, `/post/{id}/widget-data`. Anonymous `limit` cap 60 on the
  list endpoints (members keep 200). **Exempt:** `/sitemap.xml`, the
  moderator/admin routers, and every `/player/*` route (own buckets).
- Retire the placeholder `GET /rate-limit` (appraisal C11) — replace its
  body with the real budget state for the caller.
- Tests: charge/limit/reset per identity; anonymous vs member limits;
  moderator exemption; 429 shape; the fallback when Redis is down
  (monkeypatch); the `_reset_rate_limits` fixture covers keys.

### 0.3 Daily cap on the frozen player lookup bucket (D12)

- In `routers/player.py`, one helper `_enforce_player_lookup_limits(request)`
  used by `/player/p/{sqid}`, `/player/post/{storage_key}` and the three
  verify-* endpoints: keeps `ratelimit:player_verify:{ip}` 30/min and adds
  `ratelimit:player_verify_daily:{ip}` **300/86400 s**
  (`MAKAPIX_PLAYER_LOOKUP_DAY_CAP`). Same 429 text as today.
- FYI to the p3a firmware team (message in `docs/cert-renewal/messages/`
  style, or the next thread) — informational, no action requested.
- Tests: the 301st call in a day 429s; minute bucket unchanged.

### 0.4 License-aware member download (F1, D11, D14, D16)

- Migration (grep `alembic/versions` for the id before minting — the
  promoted-feed-order lesson): `posts.downloadable BOOLEAN NOT NULL
  DEFAULT true`; new table `download_events (id, user_id FK, post_id FK,
  variant, license_identifier, ip_hash, created_at)` with an index on
  `(post_id, created_at)` and `(user_id, created_at)`.
- `schemas.Post.downloadable: bool = True`; `PostUpdate`/edit accepts it;
  submit accepts it (default true).
- `routers/artwork.py`: `GET /d/{sqid}`, `/d/{sqid}.{ext}`,
  `/d/{sqid}/upscaled` switch to `get_current_user` (hard login →
  401 `login_required`), keep `can_access_post`, add the gate
  `post.downloadable or owner or moderator` → 403 `not_downloadable`,
  rate limit `ratelimit:download:{user_id}` 30/3600 s → 429, write a
  `download_events` row, add `Cache-Control: no-store`.
  `GET /download/{storage_key}` gets the same gates and a deprecation
  note; removal is in Phase 1 (D16).
- Web: the Download menu in `SelectedPostOverlay`, `WebPlayer`,
  `p/[sqid]` (appraisal D4 notes these are triplicated — do not fix that
  here, just gate all three): hidden when logged out (replaced by "Sign
  in to download"), disabled with "The artist doesn't allow downloads"
  when `!downloadable` and not owner/mod; the license badge already shown
  stays. Submit + edit forms: a `Checkbox` (kit) "Allow downloads"
  grouped with the license picker.
- Artist dashboard: "Downloads (30 d)" number from `download_events` —
  optional, small, do it if the StatsPanel change is one query.
- Tests: 401 anonymous; 403 non-downloadable for a member; 200 for owner
  and moderator; 30/h limit; event row written with license snapshot;
  `no-store` header; `PATCH` toggles the flag; OpenAPI regenerated
  (`make openapi`) and `make check` green.

### 0.5 Harvest detector v1 (E1)

- Extend `services/download_stats.rollup_download_stats` (nightly,
  already parses `vault-access.log`) to also write
  `harvest_signals_daily (date, env, identity_hash, ua_family, is_player_ua,
  distinct_keys, hits)` where `identity_hash = hash_ip(ip) + ':' +
  hash_user_agent(ua)`; keep 90 days (cleanup in the same task).
  `is_player_ua` = UA matches `ESP32HTTPClient|ESP32 HTTP Client|…`
  (one regex, documented next to `bot_detection.py`).
- Alert: identities with `distinct_keys ≥ 500` in a day and
  `is_player_ua = false` → one email per identity per day to the owner
  via the existing Resend mailer (subject "Harvest signal"), body: date,
  UA family, distinct keys, hits, top referer. Threshold in settings.
- Also roll `download_events` into a per-day count on the same table row
  class (variant `download`) so the dashboard has both.
- Mod-dashboard: extend `DownloadStatsPanel` with a "Harvest signals"
  table (top 20 identities, 7 days) using the chart kit's table styling.
  No block action yet (Phase 1.5).
- Tests: fixture log lines → expected rows; player UA excluded from
  alerts; alert dedup per day.

### 0.6 Declarative signals and the rights label (A1, D17-lite)

- `web/public/.well-known/tdmrep.json` (`[{"location":"/","tdm-reservation":1}]`),
  `<meta name="robots" content="noai, noimageai">` in `_app.tsx`,
  Next `headers()` adds `X-Robots-Tag: noai, noimageai` on `/p/:path*`,
  `/u/:path*`, `/` (these are not `noindex`; indexing is unaffected).
- `Caddyfile.global` vault blocks (both envs): `X-Robots-Tag "noindex,
  nofollow, noai, noimageai"` and `TDM-Reservation "1"`. Headers only;
  players ignore them. Ships via `main` + `docker restart caddy`.
- Rights label: where a post's `license` is null, overlays and `p/[sqid]`
  show "© {handle} · All rights reserved" in the slot the license badge
  uses; API docs (`docs/http-api/posts.md`) state that `license: null`
  means all rights reserved.
- `robots.txt`: unchanged (already blocks training crawlers).

### 0.7 Privacy policy (D15)

- `web/src/pages/privacy.tsx` "What we collect": one paragraph — we
  count image fetches per visitor (salted IP hash + browser hash, hourly
  and daily) to throttle bulk downloading, and we log which member
  downloaded which artwork; retention 90 days for signals, download
  events kept with the account. Bump the effective date. No ToS change.

### Phase 0 verification

- `make check-full` green; `make e2e` for the deterrent attributes and
  the download menu states.
- Dev live checks (public HTTPS, after `make rebuild` + api restart):
  anonymous `GET /api/post?limit=200` returns 60 items and, after
  600 posts within the hour, 429 with `Retry-After`; `curl -I` a vault
  URL on dev shows the new headers; `/api/d/{sqid}` anonymous → 401,
  member → 200 + `download_events` row; the 301st `/api/player/verify-user`
  from one IP → 429.
- Prod after deploy: same three curls; confirm `vault-access.log` rollup
  produced `harvest_signals_daily` rows the next morning; Web Player
  random channel and the app's feeds visibly unaffected (member budget
  3,000/h vs. ~120/h real).

### Phase 0 rollback

Every piece is behind a setting or a single migration: budgets can be set
to 0 = disabled; the download gates revert to `get_current_user_optional`
in one diff; the migration is reversible (`downloadable` column and the
events table drop cleanly).

## Phase 1 — gated art path + contract change (~2 weeks + app release)

### 1.0 App thread first

Write `docs/protect-artworks/messages/0001-server-protect-artworks-kickoff.md`
and push it to the app repo as `messages/0001-protect-artworks/…` (the
app-device-type D5 convention). Contents: the end-state diagram; the new
`art` object; `art_url`/`storage_key` removal with a dual window;
`/api/art/{sqid}/{variant}` semantics (JWT `Authorization` header, 401/403/429
codes, `Cache-Control: private`); Download now needs the JWT and may 403
`not_downloadable` (D16); notification thumbnails become short-lived
signed URLs; `/download/{storage_key}` removal date; ask for their release
ETA and whether their image cache keys on URL (it will change).

### 1.1 Gated path `GET /api/art/{sqid}/{variant}` (C1)

- Variants: `native | png | gif | webp | bmp | upscaled` → path via
  `vault.get_file_path`/`get_upscaled_file_path` with the stored
  `storage_shard` (never derived).
- Identity resolution (one dependency, reused by 0.2's budget):
  1. member/app JWT (cookie or bearer) → `user:{id}`;
  2. anonymous viewer cookie (1.2) → `viewer:{token_id}` *and* the IP-hash
     budget;
  3. unfurler UA allowlist (D13; regex over Slackbot, Discordbot,
     Twitterbot, facebookexternalhit, Bluesky, Mastodon, TelegramBot,
     WhatsApp, LinkedInBot) → `unfurl:{hash_ip}` with its own small
     budget (100/day);
  4. else 401 JSON `viewer_token_required`.
- `can_access_post`; budget `consume_posts(identity, 1)` but counted as
  **distinct sqids per hour** (`SADD budget:art:{identity}:h:…` + `SCARD`)
  so a page that re-requests the same image is not charged twice.
- Response: `FileResponse` with `Cache-Control: private, max-age=21600`,
  `Vary: Cookie, Authorization`, `ETag: "{storage_key}-{variant}"`,
  `Content-Type` by extension, `Accept-Ranges`, HEAD supported. Verify
  Starlette's `FileResponse` conditional-request (304) behaviour on the
  pinned version; if absent, handle `If-None-Match` by hand.
- Blocked identities (1.5) → 403 `identity_blocked`.
- Tests: each identity path; 401/403/429; distinct-sqid charging; ETag/304;
  `storage_shard` honoured for a legacy 3-level post; no CORS headers
  needed (same-origin) — assert none are added.

### 1.2 Anonymous viewer token (C4)

- `POST /api/viewer` → sets HttpOnly `SameSite=Lax` `Secure` cookie
  `mpx_viewer` = PyJWT `{typ:"viewer", jti, ih: hash_ip, uh: hash_ua, exp:
  +6h}` signed with the existing secret; mint limit 20/h per IP-hash.
- Validation on the gated path: signature, `exp`, `ih` matches the current
  IP-hash (IPv6 → hash the /64), `uh` matches → else 401 and the client
  re-mints silently.
- Frontend: `useViewerSession()` in `_app.tsx` ensures the cookie exists
  before the first `<ArtworkImage>` mounts (one fetch, cached in memory);
  on 429 from the art path, `<ArtworkImage>` renders a "Sign in to keep
  browsing" placeholder (kit `Notice`) and the page keeps working.
- Tests: mint, bind, expiry, mismatch, mint rate limit.

### 1.3 Serialization split (C3) with a dual window

- `schemas.PostPlayer` = today's `Post` (keeps `art_url`, `storage_key`,
  `files`), used by `player_rpc` (`query_posts`, `get_post`, `get_playset`)
  and the D9 endpoints; verify-* keep `latest_artwork_url`. Nothing on the
  frozen surfaces changes byte-for-byte — add a snapshot test on a
  fixture post.
- `schemas.Post` (web/app) gains
  `art: {sqid, native_format, variants: [..], has_upscaled: bool, url:
  "/api/art/{sqid}/native"}` and, under setting
  `MAKAPIX_WEB_ART_MODE = legacy | dual | gated` (default `dual` at
  deploy), drops `art_url` and `storage_key` when `gated`.
- Notifications (`content_art_url`, `actor_avatar_url` in REST, SSE and
  FCM payloads): out-of-band consumers cannot hold a cookie, so these
  become signed short-lived gated URLs (`/api/art/{sqid}/native?t=<jwt,
  24h, sub=recipient>`) — the one place C5 is the right shape. Avatars
  are out of scope (separate sub-vault, not artwork) and keep their URL.
- `GET /post/{storage_key}` and `GET /download/{storage_key}`: removed
  when the window closes (1.6); until then they answer but log a
  deprecation counter.
- Writer-census test: in `gated` mode, serialize a fixture post through
  every web-facing route in 01 §3 plus notifications and assert the
  vault host string never appears; a second test asserts it *does* appear
  on `player_rpc` and `/player/p/{sqid}`.
- `make openapi`; docs: `docs/http-api/posts.md`, `notifications.md`.

### 1.4 Frontend switch

- `<ArtworkImage>` reads `post.art.url` (+ variant via `post.art.variants`)
  with the legacy `art_url` as fallback during `dual`; `ensureCompatibleArtUrl`
  becomes a variant choice instead of an extension swap.
- Canvas readers (`lib/artwork-scaler/*`, `utils/webpDecoder.ts`) and the
  divoom page fetch the same-origin path — verify `COEP: require-corp`
  still passes (same-origin resources need no CORP header).
- Optional B3: `ArtworkImage` prop `blob` that fetches and sets an object
  URL (revoked on unmount); default off, enable on overlays/permalink
  where "Copy image address" matters most.
- Download menu already points at `/api/d/*` (Phase 0).

### 1.5 Harvest detector v2 + block action (E1)

- Live counters from 1.1 (`harvest:live:{identity}:h:…`, distinct sqids);
  `GET /admin/harvest-signals` merges live + nightly rows;
  `blocked_identities (kind, value, reason, by, until, created_at)` table;
  `POST /admin/harvest-signals/block` from the dashboard panel; enforced in
  identity resolution (1.1) for `viewer`, `anon`, `user` kinds (users get a
  moderation audit entry, same ladder as bans).
- Once web + app are off the vault (1.6): nightly rollup flags **any
  non-player UA on the vault** as a signal regardless of volume.

### 1.6 Close the dual window

- Trigger: app store build with the new contract is current and the
  vault log shows the app UA share on the vault ≈ 0 for 7 days.
- Set `MAKAPIX_WEB_ART_MODE=gated`; delete the deprecated storage-key
  routes; record the date in PROGRESS; the vault is now player-only.
- Rollback at any point before this: `MAKAPIX_WEB_ART_MODE=legacy`
  restores today's responses; the gated path stays harmless.

## Phase 2 — telemetry-driven (each item has a trigger; none scheduled)

| Item | Option | Trigger |
|---|---|---|
| Proof-of-work challenge before minting a viewer token; graduated throttle → block | E3 | E1 shows repeated over-budget anonymous identities after Phase 1 |
| Canary posts hidden from every human surface | E2 | enumeration patterns in the miss budget / E1 |
| Caddy `forward_auth` + `file_server` path | C2 | API latency or worker saturation attributable to `/api/art` |
| Embedded attribution / TDM metadata in PNG/GIF (WEBP only after a p3a decode test); per-download fingerprint | A3, E4 | an external consumer (takedown, platform, artist request) |
| Canvas/WebGL rendering | B4 | casual saving still reported after B1 + B3 |
| Per-post OG via gated path + unfurler budget | D13 | the SSR / per-post OG effort (appraisal F3) starts |

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Budget false positives on shared NATs (universities, offices) | anonymous over-budget is a soft "sign in" nudge; members 3,000/h; thresholds in settings; E1 shows the hit rate before tightening |
| Old app builds break when the window closes | `dual` default, long window, trigger tied to observed UA share; old builds see missing images, not crashes (ask the app team to confirm) |
| A forgotten serializer re-leaks `art_url` | writer-census test in 1.3; `AppError` codes over strings |
| API worker saturation from image bursts | budgets 429 early; `Cache-Control: private` 6 h; C2 as the scaling path |
| Shared Caddy edit for vault headers | headers only, both envs in one block edit, restart at a quiet hour; players never read headers |
| Redis outage | existing in-memory fallback pattern; budgets fail *open* (log, allow) — harvesting under an outage is acceptable, a dead site is not |
| Privacy optics of per-visitor counting | D15 paragraph, salted hashes only, 90-day retention, moderator-only dashboard |

## Out of scope, explicitly

The vault host's serving rules for players; `player_rpc` quotas (D4,
parked); sqid format; avatars and blog images; ToS text (D17); C2PA (A4);
Cloudflare or any third party (D4).
