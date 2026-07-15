# Makapix Club — First-Principles Appraisal (July 2026)

| | |
|---|---|
| **Date** | 2026-07-15 |
| **Branch / commit** | `develop` @ `3c94349` |
| **Scope** | Whole repository — `api/`, `web/`, `worker/`, `mqtt/`, `deploy/`, `docs/`. Playlists and blog-posts deliberately **excluded** per owner instruction. |
| **Method** | Multi-agent read-only appraisal: 12 blind per-area reviewers → adversarial verification of every finding → 3 first-principles architecture lenses → completeness critic. 28 agents, ~3.5M tokens. 143 raw findings, **141 survived verification**, 2 refuted. |
| **Independence** | The reviewers were **not** shown the prior [`docs/codebase-review-2026-07/`](../codebase-review-2026-07/README.md) (2026-07-06). This is a genuine independent second pass; the cross-reference in §3 is the interesting result. |
| **Deliverables** | This narrative report + [`BACKLOG.md`](./BACKLOG.md) (the full prioritized, de-duplicated, actionable remediation list). No code was changed. |

---

## 1. Executive summary

Makapix Club is, structurally, a **well-conceived single-VPS product built by someone who knows what they're doing.** The parts that usually rot first are the parts that are best here: the vault storage subsystem is genuinely excellent (opaque stored shards, atomic writes, key-rotation-for-immutable-caching, a real executed resharding), JWT/OAuth handling is textbook (pinned algorithms, PKCE + state + redirect allowlist, constant-time nonce, Apple JWKS done right), the external-app contract workflow (committed sorted `openapi.json`, drift gate, numbered message exchanges, `/config` feature discovery) is a **model practice worth keeping verbatim**, the backup/DR pipeline is drill-verified, and hot read paths use keyset pagination and batched counts rather than the naive patterns you'd expect.

The good condition is, however, **concealing real problems** — which was the premise of this exercise. Three things stand out:

1. **The back half of several lifecycles is broken and nobody knows**, because there is no error monitoring anywhere. Permanent account deletion *deterministically fails for every user* (it destroys their content, then trips an FK on the audit row it wrote about them, leaving a live PII-bearing account behind — a broken right-to-erasure). The unverified-account reaper *fails every run* (live-confirmed in worker logs). Ban enforcement is broken **both ways** (temp ban 500s, permanent ban is a silent no-op). Batch download produces empty ZIPs. Nightly rollups silently drop analytics data and then delete the raw events. Every one of these is invisible except by tailing container logs.

2. **The single biggest antipattern is copy-paste of cross-cutting logic that has already diverged.** The post-visibility predicate is hand-retyped in ~15 places and the copies now disagree — user-hidden posts leak into the following feed and hashtag counts, banned users show up in search. The AMP upload pipeline exists twice and the copy skips rate-limit and quota. The frontend has *no API client at all*: the base URL is re-derived 81 times, `interface Post` is re-declared 12 times, and a schema change breaks pages silently at runtime because nothing ties the frontend to the OpenAPI contract the backend so carefully gates. **These are the "emerging antipatterns to nip in the bud" — except several are past the bud stage and actively generating bugs.**

