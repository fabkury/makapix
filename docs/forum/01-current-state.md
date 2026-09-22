# Forum — current state (verified 2026-09-17)

Everything below was read from the `develop` checkout, the running containers,
and the prod/dev databases on 2026-09-17. Numbers are prod unless stated.

## 1. Community size and discussion demand

| Measure (prod) | Value |
|---|---|
| Accounts | 146 (60 created in the last 90 days) |
| Accounts with ≥ 1 artwork | 23 |
| Artworks | 3,148 (281 in the last 90 days; the August spike of 221 is a bulk period, not organic pace) |
| Artwork comments, all time | **63** (54 in the last 90 days, from **9** distinct commenters) |
| Reactions | 976 |
| Follows | 32 |
| Registered players | 28 |
| Moderators | 3 |
| Accounts active in the last 30 days (any post, comment or reaction) | **13** |
| Blog (postponed subsystem) | 1 post, 6 comments |

Monthly trend (prod, from `posts`/`comments`/`reactions`/`users.created_at`):

| Month | Posts | Comments | Reactions | Signups |
|---|---|---|---|---|
| 2026-03 | 27 | 3 | 72 | 6 |
| 2026-04 | 19 | 2 | 30 | 8 |
| 2026-05 | 29 | 1 | 47 | 15 |
| 2026-06 | 29 | 5 | 144 | 21 |
| 2026-07 | 41 | 28 | 224 | 24 |
| 2026-08 | 221 | 12 | 189 | 23 |
| 2026-09 (to the 17th) | 11 | 9 | 102 | 7 |

Site traffic from `site_stats_daily` (sum of daily values; page-view data
before the 2026-08-25 tracking fixes is inflated, see
`docs/artwork-views/` and the site-tracking memory):

| Month | Page views | Σ daily uniques | Σ daily authenticated uniques | Signups |
|---|---|---|---|---|
| 2026-06 | 10,827 | 745 | 177 | 17 |
| 2026-07 | 17,272 | 887 | 213 | 16 |
| 2026-08 | 10,251 | 1,078 | 171 | 14 |
| 2026-09 (to the 17th) | 1,532 | 203 | 44 | 2 |

**Reading.** Discussion is the least-used part of the site: sixty-three
comments in the site's life, nine people who ever wrote one, thirteen active
accounts a month. The Discord server linked from `/about` is dormant (owner,
D2). Whatever forum is chosen, **the dominant risk is an empty forum**, not
the technology. This shapes the recommendation more than any feature table.

## 2. Host, stack, and headroom

| Item | Value |
|---|---|
| VPS | Hetzner, 4 vCPU, 7.6 GiB RAM, **no swap**, 75 GB root (39 GB free), separate vault volumes |
| Usage right now | 2.6 GiB used, 5.0 GiB available (`free -h`); container RSS totals ≈ 1.25 GiB (`docker stats`) |
| Biggest containers | prod api 220 MiB, prod worker 206 MiB, dev worker 195 MiB, prod db 175 MiB, dev db 158 MiB, dev api 140 MiB |
| Limits | prod containers unlimited; dev containers capped (api 768M, worker 384M, db 1G, web 256M, …) |
| Stack | Python 3.12 / FastAPI / SQLAlchemy 2 / Celery, Next.js 14 (pages router, TypeScript), PostgreSQL 17, Redis 7 (×3 per env: cache, celery broker, realtime), Mosquitto |
| Reverse proxy | One shared Caddy (`caddy-docker-proxy` 2.8), **prod-owned**: routes come from compose labels; manual site blocks live in `deploy/stack/caddy/Caddyfile.global`. A new hostname goes live only after merge to `main`, pull in `/opt/makapix`, and a Caddy restart |
| Dev exposure | `development.makapix.club` sits behind HTTP basic auth and `X-Robots-Tag: noindex`; a dev forum hostname would need the same |
| Deploy | `make deploy` on prod (`git pull`, build, `up -d`, migrations); the Makefile supplies overlay, env file, and project name; bare `docker compose` does not work |
| Email | Resend (`RESEND_API_KEY`, sender `noreply@notification.makapix.club`); no SMTP relay configured today |
| Backups | Nightly (10:30 UTC, `/opt/makapix` cron): `pg_dump` of the prod DB + `restic` of `/mnt/vault-1`, MQTT certs, and the `.env` files → Backblaze B2; Hetzner VM images as layer 2; quarterly restore drill (`deploy/backup/backup-makapix.sh`, `docs/backups/`). **A forum with its own database or upload store is not covered until the script and the restore drill are extended.** |
| Repo | Public, Apache-2.0, `fabkury/makapix`, 6 stars (relevant to free open-source hosting eligibility, D10) |

## 3. Identity and authentication (the SSO question)

