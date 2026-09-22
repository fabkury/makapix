# Forum — implementation plan (NodeBB on the VPS with Makapix SSO)

> **Status: PLAN WRITTEN 2026-09-17, nothing implemented.** Executes the
> recommendation in [03-matrix-and-recommendation.md](03-matrix-and-recommendation.md)
> under the decisions in [DECISIONS.md](DECISIONS.md). Phase 0 is a
> one-day verification on dev whose gate can still flip the choice (see the
> flip table in 03 §3). Update [PROGRESS.md](PROGRESS.md) after every step.

## Target architecture

```
browser ──► forum.makapix.club ──► Caddy (labels on the forum container)
                 │                       │
                 │  cookie mpx_forum      ▼
                 │  (HS256 JWT, HttpOnly, makapix-prod-forum  (NodeBB 4.x, ghcr.io/nodebb/nodebb, pinned)
                 │   Domain=.makapix.club)  │  plugins: session-sharing, spam-be-gone, link-preview / makapix-embed
                 │                          │  database "nodebb" on makapix-prod-db (PostgreSQL 17, own role)
                 ▼                          │  volumes: config, build, uploads (uploads disabled; site assets only)
makapix.club/api/v1/auth/*  ────────────────┘  Write API v3 (bearer, ban / picture / delete / tokens)
  issues mpx_forum on login+refresh (verified email, not banned)
  clears it on logout; Celery tasks push ban / rename / avatar / delete
```

Hostnames: prod `forum.makapix.club` (cookie domain `.makapix.club`); dev
`forum.development.makapix.club` (cookie domain `.development.makapix.club`,
already what dev sets), behind the same basic auth and `noindex` as the dev
site. The dev hostname must be *under* `development.makapix.club` so the SSO
cookie's naked domain is the dev one and never reaches prod.

## Phase 0 — Verify on dev (1 day, gate)

Goal: prove the four facts the recommendation rests on, on the dev stack,
without touching prod, `main`, or `Caddyfile.global`.

