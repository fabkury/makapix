# Makapix Club — Codebase Review (July 2026)

| | |
|---|---|
| **Date** | 2026-07-06 |
| **Branch / commit reviewed** | `develop` @ `deca502` |
| **Scope** | Whole repository — `api/`, `web/`, `worker/`, `mqtt/`, `deploy/` |
| **Method** | Three parallel read-only review agents (security; backend performance & correctness; frontend/infra/maintainability), findings de-duplicated and synthesized here. The two Critical items, the top security item, and the banned-user bug were additionally re-verified by hand against the code. |
| **Nature** | Static analysis of source on `develop`. No live database, Redis, or runtime profiling was used, so scale/performance claims are reasoned from code and data-volume assumptions, not measured. |

---

## Executive summary

The codebase is, overall, in **good shape for a single-VPS social app** and shows above-average engineering discipline in the places that usually go wrong: JWT handling has no algorithm-confusion foothold, passwords use bcrypt, the OAuth/native flow has PKCE + state + a redirect allowlist, the vault storage layer is genuinely exemplary (atomic writes, opaque DB-stored shards, zip-slip/symlink defenses), and hot read paths use keyset pagination and batched count queries rather than the naive patterns you'd expect to find.

That said, the review surfaced **two Critical bugs that are live in production right now** — account deletion silently half-completes, and the batch-download feature is 100% broken — plus a cluster of high-impact issues around the **event-rollup pipeline** (which is permanently losing view data every day), **cursor pagination** (which 500s on any non-default sort), and **operational guardrails** (no CI gate before prod auto-deploy, no memory limits on a shared host, a Celery broker that can silently evict queued tasks).

None of the findings suggest the app is fundamentally unsound. They are the accumulated debt of incremental growth — most notably an unfinished user-ID migration (UUID-vs-integer mismatches) and a stats/rollup subsystem whose several consumers each compute "views" differently. The **fix-first shortlist** below is eight items; working through those removes essentially all the user-visible breakage and data loss.

### Findings by severity

| Severity | Count | What it means here |
|---|---:|---|
| **Critical** | 2 | Live, confirmed data-loss / fully-broken feature |
| **High** | 6 | Security exposure, ongoing data loss, or 500s on common paths |
| **Medium** | 20 | Real correctness/perf/ops defects; mostly bounded blast radius today |
| **Low** | ~15 | Hardening, hygiene, latent-at-scale |
| **Info** | 3 | Scale headroom notes, latent misconfig |

---

## Fix-first: the shortlist

If nothing else gets done, do these eight. Each is confirmed and each either loses data, breaks a feature, or exposes the server.

1. **[CRITICAL] Account deletion silently half-completes.** `api/app/tasks.py:3833` & `:3835` read `bdr.download_path`, but `BatchDownloadRequest` only has `file_path` (`api/app/models.py:1809`) → `AttributeError` aborts the task **after** posts/comments/reactions/players are deleted but **before** the user row, auth identities, and tokens are. The user thinks they're deleted but can still log in. **Fix:** `bdr.download_path` → `bdr.file_path` (both lines); add a regression test; alert on task failure.

2. **[CRITICAL] Batch-download (BDR) feature is 100% broken.** `process_bdr_job` calls `vault.get_artwork_file_path(...)` at `api/app/tasks.py:3344`, but `vault` is never imported — not in the function's imports (`:3184-3193`) and not at module level (every other task imports it function-locally). Every BDR job hits `NameError`, is marked `failed`, and retries 3× to the same result. **Fix:** add `from . import vault` to the function's imports; add an end-to-end test.

3. **[HIGH] Unauthenticated SSRF via `POST /tasks/hash-url`.** `api/app/routers/legacy.py:13-24` (comment literally says "TODO: Remove in production") takes a client URL and makes the worker `requests.get` it, with no auth and no private-range/loopback/metadata-IP filtering. Any internet client can probe internal containers (`db:5432`, `cache:6379`, other services), `127.0.0.1`, or `169.254.169.254`. **Fix:** delete the endpoint, or gate behind owner-auth + resolve-then-validate the target IP against an allowlist.