3. **The MQTT security boundary is broken.** The browser ships a shared `webclient` password (it's a `NEXT_PUBLIC_*` value, public by definition) and the broker ACL's final `topic read #` line — commented "deny all" — actually grants that shared account read on **every topic**: every user's social-notification stream and the entire physical-player fleet's command/status/RPC traffic. The plaintext broker port is also bound to the public internet. This is a live cross-user eavesdropping channel, not a latent one.

None of this means the app is unsound. It's the accumulated debt of fast incremental growth: an unfinished int⇄UUID⇄sqid identity migration, a stats subsystem where six services each compute "views" differently, a `tasks.py` that has grown to 4,390 lines across twelve unrelated domains, and a frontend that copies its 2,000-line page template forward every time. The fixes cluster into a small **fix-first shortlist** (§2) that removes essentially all the live data-loss and security exposure cheaply, and a longer **consolidation backlog** (§4, [`BACKLOG.md`](./BACKLOG.md)) that is mostly *de-duplication, not decomposition* — and notably adds almost no new operational surface.

### Findings by severity (post-verification)

| Severity | Count | Meaning here |
|---|---:|---|
| **Critical** | 4 | Live data-loss or a fully-broken feature, confirmed against the code/live DB |
| **High** | 30 | Security exposure, 500s on common paths, ongoing silent data corruption, or an antipattern actively spreading |
| **Medium** | 64 | Real correctness/perf/ops/structural defect with bounded blast radius today |
| **Low** | 41 | Hygiene, hardening, latent-at-scale |
| **Info** | 2 | Scale-headroom notes |

(The critical count is 4 rows but really **one root defect** — account deletion — surfaced by four independent reviewers, plus the empty-ZIP batch-download bug. See §2.)

---

## 2. Fix-first shortlist

If nothing else gets done, do these. Each is **confirmed against the code** (several against the live dev DB), and each either loses data, breaks a shipped feature, or exposes the server / other users. They are ordered by (severity ÷ effort). Backlog IDs in brackets map to [`BACKLOG.md`](./BACKLOG.md).

1. **[CRITICAL, M] Account deletion can never complete — broken right-to-erasure.** `request_account_deletion` writes an `audit_logs` row whose `actor_id` is the user being deleted; that FK is `ON DELETE RESTRICT` in the live DB, so the task's final `db.delete(user)` (`tasks.py:4080`) raises `IntegrityError` for **every** user. Users with a batch-download row crash even earlier on `bdr.download_path` (the field is `file_path`, `models.py:1864`). Push tokens, violations, reports, relay jobs are never handled. Because each step commits separately, content and vault files are wiped but the `users` row, email, and handle **persist forever** while Celery retries. This is a live, confirmed, GDPR-relevant breakage. `[A1]`

2. **[CRITICAL, S] Batch download produces empty ZIPs.** `process_bdr_job` (`tasks.py:3239`) calls `vault.get_artwork_file_path(...)` but never imports `vault` — every vault-backed artwork fails with `NameError`, users get a "ready" ZIP containing only `metadata.json`. Add `from . import vault`. `[A2]`

3. **[HIGH, S] MQTT `topic read #` ACL + browser-shipped password → total eavesdropping.** Delete line 46 of `mqtt/config/acls` (mosquitto is deny-by-default), and bind the plaintext listener (`1883`/`1884`) to loopback instead of `0.0.0.0`. Then plan the real fix: retire the shared-password browser MQTT path in favor of the authenticated SSE stream that **already exists** (`routers/realtime.py`) — a shared credential can never scope `social-notifications/user/{id}` per user. `[S1, S2]`

4. **[HIGH, S] Ban enforcement is broken both ways.** `auth.py:116` compares a tz-aware `banned_until` against `datetime.now(timezone.utc).replace(tzinfo=None)` → `TypeError` → **500 on every request** from a temp-banned user (the reports-resolution default), including public optional-auth endpoints. A "permanent" ban writes `NULL`, which every check reads as *not banned* — a silent no-op. The `_as_utc_aware` helper 28 lines up already does it right. The entire shipped ugc-safety moderation feature depends on this. `[A4]`

5. **[HIGH, S] Three token-exfiltration / login-CSRF holes, each a one-liner.** (a) `Layout.tsx` OAuth `postMessage` receiver accepts `OAUTH_SUCCESS` from **any origin** → attacker logs the victim into the attacker's account. (b) `session-transfer.tsx` writes `access_token` into the URL hash of whatever `return=` URL is supplied, with **no host allowlist** → `?return=https://evil.example` exfiltrates the bearer token. (c) Player SSE puts the 60-minute JWT in a **logged query string**. `[S4, S5, S15]`

6. **[HIGH, S] Anonymous commenters' raw IPs are broadcast to everyone.** The public `GET /post/{id}/comments` and the embeddable widget serialize `comments.author_ip` verbatim (`schemas.py:549`) — the field's own comment says "visible to moderators", but there's no per-role stripping. Any logged-out visitor can harvest anonymous commenters' IPs, directly undermining the privacy work that carefully nulls reporter IPs after 30 days. `[S3]`

7. **[HIGH, S] `cleanup_unverified_accounts` fails every run.** Live-confirmed in dev worker logs (2026-07-14 09:42 & 21:42): the all-or-nothing bulk delete trips `posts_owner_id_fkey`, rolls back, and returns an error dict Celery logs as *success*. Unverified accounts accumulate forever and their emails are never freed. `[A3]`

8. **[HIGH, M] The nightly rollup pipeline silently corrupts and then deletes analytics.** Two independent bugs: (a) a SQLAlchemy JSON dirty-tracking bug means the second slice of each day's per-country/device/type breakdowns is computed but **not persisted**, so `post_stats_daily`/`site_stats_daily` systematically undercount; (b) rollup failure/overrun is invisible (returns success-shaped error) and the 02:30 `cleanup_old_view_events` then **permanently deletes** raw events the rollup never aggregated. Users can watch a post's lifetime view count *decrease*. `[A6, A7]`

9. **[HIGH, S] SSRF endpoint still live.** `POST /tasks/hash-url` (`routers/legacy.py:14`) — comment literally says "TODO: Remove in production" — fetches a client-supplied URL server-side with no auth and no private-range filtering. Delete it. `[S8]`

10. **[HIGH, M] Cursor pagination 500s on every non-`created_at` sort — including sorts shipped in the UI.** Page 1 encodes a `created_at` cursor regardless of active sort; page 2 feeds it to whatever column the sort names → `AttributeError` / Postgres type error. The homepage's own "Reactions" and "File Size" sorts 500 on scroll, and `getattr` on an arbitrary client sort string is an unauthenticated 500 vector. `[A5]`

11. **[HIGH, S] Comment/reaction/widget endpoints ignore post visibility.** Post IDs are sequential ints, so anyone can enumerate `/post/{id}/comments`, `/widget-data`, `/reactions` and read content of `hidden_by_mod` / `unlisted` / soft-deleted posts; a nonexistent ID 500s instead of 404. And `get_widget_data` is a drifted copy that **lost the block filter** — a blocked user's comments still appear in the widget, violating shipped ugc-safety. `[A11, A12]`

12. **[HIGH, S — one line each] Ops guardrails.** Reorder `make deploy` to build-then-swap (`build && up -d`, not `down` then `up --build`) so a deploy stops taking the whole site down for the image-build duration with no rollback. Point the Celery broker at a `noeviction` Redis (it currently rides the `allkeys-lru` cache instance, so queued deletion/rollup/push tasks can be silently evicted under memory pressure). `[O2, O4]`

> **The meta-finding:** every item in this shortlist except the cursor bug is *unmonitored* — it fails silently to a `logger.error` nobody reads. **Adding even a free-tier error alerter (Sentry) or a healthchecks.io dead-man's-switch per beat task is the single highest-leverage operational change**, because it converts this entire class of "broken for weeks, discovered by accident" into "pinged the day it breaks." `[O8]`

---

## 3. Cross-reference with the 2026-07-06 review

The reviewers were blind to the prior review. The result is a clean natural experiment, and it is not encouraging: **this independent pass re-discovered every item on the July 6 "fix-first shortlist," and spot-checks confirm each is still live in the code at `3c94349`.** In the nine days since that review, essentially none of its nine shortlist items were remediated.

| July 6 shortlist item | Status at `3c94349` | This pass |
|---|---|---|
| Account deletion half-completes (`bdr.download_path`) | **Still broken** — and *worse* than reported: the audit-log FK means it fails for **every** user, not just BDR owners | `[A1]` |
| Batch-download 100% broken (`vault` not imported) | **Still broken** — `process_bdr_job:3239` still has no `vault` import | `[A2]` |
| SSRF `POST /tasks/hash-url` | **Still present** — `legacy.py:14`, still mounted | `[S8]` |
| OAuth `postMessage` accepts any origin | **Still present** — no `event.origin` check in `Layout.tsx` | `[S4]` |
| Temp-ban 500 (naive vs aware datetime) | **Still present** — `auth.py:116`, `_as_utc_aware` exists but unused there | `[A4]` |
| Celery broker on `allkeys-lru` Redis | **Still present** — `docker-compose.yml:45` | `[O4]` |
| Rollup pipeline loses view events | **Still present** — plus a newly-found JSON-persistence bug on top | `[A6, A7]` |
| Cursor pagination 500s on non-default sort | **Still present** — `pagination.py` still a `created_at`-only placeholder | `[A5]` |
| No gate before prod auto-deploy | **Still present** — web entirely ungated; deploy still down-then-build | `[O2, T2]` |
| Quick wins: `topic read #`, plaintext MQTT port, `server.key` chmod 644 | **All three still present** | `[S1, S2, S23]` |

**Interpretation.** The July 6 review was accurate — this pass confirms its findings independently. But findings sitting in a document did not translate into fixes. That is itself the most actionable observation in this report: *the gap is not detection, it's a remediation loop.* The [`BACKLOG.md`](./BACKLOG.md) is structured to be that loop — small, ranked, checkable items rather than a prose report — and the §2 shortlist plus alerting `[O8]` should be treated as a **committed sprint**, not a reading list. If a fix-first item recurs in an August review, the process, not the code, is the problem.

Two prior findings that this pass did **not** independently reproduce (worth a glance to confirm they were fixed, not just missed): if the July 6 review flagged anything the tables above omit, treat it as still-open until verified — this pass's silence is not evidence of a fix.

---

## 4. Cross-cutting themes

The 141 findings collapse into a handful of root patterns. Fixing the *pattern* is worth more than fixing its instances one at a time — the backlog groups instances under each.

**T1 — Silent failure is the house style, and there is no smoke detector.** Beat-scheduled tasks convert exceptions into `return {"status": "error"}` (no raise, no retry, no alert); Celery logs the task as *succeeded*. Combined with zero observability tooling (`grep` finds no Sentry/Prometheus/statsd/healthchecks anywhere), every one of the §2 data-loss bugs was discoverable only by a human tailing logs. **Root fix:** a shared task decorator that owns the session and re-raises, plus one alerting integration. `[O8, D6]`

**T2 — Copy-paste of cross-cutting logic that has already diverged.** This is the antipattern the owner asked to catch early — but for several instances it's already spread and producing user-visible bugs:
- The 6-condition **post-visibility predicate**, re-typed ~15× — copies disagree, leaking hidden/blocked/banned content into feeds, hashtag counts, and search. *The single most dangerous copy-paste in the repo.* `[D1]`
- The **AMP upload pipeline** (upload vs replace) — the copy skips rate-limit and quota. `[D5]`
- The frontend **post-actions menu** across three surfaces — WebPlayer was already missed for Report/mkpx. `[D4]`
- **"Total views"** computed four incompatible ways across six stats services — the same user sees different numbers on four screens. `[D8, D9]`
- `get_user_by_sqid` ×4, `_auth` test helper ×10, user factories ×40, three cursor formats, three vault modules, dimension rules in three files.

**Root fix:** each of these has an *existing good pattern in the same repo* to copy (composable `apply_block_filter`, the `apple_signin`/`download_stats` service shape). The work is consolidation onto patterns already present, done file-by-file under existing tests.

**T3 — No frontend spine.** No API client, no shared domain types, no server-state layer, no auth context, no test gate. Every page re-implements transport, auth-gating, 401-redirect, pagination bookkeeping, and its own `interface Post`. This is why the giant 2,000-line pages exist and why the `/v1` migration is **stalled at 0%** (48 files would need editing instead of one). **Root fix:** generate TS types from the committed `openapi.json` (`openapi-typescript`, zero-runtime), one `apiFetch<T>` wrapper, one `usePaginatedFeed` hook, an `AuthContext`, and wire `npm run typecheck` into `make check`. `[D2, D3, D15, T2]`

**T4 — Three-schema truth and an unfinished identity migration.** (a) The live DB carries out-of-band DDL (the feed's main composite index, both trgm search indexes, the only CHECK, most FK `ondelete`) present in *neither* `models.py` nor migrations, while tests build a *third* weaker schema from `create_all` — a DR rebuild from migrations silently produces a degraded schema. `[O3]` (b) Every entity carries int PK + UUID + sqid, all serialized in every payload, so the sqid layer buys no opacity and every consumer juggles which ID each endpoint wants — and the sprawl is *still spreading* into new features. `[D11, O3]`

**T5 — Routers are where business logic goes to accrete, because no rule says otherwise.** `tasks.py` (4,390 lines / 12 domains), `routers/auth.py` (2,857 / 5 auth systems), `posts.py` (2,260), `player.py` (1,849) all mix transport, business logic, and side effects. A `services/` layer exists and is used correctly for *some* things (`apple_signin`, `oauth_codes`, `download_stats`), proving the better shape is understood — it just isn't the default. **Root fix is cheap and mostly documentation:** state the layering rule in two sentences in `CLAUDE.md`, fix the stale `development.md` template that teaches the wrong pattern, then extract giants opportunistically when a feature next touches them. `[D6, D7, D17]`

---

## 5. First-principles / "would we build it this way today?"

The three architecture lenses converge on a clear verdict: **the core bets are right and a rebuild would keep them; the debt is vestiges and unfinished migrations, not wrong architecture.** Postgres + one Redis + Celery-with-embedded-beat + Mosquitto + shared Caddy + FastAPI + Next.js pages-router is the correct lean shape for this product. What a rebuild would change is smaller and mostly worth migrating toward incrementally.

### Worth migrating toward **now** (cheap, high-leverage, low blast radius)

| Change | Why | Effort |
|---|---|---|
| **Collapse browser realtime to SSE; MQTT for hardware only** | `realtime.py` already delivers the identical payload with real per-user auth; the shared-password web MQTT path is *structurally incapable* of per-user scoping and is the root of the ACL leak. Removes `mqtt.js`, the `/mqtt` WS route, and the password-in-bundle. | M `[S1]` |
| **Delete the dead `redis` edge service + `vault`/`www-redirect` stubs** | Zero consumers (verified); RAM + attack surface + `make ps` noise on a constrained VPS. | S `[O11]` |
| **Build-then-swap deploys; drop prod source bind-mounts** | The single largest self-inflicted outage source; also makes the image (not the working tree) the deployment unit, so rollback becomes retagging. | S–M `[O2, O6]` |
| **Fold `cleanup_old_view_events` into the rollup tail** | Removes the last wall-clock-ordering-as-correctness dependency — the exact race the team already ate once. | S `[A7]` |
| **Per-post `getServerSideProps` OG/JSON-LD on `/p/[sqid]` and `/u/[sqid]`** | The one thing that justifies carrying a Node SSR server. Today public pages are invisible to crawlers/unfurlers — a hard cap on the SEO-driven growth plan the sitemap/OG infra was built for. | L `[F3]` |
| **Type-gen the frontend from `openapi.json` + one `apiFetch`** | Highest-leverage velocity fix; also unblocks the stalled `/v1` migration (one line vs 48 files). | L `[D2]` |
| **Multi-head migration = loud boot failure, not a heuristic guess** | `main.py:96-110` picks a head via `max()` over IDs that half the migrations key to `0`; a two-headed state (easy with AI-generated revisions on parallel efforts) deploys nondeterministically. Five-line change. | S `[O5]` |
| **State the layering rule + fix the stale `development.md` template** | Agents and contributors copy the nearest example; the docs currently teach the wrong one. | S `[D6, T5-doc]` |

### Migrate **when X happens** (right today, has a clear trigger)

- **`tasks.py` / `auth.py` package splits** — task names are fully-qualified strings, so moving bodies into submodules is behavior-preserving. Do it *per-domain when that domain is next touched*, not as a project. Trigger for auth: the next OAuth provider/grant type. `[D6, D7]`
- **Stats consolidation onto one metric-definition module** — fix the two point defects (profile undercount, dashboard's stale-comment auth gap) now; fold `artist_dashboard` onto `PostStatsService` when either is next touched. `[D8, D9]`
- **Retire the legacy vault-remap duplication** (Caddy + Python) — when download-stats show 3-level legacy hits at ~zero and a fleet firmware window lands. Keep both until then; it's stable and documented. `[data-identity lens]`
- **Longer raw-event retention + on-demand SQL** instead of the hand-written rollup merge — reconsider only if artists start asking for referrer/long-window analytics the daily rollups can't answer. `[data-identity lens]`
- **Redis pub/sub behind `player_events`** — the live player-state SSE bus is single-worker-only; fine until the day someone adds `--workers` or a replica, at which point it silently breaks for a subset of connections. Keep the single-worker constraint explicit in deploy docs until then. `[player-mqtt INFO]`

### Keep as-is (the complexity earns its keep)

- **Celery + Redis broker with embedded beat in one worker** — CPU-heavy Pillow/WebP work must not share the memory-capped uvicorn process; APScheduler-in-API would tie 17 schedules to API restarts. Already the lean form. (One-image cleanup for api/worker is a nice-to-have, not urgent.)
- **The dual-checkout prod/dev model with PR gate** — it *is* the CI, and it works. (Remove the ambiguous `api`/`mqtt` aliases on `caddy_net` — everything in-repo already uses container names; the aliases are pure landmine. `[O-net]`)
- **Shared prod-owned Caddy** — forced by one IP and ports 80/443; correct.
- **The vault storage design** — the strongest subsystem; a rebuild copies it wholesale. (Just make avatars obey its one rule: store a shard, don't derive paths at call time. `[D10]`)
- **The external-app contract workflow** — best-designed subsystem in the repo; keep verbatim and *extend* it to the player protocol (export `player_protocol` schemas to a drift-gated JSON file). `[T5, velocity lens]`

### Never migrate

- **Next.js pages-router → app-router** — pure churn, buys nothing here. If SEO were ever abandoned, a Vite SPA would delete the Node container — but SEO is the plan, so keep pages-router and *use* its SSR (above).

---

## 6. Coverage gaps in this appraisal

The completeness critic (which walked the tree and compared it against every reviewer's output) surfaced areas the 12 reviewers under-covered. These are **not yet reviewed in depth** and are candidate follow-ups:

- **Mobile push / FCM subsystem got zero coverage** — `services/push.py`, `routers/me.py`, the `PushToken` model, the `tasks.py` dispatch. The native app depends on it, and it already has confirmed defects (`register_push_token` has no rate limit → row-flood; push tokens stored plaintext). **Biggest hole.** `[S20, S22]`
- **No holistic data-privacy / GDPR lens** — PII findings are scattered (raw IPs, plaintext tokens, broken erasure) but nobody assessed whether the code can actually honor a data-subject deletion/export request. Given account deletion is confirmed non-functional, the answer is currently *no*. `[A1]`
- **Backup/DR pipeline (`deploy/backup/`) unreviewed** — it's the last line of defense given the data-mutating paths are broken; nobody assessed restore RPO/RTO or the plaintext-secrets-in-backup blast radius.
- **No observability lens** — covered as `[O8]` above; it's the meta-cause of Theme T1.
- **Dependency freshness / build reproducibility** — 30 `>=`-floor deps, no lockfile, no Dependabot, images re-resolve transitive versions on every build. `[O13]`
- **i18n** — entirely absent (hardcoded English, incl. transactional emails). Likely a deliberate solo-operator non-goal, but the GeoIP code special-cases `BR` and the growth plan targets outreach — worth an explicit decision now while string sites are few.

---

## 7. How to use this

- [`BACKLOG.md`](./BACKLOG.md) is the working artifact: every finding, de-duplicated, ranked into P0–P3 tiers with severity, effort, area, and the fix. Chip away top-down; check items off in place.
- **Do the §2 shortlist + alerting `[O8]` as one committed sprint.** It's ~2–3 days of mostly S-effort fixes and it removes all live data-loss and the worst security exposure.
- Then work **Theme by Theme** (§4) rather than finding by finding — consolidating a copy-pasted pattern once retires a whole cluster of backlog rows and stops the next instance from being written.
- Re-run this appraisal after the sprint. If §2 items recur, the remediation loop — not the code — is what needs fixing (§3).

> **Method caveat:** this is static analysis on `develop` plus targeted live-DB and in-container checks. No load testing or runtime profiling was done, so scale/perf claims are reasoned from code and data-volume assumptions. Two raw findings were refuted in verification and dropped. Line numbers are as of `3c94349` and may drift.