| Step | What | Owner |
|---|---|---|
| 0.1 | DNS: `A forum.development.makapix.club → VPS IP` (Caddy needs the public name to issue TLS) | fab |
| 0.2 | Dev compose overlay: service `forum` = `ghcr.io/nodebb/nodebb:<pinned 4.16.x>`, `container_name: makapix-dev-forum`, networks `caddy_net` + `internal`, volumes `forum_config`, `forum_build`, `forum_uploads`, memory limit 768M, labels `caddy: forum.development.makapix.club`, `caddy.reverse_proxy: "{{upstreams 4567}}"`, the dev basic-auth handle and `X-Robots-Tag: noindex, nofollow, noarchive` copied from the dev `web` service. Websockets pass through Caddy's `reverse_proxy` unchanged | Claude |
| 0.3 | Database: on `makapix-dev-db`, `CREATE ROLE nodebb LOGIN PASSWORD …; CREATE DATABASE nodebb OWNER nodebb;` (secrets in `.env.dev`). NodeBB creates its own tables at setup. The API/worker role is not shared | Claude |
| 0.4 | First run: the image's `setup.json` mechanism (mounted, values from env) with `url: https://forum.development.makapix.club`, database `postgres`, admin = owner; confirm the ACP loads through Caddy | Claude |
| 0.5 | Plugins: `nodebb-plugin-session-sharing` (pin 8.0.2) and `nodebb-plugin-spam-be-gone` installed inside the container, activated, restart. Session-sharing settings: cookie name `mpx_forum`, secret = `FORUM_SSO_SECRET`, payload keys `id`/`username`/`email`/`picture`/`groups`, **revalidate** mode, group sync on with `moderators → Global Moderators` | Claude |
| 0.6 | API branch (not merged yet): issue `mpx_forum` in `set_refresh_token_cookie` (`api/app/auth.py:702`, the single choke point used by password login, GitHub callback, Apple/OAuth exchange and refresh — `routers/auth.py:530, 2216, 2458, 2527`) and clear it in `clear_refresh_token_cookie` (`auth.py:717`, used by logout `routers/auth.py:2586`). Payload: `{id: public_sqid, username: handle, email, picture: avatar_url (absolute), groups: ["moderators"] if role, exp: +24h}`; skip issuance when `not email_verified`, `banned_until` in the future, `deactivated`, or `hidden_by_mod`. Flag `FORUM_SSO_ENABLED` gates the whole thing | Claude |
| 0.7 | **Gate checks** (record each in PROGRESS.md): (a) RAM at idle and after browsing + posting, `docker stats` — bar **< 1 GiB**; (b) log in on dev site → open forum → logged in with the same handle and avatar, no registration form; (c) log out on the site → next forum request is logged out (revalidate); (d) change handle / avatar on the site → reflected on the forum on next request, or note that the Write API must push it; (e) ban a test user on the site → cookie no longer issued; `PUT /api/v3/users/{uid}/ban` with a master token works, and how to look up `uid` from our `public_sqid` (plugin hash or `bySlug`); (f) unverified-email account → forum is read-only for them; (g) post a `/p/{sqid}` link → what renders (drives step 1.4); (h) `curl` a topic page → post body present in raw HTML; (i) ACP: registration disabled, uploads disabled, ActivityPub off, email off (or Resend SMTP `smtp.resend.com:465`, user `resend`, password = API key) — confirm nothing breaks; (j) `docker exec makapix-dev-db pg_dump -Fc nodebb` works; (k) `make rebuild` on dev leaves the forum running and configured (config volume survives) | Claude |
| 0.8 | Go / no-go against the flip table in 03 §3. If go: Phase 1. If no-go on (c)/(d)/(e): re-evaluate Discourse (DiscourseConnect + `sync_sso` + `log_out`) with a swapfile; if no-go on (a): try `NODEBB_WORKERS=1`-style trimming, re-measure, else same | fab |

## Phase 1 — Production launch (3–4 days across 2–3 PRs, then seeding)

### PR-1 · API + stack (`develop`)

1. **Host-only refresh cookie (prerequisite).** In `api/app/auth.py:649-680`
   the "empty string means omit domain" branch is unreachable (an empty
   `COOKIE_DOMAIN` falls through to the dot-prefix auto-detect). Add
   `COOKIE_HOST_ONLY=true` (omit the `Domain` attribute entirely; a `Domain`
   attribute always includes subdomains, dot or no dot). Set it in
   `.env.prod` and `.env.dev`. Effect: existing refresh cookies keep working
   until re-issued; nothing on a subdomain needs it. Test: response has no
   `Domain=` on the refresh cookie; refresh still works.
2. **SSO cookie** as prototyped in 0.6, behind `FORUM_SSO_ENABLED`, with
   settings `FORUM_SSO_SECRET`, `FORUM_SSO_COOKIE_NAME`, `FORUM_SSO_COOKIE_DOMAIN`,
   `FORUM_SSO_TTL_SECONDS` (24h). Tests: issued on password login / refresh /
   GitHub callback / OAuth exchange, cleared on logout, not issued for
   unverified / banned / deactivated / hidden users, payload fields and
   signature, `Domain` and `HttpOnly` attributes.
3. **Sync tasks** (`api/app/tasks.py`, Celery, retried): `forum_sync_ban`,
   `forum_sync_unban`, `forum_sync_profile` (handle / avatar), and
   `forum_delete_account`, each calling the NodeBB Write API with
   `FORUM_API_URL` + `FORUM_API_TOKEN` (master token created in the ACP).
   Wire them into the existing ban / unban / hide / deactivate paths in
   `routers/admin.py`, the profile update path in `routers/me.py`, and the
   account-deletion flow (`docs/account-deletion/`). `uid` lookup as
   established in 0.7(e). Tests with the HTTP client mocked. No new public
   endpoint, so `api/openapi.json` should not drift; `make check` proves it.