4. **[HIGH] Temporarily-banned users get a 500 on every request.** `api/app/auth.py:116` compares a tz-aware `banned_until` against a naive `datetime.now(...).replace(tzinfo=None)` → `TypeError`, which isn't caught → 500 instead of "Account banned". The player-router copies do it correctly, so this is pure inconsistency. **Fix:** drop `.replace(tzinfo=None)` (or reuse the existing `_as_utc_aware()` helper).

5. **[HIGH] Celery broker can silently drop queued tasks.** The `cache` Redis serves both the API cache and the Celery broker with `--maxmemory-policy allkeys-lru` (`deploy/stack/docker-compose.yml:45`). Under memory pressure Redis will evict queue keys — losing view-event writes, SSAFPP conversions, BDR jobs, pushes, and account-deletion tasks with no error. Redis requires `noeviction` for broker use. **Fix:** split broker onto its own Redis (or db) with `noeviction`; keep LRU only for the cache.

6. **[HIGH] The daily rollup pipeline permanently loses ~60–90 min of view events every day.** Each of `rollup_view_events` (01:00 ET), `rollup_site_events` (02:00), and `cleanup_old_view_events` (02:30) computes its **own** `now − 7d` cutoff, so cleanup deletes a band of events that the rollup hasn't aggregated yet (`api/app/tasks.py:1275`, `:1470-1478`, `:2079-2086`, `:2169-2178`). Users can watch a post's lifetime view count **decrease** the day those events age out. This is the same race the team already caught once (the unscheduled `cleanup-old-site-events`, comment at `tasks.py:406-408`). **Fix:** compute one shared, day-aligned cutoff (e.g. midnight-UTC of `today−7d`) used identically by all three tasks, so each calendar day is rolled up exactly once and cleanup can never outrun the rollup.

7. **[HIGH] Cursor pagination 500s on any sort except the default.** `list_posts` filters the cursor by the requested sort field (`api/app/routers/posts.py:376-378`) but always **encodes** the cursor from `created_at` (`pagination.py`). Page 2 of any `sort=width|height|file_bytes|reactions|...` view either compares an ISO string to an integer column (Postgres error) or `getattr`s a non-existent attribute → 500. Works only for the default sort, which is why casual testing misses it. **Fix:** thread the actual sort field through `create_page_response` and resolve it via the same `sort_field_map` in `apply_cursor_filter`.

8. **[HIGH] Nothing gates a merge to `main`, which auto-deploys to prod.** The only check is an opt-in, bypassable local `pre-push` hook that runs formatting + OpenAPI-drift only (`deploy/hooks/pre-push`, `Makefile`); the full test suite, `tsc`, `next lint`, and the e2e suite are never run by any gate. `make deploy` on prod is `git pull main && compose up --build`. **Fix:** a minimal GitHub Actions workflow on PRs to `main` running `make check-full`, `tsc --noEmit`, `next lint`, `next build`.

---

## Cross-cutting themes

These patterns recur across many individual findings; fixing the root cause resolves several findings at once.

