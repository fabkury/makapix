# Makapix Club — Remediation Backlog (July 2026 Appraisal)

De-duplicated, prioritized, actionable. Derived from 141 verified findings across 12 areas + 3 architecture lenses ([see README](./README.md)). Each row is one unit of work with a stable ID, severity, effort (**S** <1h · **M** ~1 day · **L** multi-day), and the concrete fix. Where several reviewers found the same thing, it's merged into one row (source areas noted).

**Effort/line numbers** are as of `develop @ 3c94349` (2026-07-15). **Check items off in place.** Work top-down within a tier; but prefer resolving a whole **Theme** (README §4) at once — it retires multiple rows and stops the next copy from being written.

Legend: `[ ]` todo · severity `CRIT/HIGH/MED/LOW/INFO`.

---

## P0 — Fix-first sprint (live data-loss / security / broken features)

> **Status 2026-07-15:** the entire P0 tier is DONE — fixed on `develop` with regression tests and pushed (commits 8cbd1f7…fc83b83). Each `[x]` item below has a `fix(...)` commit and tests. Remaining follow-ups noted inline: A8 GitHub-callback integration test [T1]; A15 divoom-import batch abort; and the structural consolidations in P2 (D1 visibility helper, etc.) that the surgical P0 fixes deferred.

Do these first, as one committed sprint. All confirmed against code; several against the live dev DB.

### Correctness & data-loss