4. **Stack:** base `docker-compose.yml` service `forum` (image pinned,
   healthcheck on `/`, `restart: unless-stopped`, volumes, env from the env
   file), prod overlay (`container_name: makapix-prod-forum`, labels
   `caddy: forum.makapix.club`, `caddy.reverse_proxy: "{{upstreams 4567}}"`,
   the same security headers and JSON access log pattern as the prod `web`
   service, log file `forum-access.log`), dev overlay from Phase 0. New
   Makefile target `forum-upgrade` (pull the new pinned tag, run
   `./nodebb upgrade` in the container, restart) and `forum-shell`.
5. **Backups** (`deploy/backup/backup-makapix.sh`, `docs/backups/`): add
   `pg_dump -Fc nodebb` (second database on the prod server), the
   `forum_config` and `forum_uploads` volume paths, and the forum env
   entries; add a forum row to the restore drill and to `RESTORE.md`. The
   B2 bucket stays under the free tier at this size.
6. **Docs:** `docs/forum/RUNBOOK.md` (ACP checklist, upgrade procedure,
   how to make someone a forum moderator, how to read the forum access log,
   what to do when session-sharing breaks: `./nodebb reset -p nodebb-plugin-session-sharing`).

### PR-2 · Forum configuration, embeds, policy, nav (`develop`)

1. **NodeBB ACP checklist** (recorded in RUNBOOK.md, applied by hand on
   prod after first start): registration *disabled* (accounts arrive only
   through SSO; login page text "Sign in on makapix.club"), file uploads
   *disabled* (D11), ActivityPub *off*, email either off or Resend SMTP,
   spam-be-gone configured (hCaptcha optional), post queue *off* (D12) but
   noted as the first lever if spam appears, `robots.txt` in the ACP
   mirroring the site's AI-training-crawler blocks, privacy/terms links
   pointing at `makapix.club/privacy` and `/terms`.
2. **Categories (initial):** Announcements · Artists: Critique & WIP,
   Techniques & Palettes, Jams & Challenges · Makers: p3a, Firmware & Players,
   Build your own (MQTT/HTTP API), Show your setup · Site: Help & Feedback.
   Global Moderators group receives the three moderators via group sync.
3. **Theme/skin:** Harmony with custom CSS carrying the site's single-accent
   palette and fonts, the Makapix logo, a header link back to `makapix.club`,
   `image-rendering: pixelated` on embedded artwork images. Kept in-repo at
   `forum/theme/` and applied through the ACP custom CSS (documented).
4. **Artwork embed by link (D11).** Primary route: a small
   `nodebb-plugin-makapix-embed` (`forum/plugins/…`, GPL-3.0, hook
   `filter:parse.post`) that turns `/p/{sqid}` links into an integer-scaled
   `<img>` + caption + license from the public post JSON (`GET /api/p/{sqid}`),
   with `image-rendering: pixelated` from the skin. OpenGraph-based previews
   (`nodebb-plugin-link-preview`) are not usable until `/p/[sqid]` gains
   server-rendered per-artwork OG tags, which is a separate outreach item
   (worth doing for every share, but not on this critical path).
5. **Policy:** `/terms` — forum text licensed CC BY 4.0 (D14), bump the
   effective date and `TERMS_VERSION` (`api/app/constants.py:25`) together;
   `/privacy` — what the forum stores (handle, email, IP, posts) on the same
   server, and that account deletion removes the forum account; `/about` —
   link the forum from the About tab and state that the Rules/Moderation
   tabs apply. `web/src/components/Layout.tsx:506-529` — a "Forum" entry in
   the overflow menu next to App / Players / About / Remixes (the main nav
   items need a 12-density icon set; the overflow menu does not).
   `robots.txt` on the main site is unaffected.