| Fact | Where |
|---|---|
| Access token: JWT HS256, 60 min, stored in **`localStorage`** by the web app | `api/app/auth.py:74-78`, `web/src/pages/*.tsx` |
| Refresh token: opaque, 30 days, **HttpOnly cookie**, `Path=/`, `SameSite=Lax`, `Secure` | `api/app/auth.py:628-720` |
| Cookie `Domain` on prod: `COOKIE_DOMAIN` is unset → auto-detected as **`.makapix.club`** ("dot prefix for subdomain support"); dev sets `.development.makapix.club` | `api/app/auth.py:625,649-669`, `deploy/stack/.env.dev` |
| Sign-in methods: email+password, email OTP, GitHub OAuth, Apple Sign-In, WebAuthn restore credentials | `api/app/routers/auth.py` |
| The site is an OAuth **client**, not an OAuth2/OIDC **provider** | no authorize/token-issuing endpoints exist |
| Roles: `users.roles` JSON (`user`, `moderator`, `owner`); `banned_until`, `hidden_by_mod`, `deactivated`, `email_verified`, `reputation`, `auto_public_approval` | `api/app/models.py:59-215` |
| Moderator/owner guards | `api/app/auth.py:441-470` |

**Consequence for any third-party forum on a subdomain (D9).** Because the
refresh cookie is scoped to `.makapix.club`, the browser sends it to **every**
subdomain, including `forum.makapix.club`. Third-party forum software would
therefore receive every visitor's refresh token on every request, and a
compromise of that software (a larger, foreign attack surface) would leak
site sessions. **Prerequisite before any subdomain forum goes live:** scope
the cookie to the bare host (set `COOKIE_DOMAIN=makapix.club` without the
leading dot, or drop the dot-prefix auto-detect). Nothing on a subdomain needs
that cookie today (the vault subdomain serves static files, the API lives
under `makapix.club/api/`). Cost: existing refresh cookies become host-only on
next issue; users with an old cookie simply re-authenticate once.

**Consequence for SSO.** With the refresh cookie readable by the API on
`makapix.club`, an SSO endpoint under `/api/v1/auth/…` can identify the
browser **server-side** without JavaScript (the same way `POST /auth/refresh`
does), so a signed-payload SSO protocol (Discourse's DiscourseConnect, NodeBB's
session-sharing JWT) is implementable as one FastAPI endpoint plus tests. An
OAuth2/OIDC-provider requirement (Misago, Apache Answer, Flarum/phpBB OAuth
plugins) would instead mean building an authorization server, which is
considerably more work and surface.

## 4. Discussion and moderation features that already exist

Detail with file references is in §7 (reuse inventory). Summary:

- **Artwork comments**: two-level nesting, anonymous authors keyed by IP,
  likes, edit, owner/mod soft-delete with mod-visible tombstone
  (`original_body`), mod hide, reportable, profanity filter. **Plain text**
  (no markdown, no mentions), **no pagination** (whole thread under a
  1,000-comment cap). 63 rows on prod.
- **Blog** (`/blog`, `/b/{sqid}`): the closest existing long-form text
  feature, with its own comments, reactions, stats and image sub-vault.
  Marked *FEATURE POSTPONED* in the UI and **deprecated by standing rule:
  never extend it**. It is *not* a forum foundation.
- **Notifications**: `social_notifications` rows + SSE stream to the
  Notifications page; reaction/comment/moderator/report kinds.
- **Reports & moderation**: `POST /v1/report` for users/posts/comments (works
  logged-out), mod-dashboard triage, hide/ban/audit log, user blocks, store-
  compliant policy text on `/about?tab=moderation`, `moderation` block in
  `/v1/config` for the app.
- **Trust**: `reputation`, badges, `auto_public_approval` (artwork review
  gate). No forum-style trust levels.
- **Rate limits**: imperative `check_rate_limit(key, limit, window)` calls
  at the top of each write handler (`api/app/services/rate_limit.py`, Redis
  with in-memory fallback); `routers/rate_limit.py` is a stub.
- **Search**: PostgreSQL trigram similarity over users/posts/hashtags; no
  full-text index.
- **Web**: `kit/` primitives are the only component home; `react-markdown` +
  `remark-gfm` + `rehype-sanitize` are dependencies but used **only by the
  deprecated Blog**; artwork thumbnails render with `image-rendering:
  pixelated` in ~20 places with no shared thumbnail primitive.

## 5. Policy surfaces a forum touches

| Surface | Today | Forum impact |
|---|---|---|
| `/terms` (`TERMS_VERSION = "2026-08-14"`, `api/app/constants.py:25`) | Artwork license choices, comment/report clauses | Add forum-text license (CC BY 4.0, D14) → bump effective date + constant together |
| `/privacy` | Lists Resend, GitHub, Firebase/Apple as processors; states no third-party trackers | If a hosted forum (D10) is used, add the host as a processor; if self-hosted, add what the forum stores (IP, email) |
| `/about` Rules / Moderation tabs | Prohibited content, how to report/block, contact `acme@makapix.club` | Apply unchanged (D14); link the forum |
| `robots.txt` | Allows search engines; blocks eight AI-training crawlers (GPTBot, ClaudeBot, anthropic-ai, CCBot, Google-Extended, Applebot-Extended, meta-externalagent, Bytespider) as "no AI scraping" positioning | Forum hostname must publish the same policy |
| `/v1/config` | Announces `moderation` to the app | A later `forum` block would announce the API for native screens (D6) |

