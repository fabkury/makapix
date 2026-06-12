# Progress Log — Vault Resharding

**Current phase: Phase 3 EXECUTED on dev and prod (2026-06-10) — Phase 4
(observe) has begun. The DB points at v2 everywhere; legacy v1 URLs keep
serving from the twin copies.**
**Next action: G3 closes after (a) `status` re-check ~48 h post-flip shows
`v1_url_refs` still 0, and (b) a fielded player is observed fetching a
v2 path (will appear as level-2 traffic on the dashboard as players
receive new payloads). Then: watch the streak counter weekly (criterion:
14 liveness-valid days at 0 non-bot legacy downloads) → Phase 5.**

Newest entries first in the log; checklists mirror PLAN.md §9 gates.
Update this file at the end of every working session on this effort.

## Gate status

| Gate | Description | Dev | Prod |
|---|---|---|---|
| G0 | Groundwork deployed (PR-A refactor/instrumentation + PR-B v2 cutover) | ✅ 2026-06-10 | ✅ 2026-06-10 |
| G1 | All v1 assets copied to v2 locations (`v1_only_files` = 0) | ✅ 2026-06-10 | ✅ 2026-06-10 |
| G2 | Duplication verified (sha256, reconciliation, orphans recorded) | ✅ 2026-06-10 | ✅ 2026-06-10 ¹ |
| G3 | DB references flipped; `v1_url_refs` = 0 stable; fielded-player v2 fetch confirmed | ✅ 2026-06-10 ² | ◐ flipped 2026-06-10 ² |
| G4 | ≥14 consecutive liveness-valid days of 0 non-bot legacy downloads (evidence archived) | — | ☐ |
| G5 | Legacy copies deleted; 7 days healthy | ☐ | ☐ |
| G6 | Code cleanup merged; docs closed out | ☐ | ☐ |

¹ G2 prod carries one documented exception: a dangling reference (see
2026-06-10 Phase 1–2 log entry), not a copy/verify defect.
² G3: flip executed, idempotent, `v1_url_refs` = 0, all spot checks pass.
Remaining before fully closing: 48 h `status` re-check and observing a
fielded player fetch a v2 path (no player was due a fetch during the flip
window; their caches serve repeats).

## Log

### 2026-06-10 — Planning session (Claude + fab)

- Studied the codebase and both databases; recorded scale numbers in PLAN.md §1.
- Owner decisions D1–D5 captured; architectural decisions D6–D15 recorded
  (see DECISIONS.md).
- Wrote PLAN.md, DECISIONS.md, README.md (this folder).
- Plan critiqued by three independent review agents (data-safety,
  code-vs-plan reality, proportionality). Key accepted findings, all folded
  into PLAN.md/DECISIONS.md:
  - **Blocker:** the v1-hash fallback in the vault path builders is live code
    (`routers/artwork.py` download endpoints call it shard-less) — naive
    Phase 0 cutover would 404 all existing posts → D14 two-PR sequencing,
    `storage_shard` made a required parameter.
  - **Blocker:** blind `unflip` would break v2-born assets → flip manifest;
    `unflip` is manifest-driven with per-row v1-file checks.
  - `/api/vault/` main-domain traffic never reaches the vault-subdomain log
    (form exists in prod: 13 posts + 686 notification rows) → second log
    feed + matcher prefix; Phase 5 same-day grep of both logs.
  - Dead stats pipeline reads as a clean 14-day streak → zero-row daily
    upserts + liveness rule (day counts only with 2-level traffic > 0).
  - Per-file dual-write missed brand-new sibling files (format regen,
    upscale) → asset-level twin rule (D10).
  - Single stats table with nullable post_id replaces the two-store design;
    uniform D8 semantics so 304-only revalidators appear in the straggler
    table (D13).
  - Orphan sweep / prune could touch live `bdr/` zips and `lost+found` →
    subtree allowlist (D15, I6).
  - `blog_posts.body` markdown embeds vault URLs → added to D11 scope.
  - Copy candidate set extended to all D11 columns (notification snapshots
    can reference avatar files absent from `users.avatar_url`).
  - Flip-broken firmware would be *silent* (the `show_artwork` payload has
    no `art_url`; players build URLs from the shard) → G3 requires observing
    a real fielded player fetch a v2 artwork; `misses` (404) counter added.
  - `players` table has no IP column → Phase 4 forensics recipe corrected
    (`view_events.viewer_ip_hash`, 7-day window; MQTT broker logs).
  - JSON post-create route mints NULL-shard artwork rows → fixed in PR-A.
  - pg_dump before flip; dev rehearsal must execute flip→unflip→flip.
  - Tool gets a pytest suite, `--limit/--key` smoke flags, gate-mapped
    `status --json` fields, mounted report dir (`api/reshard-reports/`).
  - R11 (web string-manipulating shard paths) **resolved**: web does no
    shard manipulation (`ensureCompatibleArtUrl` swaps extensions only;
    upscaled served via `/api/d/{sqid}/upscaled`).
  - Player-protocol docs show wrong/3-level shard examples
    (`docs/mqtt-protocol/02-player-protocol.md` has slash-less `"7c9e66"`) —
    fix in Phase 0; document `storage_shard` as opaque variable-depth.
