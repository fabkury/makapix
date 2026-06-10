# Progress Log — Vault Resharding

**Current phase: Phase 0 complete on dev (PR-A + PR-B committed and live).**
**Next action: owner eyeballs the dashboard at development.makapix.club
(mod dashboard → Downloads tab) and ideally does one real test upload;
then push `develop`, PR → `main`, deploy to prod (`cd /opt/makapix &&
make deploy`), apply the same dev verifications on prod → that closes G0.
After G0: Phase 1 (`reshard_vault.py copy`), dev first.**

Newest entries first in the log; checklists mirror PLAN.md §9 gates.
Update this file at the end of every working session on this effort.

## Gate status

| Gate | Description | Dev | Prod |
|---|---|---|---|
| G0 | Groundwork deployed (PR-A refactor/instrumentation + PR-B v2 cutover) | ☐ | ☐ |
| G1 | All v1 assets copied to v2 locations (`v1_only_files` = 0) | ☐ | ☐ |
| G2 | Duplication verified (sha256, reconciliation, orphans recorded) | ☐ | ☐ |
| G3 | DB references flipped; `v1_url_refs` = 0 stable; fielded-player v2 fetch confirmed | ☐ | ☐ |
| G4 | ≥14 consecutive liveness-valid days of 0 non-bot legacy downloads (evidence archived) | — | ☐ |
| G5 | Legacy copies deleted; 7 days healthy | ☐ | ☐ |
| G6 | Code cleanup merged; docs closed out | ☐ | ☐ |

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

Open items carried forward:
- G0 (gate): needs prod deploy + same verifications on prod; plus one
  human-eye check of the dashboard panel and a real test upload on dev.
- First nightly rollup under the new code runs tonight (01:00 ET window);
  check the Downloads tab tomorrow for the first liveness-valid day.