- [x] **A1** · CRIT · M — **Account deletion can never complete.** `request_account_deletion` (`routers/users.py:699-708`) writes an `audit_logs` row with `actor_id` = the deleting user; that FK is `ON DELETE RESTRICT` (live DB), so `db.delete(user)` (`tasks.py:4080`) always `IntegrityError`s. Also `bdr.download_path` → should be `bdr.file_path` (`tasks.py:3908`, `models.py:1864`). Also never handles `push_tokens`, `violations`, `reports.reporter_id`, `relay_jobs`, `conformance_checks`, `github_installations`. **Fix:** correct `file_path`; delete/NULL the dependent rows (or make `audit_logs.actor_id` `SET NULL` / reassign to system user); add an end-to-end test for a user with one row in every dependent table. *(data-model, auth-account, tasks-services, data-identity)*
- [x] **A2** · CRIT · S — **Batch download produces empty ZIPs.** `process_bdr_job` (`tasks.py:3239`) uses `vault.*` but never imports it → `NameError` per artwork. **Fix:** `from . import vault`; test that a vault-backed post's ZIP contains the file; fail the BDR if zero artworks added. *(tasks-services)*
- [x] **A3** · HIGH · S — **`cleanup_unverified_accounts` fails every run** (live-confirmed, dev worker logs 2026-07-14). All-or-nothing bulk delete trips `posts_owner_id_fkey` / `auth_identities`, rolls back, returns error dict logged as success. **Fix:** delete per-user (share logic with A1's task), include `auth_identities`, skip/handle users with content, raise on failure. *(auth-account, tasks-services)*
- [x] **A4** · HIGH · S — **Ban enforcement broken both ways.** `auth.py:116` compares tz-aware `banned_until` to a naive `now` → `TypeError` → 500 on every temp-banned user's request (incl. public optional-auth). Permanent ban writes `NULL` = silent no-op. **Fix:** use `_as_utc_aware` (already at `auth.py:88`); represent permanent bans explicitly (sentinel date or boolean) and fix admin/browse filters; test both ban modes. *(auth-account)*
- [x] **A5** · HIGH · M — **Cursor pagination 500s on every non-`created_at` sort** (incl. "Reactions"/"File Size" shipped in `FilterButton`). `pagination.py` encodes only `created_at`; page 2 `getattr`s the sort column on the raw string. **Fix:** whitelist sorts with a `Literal`/`Query` enum; encode the actual sort field's value; coerce per-field; 400 on undecodable cursor. Add a page-2 test per exposed sort. *(data-model, content-api)*
- [x] **A6** · HIGH · M — **Rollups silently drop JSON breakdown data.** SQLAlchemy dirty-tracking: in-place mutation of `views_by_country` etc. isn't persisted when the dict is non-empty (i.e. after slice 1), so permanent daily breakdown columns undercount. `existing.unique_viewers += len(...)` also overcounts uniques. **Fix:** reassign a copied dict (`{**existing}`) or `MutableDict.as_mutable`; better, convert to `pg_insert ON CONFLICT` upserts like `services/download_stats.py`; regression-test a two-run merge. *(tasks-services)*
- [x] **A7** · HIGH · M — **Rollup failures invisible; cleanup then destroys un-rolled-up events.** Rollup-before-cleanup ordering is wall-clock-hoped, not enforced; a failed/overrun rollup + 02:30 cleanup = permanent view-event loss; failures return success-shaped error dicts. **Fix:** fold `cleanup_old_view_events` into the tail of `rollup_view_events` (deletes only what it aggregated) and delete the beat entry; make rollups raise + autoretry; add `soft_time_limit`. *(tasks-services, simplicity lens)*
- [x] **A8** · HIGH · M — **GitHub login corrupts `user.email`.** Overwrites email on every login (desyncs from password identity → change-password then fails), 500s on email collision or missing email, marks `email_verified=True` on unverified GitHub addresses. Four provisioning paths each differ. **Fix:** stop overwriting on login (or gate on verified + non-colliding + update `email_normalized`); only trust provider-verified addresses; handle no-email like the Apple flow; centralize provider-email policy in one service. *(auth-account)*
- [x] **A11** · HIGH · M — **Comment/reaction endpoints ignore post visibility.** Enumerable int IDs expose comments/reactors/view-counts of hidden/unlisted/soft-deleted posts; users can comment/react on them; nonexistent ID → 500 not 404. **Fix:** shared `get_accessible_post_or_404` dependency (wrapping `can_access_post`) on all comment/reaction/like read+write endpoints. *(content-api)*
- [x] **A12** · HIGH · M — **`get_widget_data` drifted copy lost the block filter.** A blocked user's comments still show in the widget (the endpoint the post widget actually uses) — violates shipped ugc-safety D10. **Fix (part of D14):** extract one `build_comment_thread` used by both; add the block filter + regression test now (one-liner). *(content-api)*
- [x] **A13** · HIGH · M — **Per-router visibility filters have drifted** (see Theme T2 / **D1**). User-hidden posts leak into `/feed/following` and hashtag counts; blocked users' posts appear in the following feed; banned users are discoverable via `/search`. **Fix:** the D1 consolidation; add a test asserting `hidden_by_user` posts appear in no public surface. *(content-api, velocity lens)*
- [x] **A9** · MED · S — **Non-latin-1 titles 500 all `/d` download endpoints** (`UnicodeEncodeError` from hand-built `Content-Disposition`; emoji/CJK titles common here). **Fix:** delete the manual header, rely on `FileResponse(filename=...)` (RFC-5987 encodes correctly); test an emoji title. *(content-api, vault-storage, security)*
- [x] **A15** · MED · S — **Moderation/batch UI ignores `response.ok`** — a 403/409/429 on hide/promote/permanent-delete/purge is silent; the mod believes it landed. **Fix:** check `response.ok` in every mutating handler in `mod-dashboard.tsx`/`divoom-import.tsx`; surface an error banner; abort the divoom batch on 401. *(frontend-quality)*
- [x] **A16** · MED · M — **Post hard-delete unlinks vault files before an abortable DB delete;** a `players.current_post_id` FK can wedge the whole nightly batch, leaving soft-deleted rows whose files are already gone. **Fix:** NULL `current_post_id` (or `ondelete SET NULL`) first; delete+commit DB row per post, then unlink; on per-post error rollback + re-fetch instead of continuing on a poisoned session. *(data-model, tasks-services)*

### Security

- [x] **S1** · HIGH · S(+M) — **MQTT `topic read #` + browser-shipped `webclient` password = read all topics** (every user's social notifications + entire player fleet's command/status/RPC). **Fix now:** delete `mqtt/config/acls:46`; **Fix real:** retire the shared-password browser MQTT path for the existing authenticated SSE (`routers/realtime.py`), or issue per-user MQTT creds — a shared credential can't scope `social-notifications/user/{id}`. *(player-mqtt, frontend-arch, security, infra-deploy, simplicity lens)*
- [x] **S2** · HIGH · S — **Plaintext MQTT listener bound to the public internet** (`1883`/`1884` on `0.0.0.0`; Docker bypasses ufw), contradicting its "network-isolation only" model. **Fix:** bind to `127.0.0.1` or drop the host mapping (in-network clients use the compose net; players use `8883` mTLS); update `mosquitto.conf`/docs; rotate `MQTT_PASSWORD`. *(infra-deploy, security)*
- [x] **S3** · HIGH · S — **Anonymous commenter IPs exposed to all visitors.** `schemas.py:549` serializes `author_ip` on the public `Comment` schema (and widget). **Fix:** remove from the public schema; expose via a mod-only schema in admin/UMD; test absence on `GET /post/{id}/comments`. *(data-model)*
- [x] **S4** · HIGH · S — **OAuth `postMessage` receiver accepts any origin** (login CSRF / account fixation). **Fix:** `if (event.origin !== window.location.origin) return;` at the top of the `Layout.tsx` handler (mirror `editor.tsx:234`); validate token shape. *(frontend-arch)*
- [x] **S5** · HIGH · S — **`session-transfer.tsx` leaks `access_token` to any origin.** `return=` gets only a `new URL()` parse, then the bearer token is base64'd into its hash — no host allowlist. **Fix:** gate `return` to a known Makapix-subdomain allowlist before writing tokens. *(critic gap, confirmed)*
- [x] **S6** · HIGH · S — **MQTT auth path skips owner ban/deactivation check** — a banned user's physical player keeps reacting/viewing over the broker. **Fix:** factor the owner-eligibility check (from `get_current_player`) into a shared helper; call it in `mqtt/player_requests.py` + `player_views.py`. *(player-mqtt)*
- [x] **S7** · HIGH · M — **Avatar ingress lacks every safety net** (no rate-limit, quota, headroom, content validation; orphans the old file on every replace → can push the vault past ENOSPC). **Fix:** delete old avatar on replace; `ensure_vault_headroom` in `save_avatar_image`; share the upload rate-limit bucket; validate bytes with Pillow. *(vault-storage)*
- [x] **S8** · HIGH · S — **SSRF: `POST /tasks/hash-url`** (`routers/legacy.py:14`, self-flagged "remove in production") fetches a client URL server-side, no auth, no private-range filter. **Fix:** delete the endpoint. *(conventions; July-6 carryover)*
- [x] **S15** · MED · S — **Player SSE puts the 60-min JWT in a logged query string.** **Fix:** switch to cookie auth like `/api/pmd/bdr/sse`, or mint a one-time ticket; handle 401-on-reconnect by refetching. *(frontend-arch)*

---

## P1 — High-value (do right after the sprint)

### Security (P1)

- [ ] **S9** · MED · S — **`reputation.py GET /{id}/reputation` is public**, returns every moderator `reason` string to anonymous callers (no auth dep, unlike the `require_moderator` adjust endpoint). **Fix:** require auth; decide whether mod reason text should be visible to the subject at all. *(critic gap, confirmed)*
- [ ] **S10** · MED · S — **`replace-artwork` has no rate limit and no quota check** — disk/CPU amplification loop (each iteration parks the old key's files 7 days outside quota). **Fix:** consume the upload rate-limit bucket + `check_storage_quota` (delta), mirroring `attach_mkpx`. *(content-api, vault-storage)*
- [ ] **S11** · MED · S — **Legacy JSON `create_post` bypasses the entire upload pipeline** (arbitrary external `art_url`, no AMP/rate/quota/dedup; lands in mod-approval queue). **Fix:** delete it (web doesn't use it) or restrict to vault-relative paths + rate limit + 409 on hash conflict. *(content-api)*
- [ ] **S12** · MED · M — **Session-revocation gaps** — password reset keeps attacker refresh tokens valid up to 30 days; native sign-out and expired-token logout can't revoke. **Fix:** revoke (all) refresh tokens inside `update_password`; let logout accept expired/no-auth and revoke the presented token; optional reuse-detection on rotated tokens. *(auth-account)*
- [ ] **S13** · MED · S — **Pre-verification account-takeover window** (register "resume" overwrites password but leaves old verification link valid). **Fix:** call `invalidate_pending_verifications` on resume; rate-limit the resume path. *(auth-account)*
- [ ] **S14** · MED · S — **PMD moderator batch actions bypass the audit log**, attributed as `deleted_by_user`/`hidden_by_user` — same mis-attribution class PR #234 just fixed for comments. **Fix:** set `hidden_by_mod`/record actor; one audit entry per batch; invalidate feed caches on HIDE/DELETE. *(content-api)*
- [ ] **S16** · MED · M — **Pyodide loaded from third-party CDN into a token-holding origin** (Divoom import). **Fix:** self-host the pinned distribution (repo already serves aux apps) or sandbox the decoder on a separate origin. *(frontend-arch)*
- [ ] **S17** · MED · S — **Caddy admin API reachable by every container on `caddy_net`** (incl. dev + third-party Piskel/Pixelc) → rewrite prod routing/TLS; Caddy holds the docker socket. **Fix:** `CADDY_ADMIN=localhost:2019`, drop the host publish; use `docker exec` for admin. *(infra-deploy)*
- [ ] **S18** · MED · S — **`POST /player/provision` unauthenticated + unthrottled** → DB row flood between hourly sweeps. **Fix:** per-IP rate limit + cap on pending registrations per IP; consider a provisioning nonce. *(security)*
- [ ] **S19** · MED · S — **Main web app has no clickjacking/security headers at the edge** (editors are protected; the session-holding app isn't). **Fix:** add `frame-ancestors 'self'` (or `X-Frame-Options`), `X-Content-Type-Options: nosniff`, HSTS to the web service Caddy labels. *(security)*
- [ ] **S20** · MED · S — **`register_push_token` has no rate limit** → `PushToken` row flood. **Fix:** per-user rate limit (same class as S18). *(critic gap, confirmed)*
- [ ] **S21** · MED · S — **Rate-limit gaps on `change_password`, register-resume, refresh, check-handle-availability.** **Fix:** per-user/per-IP throttles; a shared decorator would also de-dup ~10 hand-rolled throttle blocks. *(auth-account)*

### Ops & infra (P1)

- [ ] **O8** · HIGH(meta) · M — **No observability/alerting anywhere** (root cause of every silent-failure finding). **Fix:** one error alerter (Sentry free tier) + a healthchecks.io dead-man's-switch per beat task, so A1/A3/A6/A7-class failures page instead of hiding. *(critic gap)*
- [x] **O2** · HIGH · S — **Deploys take the whole stack down for the image-build duration, no rollback.** **Fix:** reorder `make deploy` to `build && up -d` (compose recreates only changed containers; a failed build leaves the old stack up); guard `clean` against running in prod. *(infra-deploy, simplicity lens)*
- [ ] **O1** · HIGH · M — **Split-brain env: `.env` (env_file) vs `.env.prod` (substitution)** must be hand-synced; editing the file every Makefile command names silently changes only the substituted subset. **Fix:** add `env_file: .env.prod` to every prod service (mirror dev), delete/symlink prod `.env`. One canonical file per env. *(infra-deploy)*
- [ ] **O3** · HIGH · L — **Three-way schema divergence:** live DB has out-of-band objects (main feed composite index, both trgm indexes, the only CHECK, most FK `ondelete`) in neither `models.py` nor migrations; tests use a third `create_all` schema. A DR rebuild from migrations produces a degraded schema. **Fix:** one reconciliation migration capturing the OOB objects; backport into `models.py`; add a periodic "autogenerate diff is empty" check; consider building the test schema from migrations. *(data-model)*
- [x] **O4** · MED · S — **Celery broker on `allkeys-lru` Redis** → queued tasks (deletion, rollups, push, mkpx) silently evicted under memory pressure. **Fix:** point `CELERY_BROKER_URL` at a `noeviction` Redis (repurpose the dead `redis` service, O11); keep `allkeys-lru` for the cache only; drop cache.py's broker fallback. *(infra-deploy, simplicity lens)*
- [ ] **O5** · MED · S — **Auto-migration multi-head handling silently skips a branch** (`main.py:96-110` `max()` over IDs half of which key to `0`). **Fix:** `command.upgrade(cfg, "heads")` or raise a loud `RuntimeError` naming the heads; standardize revision IDs to the date-prefixed convention; consider a `pg_advisory_lock`. *(infra-deploy, velocity lens)*
- [ ] **O9** · HIGH · M — **Tests share live Redis/Celery/broker/MQTT/vault; `make test` unguarded in prod.** Test runs enqueue real tasks the live worker executes against the live DB (small-int test IDs collide with real rows), write junk analytics, flush live rate-limit keys. **Fix:** `task_always_eager` / autouse fixture stubbing `.delay`; dedicated Redis DB index; Makefile `test` refuses `ENV=prod`. *(tests-quality)*
- [ ] **O10** · HIGH · S — **`pytest` can apply working-tree migrations to the LIVE DB** (the revision short-circuit checks the test DB, but `alembic upgrade` runs against the live/admin URL). **Fix:** skip `run_migrations` when `TEST_DATABASE_URL` is set; build the test schema via `alembic upgrade head` on `makapix_test` (also gains migration coverage). *(tests-quality)*
- [ ] **O6** · MED · M — **API/worker run the bind-mounted working tree, not the built image** — non-hermetic; `git pull` changes code under live processes; images are dead weight. **Fix:** drop prod source bind-mounts (keep dev), non-editable install without `[dev]`, add `USER`, remove `--reload`. Image becomes the deploy unit; rollback = retag. *(infra-deploy, simplicity lens)*
- [ ] **O7** · MED · M — **Prod has no resource limits / log rotation / some healthchecks** (one runaway process takes down both envs + Caddy). **Fix:** copy dev's resource-limit blocks into `docker-compose.prod.yml`; add an `x-logging` anchor with max-size/max-file; add a celery `inspect ping` worker healthcheck. *(infra-deploy)*

### Testing (P1)

- [ ] **T1** · HIGH · L — **Zero coverage for the moderation surface, core feeds, and destructive scheduled tasks** — where an auth mistake is privilege escalation and a cleanup bug is unrecoverable nightly data loss. **Fix, prioritized:** (1) table-driven permission-matrix tests for `umd.py`/`admin.py`; (2) selection-predicate tests for each `cleanup_*`/rollup task (+ idempotency: second run is a no-op); (3) happy-path tests for `/feed/promoted`, `/feed/following`, `/search`. *(tests-quality, tasks-services)*

---

## P2 — Structural debt & spreading antipatterns ("nip in the bud")

Resolve by **Theme** — each row here retires a cluster and stops the next copy. These add almost no operational surface; the existing good pattern to copy is noted.

### Consolidation (Theme T2 — copy-paste divergence)

- [ ] **D1** · MED · M — **Post-visibility predicate copy-pasted ~15× and diverging** (the most dangerous copy-paste in the repo; root of A13). **Fix:** one `visible_posts_query(db, viewer, *, include_own=False)` in `utils/visibility.py` composing the existing `apply_block_filter` + `apply_monitored_hashtag_filter`; refactor all list endpoints onto it, file-by-file under tests. *(content-api, velocity lens)*
- [ ] **D5** · MED · M — **AMP ingestion pipeline duplicated** (`upload_artwork` vs `replace_artwork`, ~150 lines; the copy lacks rate-limit + quota → S10). **Fix:** extract `inspect_artwork_upload(bytes, filename) -> AMPMetadata` + `purge_post_vault_files(post)`; route both ingestion paths and all three delete paths through them. *(content-api, vault-storage, velocity lens)*
- [ ] **D8** · MED · M — **"Total views" computed four incompatible ways** across six stats services (feed card / post panel / profile / dashboard all differ). **Fix:** one stitching helper (raw-since-latest-rollup + daily rows) + one documented definition per exposed metric; route all callers through it. Fix the profile undercount + the dashboard's stale-comment auth gap now (few-line each). *(tasks-services, data-identity lens)*
- [ ] **D9** · MED · M — **`artist_dashboard` duplicates `stats.py`** (~300 lines), drops authenticated history on a stale premise (`PostStatsDaily` *has* had auth columns since `models.py:1256`), and is N+1. **Fix:** parameterize the shared aggregation by `post_ids`; fix the auth branch; grouped SQL instead of per-post calls. *(tasks-services, data-identity lens)*
- [ ] **D10** · MED · L — **Three parallel vault modules with contradictory sharding** (artwork stores an opaque shard; avatars *derive* paths at call time → a future v3 reshard silently breaks avatars). **Fix:** one storage primitive parameterized by sub-vault; give avatars a stored shard/full relative path. *(vault-storage, data-identity lens)*
- [ ] **D21** · MED · S — **Dimension rules in three server copies** despite a "single source of truth" claim (`vault.py` vs `amp/constants.py` vs `/config`). **Fix:** `amp/constants.py` imports the thresholds from `vault.py`. *(vault-storage)*
- [ ] **D22** · MED · S — **Post-deletion paths delete only recorded formats** (SSAFPP variants orphan; only the retired sweep defends, and there's no orphan reaper until reshard Phase 5). **Fix:** apply `set(formats) | set(FORMAT_TO_EXT)` in all three paths; drop the `if formats:` gate in account deletion. *(vault-storage)*

### Frontend spine (Theme T3)

- [ ] **D2** · HIGH · L — **No API client layer** (81 base-URL re-derivations, 12 `Post` interfaces, raw fetch in ~40 files, silent contract drift; also stalls `/v1` at 0%). **Fix:** `openapi-typescript` codegen from `openapi.json` (zero-runtime) + one `apiFetch<T>` owning base URL/`/v1`/401-redirect; wire typegen into `make check`; migrate pages as touched. *(frontend-arch, frontend-quality, velocity lens)*
- [ ] **D3** · HIGH · L — **Copied 2,000-line page template:** 8 hand-duplicated infinite-scroll machines, no server-state cache, `Layout` refetches `/auth/me` per page. **Fix:** one `usePaginatedFeed(url, filters)` hook; adopt SWR for `/auth/me`, `/hashtags/top`, `/api/config`; move `Layout` into `_app.tsx`. *(frontend-arch)*
- [ ] **D4** · HIGH · L — **Post-actions menu triplicated** across `p/[sqid]`, `SelectedPostOverlay`, `WebPlayer` — already diverged (WebPlayer missing Report/mkpx). **Fix:** `usePostActions(post)` hook + `PostActionsMenu` parameterized by capability flags; migrate one surface at a time. *(frontend-quality)*
- [ ] **D14** · MED · M — **Comments UI implemented twice** (`CommentsAndReactions` 901 + `SPOCommentsOverlay` 628) + a third `Comment` type — moderation-label logic can drift (root of A12). **Fix:** shared `useComments(postId)` + `CommentList` parameterized by presentation; move `Comment` to shared/generated types. *(frontend-arch)*
- [ ] **D15** · MED · M — **Auth identity across 7 localStorage keys, 3 writers, incomplete `clearTokens`** (stale fragments after logout; profile link flashes empty after OAuth). **Fix:** `AuthContext` in `_app.tsx` as sole owner (single persist/clear covering all 7); stopgap: make `clearTokens` remove `user_key`+`public_sqid` today. *(frontend-arch)*

### Layering & structure (Theme T5)

- [ ] **D6** · MED · L(+S) — **`tasks.py` 4,390 lines / 12 domains, error-swallowing convention.** **Fix now (S):** shared task decorator that owns the session and re-raises/retries (stop `return {"status":"error"}`); **later (L, opportunistic):** split into a `tasks/` package (names are FQ strings, so moving bodies is safe), move the inline HTML template to a Jinja template *with escaping*. *(tasks-services, simplicity + velocity lens)*
- [ ] **D7** · MED · L — **`routers/auth.py` 2,857 lines / 5 auth systems;** GitHub OAuth duplicated ×2 (divergent email trust → A8), user provisioning ×4, GitHub-App admin + inline HTML in the router. **Fix:** extract `services/user_provisioning.py` + `services/github_oauth.py` (mirror the existing `apple_signin` service); grant handlers as a dispatch dict; move github-app endpoints to their own router; template the callback HTML. Do it before the next provider/grant. *(auth-account, velocity lens)*
- [ ] **D13** · MED · L — **Moderation surface split accidentally** across `admin`/`umd`/`pmd`/`badges` (admin keys by UUID, umd by sqid; 6 duplicate endpoint pairs; audit `target_id` format varies; umd hard-delete violates the soft-delete invariant). **Fix:** pick sqid addressing, collapse the pairs, standardize audit action names + `target_id`, make umd `delete_comment` soft-delete. *(content-api)*
- [ ] **D17** · MED · L — **`player.py` 1,849-line god router** (device lifecycle + certs + public verify + SSE + control); command-payload builder duplicated verbatim; `get_user_by_sqid` reimplemented ×4. **Fix:** split into `player_provisioning`/`player_public`/`player_control`; extract `build_command_payload`; one canonical `get_user_by_sqid`. *(player-mqtt)*
- [ ] **D18** · MED · S — **`async def` handlers doing blocking SQLAlchemy I/O** (`search`, `stats`, `tracking`, `users`) block the event loop on the single worker. **Fix:** drop `async` (→ threadpool) on the sync-DB handlers. One line each. *(conventions)*
- [ ] **D25** · MED · M — **Error-envelope convention aspirational** (~480 `HTTPException` vs ~50 `AppError`; enumerated codes like `handle_taken`/`quota_exceeded`/`token_expired`/`account_banned` never actually raised → app team must parse strings). **Fix:** convert the client-branched raise sites to `AppError`; fix the `/v1` 404-detail-dict mangling; grep-check discouraging new `HTTPException` in v1 routers. *(conventions, content-api)*

### Identity & schema (Theme T4)

- [ ] **D11** · MED · (policy) — **Identity sprawl** (int PK + UUID + sqid all serialized everywhere; sqids are unsalted/reversible so int IDs add pure surface). **Fix:** adopt the rule that every *new* endpoint/topic/payload is sqid-keyed (comment-author-sqid already does this); stop serializing raw int IDs / `user_key` in new schemas; don't churn existing app-team contracts. *(data-model, data-identity lens)*
- [ ] **D12** · MED · M — **`public_sqid` nullable, manually assigned post-insert at 8+ sites** (a forgotten assignment → content invisible to feed + 500s; NOT-NULL follow-up outstanding since June). **Fix:** compute at serialization time or via a Postgres generated column; or centralize into one helper, backfill, add `NOT NULL` + CHECK, drop the defensive filters. *(data-model, data-identity lens)*
- [ ] **D23** · LOW · M — **Zero CHECK constraints; all enums/invariants Python-only** (bad rows already leaked — `list_comments` filters `depth>2` "to prevent widget errors"). **Fix:** one migration adding CHECKs for status/kind/depth/reaction-XOR; mirror in `models.py` `__table_args__`. *(data-model)*
- [ ] **D24** · LOW · M — **Pagination fragmented into 3 cursor formats + misleading `PLACEHOLDER`/`TODO` code** in the production paginator. **Fix:** delete the stale comments, document the format, migrate `pmd`/`social_notifications`/`search` onto the shared helper once A5 lands. *(data-model, conventions)*

### Perf & resilience (P2)

- [ ] **D19** · MED · M — **Hashtag aggregation loads the entire posts table into ORM memory** on every cache miss (attacker/crawler can force misses). **Fix:** one SQL `unnest`+`GROUP BY` aggregation, or a `hashtag_stats` rollup table via the existing beat. *(content-api, search)*
- [ ] **D20** · MED · M — **Quota accounting drifts from disk 4 ways** (upscaled previews, grace copies, avatars uncounted; users charged for server-generated variants). **Fix:** decide the policy (charge native+mkpx only, or record upscaled + check projected size); fix the soft-deleted-posts filter mismatch. *(vault-storage)*
- [ ] **D16** · MED · M — **`cache.py`:** `KEYS`-based invalidation, TTL-dropping clamp, non-atomic rate limit, lossy type round-trip, scattered key literals (unread-count keys can go immortal). **Fix:** central keys module + `invalidate_feed_caches()`; `SCAN` not `KEYS`; Lua/pipeline for incr+expire; always JSON-encode. *(tasks-services)*
- [ ] **D26** · MED · M — **MQTT subscribers use blocking `connect()` at startup, no self-heal on initial failure** (paho auto-reconnect only kicks in after a first success; broker-not-ready-at-boot → subscriber dead until API restart). **Fix:** mirror `publisher.py` (`connect_async` + `reconnect_delay_set` + `loop_start`), or `depends_on: service_healthy`; periodic liveness recreate. *(player-mqtt)*
- [ ] **D27** · MED · M — **New-post notification fan-out runs synchronously in the request** with per-message broker `PUBACK` waits (a popular poster / slow broker = multi-second post creation). **Fix:** move to a Celery task dispatched after commit, like the push path. *(player-mqtt)*
- [ ] **F1** · MED · M — **Fetch effects without cancel/order guards on core pages;** search fires twice per keystroke. The correct `fetchVersionRef` pattern exists in `u/[sqid].tsx` but isn't on the highest-traffic page. **Fix:** adopt `fetchVersionRef`/`AbortController` in `p/[sqid]` + `search`; hoist `/auth/me` out of the per-post effect. *(frontend-quality)*
- [ ] **F2** · MED · M — **Keyboard accessibility broken in the core browse flow** (no focus indicator on cards, click-only stat buttons, untrappable modal, `role="button"` ignoring keys). **Fix:** `:focus-visible` on cards, real `<button>`s, `onKeyDown`, dialog focus-trap. Fixing the shared menu (D4) fixes several copies at once. *(frontend-quality)*
- [ ] **T5** · MED · M — **OpenAPI gate detects uncommitted drift, not breaking changes.** A renamed field / removed endpoint passes if you re-run `make openapi` — the app team + players break at runtime. **Fix:** add an `oasdiff` breaking-change step vs the last released contract. *(tests-quality, velocity lens)*
- [ ] **T2** · MED · M — **Frontend entirely ungated** (`check-full` runs zero web code; typecheck only at deploy-build). **Fix:** add `cd web && npm run typecheck` + lint to `make check`; wire a Playwright smoke spec into `check-full`. *(tests-quality, frontend-arch, velocity lens)*
- [ ] **T3** · MED · M — **Playwright "e2e" stale (last run May 21) and fully API-stubbed** → it's a component suite; contract drift is invisible; one assertion is always-true. **Fix:** anchor the vacuous regex; run on a schedule / in `check-full`; add one unstubbed `register→upload→view` journey against the dev stack. *(tests-quality)*
- [ ] **T4** · MED · M — **Per-test app lifespan churns real MQTT connections → OOM papered by the chunk runner;** view subscriber never stopped (dead `stop` fn, also in prod shutdown). **Fix:** `stop_view_subscriber()` in lifespan shutdown; env flag to skip MQTT startup under pytest, or session-scope the client; then retire/shrink chunking. *(tests-quality, infra-deploy, velocity lens)*

### Growth-enabling (P2)

- [ ] **F3** · HIGH · L — **All public content is client-side rendered, no per-post OG/metadata** → artwork/profile pages are invisible to crawlers and unfurl as the generic site card. Caps the SEO-driven growth plan the sitemap/OG infra was built for. **Fix:** `getServerSideProps` on `/p/[sqid]` + `/u/[sqid]` emitting per-page title/OG/JSON-LD; hydrate interactivity client-side as today. *(frontend-arch, simplicity lens)*

---

## P3 — Dead code, cleanup, docs, hygiene

Low-risk deletions and hygiene. Several are `S` and satisfying to batch. **Add `ruff check` to `make check` (T6) first** — it will catch a chunk of the dead-import debris automatically.

### Dead code / cruft removal

- [ ] **C1** · MED · S — Delete `SelectedArtworkOverlay.tsx` (1,229 lines, dead twin shadowing the live overlay) + `hooks/useArtworkScaling.ts` + empty `pages/posts/`,`pages/users/`. *(frontend-arch)*
- [ ] **C2** · MED · S — Rewrite `pages/user/[id].tsx` (1,700-line dead/drifted profile, lacks report/block/follow) as a thin redirect like `post/[id].tsx`. *(frontend-arch, frontend-quality, data-identity lens)*
- [ ] **C3** · MED · M — **Relay/GitHub-Pages pipeline broken at two points, dormant, still mounts routes + stores token paths.** Delete the relay router/task/`validation.py`/`RelayJob` model (safer), or fix + test if wanted. *(vault-storage, security)*
- [ ] **C4** · MED · S — Delete `api/app/d_cloud_sync.py` (broken, unimportable, references a hardcoded-credential module, does outbound HTTP — security-relevant clutter inside the deployed package). *(vault-storage, security, conventions)*
- [ ] **C5** · LOW · S — Delete `mqtt_legacy.py` (dead, publishes to an ACL-denied topic) + the `mqtt/__init__.py` fallback; point the demo at `publisher.publish` or remove it. *(player-mqtt, conventions)*
- [ ] **C6** · LOW · S — Drop the dead `PostStatsCache` table + its zombie hourly `cleanup_expired_stats_cache` beat task (empty table swept 24×/day). *(tasks-services, data-identity lens)*
- [ ] **C7** · LOW · S — Delete `utils/transparency.py` (dead, documents a policy the live AMP copy abandoned), the uncalled avatar helpers, and unused imports. *(vault-storage)*
- [ ] **C8** · MED · S — Delete the dead widget-init effect in `p/[sqid].tsx:568-616` — it leaks an unstoppable 10 Hz retry loop per post view (CPU/battery drain on the most-visited page). *(frontend-quality)*
- [ ] **C9** · LOW · S — `components/ui/` shadcn kit is inert (no Tailwind pipeline); 13/15 unused, the 2 used render unstyled. Delete it (or actually install Tailwind); restyle the 2 usages in the styled-jsx convention. *(frontend-quality)*
- [ ] **C10** · LOW · S — Delete `pages/debug-env.tsx` (routable in prod); remove the placeholder menu items duplicated in 3 menus + phantom auto-scroll ref (or implement the divoom log auto-scroll). *(frontend-quality)*
- [ ] **C11** · LOW · S — Remove/gate the `/mqtt/demo` and `/rate-limit` placeholder endpoints (the latter advertises fabricated budgets) — they ship in the OpenAPI contract as if real. *(conventions)*
- [ ] **C12** · LOW · S — Download routes: treat NULL `storage_shard` as 404, not an uncaught `ValueError` → 500 (keep the ValueError for write paths). *(vault-storage)*

### Security hardening (low)

- [ ] **S22** · LOW · M — Device private keys + GitHub tokens + push tokens stored **plaintext** in the DB (a DB dump / backup compromise = full fleet re-issue). **Fix:** stop persisting `key_pem` after delivery, or encrypt with an out-of-DB key; GitHub tokens are re-mintable. *(data-model, critic)*
- [ ] **S23** · LOW · S — `chmod 600 server.key` in `gen-certs.sh` (currently 644, world-readable, in a shared-RW mount); mount only the files api/worker need, read-only where possible. *(infra-deploy)*
- [ ] **S24** · LOW · S — `try_delete_avatar_by_public_url` builds unlink paths from unvalidated URL segments (latent traversal; one refactor from reachable). **Fix:** validate each shard segment `^[0-9a-f]{2}$` / `resolve()`+containment check. *(vault-storage)*
- [ ] **S25** · LOW · S — `GET /relay/jobs/{id}` has no auth/ownership (IDOR on repo name/SHA/error). **Fix:** require owner/mod (moot if C3 deletes relay). *(security)*
- [ ] **S26** · LOW · M — Website registration emails the account password in plaintext. **Fix:** one-time setup token / force password set after verification instead of mailing the credential. *(auth-account)*
- [ ] **S28** · INFO · S — Document the X-Forwarded-For trust invariant (all IP throttles/ownership silently depend on it) + a startup assertion, so adding a CDN forces an explicit review. *(security)*

### Correctness (low)

- [ ] **DOC7** · LOW · S — Editing a comment bypasses the profanity filter + rate limit applied at creation. **Fix:** apply both in `update_comment`. *(content-api)*
- [ ] **DOC8** · MED · S — `PATCH /user/{id}` handle change bypasses the email-verification gate + audit logging that `/auth/change-handle` enforces. **Fix:** one `change_handle(db, actor, target, new_handle)` service both call. *(auth-account)*
- [ ] **DOC9** · LOW · S — `link_oauth_identity` raises `IntegrityError` with wrong constructor args → `TypeError`/500 on the concurrent-OAuth race. **Fix:** raise a domain exception mapped to 409. *(auth-account)*
- [ ] **DOC10** · MED · M — `email_normalized` written only at password registration (OAuth accounts NULL → alias-abuse protection gaps; 5 divergent lookup idioms). **Fix:** a `@validates('email')` maintaining it + one `find_user_by_email` normalizer; backfill NULLs. *(auth-account)*
- [ ] **DOC11** · LOW · S — Session-acquisition + naive-datetime conventions drift across tasks (works only while sessions are UTC). **Fix:** one `task_session()` contextmanager; ban `next(get_session())` + `utcnow()` (ruff DTZ). *(tasks-services)*
- [ ] **DOC12** · LOW · S — Bare `except:` + silent `pass` in `github.py`/`tasks.py`/`relay.py` (swallows KeyboardInterrupt/SystemExit; hides failures). **Fix:** narrow to `except Exception`, log before continuing. *(conventions)*
- [ ] **DOC6** · LOW · S — Stale TODOs mix noise (done work) with a real hazard: ban/delete does **not** cascade-hide a user's content, so a banned user's posts stay visible. **Fix:** implement cascade-hide-on-ban (or track it); delete the done TODOs. *(conventions)*

### Hygiene & docs drift

- [ ] **T6** · LOW · S — Ruff is configured (E/F/I/B) but never run by any gate. **Fix:** add `ruff check app tests scripts` to `make check` (fix/ignore existing violations first). *(vault-storage, tests-quality, conventions)*
- [ ] **T7** · LOW · M — Promote `_auth`, user/moderator/post factories, and `vault_tmp` into `conftest.py` (currently `_auth` ×10, user factories ×40, `vault_tmp` ×4); the duplication is the biggest friction against closing coverage gaps. *(tests-quality)*
- [ ] **T8** · LOW · M — ~44% of test HTTP calls pin the deprecated bare-root mounts (and assert the wrong error shape). **Fix:** mechanically migrate test paths to `/v1`, keep a few explicit legacy-mount regression tests. *(tests-quality)*
- [ ] **T9** · LOW · S — Test seed data is wiped after the first test in each chunk (later tests run with no owner account, ordering-dependent). **Fix:** re-run `ensure_seed_data()` in the fixture teardown; replace inline `TestClient(app)` with the fixture. *(tests-quality)*
- [ ] **O11** · LOW · S — Delete the dead `redis` edge service + `redis_data` volume (zero consumers, passwordless on `caddy_net`) and the `vault`/`www-redirect` `sleep infinity` stubs — or repurpose `redis` as the O4 `noeviction` broker. *(infra-deploy, simplicity lens)*
- [ ] **O-net** · LOW · S — Remove the ambiguous `api`/`mqtt` aliases on `caddy_net` (both envs claim them; DNS resolves nondeterministically). Everything in-repo already uses container names — verify with a Caddy-label grep, then delete. *(simplicity lens)*
- [ ] **DOC1** · LOW · S — Update `docs/architecture.md` to the 2-level `/{a}/{b}/` vault model, drop playlist/playset table rows, fix the module count. *(conventions)*
- [ ] **DOC2** · MED · M — Rewrite `README.stack.md` around the Makefile/dual-env model (its commands fail + name nonexistent containers — it's the mid-outage fallback doc); regenerate one env template from the real key set; delete `.env.example`; archive `apps/cta` + `monitor-cta-stats.sh`. *(infra-deploy)*
- [ ] **DOC3** · LOW · S — Reconcile `docs/api-versioning-policy.md` with reality (web is 100% on bare `/api`; `/v1` stalled at 0%; the "one-release" dual-mount is now permanent). Either migrate web to `/v1` (via D2) or document web-stays-on-root-by-design. *(conventions, simplicity + velocity lens)*
- [ ] **DOC4** · LOW · S — Fix `docs/development.md` "Adding New Features" (registers with `prefix="/api"`, imports `get_db` from the wrong module, directs new tasks into the `tasks.py` monolith — agents copy it). Add the two-sentence layering rule to `CLAUDE.md`. *(velocity lens)*
- [ ] **DOC5** · LOW · S — Update `docs/mqtt-protocol/01-architecture.md`: cert validity is 3 years not 1; regenerate the ACL tables from the (fixed) live file. *(player-mqtt)*
- [ ] **DOC13** · LOW · M — Standardize path-param naming (`{public_sqid}` for sqid resources, `{comment_id}` snake_case; stop reusing `{id}` for both int and UUID). *(conventions)*
- [ ] **DOC14** · LOW · S — Use the module-level logger everywhere (player.py has ~10 inline `getLogger`) + lazy `%s` formatting (ruff G-series). *(conventions)*
- [ ] **F4** · LOW · M — Move shared spinner/status-banner/menu/panel CSS into `globals.css`/modules (colocated styled-jsx is the biggest driver of the 2,000-line files; portals can use global classes, killing SPO's imperative hover handlers) — shrinks the giants 20-40%. *(frontend-quality)*
- [ ] **F5** · LOW · S — Remove/fix the dead sqid-vs-id identity comparisons in the client; standardize on `public_sqid`, name vars by encoding (`userIdInt`/`userSqid`). *(frontend-quality)*

---

## Follow-up reviews (not yet covered — README §6)

- [ ] **G1** — Focused review of the **FCM/push subsystem** (`services/push.py`, `routers/me.py`, `PushToken`, dispatch): rate-limiting, token-at-rest, preference authZ, tests. *(biggest coverage hole)*
- [ ] **G2** — **Data-privacy / GDPR-erasure audit:** enumerate every PII store + retention; verify (or fix) that account deletion + a data-export path can satisfy a data-subject request (currently: no, per A1).
- [ ] **G3** — Review **`deploy/backup/`** for restore-drill recency, plaintext-secret blast radius, and whether a broken-deletion/corruption event is actually recoverable.
- [ ] **G4** — Decide **i18n** posture explicitly (hardcoded English incl. emails; GeoIP special-cases BR; outreach growth plan) — flag retrofit cost now while string sites are few.
- [ ] **G5** — **Dependency management:** pin via a lockfile (`uv`/`pip-tools`), add a periodic audit; there's no CI to catch drift/CVEs and images re-resolve on every build.

---

### Refuted in verification (recorded so they aren't re-raised)

- ~~Cert renewal orphans the previous serial (un-revocable 3 years)~~ — refuted on inspection of the renewal path. *(player-mqtt)*
- ~~`search_all` divides by `len(types)`, empty list → 500~~ — not reachable; `types` defaults non-empty and FastAPI substitutes the default when absent. Verified empirically. *(security)*