- **No implementation or migration work has started.**

### 2026-06-10 — Firmware resolved; Phase 0 PR-A implemented on dev (Claude + fab)

- Owner confirmed: **no fielded firmware validates or parses `storage_shard`**
  — all use the server-provided value verbatim. D2 resolved, R8 downgraded.
- **PR-A implemented** (working tree on `develop`, not yet committed):
  - `app/vault.py`: `storage_shard` now a **required** parameter of all
    path/URL builders (silent v1-hash fallback removed); explicit
    `compute_storage_shard_v1`/`_v2` + `derive_twin_shard`; atomic
    temp+fsync+rename writes (`*.reshard-tmp`); dual write-through and
    dual-delete in the primitives (`save_artwork_to_vault`,
    `save_upscaled_artwork`, `delete_artwork_from_vault`,
    `delete_all_artwork_formats`). `compute_storage_shard` still returns v1
    (PR-B flips it).
  - Fixed the shard-less call sites: `routers/artwork.py`
    (`get_post_file_path_from_storage_key` + 2 callers) and the JSON create
    route (`routers/posts.py` now sets `storage_shard`). Caller audit:
    every other call site already passed the stored shard.
  - `avatar_vault.py`/`blog_vault.py`: dual-location saves; deletes remove
    both scheme-derived paths; avatar delete parses both URL depths.
  - `tasks.py`: format-regeneration + upscale writes routed through the
    vault primitives (no more direct `write_bytes`).
  - Schema: `vault_sharding_stats_daily` (UNIQUE NULLS NOT DISTINCT;
    aggregate rows post_id NULL + per-post straggler rows), Alembic
    `a71f178d6e9b`, applied on dev. Also fixed `alembic/env.py` to import
    models (autogenerate previously saw empty metadata → mass drop_table).
  - `services/download_stats.py` rewritten: both-depth/all-class regex,
    query-string stripping, GET/HEAD × 200/206/304 + 404 `misses` (D8),
    **two log feeds** (vault subdomain + main-domain `/api/vault` from the
    shared `access.log`, filtered by `request.host` — no Caddy changes
    needed, verified entries exist for both env hosts), date-aware log-file
    selection, zero-row aggregate upserts, `compute_legacy_streak` with the
    liveness rule, telemetry (`legacy_hits_non_bot`, `streak_days`).
    Existing `download_stats_daily` semantics untouched.
  - `GET /admin/vault-sharding-stats` (moderator, Redis-cached) + schemas;
    `VaultShardingPanel` added to the mod dashboard Downloads tab (streak
    card with data-gap/miss warnings, paired-bar trend, class totals,
    straggler table).
  - `scripts/reshard_vault.py`: `status` (gate-mapped JSON fields), `copy`,
    `verify` (manifest to gitignored `api/reshard-reports/`), `clean-tmp`;
    I6 allowlist verified against real vault (`bdr/`, `lost+found` fenced).
  - Player docs: fixed 3 wrong slash-less `storage_shard` examples in
    `docs/mqtt-protocol/02-player-protocol.md`; documented the field as
    opaque/variable-depth in 4 docs.
  - Tests: 250 passing (82 new: shard derivation incl. worked example,
    dual write/delete, both-depth avatar delete, stats parsing/statuses/
    host-filter/query-strings, streak liveness rules, copy idempotency,
    stale-twin re-copy, sha256 corruption detection, allowlist exclusion,
    admin endpoint).