6. Playwright smoke: site login → forum shows the handle (can run against
   dev only; document as a manual step if the basic-auth hop is awkward).

### Seeding (owner + moderators, ~1 day, before the DNS switch)

Twenty to thirty evergreen topics: welcome + rules (pinned), p3a quick start
and FAQ (from `docs/player/`), firmware update notes, "build your own player"
(MQTT + HTTP API pointers), Divoom import how-to, palette and technique
threads, "show your setup", a critique-request template, the changelog
thread. Route new support email replies to forum threads from launch day.

### Launch checklist

1. `make check-full` on dev; PR `develop → main`; `cd /opt/makapix && make deploy`.
2. DNS `A forum.makapix.club → VPS IP`; Caddy picks the labels from the
   running container (no `Caddyfile.global` change, no Caddy restart needed
   — confirm the certificate appears in the Caddy log via the worker).
3. `CREATE ROLE/DATABASE nodebb` on `makapix-prod-db`; first start; ACP
   checklist; master token → `.env.prod`; sync tasks smoke (ban a test
   account, confirm on the forum; **never the demo account `fhi@kury.dev`**).
4. `FORUM_SSO_ENABLED=true` on prod; restart api; owner logs in, opens the
   forum, posts the welcome topic.
5. Nightly backup runs once with the new entries; verify the `nodebb` dump is
   in the restic snapshot.
6. PROGRESS.md entry; `docs/forum/README.md` status → LIVE; memory note.

## Phase 2 — After launch

| When | What |
|---|---|
| Launch + 90 days | Review against the criteria in 03 §5; keep / freeze read-only / rethink |
| When the app team has capacity (D6) | `forum` block in `/v1/config` (base URL, enabled) and a token-exchange endpoint (Makapix JWT → NodeBB user token via `POST /api/v3/users/{uid}/tokens`) so native screens can use NodeBB's read/write API; app thread in the app repo `messages/<NNNN>-forum/` |
| If asked | Bridge forum reply notifications into the site's Notifications page (needs a NodeBB webhook or a poller; investigate before promising) |
| Monthly | `make forum-upgrade` on dev, then prod, following NodeBB's release notes and advisories |

## Rollback

- **Before launch:** stop the container; drop the `nodebb` database; delete
  the DNS record. Nothing else changed.
- **After launch:** `FORUM_SSO_ENABLED=false` (no new cookies), remove the
  nav link, stop the container. The database and volumes stay (and stay in
  backups) so the forum can be frozen read-only or restored later. The
  host-only refresh cookie stays: it is a hardening, not a forum feature.

## Verification summary

| Phase | Proof |
|---|---|
| 0 | The 0.7 checklist recorded in PROGRESS.md with numbers |
| 1 | `make check-full` green; new pytest cases for cookies, gating, sync tasks; manual ACP checklist signed off; backup snapshot contains the `nodebb` dump; live SSO round-trip on prod by the owner |
| 2 | 90-day numbers in PROGRESS.md |

## Risks specific to this plan

| Risk | Mitigation |
|---|---|
| Caddy label pass-through for a container not in the `web`/`api` pattern | Same mechanism as `www-redirect` and dev `web`; verified on dev in 0.2 before prod |
| `make deploy` recreates the forum container on every deploy (restart, brief downtime) | Acceptable; NodeBB restarts in seconds; the config volume persists |
| NodeBB rebuild step (`./nodebb build`) inside the container needs memory during upgrades | Run upgrades off-peak; dev limit 768M catches regressions first |
| Session-sharing "revalidate" logs out users who cleared site cookies while still browsing the forum | Expected behaviour; the login page links back to the site |
| Two design systems drift | Theme CSS lives in-repo; review when the site theme changes |
| Prod database role separation | The `nodebb` role owns only its database; the API/worker role is untouched; `pg_dumpall --globals-only` already captures roles |