- **Unfinished user-ID migration (UUID ⇄ integer).** `User.id`, `Report.reporter_id`, and `AuditLog.actor_id` are `Integer`, but several endpoints still parse/declare them as `UUID`, so moderator user-report actions and admin audit filters 500 (`routers/reports.py:115-127,53,70-71`; `routers/admin.py:566,580-581`). Same root cause as several "leftover" comparisons.
- **The stats/rollup subsystem is fragile and inconsistent.** Beyond the shortlist rollup bug: rollups aren't crash-idempotent and double-count on the next run (`tasks.py:1466-1480`, `:2067-2088`); unique-viewer counts double-count across the split-day boundary (`:1394,1418,1937,1981`); player views for a date with no site events are deleted un-aggregated (`:1926` vs `:2079-2086`); and **three** code paths compute "total views" differently, two of which undercount recent posts (`services/post_stats.py:92-133` correct vs `user_profile_stats.py:137-149` and `routers/reactions.py:412-437`). Users see different view numbers on the profile, the widget, and the stats page. A single shared, day-aligned, watermark-based aggregation would collapse most of this.
- **A whole class of cursor-pagination bugs.** The non-default-sort 500 (shortlist #7), search pagination that's silently dead and would crash if reached (`routers/search.py:109-113,157-167`), and followers/following lists that filter on the wrong entity's timestamp and silently skip/duplicate rows past page 1 (`routers/users.py:1327-1335,1392-1401`). The cursor helper is being used with the wrong sort key in several places.
- **Reverse-proxy client-IP handling is broken, undermining rate limiting.** Uvicorn runs without `--proxy-headers` and there's no ProxyHeaders middleware, so `request.client.host` is always Caddy's bridge IP — collapsing every auth throttle (login, register, forgot-password, OTP) into **one global bucket** an attacker can exhaust to lock everyone out. Meanwhile the *other* `get_client_ip` trusts the client-controlled leftmost `X-Forwarded-For`, so the player-token brute-force limiter and IP bans are trivially bypassable (`routers/auth.py:140-147` vs `auth.py:547-565`, `utils/view_tracking.py:206-213`). These two bugs point in opposite directions and both need the same fix: run behind `--proxy-headers --forwarded-allow-ips=<caddy>` and use one correct `get_client_ip`.
- **Operational guardrails are thin for something that auto-deploys to prod.** No CI (shortlist #8); prod actually runs a **single** uvicorn worker because the 2-worker `api/Dockerfile.prod` is dead code never referenced by any compose file; no container has a memory limit on a host shared by prod **and** dev; plaintext MQTT (:1883) is published on the public interface in prod.

---

## Detailed findings

Severity in brackets. Confidence is **Confirmed** (code path traced) unless marked *Suspected*. Locations are `file:line` on `develop@deca502`.

### 1 · Security

- **[HIGH] Unauthenticated SSRF — `POST /tasks/hash-url`.** `routers/legacy.py:13-24` → `tasks.py:460-483`. See shortlist #3.
- **[MEDIUM] Reverse-proxy client-IP broken → rate limits ineffective *and* spoofable.** No `--proxy-headers`/ProxyHeaders anywhere; two conflicting `get_client_ip` impls (`routers/auth.py:140-147` uses `request.client.host`; `auth.py:547-565` & `utils/view_tracking.py:206-213` trust leftmost XFF). Auth throttles collapse to one global bucket (lockout DoS); XFF-based limits (incl. 60/hr player-token brute-force cap at `auth.py:372-381`) and IP bans are bypassable; `comment.author_ip` (`routers/comments.py:211`) is poisonable. **Fix:** `--proxy-headers --forwarded-allow-ips=<caddy CIDR>`, single correct `get_client_ip`.
- **[MEDIUM] Player bootstrap endpoints are UUID-only bearer credentials.** `routers/player.py:337-409` (`GET /player/{key}/credentials` returns the device mTLS **private key** + mints the API token) and `:412-456` (`POST …/token/rotate` revokes the live device's token then issues a new one — `services/player_tokens.py:35-46`). Knowing a `player_key` (used as a semi-public identifier elsewhere) yields device takeover + DoS with no owner binding/notification. **Fix:** separate one-time provisioning secret; stop returning `key_pem` on repeat fetch; alert owner on rotation.
- **[LOW] Internal error strings leaked to clients** via `detail=str(e)` — `routers/relay.py:63,94,123,288`, `player.py:518,1667,1676`, `auth.py:1618,2146`, `mqtt.py:58`, `posts.py:1465`. Recon-grade info disclosure (paths, deps). **Fix:** log server-side, return generic message. (No stack traces reach clients — debug is off.)
- **[LOW] `POST /report` has no rate limit and no target validation** (`routers/reports.py:24-47`, TODOs acknowledge both) → report-queue spam, junk rows.
- **[LOW] `GET /relay/jobs/{id}` has no auth/ownership check** (`routers/relay.py:381-397`). Low practical risk (unguessable UUID) but returns repo/commit/error strings.
- **[INFO] CORS credential-reflecting wildcard is possible.** `main.py:223-244`: `allow_credentials=True` with origins from env; if an operator ever sets `CORS_ORIGINS="*"`, Starlette reflects any origin *with* credentials (only a warning is logged). Latent; primary auth is bearer-header not cookie. **Fix:** hard-reject `"*"` when credentials are allowed.
- **[INFO] Login user-enumeration + DEBUG SQL echo.** `auth.py:470-481` returns 403 "Email not verified" before the password check (documented UX tradeoff); `db.py:46` enables SQL `echo` when `LOG_LEVEL=DEBUG`. Ensure prod is never `DEBUG`.

**Notably safe:** no SQL injection (the few `text()` calls are static/parameterized), no path traversal (vault paths built from DB-stored opaque shards + UUID keys, extensions whitelisted, `mkpx/` blocked at the mount), zip-slip/symlink defenses on uploads, image inspection in an isolated 30s-timeout subprocess, only one `dangerouslySetInnerHTML` in the web app (a static dev-console script), and no secrets committed to git.

### 2 · Correctness & data integrity (backend)

- **[CRITICAL] Account deletion crashes half-way** — `tasks.py:3833,3835` (`download_path`→`file_path`). Shortlist #1.
- **[CRITICAL] BDR feature fully broken** — missing `vault` import in `process_bdr_job`, `tasks.py:3344`. Shortlist #2.
- **[HIGH] Temp-banned users → 500 on every request** — `auth.py:116`. Shortlist #4.
- **[HIGH] Cursor pagination 500s on non-default sorts** — `posts.py:376-378` + `pagination.py`. Shortlist #7.
- **[HIGH] Rollup/cleanup cutoff misalignment loses view events daily** — `tasks.py:1275,1470-1478,2079-2086,2169-2178`. Shortlist #6.
- **[MEDIUM] Search pagination is dead code and would crash if reached.** `routers/search.py:109-113,157-167,186,236-249`: per-type slicing before accumulation makes `next_cursor` unreachable; if a cursor were supplied, `float(last_similarity)` on an ISO datetime → `ValueError`/500; user branch encodes no sort value.
- **[MEDIUM] Followers/following pagination filters the wrong timestamp.** `routers/users.py:1327-1335,1392-1401` selects `User` rows but the cursor encodes the user's **signup** time, then page 2 filters `Follow.created_at < user.created_at` → silent skips/dupes once the list exceeds one page.
- **[MEDIUM] UUID-vs-Integer mismatches break report actions & admin filters.** `routers/reports.py:115-127,53,70-71`; `routers/admin.py:566,580-581`. Moderators can't `ban`/`hide` user reports via `PATCH /report/{id}`; audit `actor_id` / report `reporter_id` filters 500.
- **[MEDIUM] Rollups aren't crash-idempotent.** `tasks.py:1466-1480,2067-2088` commit `+=` increments in batches, delete raw events only at the end → a mid-run crash double-counts on the next run, silently inflating historical daily stats.
- **[MEDIUM] `unique_viewers`/`unique_visitors` double-counted across the split-day boundary.** `tasks.py:1394,1418,1937,1981`. Fixed for free by the day-aligned cutoff (#6).
- **[MEDIUM] `rollup_site_events` drops player views for site-event-less dates.** `tasks.py:1926` (upsert loops only over site-event dates) vs `:2079-2086` (player events deleted unconditionally). Quiet web-traffic days lose player views permanently.
- **[MEDIUM] Shared feed cache leaks the cache-filler's `user_has_liked` to anonymous users.** `posts.py:949-963` bakes the filler's like-state into the shared key; the hit path only overwrites it `if current_user` (`:911-916`). Anon visitors see a logged-in user's like flags (≤ TTL, 2–5 min). Same in `search.py:383-396/438` and `:719-734/778`. **Fix:** annotate likes *after* `cache_set` (populate cache with `current_user_id=None`).
- **[MEDIUM] Three "total views" computations disagree.** Correct: `services/post_stats.py:92-133`. Undercounting: `services/user_profile_stats.py:137-149` (rollups only → a <7-day-old post shows 0 views on its author's profile) and `routers/reactions.py:412-437` (`get_widget_data` drops a boundary slice). **Fix:** use the no-date-filter formulation everywhere.
- **[MEDIUM] `periodic_check_post_hashes` only ever checks the same 100 posts.** `tasks.py:594-606`: `.limit(100)` with no `ORDER BY`/watermark → integrity checking silently stops covering the catalog past 100 posts. **Fix:** add `hash_checked_at`, iterate `NULLS FIRST`.
- **[MEDIUM] `feed_following` missing visibility filters + pagination.** `routers/search.py:822-841` omits `hidden_by_user`/`non_conformant` predicates (so author-hidden and mod-flagged posts still appear in followers' feeds) and ignores the cursor (silent cap at `limit`).
- **[LOW] Idempotent write endpoints 500 under concurrent duplicates.** No `IntegrityError` catch on reaction/follow/comment-like inserts (`routers/reactions.py:165-229`, `users.py:1178-1203`, `comment_likes.py:94-106`); the reaction 5-cap can also over-admit to 6 under a race. **Fix:** `ON CONFLICT DO NOTHING` / catch-rollback-return.
- **[LOW] SSAFPP retry loses `PostFile` rows.** `tasks.py:2885-2890,2993-3000,3130`: files written immediately but rows committed at the end; a retry sees the file exists → records `"exists"` → never creates the DB row, making that on-disk format unreachable until manual backfill.
- **[LOW] Assorted:** comments endpoint ignores `cursor`/`view`, silently truncates at `limit`, drops replies whose parents fall outside the window (`routers/comments.py:31-123`); `save_upscaled_artwork` skips the `ensure_vault_headroom` free-space check (`vault.py:458-471`); `replace_artwork` takes no row lock → concurrent replaces orphan bytes (`posts.py:1781+`); `permanent_delete_post` deletes vault files before the DB row → a DB failure leaves live posts with dead art URLs (`posts.py:1415-1435`); naive `datetime.utcnow()` written into tz-aware `read_at` (`services/social_notifications.py:289,321`).

### 3 · Performance & scalability (backend)

- **[HIGH] Celery broker on `allkeys-lru` Redis can silently drop tasks** — `docker-compose.yml:45`. Shortlist #5.
- **[MEDIUM] Hashtag endpoints load the entire posts table into Python per cache miss.** `routers/search.py:295,499,638` do `base_query.all()` (full rows incl. `description`) and aggregate in Python; cache keys include `q`/`cursor` so search-as-you-type triggers a full-table load per keystroke, and the `ILIKE '%q%'` can't use the GIN index. Fine at hundreds of posts; seconds of work at 10k–100k. **Fix:** SQL `unnest(hashtags) … GROUP BY` (or a small refreshed stats table); key typeahead cache on the normalized prefix only.
- **[MEDIUM] Artist dashboard: unbounded row loads + per-post N+1.** `services/artist_dashboard.py:189-196,288-292,322-330,407-409` materialize every recent view event / reaction / comment for all the artist's posts and aggregate in Python, then call `get_post_stats` per listed post. Tens of MB + 100+ queries for a busy artist. **Fix:** aggregate in SQL, cache the artist aggregate, batch per-post stats by `post_id IN (...)`.
- **[LOW] N+1 in secondary paths.** `comment_likes.py:169-171` lazy-loads `like.user` per row (≤200 queries); `tasks.py:3265-3272` queries `User.handle` once per comment in the BDR export. **Fix:** `joinedload` / batch by `IN`.
- **[LOW] `check_rate_limit` re-arms the TTL on every allowed request and is non-atomic.** `services/rate_limit.py:99-118`: `incr` then unconditional `expire` means the window never rolls off during steady activity (4 uploads spread over 4h can still exhaust a "4/hour" budget); read-then-incr is racy. **Fix:** set expiry only when `INCR` returns 1 (as `cache.py:308-311` already does).
- **[INFO] Scale-headroom notes (not bugs today):** one Celery task per view event (`utils/view_tracking.py:339,429-442`) — batch when volume grows; single uvicorn process with a ~40-thread pool vs 30-conn DB pool (`db.py:49-52`) — threads will time out on the pool under saturation; public-feed queries ride the single-column `created_at` index (`models.py:445-449`) — a partial composite index is the natural next step; rollup batching uses `OFFSET` (O(n²)) — switch to keyset if event volume grows.

### 4 · Infrastructure, deployment & operations

- **[HIGH] No CI gate before prod auto-deploy** — `deploy/hooks/pre-push`, `Makefile`. Shortlist #8.
- **[MEDIUM] Prod runs a single uvicorn worker; `api/Dockerfile.prod` (2 workers) is dead code.** No compose/Makefile/doc references `Dockerfile.prod`; the prod overlay (`docker-compose.prod.yml:42-55`) overrides only env/volumes, so the base single-process `command` (`docker-compose.yml:113`) wins. Half the intended concurrency, plus a misleading file. **Fix:** set `command: uvicorn … --workers 2` in the prod overlay (or wire in `Dockerfile.prod` and delete the base override).
- **[MEDIUM] No memory limits anywhere; prod has no resource limits at all — on a host shared with dev.** `docker-compose.dev.yml` sets CPU-only; `docker-compose.prod.yml` sets none. One leaking/spiking container (Pillow on a big image, a runaway worker) can OOM the whole VPS and take down prod **and** dev together. **Fix:** `mem_limit` on `api`/`worker`/`db`/`web` in the prod overlay.
- **[MEDIUM] Plaintext MQTT (:1883) is published on the public interface in prod.** `docker-compose.prod.yml:35-37` binds `1883:1883` to `0.0.0.0`; that listener has password auth but **no TLS** (`mqtt/config/mosquitto.conf:11`), so `svc_backend`/`webclient`/player creds cross the wire in cleartext for external connections. The plaintext broker is only needed in-cluster. **Fix:** drop the host mapping (or bind `127.0.0.1:1883`); keep only 8883 (mTLS) public.
- **[LOW] Prod API/worker images ship dev deps and run as root.** `api/Dockerfile:15` & `worker/Dockerfile:15` install `[dev]` extras (pytest/black/ruff); none of the Python/MQTT Dockerfiles set `USER` (only `web` drops privileges). Larger surface, no privilege separation. **Fix:** non-`[dev]` prod install + non-root `USER`.
- **[LOW/INFO] Missing HSTS/security headers on the main app; unbounded static volume; ungated debug page.** `Caddyfile.global` sets security headers only inside the vault site blocks (`:100,:128`), not the main site; `web_next_static` is never pruned (`web/entrypoint.sh:18-20`) → slow unbounded disk growth across deploys; `web/src/pages/debug-env.tsx` ships to prod at `/debug-env` (exposes API base URL + token presence — only the visitor's own data, so low risk). **Fix:** HSTS/CSP snippet in Caddy global; periodic volume prune; gate/remove `debug-env`.

> **By design (not findings):** the `webclient` MQTT password baked into the client bundle is fine — the ACL restricts it to read-only subscribe on notification topics (`mqtt/config/acls:39-44`). Rate limiter fails **closed** to an in-memory limiter. Refresh-token cookie is `HttpOnly` + `SameSite`.

### 5 · Frontend & maintainability

- **[MEDIUM] 1,700-line legacy `web/src/pages/user/[id].tsx` duplicates the canonical `u/[sqid].tsx` and has diverged.** Header calls it a redirect, but unlike the clean 119-line `post/[id].tsx` stub it keeps a full second profile implementation as a fallback for users lacking `public_sqid` — which is backfilled for everyone (`api/app/auth.py:154-157`), so ~1,560 lines are effectively dead and drifting (last touched 2026-04-11 vs canonical 2026-06-25). **Fix:** reduce to a thin redirect stub.
- **[MEDIUM] Next.js pinned to 14.2.3** (`web/package.json`) — misses ~2 years of 14.2.x security patches. *Mitigated:* no `middleware.ts` (so the middleware-auth-bypass CVE line doesn't apply), no `pages/api`, raw `<img>` not `next/image`. **Fix:** bump to latest 14.2.x (drop-in), re-`next build`. *(Suspected exploitability, Confirmed version.)*
- **[LOW] `pyodide` npm dep is unused; divoom-import decode depends on an external CDN.** `pyodide` is declared but never imported; the runtime injects `<script src="https://cdn.jsdelivr.net/pyodide/...">` (`web/src/lib/divoom/pyodideDecoder.ts:135`) — a hard third-party dependency on the one page that sets COEP `require-corp`. **Fix:** drop the dep or self-host Pyodide (as already done for zstd/lzo/webp WASM).
- **[LOW] `any`/unsafe casts concentrated in a few files** (61 total; worst: `pages/p/[sqid].tsx` ×9, `divoom-import.tsx` ×6, `utils/webpDecoder.ts` ×5, `components/PlayerCard.tsx` ×5, `pages/search.tsx` ×4). `strict` is on and `tsc` passes; type the API responses on the two biggest pages, leave vendor-glue `any`s.
- **[LOW] 70 raw `<img>` without dimensions (CLS risk) + 37 shipped `console.*`; a prod console monkeypatch.** `_document.tsx:16-24` unconditionally patches `console.warn`/`error` for all prod users (vs `_app.tsx:111-133` which correctly gates on `NODE_ENV`). **Fix:** add `width`/`height` on grid images; gate the `_document` filter to non-prod.
- **[LOW/INFO] Dead prototype files tracked at repo root:** `backend_service.py` (92-line demo, imported nowhere), `views.csv` (its sample data), and `logo-intro-lossy.webp`/`logo-intro-last-frame.webp` (the former byte-identical to `web/public/brand/…`). **Fix:** delete.

### 6 · Testing & CI

- **[MEDIUM] Tests build the schema via `Base.metadata.create_all()`, not Alembic** (`api/tests/conftest.py:97-99`) — the migration chain is **never** exercised, so model/migration drift ships undetected. **Fix:** `alembic upgrade head` against the fresh test DB.
- **[MEDIUM] Whole routers/services have no direct tests** (see map below) — clustered around discovery/social/catalog endpoints. **Fix:** smoke tests for the highest-value gaps (`search`, `playlists`, `social_notifications`, `sitemap`).
- The harness itself is otherwise solid: real Postgres (`makapix_test`), real Redis for rate limits, per-test `TRUNCATE … CASCADE` isolation, `TestClient` with `get_session` override. 41 `test_*.py` files.

**Test coverage map (approximate)** — ~18 of 31 routers have direct tests.

| Well covered | Partial / indirect | **No direct tests** |
|---|---|---|
| auth (login/JWT/OAuth/OTP/pw), vault (upload/serving/reshard/avatar), posts/replace/mkpx, MQTT/player-RPC, hashtags/mod, handles/users/profile, health/config/errors | reactions & comments (comment_likes router not hit directly), rollups/cleanup (site/view-event rollups thin) | **search, playlists, social_notifications, sitemap, badges**, licenses/categories/blog_posts/pmd/umd/relay/system routers; password_reset / email_verification / profanity / site_stats / player_views services |

---

## What's already done well

Worth stating plainly, because it's a lot and it's the reason the findings above are mostly bounded:

- **Auth & sessions:** single fixed JWT algorithm (no alg-confusion / no `none`), boot-time secret entropy checks, per-request re-read of the user so bans/deactivations take effect immediately despite stateless tokens; bcrypt passwords; refresh tokens SHA-256-hashed at rest, DB-revocable, rotated with a grace window.
- **OAuth:** state nonce in a `SameSite=None; Secure` cookie, PKCE **S256** required for the native flow with an allowlisted `redirect_uri`, single-use codes via Redis `GETDEL`, account linking only on a **verified** GitHub email.
- **Vault layer (exemplary):** atomic temp-file + fsync + rename writes, stored-shard-as-source-of-truth with explicit refusal to derive paths, disciplined twin mirroring and a clean miss-only legacy remap, streaming mkpx writes; zip-slip/symlink/size defenses on uploads; extension whitelist; `mkpx/` blocked at the static mount.
- **Hot read paths:** keyset (not `OFFSET`) pagination on the default feed, batched `IN` count annotation, `selectin` on `Post.files`, capped/cached player-verify endpoints; view/site events recorded fully off the request path.
- **Frontend:** genuinely robust API client (single-flight token refresh, definitive-vs-transient failure handling, SSR-guarded `localStorage`); XSS-safe user content (hand-rolled whitelist markdown parser, `rehype-sanitize` for blog); good bundle discipline (lazy `ssr:false` for heavy components, on-demand WASM codecs); front/back contract mirrors kept in sync (`DEVICE_LABELS`, `MONITORED_HASHTAGS`); deliberate effect race-guards where they matter.
- **Care in the known-hard spots:** mod-hashtags uses `FOR UPDATE`, replace-artwork rotates storage keys for cache correctness, the racing site-events cleanup was identified and unscheduled, uploads insert the DB row before the vault write so the unique index prevents orphan files, and the rollup **consumer** is gap-tolerant.

---

## Methodology, coverage & limitations

Three independent read-only agents reviewed the repo in parallel along different axes (security; backend performance & correctness; frontend/infra/maintainability). Every finding above cites code the reviewing agent actually read. To guard against false positives on the highest-stakes claims, the two Critical items, the SSRF, and the banned-user bug were **re-verified by hand** (the confirming reads: `models.py:1778/1809` has only `file_path`; `tasks.py:3184-3193` imports lack `vault` and no module-level `vault` import exists; `legacy.py:13-24` has no auth dependency; `auth.py:116` compares aware-vs-naive).

**Depth was uneven, by design.** Reviewed in depth: `auth.py`, `main.py`, `db.py`, `cache.py`, `pagination.py`, `models.py`, `tasks.py` (beat/rollup/SSAFPP/BDR/deletion), `vault*.py`, the main feed/search/posts/reactions/comments/users/admin/reports/player routers, the core services, the full route→auth-dependency map, all Dockerfiles + compose overlays + Caddy/Mosquitto config, and the web API client + hot components. `tsc --noEmit` (clean) and `next lint` (clean; 132 warnings) were run.

**Not (or only lightly) covered — treat as unknown, not clean:** the 2,692-line `routers/auth.py` OAuth/OTP/registration internals; `blog_posts.py` + blog stats (patterns mirror the post-stats code, so the stats findings **likely apply there too** — *Suspected*); the `app/mqtt/` subscriber threads and Mosquitto ACL/topic config at the broker level; `player_rpc`/`relay` task bodies; email services; `d_cloud_sync.py`; a dependency-version audit of `requirements*.txt`; the largest web components' internal render/memoization behavior; the Playwright e2e suite contents; and any runtime/load behavior (this was static review only). A follow-up pass on the auth router and the MQTT broker config would be the highest-value next investment.

---

## Suggested remediation order

1. **Today (data loss / broken features):** shortlist #1 and #2 — both are one-line-ish fixes with regression tests.
2. **This week (security + ongoing data loss):** shortlist #3 (SSRF), #4 (banned-user 500), #5 (broker eviction), #6 (rollup data loss). Do the reverse-proxy `--proxy-headers` fix here too — it unblocks all the rate-limiting findings at once.
3. **Next (user-visible correctness):** shortlist #7 (pagination) and the rest of the pagination class; the UUID-vs-integer cleanup; unify the three "views" computations; the anon `user_has_liked` cache leak.
4. **Then (guardrails & hygiene):** shortlist #8 (CI), prod worker count + memory limits + MQTT port, `alembic`-based tests + smoke tests for the untested routers, and the maintainability cleanup (legacy profile page, dead root files, Next.js bump).