- **Live smoke tests on dev:** rollup wrote 6 aggregate zero-rows for
  2026-06-09; `status` reconciled 2,696 posts / 5,550 refs / 10,782 v1
  files (5,233 orphans = known dev/prod `post_files` divergence, R16);
  single-key `copy`+`verify` round-trip passed (`6c/0a/5d` → `2c/0a`,
  masking verified); **2-level URL served by Caddy with zero config
  changes** (HTTP 200 with immutable cache headers).
- `make rebuild` run on dev to load the new code into running services.

### 2026-06-10 — PR-A committed; PR-B implemented, verified, committed (Claude + fab)

- PR-A committed as two commits on `develop`: `d3153c0` (plan docs) and
  `c732d25` (implementation).
- **PR-B (v2 cutover):** `compute_storage_shard` → v2; avatar/blog URL
  builders follow automatically. D10 refined with the v2-born exemption:
  `vault.should_mirror_to_twin` — v1-canonical assets always maintain
  their v2 twin; v2-canonical assets mirror back only with legacy
  presence; **v2-born assets stay single-copy** (legacy tree stops
  growing at cutover). Tests updated/added (v2-born no-twin,
  legacy-presence mirror, avatar equivalents).
- Full suite green (250 tests) under the cutover; api+worker restarted on
  dev (code is bind-mounted; web unchanged by PR-B).
- **Live dev verification:** new-asset save through the primitive landed
  at a 5-char v2 shard (`2c/20`), v2 file only, no v1 twin, dual-delete
  cleanup OK; existing v1 post download endpoint returned 200
  (`/api/d/zVQ`, 35 KB); MQTT subscribers healthy after restart.

### 2026-06-10 — G0 closed: dev e2e upload + prod deploy + verifications (Claude + fab)

- **Dev e2e upload** (post 3425, hidden, deleted after): landed at v2 shard
  `2b/1a` (5 chars in DB); worker generated all 4 format variants +
  upscaled at v2 only — **no v1 twin**; `art_url` served 200 via Caddy;
  `/api/d/MU3S` 200 (authed; anonymous 404 was the hidden_by_user
  visibility check working). Moderator permanent-delete removed every copy
  (dual-delete verified through the API).
- **Pushed develop; PR #190 merged to main; prod deployed** via
  `make deploy` (migration `a71f178d6e9b` auto-applied). Prod MQTT
  subscribers needed the known post-broker-restart api restart; settled.
