# Makapix Club — Codebase Review (July 2026)

| | |
|---|---|
| **Date** | 2026-07-06 |
| **Branch / commit reviewed** | `develop` @ `deca502` |
| **Scope** | Whole repository — `api/`, `web/`, `worker/`, `mqtt/`, `deploy/` |
| **Method** | Multi-agent read-only review. Three top-level agents (security; backend performance & correctness; frontend/infra/maintainability), each of which fanned out to deep-dive sub-agents (React, infra/ops, API test-coverage). All findings de-duplicated and synthesized here; the load-bearing and contradictory claims were re-verified by hand against the code. |
| **Nature** | Static analysis of source on `develop`. No live database, Redis, or runtime profiling was used, so scale/performance claims are reasoned from code and data-volume assumptions, not measured. |
| **Revision** | v2. v1 (commit after `deca502`) captured the top-level agents' findings; **this v2 integrates the three deep-dive sub-agent reports** (frontend/React, infra/ops, test-coverage) that completed afterward — it adds one High and several Medium findings, expands the test and frontend sections, and **corrects one v1 error** (the MQTT `webclient` ACL, wrongly called "by design" in v1, is in fact a finding — see §1). |

---

## Executive summary

The codebase is, overall, in **good shape for a single-VPS social app** and shows above-average engineering discipline in the places that usually go wrong: JWT handling has no algorithm-confusion foothold, passwords use bcrypt, the *backend* OAuth flow has PKCE + state + a redirect allowlist, the vault storage layer is genuinely exemplary (atomic writes, opaque DB-stored shards, zip-slip/symlink defenses), the backup subsystem is solid (client-side-encrypted restic to B2 with a dead-man's-switch and a real restore drill), and hot read paths use keyset pagination and batched count queries rather than the naive patterns you'd expect.

That said, the review surfaced **two Critical bugs live in production right now** — account deletion silently half-completes, and the batch-download feature is 100% broken — plus a cluster of high-impact issues around the **event-rollup pipeline** (permanently losing view data daily), **cursor pagination** (500s on any non-default sort), a **frontend OAuth token-injection** gap, and **operational guardrails** (no CI before prod auto-deploy, no prod memory limits on a shared host, a Celery broker that can silently evict queued tasks, and MQTT exposure).

A theme worth stating up front: **the two Criticals and the daily data-loss bug all live in code that has no tests** — the entire Celery rollup/cleanup chain, `process_bdr_job`, and `delete_user_account_task` are untested (see §6). That's not a coincidence; it's why they shipped. None of the findings suggest the app is fundamentally unsound — they're the accumulated debt of incremental growth (an unfinished UUID⇄integer ID migration; a stats subsystem where several consumers each compute "views" differently; frontend fetch effects that didn't all adopt the codebase's own race-guard pattern). The **fix-first shortlist** below removes essentially all the user-visible breakage, data loss, and security exposure.

### Findings by severity

| Severity | Count | What it means here |
|---|---:|---|
| **Critical** | 2 | Live, confirmed data-loss / fully-broken feature |
| **High** | 7 | Security exposure, ongoing data loss, or 500s on common paths |
| **Medium** | ~26 | Real correctness/perf/ops/a11y defects; mostly bounded blast radius today |
| **Low** | ~22 | Hardening, hygiene, latent-at-scale |
| **Info** | ~4 | Scale headroom notes, latent misconfig |

---

## Fix-first: the shortlist

If nothing else gets done, do these nine. Each is confirmed and each either loses data, breaks a feature, or exposes the server / user sessions.

1. **[CRITICAL] Account deletion silently half-completes.** `api/app/tasks.py:3833` & `:3835` read `bdr.download_path`, but `BatchDownloadRequest` only has `file_path` (`api/app/models.py:1809`) → `AttributeError` aborts the task **after** posts/comments/reactions/players are deleted but **before** the user row, auth identities, and tokens are. The user thinks they're deleted but can still log in. **Fix:** `bdr.download_path` → `bdr.file_path` (both lines); add a regression test; alert on task failure.

2. **[CRITICAL] Batch-download (BDR) feature is 100% broken.** `process_bdr_job` calls `vault.get_artwork_file_path(...)` at `api/app/tasks.py:3344`, but `vault` is never imported — not in the function's imports (`:3184-3193`) and not at module level (every other task imports it function-locally). Every BDR job hits `NameError`, is marked `failed`, retries 3×. **Fix:** add `from . import vault` to the function's imports; add an end-to-end test.

3. **[HIGH] Unauthenticated SSRF via `POST /tasks/hash-url`.** `api/app/routers/legacy.py:13-24` (comment literally says "TODO: Remove in production") takes a client URL and makes the worker `requests.get` it, with no auth and no private-range/loopback/metadata-IP filtering. **Fix:** delete the endpoint, or gate behind owner-auth + resolve-then-validate the target IP against an allowlist.

4. **[HIGH] Frontend OAuth handler accepts tokens from any origin (token injection).** `web/src/components/Layout.tsx:269-306` handles `postMessage` `OAUTH_SUCCESS` and writes the supplied tokens to `localStorage` **without checking `event.origin`** (a code comment even flags the missing check). Any page holding a reference to the app window can inject attacker-controlled tokens → session fixation / account takeover. **Fix:** `if (event.origin !== window.location.origin) return;` at the top of the handler. *(The **backend** OAuth flow — state, PKCE, redirect allowlist — is solid; this is a separate frontend surface.)*

5. **[HIGH] Temporarily-banned users get a 500 on every request.** `api/app/auth.py:116` compares a tz-aware `banned_until` against a naive `datetime.now(...).replace(tzinfo=None)` → `TypeError` → 500 instead of "Account banned". The player-router copies do it correctly. **Fix:** drop `.replace(tzinfo=None)`.

6. **[HIGH] Celery broker can silently drop queued tasks.** The `cache` Redis serves both the API cache and the Celery broker with `--maxmemory-policy allkeys-lru` (`deploy/stack/docker-compose.yml:45`). Under memory pressure Redis evicts queue keys — losing view-event writes, conversions, BDR jobs, pushes, and **account-deletion** tasks with no error. Redis requires `noeviction` for broker use. **Fix:** split the broker onto its own Redis (or set `noeviction`); keep LRU only for the cache.

7. **[HIGH] The daily rollup pipeline permanently loses ~60–90 min of view events every day.** `rollup_view_events` (01:00 ET), `rollup_site_events` (02:00), and `cleanup_old_view_events` (02:30) each compute their **own** `now − 7d` cutoff, so cleanup deletes a band of events the rollup hasn't aggregated yet (`api/app/tasks.py:1275`, `:1470-1478`, `:2079-2086`, `:2169-2178`). Users can watch a post's lifetime view count **decrease**. Same race the team already caught once (the unscheduled `cleanup-old-site-events`, comment at `tasks.py:406-408`). **Fix:** one shared, day-aligned cutoff used identically by all three tasks.

8. **[HIGH] Cursor pagination 500s on any sort except the default.** `list_posts` filters the cursor by the requested sort field (`api/app/routers/posts.py:376-378`) but always **encodes** the cursor from `created_at` (`pagination.py`). Page 2 of any `sort=width|height|file_bytes|reactions|...` view either compares an ISO string to an integer column or `getattr`s a non-existent attribute → 500. **Fix:** thread the actual sort field through `create_page_response` and resolve it via `sort_field_map`.

9. **[HIGH] Nothing gates a merge to `main`, which auto-deploys to prod.** The only check is an opt-in, bypassable local `pre-push` hook running formatting + OpenAPI-drift only (`deploy/hooks/pre-push`, `Makefile`); the full test suite, `tsc`, `next lint`, and the e2e suite are never gated. `make deploy` on prod is `git pull main && compose up --build`. **Fix:** a minimal GitHub Actions workflow on PRs to `main` running `make check-full`, `tsc --noEmit`, `next lint`, `next build`.

> **One-line security quick wins** (near-zero effort, do alongside the above): delete `mqtt/config/acls:46` (`topic read #` — grants the public webclient read on *all* topics, see §1); drop/loopback-bind the plaintext MQTT host port in prod (`docker-compose.prod.yml:35-37`); `chmod 600` the broker `server.key` (`gen-certs.sh:87` currently `644`).

---

## Cross-cutting themes

Fixing these root causes resolves several individual findings at once.

- **Untested critical paths.** The two Criticals (#1, #2) and the daily data-loss bug (#7) all live in code with **zero test coverage** — the whole Celery rollup/cleanup chain, `process_bdr_job`, and `delete_user_account_task` are untested (§6). Two test files (`test_artist_dashboard.py`, `test_health.py`) contribute **zero assertions** and inflate the apparent count. This is the single highest-leverage area: tests here would have caught all three.
- **Unfinished user-ID migration (UUID ⇄ integer).** `User.id`, `Report.reporter_id`, and `AuditLog.actor_id` are `Integer`, but several endpoints still parse/declare them as `UUID`, so moderator user-report actions and admin audit filters 500 (`routers/reports.py:115-127,53,70-71`; `routers/admin.py:566,580-581`).
- **The stats/rollup subsystem is fragile and inconsistent.** Beyond #7: rollups aren't crash-idempotent and double-count on the next run (`tasks.py:1466-1480`, `:2067-2088`); unique-viewer counts double-count across the split-day boundary (`:1394,1418,1937,1981`); player views for a date with no site events are deleted un-aggregated (`:1926` vs `:2079-2086`); and **three** code paths compute "total views" differently, two of which undercount recent posts (`services/post_stats.py:92-133` correct vs `user_profile_stats.py:137-149` and `routers/reactions.py:412-437`). A single shared, day-aligned, watermark-based aggregation collapses most of this.
- **A whole class of cursor-pagination bugs.** The non-default-sort 500 (#8), search pagination that's silently dead and would crash if reached (`routers/search.py:109-113,157-167`), and followers/following lists that filter on the wrong entity's timestamp and silently skip/duplicate rows past page 1 (`routers/users.py:1327-1335,1392-1401`).
- **Frontend fetch effects that didn't adopt the codebase's own race-guard.** `SelectedPostOverlay` and `p/[sqid].tsx` correctly use a `cancelled` flag; their siblings `CommentsAndReactions` (`:85-120`) and `WebPlayer` (`:1217-1232`) don't, so navigating between posts can render stale reactions/comments. Same "fix already exists next door" shape as several backend findings.
- **Reverse-proxy client-IP handling is broken, undermining rate limiting.** Uvicorn runs without `--proxy-headers`, so `request.client.host` is always Caddy's bridge IP — collapsing every auth throttle into **one global bucket** an attacker can exhaust to lock everyone out. Meanwhile the *other* `get_client_ip` trusts the client-controlled leftmost `X-Forwarded-For`, so the player-token brute-force limiter and IP bans are bypassable (`routers/auth.py:140-147` vs `auth.py:547-565`, `utils/view_tracking.py:206-213`). One fix (`--proxy-headers --forwarded-allow-ips=<caddy>` + a single correct `get_client_ip`) unblocks all of it.
- **Operational guardrails are thin for something that auto-deploys to prod.** No CI (#9); prod runs a **single** uvicorn worker (the 2-worker `api/Dockerfile.prod` is dead code) **and** runs the bind-mounted host working tree rather than the built image (`docker-compose.yml:114-115,160-162`); no prod memory limits on a host shared with dev; plaintext MQTT + an over-permissive MQTT ACL are exposed.

---

## Detailed findings

Severity in brackets. Confidence is **Confirmed** (code path traced) unless marked *Suspected*. Locations are `file:line` on `develop@deca502`.

### 1 · Security

- **[HIGH] Unauthenticated SSRF — `POST /tasks/hash-url`.** `routers/legacy.py:13-24` → `tasks.py:460-483`. Shortlist #3.
- **[HIGH] Frontend OAuth `postMessage` handler doesn't verify `event.origin`.** `web/src/components/Layout.tsx:269-306`. Shortlist #4. Token injection into `localStorage` from any origin able to `postMessage` the app window.
- **[MEDIUM] MQTT ACL grants the *public* webclient read on ALL topics.** `mqtt/config/acls:46` — a bare `topic read #` sits inside the `user webclient` stanza (opened `:39`; no `user`/`pattern` line follows), so it applies to `webclient`, not as a global "deny". The comment (`:45`) intends "default deny", but Mosquitto already default-denies unlisted topics when an `acl_file` is set, so this line only *adds* permission. The `webclient` password is **public** by design (baked into the browser bundle via `NEXT_PUBLIC_MQTT_WEBCLIENT_PASSWORD`; `web/Dockerfile:62-65`), so **any site visitor** can subscribe to `makapix/player/#` and watch every player's commands/status/view events — a cross-user activity/privacy leak. **Fix:** delete line 46. *(This corrects a v1 "not a finding" note.)*
- **[MEDIUM] Reverse-proxy client-IP broken → rate limits ineffective *and* spoofable.** No `--proxy-headers`/ProxyHeaders middleware; two conflicting `get_client_ip` impls (`routers/auth.py:140-147` uses `request.client.host`; `auth.py:547-565` & `utils/view_tracking.py:206-213` trust leftmost XFF). Auth throttles collapse to one global bucket (lockout DoS); XFF-based limits (incl. the 60/hr player-token brute-force cap at `auth.py:372-381`) and IP bans are bypassable; `comment.author_ip` (`routers/comments.py:211`) is poisonable.
- **[MEDIUM] Player bootstrap endpoints are UUID-only bearer credentials.** `routers/player.py:337-409` (`GET …/credentials` returns the device mTLS **private key** + mints the API token) and `:412-456` (`POST …/token/rotate` revokes the live device's token then issues a new one — `services/player_tokens.py:35-46`). Knowing a `player_key` (a semi-public identifier elsewhere) yields device takeover + DoS with no owner binding/notification.
- **[LOW] Internal error strings leaked to clients** via `detail=str(e)` — `routers/relay.py:63,94,123,288`, `player.py:518,1667,1676`, `auth.py:1618,2146`, `mqtt.py:58`, `posts.py:1465`. Recon-grade info disclosure. (No stack traces reach clients.)
- **[LOW] Broker `server.key` is world-readable (`644`).** `deploy/stack/mqtt/gen-certs.sh:87` `chmod 644 server.key`; confirmed on disk. (`ca.key` correctly `600`.) Any process/user on the host can read the broker's TLS private key.
- **[LOW] MQTT passwords echoed to logs on every startup.** `gen-passwd.sh:43-45` print backend/player/webclient passwords to stdout; `mosquitto.conf:6` `log_dest stdout` → they land in `docker logs`/json-file.
- **[LOW] `POST /report` has no rate limit and no target validation** (`routers/reports.py:24-47`, TODOs acknowledge both) → report-queue spam, junk rows.
- **[LOW] `GET /relay/jobs/{id}` has no auth/ownership check** (`routers/relay.py:381-397`). Low practical risk (unguessable UUID) but returns repo/commit/error strings.
- **[LOW] Caddy admin API reachable across `caddy_net`.** `docker-compose.yml:191` `CADDY_ADMIN=0.0.0.0:2019` (host mapping is correctly loopback-only). Any container on `caddy_net` can `POST caddy:2019/load` to reconfigure the proxy. All first-party today.
- **[INFO] CORS credential-reflecting wildcard is possible.** `main.py:223-244`: if an operator ever sets `CORS_ORIGINS="*"`, Starlette reflects any origin *with* credentials (only a warning logged). **Fix:** hard-reject `"*"` when credentials are allowed.
- **[INFO] Login user-enumeration + DEBUG SQL echo.** `auth.py:470-481` returns 403 "Email not verified" before the password check (documented UX tradeoff); `db.py:46` enables SQL `echo` when `LOG_LEVEL=DEBUG`. Ensure prod is never `DEBUG`.

**Notably safe:** no SQL injection (the few `text()` calls are static/parameterized), no path traversal (vault paths from DB-stored opaque shards + UUID keys, extensions whitelisted, `mkpx/` blocked at the mount), zip-slip/symlink defenses on uploads, image inspection in an isolated 30s-timeout subprocess, XSS-safe user content (whitelist markdown parser + `rehype-sanitize`), no secrets committed to git (verified via `git ls-files`; FCM/backup creds live outside the repo).

### 2 · Correctness & data integrity (backend)

- **[CRITICAL] Account deletion crashes half-way** — `tasks.py:3833,3835`. Shortlist #1.
- **[CRITICAL] BDR feature fully broken** — missing `vault` import, `tasks.py:3344`. Shortlist #2.
- **[HIGH] Temp-banned users → 500 on every request** — `auth.py:116`. Shortlist #5.
- **[HIGH] Cursor pagination 500s on non-default sorts** — `posts.py:376-378` + `pagination.py`. Shortlist #8.
- **[HIGH] Rollup/cleanup cutoff misalignment loses view events daily** — `tasks.py:1275,1470-1478,2079-2086,2169-2178`. Shortlist #7.
- **[MEDIUM] Search pagination is dead code and would crash if reached.** `routers/search.py:109-113,157-167,186,236-249`.
- **[MEDIUM] Followers/following pagination filters the wrong timestamp.** `routers/users.py:1327-1335,1392-1401` — cursor encodes the user's **signup** time → silent skips/dupes past page 1.
- **[MEDIUM] UUID-vs-Integer mismatches break report actions & admin filters.** `routers/reports.py:115-127,53,70-71`; `routers/admin.py:566,580-581`.
- **[MEDIUM] Rollups aren't crash-idempotent.** `tasks.py:1466-1480,2067-2088` commit `+=` increments in batches, delete raw events at the end → a mid-run crash double-counts on the next run.
- **[MEDIUM] `unique_viewers`/`unique_visitors` double-counted across the split-day boundary.** `tasks.py:1394,1418,1937,1981`. Fixed for free by the day-aligned cutoff (#7).
- **[MEDIUM] `rollup_site_events` drops player views for site-event-less dates.** `tasks.py:1926` vs `:2079-2086`.
- **[MEDIUM] Shared feed cache leaks the cache-filler's `user_has_liked` to anonymous users.** `posts.py:949-963` vs `:911-916`; same in `search.py:383-396/438` and `:719-734/778`. Anon visitors see a logged-in user's like flags (≤ TTL). **Fix:** annotate likes *after* `cache_set`.
- **[MEDIUM] Three "total views" computations disagree.** Correct: `services/post_stats.py:92-133`. Undercounting: `services/user_profile_stats.py:137-149` (a <7-day-old post shows 0 views on its author's profile) and `routers/reactions.py:412-437`.
- **[MEDIUM] `periodic_check_post_hashes` only ever checks the same 100 posts.** `tasks.py:594-606` — `.limit(100)` with no `ORDER BY`/watermark.
- **[MEDIUM] `feed_following` missing visibility filters + pagination.** `routers/search.py:822-841` omits `hidden_by_user`/`non_conformant` (author-hidden and mod-flagged posts still appear in followers' feeds) and ignores the cursor.
- **[LOW] Idempotent write endpoints 500 under concurrent duplicates.** No `IntegrityError` catch on reaction/follow/comment-like inserts (`routers/reactions.py:165-229`, `users.py:1178-1203`, `comment_likes.py:94-106`); the reaction 5-cap can over-admit to 6 under a race.
- **[LOW] SSAFPP retry loses `PostFile` rows.** `tasks.py:2885-2890,2993-3000,3130` — a retry sees the file exists → records `"exists"` → never creates the DB row.
- **[LOW] Assorted:** comments endpoint ignores `cursor`/`view`, truncates at `limit`, drops replies whose parents fall outside the window (`routers/comments.py:31-123`); `save_upscaled_artwork` skips `ensure_vault_headroom` (`vault.py:458-471`); `replace_artwork` takes no row lock → concurrent replaces orphan bytes (`posts.py:1781+`); `permanent_delete_post` deletes vault files before the DB row (`posts.py:1415-1435`); naive `datetime.utcnow()` into tz-aware `read_at` (`services/social_notifications.py:289,321`).

### 3 · Performance & scalability (backend)

- **[HIGH] Celery broker on `allkeys-lru` Redis can silently drop tasks** — `docker-compose.yml:45`. Shortlist #6.
- **[MEDIUM] Hashtag endpoints load the entire posts table into Python per cache miss.** `routers/search.py:295,499,638` do `base_query.all()` (full rows) and aggregate in Python; cache keys include `q`/`cursor` so search-as-you-type triggers a full-table load per keystroke, and `ILIKE '%q%'` can't use the GIN index. **Fix:** SQL `unnest(hashtags) … GROUP BY`; key typeahead cache on the normalized prefix.
- **[MEDIUM] Artist dashboard: unbounded row loads + per-post N+1.** `services/artist_dashboard.py:189-196,288-292,322-330,407-409` materialize every recent view event / reaction / comment and aggregate in Python, then call `get_post_stats` per listed post.
- **[LOW] N+1 in secondary paths.** `comment_likes.py:169-171` (lazy `like.user` per row); `tasks.py:3265-3272` (`User.handle` per comment in BDR export).
- **[LOW] `check_rate_limit` re-arms the TTL on every allowed request and is non-atomic.** `services/rate_limit.py:99-118` — the window never rolls off during steady activity. **Fix:** set expiry only when `INCR` returns 1 (as `cache.py:308-311` already does).
- **[INFO] Scale-headroom notes (not bugs today):** one Celery task per view event (`utils/view_tracking.py:339,429-442`); single uvicorn process with a ~40-thread pool vs a 30-conn DB pool (`db.py:49-52`); public-feed queries ride the single-column `created_at` index (`models.py:445-449` — a partial composite index is the natural next step); rollup batching uses `OFFSET` (O(n²)).

### 4 · Infrastructure, deployment & operations

- **[HIGH] No CI gate before prod auto-deploy** — `deploy/hooks/pre-push`, `Makefile`. Shortlist #9.
- **[MEDIUM] Prod runs a single uvicorn worker; `api/Dockerfile.prod` (2 workers) is dead code.** No compose/Makefile/doc references `Dockerfile.prod`; the base single-process `command` (`docker-compose.yml:113`) wins because the prod overlay never re-specifies it. **Fix:** set `command: uvicorn … --workers 2` in the prod overlay (or wire in `Dockerfile.prod`).
- **[MEDIUM] Prod runs the bind-mounted host working tree, not the built image.** `docker-compose.yml:114-115` (`../../api:/workspace/api`) and worker `:160-162` are in the **base** file, so they apply to prod and shadow the image's `COPY`. Running code = host tree; the image only supplies deps. `git pull` + restart changes prod code without a rebuild, and pulled code needing a new dep breaks until `--build`. **Fix:** don't bind-mount source in the prod overlay; treat the image as the source of truth.
- **[MEDIUM] No memory limits anywhere; prod has no resource limits at all — on a host shared with dev.** `docker-compose.dev.yml` caps CPU (and some memory) per service; `docker-compose.prod.yml` + base set **none**. One leaking/spiking container can OOM the whole VPS and take down prod **and** dev together. **Fix:** `mem_limit` on `api`/`worker`/`db`/`web` in the prod overlay.
- **[MEDIUM] Plaintext MQTT (:1883) is published on the public interface in prod.** `docker-compose.prod.yml:35-37` binds `1883:1883` to `0.0.0.0`; that listener has password auth but **no TLS** (`mosquitto.conf`), and its own config comment says it's for the internal API only. Sniffed `svc_backend` creds let an attacker publish `makapix/player/+/command`. **Fix:** drop the host mapping (or bind `127.0.0.1`); keep only 8883 (mTLS) public.
- **[MEDIUM/LOW] `make clean` / `down -v` destroys the dev DB (prod is protected, dev isn't).** `pg_data_prod` is `external: true` (safe); `pg_data_dev` (`docker-compose.dev.yml:227-229`) is **not**, so `make clean` (`Makefile:179`) wipes it. Recoverable but an asymmetric foot-gun. **Fix:** mark `pg_data_dev` external too.
- **[LOW] Prod API/worker images ship dev deps and run as root.** `api/Dockerfile:15` & `worker/Dockerfile:15` install `[dev]` extras; none of the Python/MQTT Dockerfiles set `USER` (only `web` drops privileges). **Fix:** non-`[dev]` prod install + non-root `USER`.
- **[LOW] Embedded Celery beat in the worker.** `worker/worker.py:60` runs `worker --beat`. Safe at one worker per env, but scaling the worker → **duplicate beat → double rollups/cleanups**. Note if you ever add worker replicas.
- **[LOW/INFO] Assorted ops hygiene:** no HSTS/security headers on the main site (`Caddyfile.global` sets them only in the vault blocks); `web_next_static` volume never pruned (`web/entrypoint.sh:18-20`) → slow unbounded disk growth; `web/src/pages/debug-env.tsx` ships to prod at `/debug-env`; two `alpine:latest` stub containers unpinned (`docker-compose.yml:226,237` — everything real is pinned); Pixelc build fetches libwebp/giflib tarballs with no checksum (`/opt/Pixelc/Dockerfile:10,21`); divergent env examples and stale container names in `README.stack.md`.

> **By design (verified, not findings):** the `webclient` password being public is fine *in principle* — the problem is only the over-broad ACL line above; rate limiter fails **closed** to an in-memory limiter; refresh-token cookie is `HttpOnly` + `SameSite`; DB ports are loopback-only in both envs; `pg_data_prod`/`caddy_data`/`caddy_config` are protected from `down -v`; `gen-certs.sh:18-52` encodes the June-2026 CA incident (refuses to mint a new CA that would invalidate player certs).

### 5 · Frontend & maintainability

- **[MEDIUM] Search debounce is fully defeated + no race guard.** `web/src/pages/search.tsx:267-273,323-341` — `handleSearchChange` updates `?q=` then sets a 300 ms timer, but a *separate* effect on `[router.query.q]` fires `performSearch` **immediately** on every `?q=` change, so the debounce never applies (every keystroke hits `/api/search`, plus a duplicate 300 ms later) and out-of-order responses render stale results. **Fix:** drop the redundant path; add a cancellation guard.
- **[MEDIUM] Widget/WebPlayer fetch effects overwrite state on stale responses.** `CommentsAndReactions.tsx:85-120` and `WebPlayer.tsx:1217-1232` await then unconditionally `setState`; navigating/advancing between posts lets an older response land last → wrong reactions/comments. The sibling `SelectedPostOverlay.tsx:744-772` already uses a `cancelled` flag — apply the same pattern.
- **[MEDIUM] Notifications context value isn't memoized → app-wide re-renders.** `web/src/contexts/SocialNotificationsContext.tsx:227-240` passes a fresh object to the Provider every render, so every consumer re-renders on any state change (incl. `loading` toggling during fetches). **Fix:** `useMemo` the value.
- **[MEDIUM] Modal overlays have no focus trap / focus management.** `SelectedPostOverlay.tsx:1547-1552`, `SelectedArtworkOverlay.tsx:859` — `role="dialog" aria-modal="true"` with Escape + click-outside, but focus is never moved into the dialog and Tab can escape to the background; the comments sub-overlay has no Escape-to-close (`SelectedPostOverlay.tsx:1466`). **Fix:** initial focus + trap, Escape on the sub-overlay.
- **[MEDIUM] 1,700-line legacy `web/src/pages/user/[id].tsx` duplicates the canonical `u/[sqid].tsx` and has diverged.** Header calls it a redirect, but it keeps a full second profile implementation as a fallback for users lacking `public_sqid` — which is backfilled for everyone (`api/app/auth.py:154-157`), so ~1,560 lines are effectively dead and drifting. **Fix:** reduce to a thin redirect stub (like `post/[id].tsx`).
- **[MEDIUM] Next.js pinned to 14.2.3** (`web/package.json`) — misses ~2 years of 14.2.x security patches. *Mitigated:* no `middleware.ts`, no `pages/api`, raw `<img>` not `next/image`. **Fix:** bump to latest 14.2.x (drop-in). *(Suspected exploitability, Confirmed version.)*
- **[LOW] Unbounded feed, no virtualization.** `CardGrid.tsx:301` + `index.tsx:151` accumulate all posts as DOM nodes. **Well mitigated** by `content-visibility:auto` + `contain-intrinsic-size` (`CardGrid.tsx:416-417`) so offscreen paint/decode is cheap, but node count still grows unbounded — consider a page cap/windowing for very long feeds.
- **[LOW] Redundant duplicate network request in the artwork overlay.** `SelectedArtworkOverlay.tsx:63-90,427,456` issues two GETs to `/api/post/{id}/reactions` (for `.mine` and `.totals`) where the endpoint returns both, and a third for comments — where the sibling uses one `/widget-data`. **Fix:** collapse to one request.
- **[LOW] `usePMDSSE` stale-closure + reconnect churn.** `web/src/hooks/usePMDSSE.ts:37-52,111,127-137` — inline callback props re-establish the EventSource every render. **Fix:** stabilize callbacks via refs.
- **[LOW] `localStorage` writes without try/catch in `WebPlayer`.** `WebPlayer.tsx:794,1726,1733` (targets old/low-end kiosk browsers where `setItem` can throw). `Layout.tsx` wraps all writes; `WebPlayer` doesn't.
- **[LOW] `useArtworkScaling` may be dead code.** `web/src/hooks/useArtworkScaling.ts:11-140` runs once (`deps [gridRef]`) and does imperative DOM mutation, but `CardGrid` does its **own** scaling in a `useLayoutEffect` keyed on `posts` (`CardGrid.tsx:197-292`). **Confirm it's still wired**; if not, delete.
- **[LOW] Uncleaned `setTimeout`s + object-URL leak.** `PlayerBar.tsx:99-101` (untracked pulse timers → setState-after-unmount); `submit.tsx:311-312,387-388` (`createObjectURL` without revoking the prior URL or on unmount).
- **[LOW] `pyodide` npm dep is unused; divoom decode depends on an external CDN.** `pyodide` is declared but never imported; the runtime injects `<script src="https://cdn.jsdelivr.net/pyodide/...">` **lazily inside `init()`** (`web/src/lib/divoom/pyodideDecoder.ts:135`) — so it's *not* eager (page load is unaffected), but a user decoding a divoom file depends on jsdelivr, and the dep is dead weight in the manifest. **Fix:** drop the dep or self-host Pyodide (as done for zstd/lzo/webp WASM).
- **[LOW] `any`/unsafe casts concentrated in a few files** (61 total; worst: `p/[sqid].tsx` ×9, `divoom-import.tsx` ×6, `webpDecoder.ts` ×5, `PlayerCard.tsx` ×5, `search.tsx` ×4). `strict` is on and `tsc` passes.
- **[LOW/INFO] Dead prototype files at repo root:** `backend_service.py`, `views.csv`, and duplicated `logo-intro-*.webp` (one byte-identical to `web/public/brand/…`). **Fix:** delete.

### 6 · Testing & CI

- **[MEDIUM] The load-bearing Celery rollup/cleanup chain has *no* tests.** Of ~30 tasks, only `cleanup_retired_artwork` has a direct test. **Untested:** `rollup_view_events` (~250 lines), `rollup_site_events` (~430 lines), `cleanup_old_view_events`, `cleanup_old_site_events` — the exact order-sensitive chain CLAUDE.md flags as load-bearing — plus `write_view_event`, `process_ssafpp`, `process_bdr_job`, and `delete_user_account_task`. **The two Criticals and the daily data-loss bug all live here.** This is the highest-leverage test gap.
- **[MEDIUM] Two test files provide false coverage (zero assertions).** `test_artist_dashboard.py` — 5 test functions, every body is `pass` (only comments). `test_health.py` — dead file (`# Health check test removed`), so `/health` is untested *even though it's the container healthcheck target* (`docker-compose.yml:128`). **Fix:** implement or delete; they inflate the apparent count.
- **[MEDIUM] Tests build the schema via `Base.metadata.create_all()`, not Alembic** (`api/tests/conftest.py:97-99`) — the migration chain is **never** exercised, so model/migration drift ships undetected. **Fix:** `alembic upgrade head` against the fresh test DB.
- **[LOW] Over-mocking the thing under test.** Rate-limit 429 (`test_player_rpc_http.py:390`) and storage-quota 413 (`test_mkpx.py:212`) are asserted only by patching the gate itself → they validate the endpoint's *reaction*, not the gate logic. (Quota accounting *is* tested for real at `test_mkpx.py:423`.)
- **[LOW] Shared mutable global state in auth tests.** `test_auth.py:47-70` and `test_oauth_native.py:87-164` assign `auth_router.GITHUB_*` at process-global scope with no teardown → values leak across tests (low real risk; always the same value). Also `test_auth.py`/`test_posts.py` build bare `TestClient(app)` instead of the `client` fixture, bypassing the session-override (works only because `TEST_DATABASE_URL` steers to the same DB).

**Coverage map (approximate)** — ~10 of 31 routers have any direct endpoint test; ~9 of 25 services have meaningful tests. The harness itself is a genuine integration harness (real Postgres `makapix_test`, real Redis, per-test `TRUNCATE … CASCADE` isolation) and the covered areas are covered *well*.

| Well covered | Partial | **No direct tests** |
|---|---|---|
| auth/token/OTP/OAuth, vault (upload/serving/reshard/avatar), posts/replace/mkpx, player + player-RPC, MQTT publisher/player-requests + cert lifecycle, hashtags/mod, handles/user-update, realtime, config, errors | system (`/health` untested), users (browse/follow/avatar/delete/highlights untested), admin (2 of ~13 endpoints), reactions/comments (models inserted directly; POST endpoints not hit), rollups (only download-stats service, not the beat tasks) | **search, playlists, comments, reactions endpoints, reports, moderation (umd/pmd/ban/hide), sitemap, tracking, badges, categories, licenses, profiles, social_notifications, blog CRUD, mqtt/relay/legacy/stats routers**; services: artist_dashboard, post_stats, site_stats, social_notifications, profanity, password_reset, email_verification, player_views |

The **social/content-management half of the app** (comments, reaction/comment endpoints, playlists, search, reports, moderation, feeds, tracking) is essentially untested.

---

## What's already done well

Worth stating plainly — it's the reason most findings above are bounded:

- **Auth & sessions:** single fixed JWT algorithm (no alg-confusion / no `none`), boot-time secret-entropy checks, per-request user re-read so bans/deactivations take effect immediately; bcrypt passwords; refresh tokens hashed at rest, DB-revocable, rotated with a grace window. **Backend OAuth:** state nonce in a `SameSite=None; Secure` cookie, PKCE **S256** required with an allowlisted `redirect_uri`, single-use codes via Redis `GETDEL`, linking only on a **verified** GitHub email.
- **Vault layer (exemplary):** atomic temp-file + fsync + rename writes, stored-shard-as-source-of-truth with explicit refusal to derive paths, twin mirroring + a clean miss-only legacy remap; zip-slip/symlink/size defenses; extension whitelist; `mkpx/` blocked at the mount.
- **Backups (solid):** client-side-encrypted restic to B2, healthchecks.io dead-man's-switch, weekly `forget --prune` + `check --read-data-subset`, and a real quarterly restore drill that byte-compares vault files and row-counts a restored dump. Secrets live outside the repo.
- **Hot read paths:** keyset (not `OFFSET`) pagination on the default feed, batched `IN` count annotation, `selectin` on `Post.files`; view/site events recorded fully off the request path.
- **Frontend:** genuinely robust API client (single-flight token refresh, definitive-vs-transient failure handling, SSR-guarded `localStorage`); disciplined code-splitting (lazy `ssr:false`, on-demand WASM codecs, Pyodide loaded only on use); a **size-capped LRU** widget cache and an extracted 1 Hz countdown so the player's tick re-renders only the banner; consistent a11y basics (verified `alt`/`aria-label` across 73 images — no systemic gap); the *correct* async race-guard pattern in several components (the findings above are its siblings that didn't adopt it).
- **Infra:** model multi-stage `web/Dockerfile` (non-root, ~165 MB standalone, static-merge entrypoint that avoids mid-deploy 404s); core-path healthchecks + ordered `depends_on`; loopback-only DB ports; critical volumes protected from `down -v`; the CA-pair guard that encodes the June-2026 incident.
- **Care in the known-hard spots:** mod-hashtags uses `FOR UPDATE`, replace-artwork rotates storage keys for cache correctness, the racing site-events cleanup was identified and unscheduled, uploads insert the DB row before the vault write so the unique index prevents orphan files.

---

## Methodology, coverage & limitations

Multiple independent read-only agents reviewed the repo in parallel along different axes, each fanning out to deep-dive sub-agents (React, infra/ops, API test-coverage). Every finding cites code an agent actually read. The highest-stakes and contradictory claims were **re-verified by hand**: the two Criticals (`models.py:1809` has only `file_path`; `tasks.py:3184-3193` imports lack `vault`), the SSRF (`legacy.py` has no auth dep), the banned-user bug (`auth.py:116` aware-vs-naive), the OAuth `postMessage` gap (`Layout.tsx:271` comment + no `event.origin` check), the MQTT ACL (`acls:46` under the `webclient` stanza), the two zero-assertion test files, and the prod bind-mount (`docker-compose.yml:114-115`).

**Depth was uneven, by design.** Reviewed in depth: `auth.py`, `main.py`, `db.py`, `cache.py`, `pagination.py`, `models.py`, `tasks.py`, `vault*.py`, the main feed/search/posts/reactions/comments/users/admin/reports/player routers, core services, the full route→auth-dependency map, all Dockerfiles + compose overlays + Caddy/Mosquitto/ACL config, the backup scripts, the web API client + hot components + hooks + contexts, and the test suite. `tsc --noEmit` (clean) and `next lint` (clean; 132 warnings) were run.

**Not (or only lightly) covered — treat as unknown, not clean:** the 2,692-line `routers/auth.py` OAuth/OTP/registration internals; `blog_posts.py` + blog stats (patterns mirror the post-stats code, so the stats findings **likely apply there too** — *Suspected*); the `app/mqtt/` subscriber threads; `player_rpc`/`relay` task bodies; email services; a dependency-version audit of `requirements*.txt`; the largest web components' internal render behavior; the Playwright e2e suite contents; and any runtime/load behavior (this was static review only). A follow-up pass on the auth router internals would be the highest-value next investment.

---

## Suggested remediation order

1. **Today (data loss / broken features):** shortlist #1 and #2 — both are ~one-line fixes; add the regression tests §6 flags as missing while you're there.
2. **This week (security + ongoing data loss):** shortlist #3 (SSRF), #4 (OAuth origin), #5 (banned-user 500), #6 (broker eviction), #7 (rollup data loss), plus the one-line MQTT/cert quick wins. Do the reverse-proxy `--proxy-headers` fix here too — it unblocks all the rate-limiting findings at once.
3. **Next (user-visible correctness):** shortlist #8 (pagination) and the rest of the pagination class; the UUID-vs-integer cleanup; unify the three "views" computations; the anon `user_has_liked` cache leak; the frontend stale-response races.
4. **Then (guardrails & hygiene):** shortlist #9 (CI), prod worker count + bind-mount + memory limits + MQTT exposure, `alembic`-based tests + smoke tests for the untested social/content routers, and the maintainability cleanup (legacy profile page, dead files, Next.js bump).