## 6. Outreach context

`docs/outreach/` is community-led growth: Lospec (8,300-member Discord),
Pixel Joint (forums + weekly challenge since 2004), r/PixelArt, maker
communities (ESP32, Pixelix/WLED/Awtrix owners). Site copy calls Makapix "the
open community for pixel art on physical displays". The 90-day plan's
"set up the Discord structure" item produced the now-dormant server. A
public, indexable forum is the only surface in this list that accrues
searchable, permanent content (Discord content is invisible to search).

## 7. Reuse inventory (what a native forum would build on)

Condensed from a file-level sweep on 2026-09-17; line numbers are on
`develop` @ `41a0a5d`.

**Directly reusable**

| Piece | Where | Note |
|---|---|---|
| Cursor pagination (keyset, `(sort, id)` tiebreak) | `api/app/pagination.py:11-183` | Comments never adopted it; topics/replies would |
| Block filtering, generic over any author column | `api/app/utils/blocks.py:24-112` | `apply_block_filter`, `blocked_ids_for`, `ensure_not_blocked` |
| Audit writer with free-text `target_type` | `api/app/utils/audit.py:73-115`, `models.py:1204-1229` | New action names, no migration |
| Report pipeline (anonymous reports, rate limits, mod alerts by email + notification) | `api/app/routers/reports.py:36-188` | Target type is a closed `Literal["user","post","comment"]` in `schemas.py:1022,1045` plus four per-type switches in `reports.py:44-133, 350-428` |
| Shared report dialog, gated on `/v1/config` | `web/src/components/ReportDialog.tsx` (436) | Wired into three surfaces today |
| Mod dashboard (8 tabs) | `web/src/pages/mod-dashboard.tsx:230-249, 363` | A forum queue = ninth tab + loader branch |
| Ban / hide / moderator-grant paths | `api/app/routers/admin.py:35-420` | Also the hook points for forum sync tasks in `PLAN.md` |
| SSE stream + notification bus | `api/app/routers/realtime.py`, `services/event_bus.py` | Any new type rides for free |
| Rate limiter | `api/app/services/rate_limit.py:74-123` | One call per write endpoint |
| Profanity check | `api/app/routers/comments.py:179-184` | `better_profanity` |
| Sqids | `api/app/sqids_config.py` | Add a fourth encode/decode pair or reuse `encode_id` |
| Sitemap generator with visibility mirror | `api/app/routers/sitemap.py:46-138` | Add a topics block |
| `/v1/config` capability blocks (presence = launch) | `api/app/routers/system.py:28-90` | `forum` block convention ready-made |
| `kit/` primitives (Button, Dialog, Field, Notice, Tabs, …) | `web/src/components/kit/` (828 lines) | |
| Fetch layer with token refresh | `web/src/lib/api.ts:142-336` | |
| Router mounting + OpenAPI regeneration | `api/app/main.py:282-308`, `make openapi` | Additive changes stay in v1 (`docs/api-versioning-policy.md`) |

**Reusable only with changes**

| Piece | Gap |
|---|---|
| `SocialNotification` + `create_notification` (`services/social_notifications.py:38-118`) | Post-shaped: requires a `models.Post`, has `post_id` FK and no generic target. Forum types need a nullable `topic_id` (migration) or a detour through `create_system_notification`; four web renderers (`notifications.tsx:91-240`, hook, context, badge) each need a branch |
| Comment model/router as a reply engine (`routers/comments.py`, 552 lines) | Plain-text bodies, no pagination, no edit history, hard depth cap of 2, `post_id` FK. A forum reply table would be a new model that borrows the tombstone/hide pattern, not a reuse |
| Markdown rendering | Exists only in the deprecated Blog (`pages/b/[sqid].tsx:253` with `rehypeSanitize`); a server-side storage/escaping policy has never been decided |
| Search (`routers/search.py:44-268`) | Trigram `similarity()` over posts runs without an index (only `ix_users_handle_trgm` exists) and **requires auth**; forum search needs a GIN index and a public variant |
| Navigation (`components/Layout.tsx:29-58, 506-529`) | Main nav items need a 12-density PNG icon set; the overflow menu (App, Players, About, Remixes) needs none |

**Missing entirely**

- Server-side rendering for public content pages: every sqid page fetches
  in a `useEffect`; only two utility pages use `getServerSideProps`; `/p/[sqid]`
  has **no OpenGraph tags** at all.
- Email digests, per-user email preferences, unsubscribe
  (`services/email.py` is six one-shot Resend senders).
- Trust levels or automatic reputation accrual (`ReputationHistory` is
  manual, moderator-only).
- A shared artwork thumbnail primitive.

**Calibration: the Blog.** The deprecated Blog is what a parallel long-form
content type cost here: ~1,200 API lines (`routers/blog_posts.py`, every
handler now returning 503), ~1,800 web lines, a parallel comment/reaction/
stats stack, its own image sub-vault — and it still lacks notification,
search, sitemap and mod-dashboard integration. A forum MVP is at least that
much, plus those four integrations, plus SSR.