- **Prod hotfix (PR #191):** rollup returned all zeros on prod — Caddy
  tags per-site log outputs `http.log.access.log0/.log1`, and the
  exact-match logger filter dropped every vault-subdomain entry (dev's
  genuinely-quiet log masked it). Prefix-match fix + regression test;
  merged, pulled on prod, api+worker restarted.
- **Prod verifications, all green:**
  - existing v1 post download 200; legacy `/api/vault/...` form serves 200
    (live specimen of the second-feed population);
  - v2-born primitive smoke: shard `06/1c`, v2-only, dual-delete clean;
  - `status` baseline: **2,871 posts / 11,324 referenced files / 11,329 on
    disk / 0 NULL shards / 0 derivation mismatches / 0 anomalous URL refs /
    only 6 orphans** (dev's 5,233 were dev-divergence noise, R16);
    v1 URL refs: art_url 2,871, avatars 15, notifications 322+461, blog 1+1;
  - rollup for 2026-06-09: 2,491 artworks, 3,131 human downloads, 3,144
    legacy non-bot hits (incl. avatar 13), 0 misses, streak 0 — correct,
    legacy traffic is alive until the Phase 3 flip;
  - aggregate zero-rows present for all 6 class×level combos;
  - `/admin/vault-sharding-stats` 401 anonymous.

### 2026-06-10 — Phases 1–2 executed on dev and prod (Claude + fab)

Pre-flight: 8.3–8.4 GB free on both vault mounts (~1 GB needed). Baselines
archived in each env's `api/reshard-reports/phase1-baseline-{dev,prod}.json`.

- **Dev copy:** `--limit 10` smoke → full run: 5,536 copied (+13 from the
  earlier smoke, +1 `optional_absent` = an upscaled that was never
  generated), 0 missing sources; converge re-run: 5,549 already_twinned,
  0 work. Post-state: twinned=5,549, v1-only=5,233 = exactly the orphan
  set (dev/prod divergence residue, R16).
- **Dev verify:** 5,549/5,549 sha256 matches, 0 failures
  (`phase2-verify-dev.json`).
- **Prod copy:** `--limit 10` smoke → full run: 11,313 copied (+10 smoke),
  converge re-run clean. **1 missing source**: avatar
  `ef0124df-…gif` is referenced only by old
  `social_notifications.actor_avatar_url` snapshots and exists at NEITHER
  location — a pre-existing dangling reference (those thumbnails already
  404 today). Phase 3's flip will skip+log it per D11's target-exists
  check; no action needed.
- **Prod verify:** 11,323/11,324 verified, the single failure is the
  documented dangling reference (`phase2-verify-prod.json`).
- **Prod orphans (6) identified and explained:** 2 artwork GIFs whose
  posts were permanently deleted (no DB rows) + 4 avatar files replaced
  before deletes were robust (no `users.avatar_url` references). True
  residue; Phase 5 sweeps them after review.
- Spot-check: freshly copied prod v2 file served 200 via
  vault.makapix.club.
- **State now: every servable v1 file has a sha256-verified v2 twin in
  both environments. Both URL forms are live. The DB still references v1
  everywhere (flip pending).**

### 2026-06-10 — flip/unflip tool modes implemented (Claude + fab)

- `reshard_vault.py` gains `flip` and `unflip` per PLAN §6 (+13 tests
  against the real test DB):
  - flip: JSONL manifest written+fsynced BEFORE each DB write; per-post D9
    re-verify globs the actual v1 sibling set and repairs missing/stale v2
    twins; posts whose art_url can't be safely rewritten are skipped whole
    (never half-flipped); pattern-scoped rewrites of all D11 columns incl.
    blog body, gated on the v2 target file existing; idempotent.
  - `--null-dangling` (opt-in): NULLs nullable scalar URL columns whose
    file exists at NEITHER location (the documented prod dangling avatar
    ref) — without it, `v1_url_refs` can never reach 0 at G3.
  - unflip: manifest-driven (never a blind rewrite), reverse order, skips
    rows changed since flip, refuses to restore a row whose v1 files are
    gone.
- Dev dry-run sanity: 2,696 posts + 8/36/58/1/1 column rewrites — matches
  `status` predictions exactly. `would_repair_twins=5224` is dev-only:
  D9 re-verify covers each post's full on-disk sibling set, which on dev
  exceeds its sparse `post_files` (the same divergence behind dev's orphan
  count); expect ~0 on prod.

### 2026-06-10 — Phase 3 executed on dev and prod (Claude + fab)

- PR #192 merged; prod pulled (script-only change, no restarts needed).
- **pg_dumps** (pre-flip, both DBs):
  `/home/fab/backups/vault-resharding/pre-flip-{dev,prod}-2026-06-10.sql.gz`
  (sha256 `5d5c7936…` dev, `25418df4…` prod).
- **Dev rehearsal** (manifest `flip-manifest-dev-rehearsal.jsonl`):
  `flip --limit 10` → spot checks 200 → full flip (2,696 posts; 5,203
  twins repaired = the post_files-sparsity variants; 8/36/58/1/1 column
  rewrites) → idempotent re-run clean → `v1_url_refs` all 0 → **unflip
  restored exactly 5,496 rows** and counts returned to pre-flip values →
  v1 serving re-verified → **final flip** (manifest
  `flip-manifest-dev-final.jsonl`), zero repairs needed. App checks:
  API payload art_url v2, download endpoint 200, avatar 200.
- **Prod flip** (manifest `flip-manifest-prod.jsonl`): smoke `--limit 10`
  verified the 54 `skipped_missing_v2_target` were all rows referencing
  the single known dangling avatar (count matched exactly) → full flip
  with `--null-dangling`: **2,871 posts flipped, 15+729+2 URL columns
  rewritten, 54 dangling notification thumbnails NULLed** (recorded in
  manifest), zero twin repairs (post_files complete on prod) → idempotent
  re-run clean → `v1_url_refs` = 0 across all columns, 0 shard
  mismatches, disk untouched (6 orphans remain the only v1-only files).
- **Prod app checks:** flipped post payload serves v2 art_url (fetch
  200), download endpoint 200, flipped avatar 200, 0 api errors.
- **Player observation:** no fielded player was due a vault fetch during
  the flip window (their on-device caches serve repeats; v2 fetches begin
  as new payloads arrive). Level-2 traffic on the dashboard is the
  confirmation signal. Recent v1 fetches (one human browser on cached
  pages) are harmless — both URL forms serve throughout Phase 4.
- **Phase 4 (observe) begins now.** The retirement streak can start
  counting once daily non-bot legacy downloads reach 0.

### 2026-06-10 — repo docs aligned to the 2-level structure (Claude + fab)

- Structural descriptions updated: `CLAUDE.md` (Vault Storage System),
  `docs/architecture.md`, `deploy/stack/README.stack.md`,
  `_docs/ARCHITECTURE.md`, `_docs/dual-environment/01-current-architecture.md`.
- Example payloads across `docs/player/*`, `docs/http-api/*`,
  `docs/mqtt-protocol/*`, `docs/mqtt-api/*`, `_docs/MQTT_PLAYER_API.md`,
  `_docs/PHYSICAL_PLAYER.md` now show 2-level shards (generic examples
  `21/32`; the real protocol UUID's true shard `23/16`; the worked-example
  UUID's true shard `24/07`). `_docs/legacy/` left as historical record.
- The opacity contract ("use `storage_shard` verbatim, depth may change")
  stays in all player-facing docs.

### 2026-06-10 — prod `VAULT_PUBLIC_BASE_URL` finally in effect (Claude + fab)

- Found while investigating player p3a downloads: prod had the variable
  in `deploy/stack/.env`, but the Makefile runs compose with
  `--env-file .env.prod` — so the running api/worker had it **empty**
  since the feature shipped, and every prod upload stored a relative
  `/api/vault/...` in `art_url` (served through FastAPI StaticFiles, no
  immutable cache headers). Dev was unaffected (`.env` → `.env.dev`
  symlink).
- Fix: added `VAULT_PUBLIC_BASE_URL=https://vault.makapix.club` to
  `.env.prod`, recreated api + worker (`up -d --no-deps`). Verified:
  env present in both containers, API healthy, `get_artwork_url` emits
  the vault-subdomain URL, MQTT subscriber processing player status.
- Stats impact: new-upload downloads will shift from the main-domain
  `/api/vault` feed (pass 2) to the vault-subdomain feed — expect the
  main-domain share of sharding stats to decay from today.
- **URL-prefix backfill (same day):** rewrote every stored relative
  `/api/vault/...` value to the absolute vault-subdomain form
  (`'^/api/vault' → 'https://vault[-dev].makapix.club'` — prefix only,
  shard paths untouched; pattern-scoped per D11, external URLs can't
  match). Prod: 13 `posts.art_url` + 2 `users.avatar_url` +
  381 `sn.content_art_url` + 251 `sn.actor_avatar_url` + 1
  `blog_posts.body` = 648 rows. Dev: 58 + 36 + 1 = 95 rows (posts/users
  already clean — the var has been live on dev since May 31). Old/new
  values recorded in `api/reshard-reports/backfill-url-prefix-{prod,dev}-
  20260610.jsonl` (same style as flip manifests). Verified: 0 relative
  refs remain in either env; rewritten artwork/avatar/blog-image URLs
  fetch 200 from both vault subdomains. Note 2,858 prod posts already
  stored absolute vault URLs, so consumers (web + firmware) demonstrably
  handle the absolute form.
- Caveat for the dev-DB-clones-prod flow: prod rows carry
  `https://vault.makapix.club/...`, so a fresh clone points dev payloads
  at the prod vault (pre-existing for posts; now also true for the
  backfilled columns). Harmless for browsing; rewrite the host if dev
  must be self-contained.

Open items carried forward:
- ~48 h: re-run `status` on both envs (`v1_url_refs` must still be 0 —
  in-flight sessions/notification snapshots can reinstate v1 values; if
  any appear, re-run `flip`).
- Confirm level-2 player traffic on the dashboard (closes G3 prod).
- Owner: eyeball the dashboard panel (Downloads tab, both envs).
- Weekly: check the streak counter; investigate any `misses`.

### 2026-06-12 — D16: serving-layer legacy-URL alias implemented on develop (Claude + fab)

- **Decision D16** (see DECISIONS.md): legacy 3-level URLs stay valid
  permanently at the serving layer — miss-only remap to the 2-level
  location, served directly (200, no redirect). Pure string transform
  (leading hex char of each of the first two components `& 0x3`); no
  hashing, no DB. D4/G4 unchanged: the alias is a safety net behind the
  retirement gate, not a substitute for it.
- **Caddy** (`deploy/stack/caddy/Caddyfile.global`): new
  `legacy_shard_remap` snippet (path_regexp + two 16-entry char maps +
  `rewrite`, gated on `not file`), imported by both vault site blocks.
  `caddy validate` clean on caddy 2.7.6. Functionally verified in a
  scratch caddy:2.7.6 container: legacy→v2 200, twin-on-disk served
  as-is, avatar prefix, 404 when missing everywhere, non-vault paths
  untouched — and the access log records the **original** 3-level URI,
  so the D8/D13 stats pipeline and G4 keep measuring legacy traffic.
- **API** (`api/app/vault_serving.py`): `/api/vault/` mount now uses
  `LegacyShardFallbackStaticFiles` (StaticFiles subclass overriding
  `lookup_path`; same miss-only semantics, artwork + avatar shapes).
  New `api/tests/test_vault_serving.py` (transform cross-checked against
  `compute_storage_shard_v1/v2`, worked example, serving semantics);
  full API suite green (275 passed). Live-verified on dev after API
  restart: legacy-shaped path with no file at that location serves the
  v2 bytes (200); true v1 twin path and v2 path unchanged; 404 preserved.
- **Activation status:** dev API live as of today. The Caddy change is
  NOT live anywhere yet — the shared caddy container (owned by
  makapix-prod) mounts `/opt/makapix/deploy/stack/caddy/Caddyfile.global`,
  so both vault subdomains pick it up only after merge to `main` + prod
  pull + `docker restart caddy` (caddy-docker-proxy does not watch the
  base file). Post-activation check: curl a legacy-shaped URL that has
  no legacy file (e.g. a v2-born asset's v1-derived path) on each vault
  subdomain → 200, and confirm the log line shows the 3-level URI.
- Note for Phase 5 planning: dev currently has no v2-born posts (no
  uploads since the 2026-06-10 cutover), so every dev asset still has a
  twin; the live remap test used a synthetic legacy-shaped path.

### 2026-06-12 (later) — D16 deployed to prod; live on all serving paths (Claude + fab)

- PR #195 (develop → main, merge `1e41b47`) deployed via `make deploy`;
  the whole prod stack was recreated, so caddy re-read the new
  Caddyfile.global on start (no separate restart needed).
- Live verification, both envs, synthetic legacy-shaped paths with no
  file at the requested location (prod `42/4a/ff/…` → `02/0a/…`, dev
  `51/44/aa/…` → `11/04/…`): HTTP and HTTPS both 200 with bytes
  identical to the v2 file; misses still 404; prod `/api/vault/` mount
  fallback 200.
- Confirmed in the live prod vault-access.log: the remapped request is
  logged with the ORIGINAL 3-level URI (status 200) — G4 measurement
  intact.
- MQTT subscribers reconnected cleanly after the stack restart (api
  started after the broker; no publisher-left-dead condition).
- D16 is now fully active: legacy 3-level URLs remain valid on
  vault.makapix.club, vault-dev.makapix.club, and /api/vault/ in both
  environments, independent of the twin copies' existence.
