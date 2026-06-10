# Vault Resharding Migration Plan

3-level sharding → 2-level sharding, non-destructive, dual-location window,
data-driven retirement. See `DECISIONS.md` for the decision log and
`PROGRESS.md` for execution state. Phase numbering matches the owner's
original 5-step outline, with a Phase 0 (code groundwork) in front and a
Phase 6 (cleanup) behind.

> This plan was amended on 2026-06-10 after review by three independent
> critique agents (data-safety, code-reality, proportionality). File:line
> references are hints captured at planning time; symbol names are
> authoritative.

---

## 1. Background and motivation

Current layout (`api/app/vault.py:compute_storage_shard`):

```
{VAULT_LOCATION}/{h[0:2]}/{h[2:4]}/{h[4:6]}/{storage_key}.{ext}
where h = sha256(str(storage_key)).hexdigest()
```

That is 256³ = 16,777,216 possible shards. Production reality (2026-06-10):

| Metric | Production | Dev |
|---|---|---|
| posts (all `kind=artwork`) | 2,871 | 2,696 |
| `post_files` rows (format variants) | 8,436 | 2,845 |
| files on disk (incl. `_upscaled`, avatars, blog) | 11,329 | 10,782 |
| directories on disk | 6,195 | 5,772 |
| vault size | ~1.0 GB | ~0.9 GB |
| `posts.storage_shard IS NULL` | 0 | 0 |
| `posts.art_url LIKE '/api/vault/%'` | 13 | — |
| `social_notifications` URLs `LIKE '/api/vault/%'` | 381 + 305 | — |
| users with avatars (vault-hosted; rest are GitHub URLs) | 15 of 43 | — |
| blog posts | 1 | — |
| registered players | 257 | 249 |

More directories than artworks. Target: 64 × 64 = **4,096 shards** (≤ 4,160
directories total), ~3 files/shard today, ~244 files/shard at 1M artworks —
healthy at any plausible scale.

## 2. Target design (v2 sharding)

```
{VAULT_LOCATION}/{a}/{b}/{storage_key}.{ext}
where d = sha256(str(storage_key)).digest()
      a = f"{d[0] & 0x3F:02x}"   # "00".."3f"
      b = f"{d[1] & 0x3F:02x}"   # "00".."3f"
```

- Hash input unchanged: lowercase hyphenated UUID string.
- Worked example: key `a1b2c3d4-e5f6-7890-abcd-ef1234567890` → hexdigest
  `a447ee…` → v1 `a4/47/ee`, v2 `24/07`. v2 is not a substring of v1 in
  general.
- **Coexistence:** v1 and v2 trees share the same root. v2 dirs (`00`–`3f`)
  overlap v1 first/second-level dir names; disambiguation is by **path
  depth**, never by name. Inside `{a}/{b}/`, v1 entries are 2-hex-char
  *subdirectories*, v2 entries are UUID-named *files* — no collisions.
  Consequence: all delete/prune/orphan tooling must be depth-aware (§6).
- `posts.storage_shard` (String(8)) stays the opaque source of truth:
  `"aa/bb/cc"` (8 chars, v1) or `"aa/bb"` (5 chars, v2). All consumers
  (path builders, URL builders, player payloads at
  `services/player_rpc.py:105`, `routers/player.py:1360` and `:1508`,
  BDR/format-regen/upscale tasks) treat it opaquely — verified, including
  the player protocol schema (`player_protocol/schemas.py:302`, plain `str`).
- Sub-vaults keep their prefixes: `avatar/{a}/{b}/…`, `blog_image/{a}/{b}/…`.
- Serving needs **zero config changes**: Caddy vault vhosts are bare
  `file_server` blocks (`deploy/stack/caddy/Caddyfile.global:29-49`) and the
  FastAPI mount is plain StaticFiles (`api/app/main.py:277-287`); the
  security middleware is path-blind.

## 3. Asset classes and their file sets

| Class | Files per item | DB references | Count (prod) |
|---|---|---|---|
| artwork | one file per `post_files` row (`{key}.{png\|gif\|webp\|bmp}`) + optional `{key}_upscaled.webp` | `posts.storage_shard` (canonical), `posts.art_url` (denormalized), `social_notifications.content_art_url` (snapshot) | 2,871 posts / ~11k files |
| avatar | single `{avatar_id}.{png\|gif\|webp\|jpg}` | `users.avatar_url` (the URL *is* the reference) + `social_notifications.actor_avatar_url` (snapshots, incl. UUIDs no longer in `users.avatar_url`) | 15 vault-hosted |
| blog_image | `{image_id}.{ext}` | `blog_posts.image_urls[]` **and embedded in `blog_posts.body` markdown** | 1 |

Files on disk with no DB reference are **orphans**: reported by tooling,
excluded from copy/flip, reviewed in Phase 5. The vault root also contains
**out-of-scope live data** that tooling must never touch: `bdr/` (batch
download zips, referenced by `batch_download_requests.file_path`, served via
`routers/pmd.py`) and `lost+found`. See §6 "universe".

## 4. Code touchpoints inventory

| Location | Role | Change |
|---|---|---|
| `api/app/vault.py:compute_storage_shard` | v1 shard at post creation | becomes v2; add explicit `compute_storage_shard_v1` for legacy-path derivation by tooling/dual helpers |
| `api/app/vault.py` path/URL builders (`get_artwork_folder_path`, `get_artwork_file_path`, `get_artwork_url`, `get_upscaled_file_path`) | accept optional `storage_shard` with silent v1-hash fallback | **make `storage_shard` required** — the fallback is live code, not dead: see next row. Interpreter then forces an audit of every caller |
| `api/app/routers/artwork.py:get_post_file_path_from_storage_key` (~:32–52, used by download endpoints ~:255, ~:370) | calls `get_artwork_file_path(storage_key, ext)` **without** the stored shard → depends on the v1 fallback | pass `post.storage_shard`. **This must ship (PR-A) before the v2 cutover (PR-B)** or every existing post's download 404s at Phase 0 (critique finding) |
| `api/app/routers/posts.py:~410–504` (JSON create route) | creates `kind="artwork"` posts with client-supplied `art_url` and **no `storage_shard`** | set a shard at creation here too; "0 NULL rows" is a data snapshot, not a code invariant. (`playlists.py:167` sets `storage_shard=None` by design — tooling scopes to `kind='artwork'` and tolerates NULL/no-file rows) |
| `api/app/vault.py` write/delete primitives | single-location writes, in-place (non-atomic) | dual write-through + dual-delete per D10 (asset-level twin rule), temp-file + `fsync` + atomic rename discipline. Dual logic lives **only** in the vault primitives (`vault.py`, `avatar_vault.py`, `blog_vault.py`), never at call sites |
| `api/app/avatar_vault.py` (`get_avatar_folder_path`, `get_avatar_url`, `try_delete_avatar_by_public_url`) | always computes 3-level inline; delete helper requires ≥6 path parts and deletes exactly one path | v2 for new saves; delete helper derives the UUID then unlinks **both** candidate paths (privacy: avatar replacement must not leave the twin serving the old image) |
| `api/app/blog_vault.py:delete_blog_image` | recomputes path from hash (no URL parsing; currently called by no router — feature is locked) | derive and delete both depths; correct the earlier inventory claim that it parses URLs |
| `api/app/routers/posts.py:674` / `:1584–1652` | shard at upload-creation; pixel-edit/format-change re-save + delete | picks up v2 via `compute_storage_shard`; dual behavior comes from the primitives |
| `api/app/tasks.py` format-regeneration and upscale tasks (~:2722–2874) | write **new** sibling files at the canonical shard | covered by the asset-level dual-write rule in D10 — a brand-new file must be mirrored even though no twin pre-exists |
| `api/app/services/download_stats.py` | 3-level-only, artwork-only, GET+200-only regex over the vault-subdomain log; `_select_log_files` only sees files with mtime < 48 h | new parsing per §7: both depths, all classes, D8 statuses, query-string stripping, `/api/vault/` main-domain feed, 404 ("miss") counting, date-aware log-file selection |
| `api/app/tasks.py:rollup_download_stats` (beat, 01:00–05:00 ET window) | nightly rollup | extended for §7; telemetry dict gains legacy-hit count + current streak so the signal lands in worker logs |
| `api/app/routers/admin.py:774–853` | `/admin/download-stats` (moderator, ~300 s Redis cache) | sibling endpoint `/admin/vault-sharding-stats` (§8) |
| `web/src/components/DownloadStatsPanel.tsx`, `web/src/pages/mod-dashboard.tsx` | Downloads tab | trend split + streak + straggler table + miss counter (§8) |
| `api/scripts/backfill_vault_urls.py` | precedent for idempotent batch URL rewriting | pattern source for the new tool |
| `api/tests/test_vault.py` | hardcodes 3-level shapes | v2 tests + coexistence tests |
| `docs/player/*`, `docs/http-api/player-rpc.md`, `docs/mqtt-protocol/02-player-protocol.md` | protocol docs show 3-level examples; `02-player-protocol.md` shows a **wrong slash-less** `"storage_shard": "7c9e66"` (:143, :287, :552) contradicting its own :563 | fix examples; document `storage_shard` as an opaque relative path of variable depth that clients must not parse or validate |

**Resolved audit item (was R11):** web does **not** string-manipulate shard
paths — upscaled images come from `/api/d/{sqid}/upscaled` and
`ensureCompatibleArtUrl` only swaps file extensions. No web change needed.

**Resolved audit item (firmware):** the `show_artwork` command payload
(`routers/player.py:1356`, `:1508`) carries `storage_shard` and no `art_url`
— firmware builds URLs from the shard string. Owner confirmed (2026-06-10)
that **no fielded firmware validates or parses the shard; all use it
verbatim**, so 5-char v2 shards flow through cleanly (D2, R8).

## 5. Invariants (hold through the entire effort)

- **I1** — No URL that was valid before the migration breaks before Phase 5;
  Phase 5 only after the D4 criterion.
- **I2** — Stored values (`posts.storage_shard`, stored URLs) are the single
  source of truth for an asset's canonical location; code never guesses
  depth except in explicit v1/v2 derivation functions used by tooling and
  dual helpers.
- **I3** — All migration tooling is idempotent and re-runnable; destructive
  modes re-verify preconditions per item immediately before acting and
  support `--dry-run`.
- **I4** — Every phase is rehearsed on dev (`/opt/makapix-dev`, dev vault,
  development.makapix.club) before running in prod.
- **I5** — `PROGRESS.md` is updated whenever any phase work happens.
- **I6** — Destructive tooling operates only inside an explicit subtree
  allowlist (§6); anything unrecognized is reported, never touched.

## 6. The migration tool: `api/scripts/reshard_vault.py`

One script, subcommand per phase, modeled on `backfill_vault_urls.py`
(runs inside the api container: `cd deploy/stack && docker compose exec api
python scripts/reshard_vault.py <cmd> …`). Common flags:
`--class artwork|avatar|blog_image` (default all), `--dry-run`,
`--limit N` and `--key <uuid>` (smoke-scale runs), `--json`.

**Universe (I6).** The tool recognizes exactly: 2-hex-char shard directories
at the vault root, `avatar/`, and `blog_image/`. `bdr/`, `lost+found`, and
any other entry are out of scope: listed in `status` output as
`out_of_scope_paths`, never copied, never deleted, never pruned.

**Temp files.** All copies write `<name>.reshard-tmp` in the destination
directory, `fsync`, then atomically rename. `status` ignores and reports
stray temp files; `clean-tmp` removes them.

| Subcommand | Phase | Behavior |
|---|---|---|
| `status` | any | Reconciliation report with named, gate-mapped fields (see below). |
| `copy` | 1 | Candidate set = union of: posts (`kind='artwork'`) × `post_files` formats + existing `_upscaled` files, **plus every vault-pattern v1 URL found in all six D11 columns and `blog_posts.body`** (catches still-served files whose only reference is a notification snapshot). Per post: assert `storage_shard == compute_storage_shard_v1(storage_key)`, fail loudly on mismatch. Copy v1 → v2 (temp+rename); skip if twin matches sha256; re-copy if mismatched. Never touches v1 files. |
| `verify` | 2 | For every candidate (all formats + `_upscaled`): v2 file exists, `sha256(v1) == sha256(v2)`, sizes match. Writes a JSON manifest to `--report` (default `api/reshard-reports/`, bind-mounted and gitignored — reports must survive the container). Nonzero exit on any failure. |
| `flip` | 3 | Batched (default 500/txn). Per post: re-verify the **full sibling set** (copy *missing* twins, repair stale ones — D9), then set `storage_shard` → v2 and rewrite `art_url`. Rewrites `users.avatar_url`, `blog_posts.image_urls[]`, `blog_posts.body`, `social_notifications.actor_avatar_url` / `content_art_url` — pattern-scoped per D11, and **only after confirming the v2 target file exists** (else skip + log). Before any DB write, appends to a flip manifest file (`api/reshard-reports/flip-manifest-*.jsonl`: table, row id, column, old value, new value). Logs every skipped URL. Re-run until clean (in-flight sessions can reinstate v1 values; see G3). |
| `unflip` | 3 rollback | Consumes the flip manifest — only touches rows it flipped (a blind v2→v1 rewrite would corrupt v2-born assets that have no v1 files). Per row, additionally verifies the v1 file exists before rewriting. Refuses to run if Phase 5 deletion has started. |
| `delete-legacy` | 5 | Requires `--i-have-verified-the-retirement-criterion`. Per file: confirm v2 twin exists and sha256 matches, then delete the v1 file. Allowlist-scoped (I6). Orphans deleted only with explicit `--include-orphans` after review. Then `prune-empty-dirs`. |
| `prune-empty-dirs` | 5 | Removes empty directories bottom-up, depth-aware, allowlist-scoped. |
| `clean-tmp` | any | Removes `*.reshard-tmp` strays. |

**`status --json` gate-mapped fields** (each PLAN gate names the fields that
must be zero): `v1_only_files`, `twinned`, `stale_twins`, `v2_only`,
`null_shard_rows`, `shard_derivation_mismatches`, `orphans`,
`out_of_scope_paths`, `tmp_files`, and `v1_url_refs` broken down per D11
column (including `blog_posts.body`).

Avatar/blog items are identified by parsing stored URLs (UUID + ext + v1
shard components); the v2 path derives from the UUID. Iteration is always
**from the DB**; disk walks exist only for orphan/out-of-scope detection.

**Test suite (Phase 0, pytest, tmpdir vault + test DB):** `copy` idempotency
and stale-twin re-copy; `verify` failing on a corrupted byte; `flip`→`unflip`
round-trip equals identity (manifest-driven); the D11 rewrite as a pure
function against GitHub avatar URLs, empty strings, already-v2 values, the
`image_urls[]` array column, and markdown bodies; `flip` skipping URLs whose
v2 target is missing; `unflip` refusing rows whose v1 file is absent;
`delete-legacy` refusing on missing/mismatched twin; `prune-empty-dirs` on
mixed-depth trees; allowlist exclusion of `bdr/`-like entries.

## 7. Statistics pipeline changes (Phase 0)

**Parsing.** Strip any query string from `request.uri`, then match:

```
^/(?:api/vault/)?(?:(?P<cls>avatar|blog_image)/)?
 (?P<s1>[0-9a-f]{2})/(?P<s2>[0-9a-f]{2})(?:/(?P<s3>[0-9a-f]{2}))?/
 (?P<uuid>[0-9a-f-]{36})(?P<up>_upscaled)?\.(?P<ext>png|gif|webp|bmp|jpg)$
```

`shard_level = 3 if s3 else 2`. Keep `re.IGNORECASE` (deliberate: matches
current behavior; case-mismatched paths 404 on the case-sensitive FS anyway).

**Two log feeds, not one.** The vault-subdomain log
(`vault-access.log` / `vault-dev-access.log`) **does not see** relative
`/api/vault/…` requests served by FastAPI StaticFiles on the main domain —
and that URL form demonstrably exists in prod data (13 `posts.art_url`,
686 `social_notifications` rows). Phase 0 must ensure main-domain `/api/vault`
requests are logged by Caddy (add a log directive if absent) and feed them
through the same matcher (the `(?:api/vault/)?` prefix group). Without this,
the retirement criterion has a blind spot and Phase 5 could 404 live
consumers. (Critique finding; was unmitigated.)

**Counting semantics (D8, uniform).** All counters in the new table count
`GET`/`HEAD` with status 200/206/304 — including the per-post straggler rows,
so a player that only *revalidates* (304) both pins the streak at zero **and
appears in the straggler table**. Additionally count status 404 per
class×level as `misses` (aggregate rows only): a v1 404 during the dual
window is a dual-delete/copy bug alarm; after Phase 5 it confirms residual
legacy demand. The existing `download_stats_daily` table and its GET+200
semantics are **left completely untouched** (historical continuity by not
touching it at all — supersedes the earlier two-store design, critique
finding).

**Schema (one Alembic migration, single new table):**

```sql
CREATE TABLE vault_sharding_stats_daily (
  id               SERIAL PRIMARY KEY,
  date             DATE NOT NULL,
  asset_class      VARCHAR(16) NOT NULL,        -- artwork | avatar | blog_image
  shard_level      SMALLINT NOT NULL,           -- 2 | 3
  post_id          INTEGER NULL REFERENCES posts(id) ON DELETE CASCADE,
  downloads_human  INTEGER NOT NULL DEFAULT 0,
  downloads_bot    INTEGER NOT NULL DEFAULT 0,
  misses           INTEGER NOT NULL DEFAULT 0,  -- 404s; aggregate rows only
  CONSTRAINT uq_vault_sharding_stats
    UNIQUE NULLS NOT DISTINCT (date, asset_class, shard_level, post_id)
);
```

- Aggregate rows (`post_id IS NULL`): **always upserted for every
  class×level combination, including all-zero days** (6 rows/day). A missing
  day therefore means "rollup did not run", never "quiet day" — the streak
  logic depends on this distinction (critique finding: an upsert-only
  pipeline makes a dead log mount indistinguishable from 14 clean days).
- Per-post rows: written only for level-3 artwork hits (the straggler
  drill-down).
- `rollup_download_stats` populates this table in the same nightly pass; its
  returned telemetry dict (already logged by Celery) gains
  `legacy_hits_non_bot` and `streak_days` so Phase 4 monitoring lands in
  `make logs` for free.
- `_select_log_files` is made date-aware (current code only sees files with
  mtime < 48 h, so re-runs for older dates silently return zeros). Note log
  retention is bounded by `roll_keep 10` × 50 MB as well as `roll_keep_for
  90d` — fine for the 14-day criterion, not a promise for arbitrary re-runs.

## 8. Moderator Dashboard — Downloads tab (Phase 0)

New section "Vault resharding" inside the existing Downloads tab
(`DownloadStatsPanel.tsx` / `mod-dashboard.tsx`), fed by moderator endpoint
`GET /api/admin/vault-sharding-stats?days=30` (Redis-cached ~5 min, like its
sibling at `routers/admin.py:774`):

1. **Trend chart** — daily downloads split 2-level vs 3-level; humans solid,
   bots toggleable; per-class breakdown; `misses` series visible.
2. **Retirement streak counter** — "Legacy non-bot downloads: 0 for N
   consecutive days (criterion: 14)". A day counts **only if** (a) aggregate
   rows exist for it and (b) total 2-level traffic > 0 that day (liveness —
   an all-quiet day means the pipeline is broken, not that the internet went
   silent). Missing/dead days are displayed as **data gaps that block the
   gate**, not as zeros.
3. **Legacy stragglers table** — per-post level-3 rows from the last 14 days
   (D8 semantics, so 304-only revalidators appear): title, sqid, owner,
   counts, last-seen date.

**Requester forensics (Phase 4, by hand):** the `players` table has **no IP
column** (critique correction — the original plan's "last-seen IPs" recipe
doesn't exist). Recipe: pull IPs/UAs from Caddy vault logs; correlate via
`view_events.viewer_ip_hash` (sha256 of IP, **7-day retention** — act within
the window) and MQTT broker logs; record findings in PROGRESS.md.

---

## 9. Phases

### Phase 0 — Groundwork (code + deploy; no data migration)

Ships as **two PRs** so each is independently revertible (critique finding —
a single revert of a combined deploy would 404 v2-born posts at the
shard-less call sites):

**PR-A — refactor + instrumentation (no behavior change for new uploads):**
- [ ] `storage_shard` becomes a required parameter of all vault path/URL
      builders; fix `routers/artwork.py:get_post_file_path_from_storage_key`
      and audit every caller the interpreter flags.
- [ ] JSON create route (`posts.py:~410`) sets `storage_shard` at creation.
- [ ] Dual write-through / dual-delete in the vault primitives only (D10):
      asset-level twin rule, temp+rename atomicity; avatar/blog delete
      helpers derive and delete both depths.
- [ ] Stats: §7 parsing, both log feeds (incl. main-domain `/api/vault`
      logging), Alembic migration, zero-row upserts, date-aware file
      selection, telemetry fields.
- [ ] Dashboard endpoint + UI section (§8).
- [ ] `reshard_vault.py` (`status`, `copy`, `verify`, `clean-tmp` at
      minimum) + the §6 pytest suite.
- [ ] Docs: fix player-protocol examples (incl. the wrong slash-less shard
      in `docs/mqtt-protocol/02-player-protocol.md`); document
      `storage_shard` as opaque, variable-depth, not to be parsed.
- [x] ~~Ask owner about firmware shard handling~~ — answered 2026-06-10:
      no firmware validates/parses `storage_shard`; used verbatim (D2).

**PR-B — v2 cutover for new writes:**
- [ ] `compute_storage_shard` → v2 (+ `compute_storage_shard_v1` for
      tooling); avatar/blog writers → v2.
- [ ] Tests: v2 unit tests, coexistence tests.

Gate **G0**: both PRs deployed to dev *and* prod; a new upload lands at a
2-level path and round-trips (web display, player fetch, **and the
download endpoints for a pre-existing v1 post still work**); nightly rollup
writes aggregate rows including zeros; dashboard renders with a data-gap-free
day; `make test` green; `status --json` runs clean
(`out_of_scope_paths` reviewed, `null_shard_rows` = 0 for `kind='artwork'`,
`shard_derivation_mismatches` = 0). From this moment the v1 *asset set* is
frozen (D7) — but v1 *files* still mutate via edits until Phase 3
(dual-write keeps twins in sync once they exist; `copy` converges the rest).

Rollback: revert PR-B (new uploads revert to v1 paths; v2-born posts keep
working because every consumer now passes the stored shard — that is what
PR-A guarantees). PR-A itself is behavior-preserving.

### Phase 1 — Duplicate (copy v1 → v2)

- [ ] Pre-flight: `df` headroom ≥ 2× vault size; `status --json` baseline
      archived in PROGRESS.md.
- [ ] Dev: `copy --limit 10` → spot-check → full `copy`; then prod, same
      sequence.
- [ ] Re-run `copy` until it reports 0 work remaining (idempotent; edits
      during this phase create work).

Gate **G1**: `status --json` shows `v1_only_files` = 0 and
`shard_derivation_mismatches` = 0 (every DB-referenced v1 asset, across all
D11 reference sources, has a verified v2 twin).
Rollback: none needed — additive only.

### Phase 2 — Verify duplication

- [ ] Run `verify` (full sha256 pass, both environments); archive the JSON
      manifest path + summary in PROGRESS.md (manifests live in
      `api/reshard-reports/`, mounted, gitignored).
- [ ] Reconcile counts: DB-expected vs disk; review and record the orphan
      list and `out_of_scope_paths`.

Gate **G2**: `verify` exits 0; `stale_twins` = 0; orphans explained
(deleted posts etc.) and recorded.

### Phase 3 — Flip DB references

- [ ] **`pg_dump` first**, both environments, before any flip
      (`docker compose exec db pg_dump -U owner makapix | gzip >
      backups/pre-flip-$(date +%F).sql.gz`); record path in PROGRESS.md.
- [ ] Dev rehearsal: `flip --limit 10` → checks → full `flip` → verify →
      **`unflip` → verify → `flip`** (a rollback path that has never been
      executed doesn't exist — critique finding).
- [ ] Dev verification: web pages, API payloads, player sync (MQTT payload
      `storage_shard` is 5-char v2; player renders), avatars, blog post
      body images, notifications thumbnails.
- [ ] Quick broker check for retained messages (publisher uses
      `retain=False` throughout — `mqtt/notifications.py:71,84,154,169` —
      so expect none; verify and move on).
- [ ] Prod: quiet window; `flip --limit 10` → spot-check → full `flip`.
- [ ] **Verify at least one real fielded-firmware player fetches and renders
      a v2-shard artwork** (watch vault log for its fetch; watch for 404s or
      malformed URIs — firmware choking on a 5-char shard produces silence
      or garbage, not errors in our logs). R15.
- [ ] Re-run `flip` + `status` daily for a few days until `v1_url_refs` = 0
      stays 0 (in-flight sessions and notification snapshots can reinstate
      v1 values committed pre-flip).
- [ ] Watch the dashboard: legacy traffic should start decaying as players
      re-sync; `misses` should stay 0.

Gate **G3**: `status --json` `v1_url_refs` = 0 across all D11 columns and
stays 0 on re-check after 48 h; spot checks pass; fielded-player v2 fetch
confirmed; no error spike in `make logs-api`.

Rollback: `unflip` (manifest-driven; both file sets exist until Phase 5);
`pg_dump` as the backstop for malformed-rewrite bugs `unflip` can't see.

### Phase 4 — Observe (weeks → months)

- [ ] Weekly: check dashboard (owner sets a recurring reminder); rollup
      telemetry (`legacy_hits_non_bot`, `streak_days`) is in worker logs via
      `make logs` as a second channel.
- [ ] Any v1 `misses` (404s) during this phase = dual-delete/copy bug —
      investigate immediately.
- [ ] If legacy non-bot traffic plateaus > 0: forensics per §8 (Caddy log
      IPs/UAs; `view_events.viewer_ip_hash` within its 7-day window; MQTT
      broker logs); levers: force playlist re-sync / `show_artwork` refresh
      via MQTT, firmware update, contacting the owner. Record each
      investigation in PROGRESS.md.

Gate **G4**: ≥ 14 consecutive *liveness-valid* days (per §8 rules: rows
present, 2-level traffic > 0) with 0 non-bot legacy downloads across all
classes **and both log feeds**. Archive the evidence (dashboard screenshot +
SQL output) in PROGRESS.md before proceeding.

### Phase 5 — Delete legacy copies (destructive; manual; dev before prod)

Preconditions (same day as deletion):
- [ ] Re-run the rollup for the current partial day; grep both live logs
      (vault + main-domain `/api/vault`) for v1-pattern hits since midnight.
- [ ] Re-run the D11 v1-pattern scan (`status --json` `v1_url_refs` = 0),
      plus a one-off grep of *all* user-text columns (`posts.description`,
      comments, `blog_posts.body`) for the v1 vault pattern; report any hits.
- [ ] Full-vault backup tarball stored outside the vault mount; record
      location + checksum in PROGRESS.md; retain ≥ 90 days (D12).

Execution:
- [ ] `delete-legacy --dry-run`; reconcile counts against `status`.
- [ ] `delete-legacy --i-have-verified-the-retirement-criterion` (per-file
      re-verify built in; allowlist-scoped).
- [ ] Review orphan list; `--include-orphans` only if approved;
      `prune-empty-dirs`; `clean-tmp`.

Gate **G5**: only v2 copies remain (`status`: `twinned` = 0, `v1_only_files`
= 0); for the following 7 days: no non-bot v1 `misses`, no vault 5xx, no
user reports. Rollback: restore from the D12 backup.

### Phase 6 — Cleanup (one PR)

- [ ] Remove dual-write/dual-delete helpers, `compute_storage_shard_v1`,
      `copy`/`unflip`/`delete-legacy` tooling modes (keep `status`), and the
      v1 branch of the stats matcher — all in this same PR (no multi-release
      ceremony; after Phase 5, v1 requests 404 and are never counted).
- [ ] Keep `vault_sharding_stats_daily` data as history; keep the `misses`
      counter (generally useful).
- [ ] **Explicitly out of scope:** retiring `posts.art_url` (pre-existing
      deprecation) — separate effort, not blocking these docs' COMPLETE
      stamp.
- [ ] Close out: README status COMPLETE with dates; final PROGRESS entry.

---

## 10. Risk register

| # | Risk | Mitigation |
|---|---|---|
| R1 | Unknown firmware derives v1 paths locally (D2) → legacy traffic never zero | Empirical gate G4 + straggler drill-down + §8 forensics (note: no player-IP column; use `view_events.viewer_ip_hash`, 7-day window). Levers in Phase 4; worst case: targeted firmware update or keep v1 copies. Deletion is manual. |
| R2 | Players hold cached v1 `art_url` payloads indefinitely (offline devices) | Both URLs valid through Phase 4; a device returning after Phase 5 re-syncs and self-heals; only its stale cache misses once. |
| R3 | Artwork file changes between copy and flip (pixel edits, format regen, upscale create **new** sibling files with no twin) | D10 asset-level twin rule (mirror new files unconditionally per the canonical shard) + D9 flip re-verifies the full sibling set, copying missing twins. |
| R4 | Post deleted during dual window orphans its twin | D10 dual-delete; orphan sweep in Phase 5 as backstop. |
| R5 | Revalidations (304) / HEAD invisible → criterion met while consumers still reference v1 | D8 uniform semantics in **all** new counters, including per-post straggler rows. |
| R6 | `/api/vault/…` main-domain traffic invisible to vault-subdomain logs (form exists in prod: 13 + 686 rows) | §7 second log feed + `(?:api/vault/)?` matcher + Phase 5 same-day grep of both logs. |
| R7 | Dead pipeline reads as a clean streak (rollup writes nothing on zero hits; log dir missing returns `[]`) | Zero-row upserts; streak requires liveness (rows present + 2-level traffic > 0); data gaps block the gate and are displayed. |
| R8 | Flip-broken firmware produces *silence*, not errors (e.g. asserts 8-char shard) | **Downgraded 2026-06-10:** owner confirmed no firmware validates/parses the shard — all use it verbatim (D2). G3 keeps the fielded-player v2-fetch observation as a cheap sanity check; `misses` monitoring stays. |
| R9 | Blind URL rewriting corrupts external URLs (GitHub avatars; client-supplied `art_url` via JSON route) | D11 pattern-scoping + flip verifies target file exists + manifest + `unflip` is manifest-driven; pure-function rewrite tests. |
| R10 | Orphan sweep / prune destroys live non-asset data (`bdr/` zips, `lost+found`) | I6 allowlist; `batch_download_requests.file_path` documented as out-of-scope reference; `out_of_scope_paths` surfaced in `status`. |
| R11 | Flip overwrites the only record of the v1 location (rows whose stored shard ≠ derivation become unaddressable) | `copy`/`verify` assert `storage_shard == compute_storage_shard_v1(storage_key)`; flip manifest preserves old values. |
| R12 | `social_notifications` snapshots reference avatar files absent from `users.avatar_url` (failed past deletes) → flip rewrites to nonexistent v2 target | Copy candidate set includes all D11 columns; flip skips+logs URLs whose v2 target is missing. |
| R13 | Stale denormalized URLs / blog `body` markdown 404 after Phase 5 | `blog_posts.body` in D11 scope; Phase 5 all-text-columns grep. |
| R14 | Disk space / backup growth during window | Pre-flight `df`; ~1 GB extra; trivial. |
| R15 | Search engines / third-party embeds of v1 URLs | `X-Robots-Tag: noindex` already served; bots excluded from criterion (D4); post-Phase-5 404s acceptable. |
| R16 | Dev/prod divergence makes rehearsal misleading | Dev vault+DB are near-clones; `status` reconciliation and all gates run per-environment. |

## 11. Rough timeline

| Phase | Estimate |
|---|---|
| 0 | 1–2 weeks (two PRs, tests, review, dev+prod deploys) |
| 1–2 | days (mostly waiting on runs + verification) |
| 3 | 1 day + ~1 week of converge-and-watch |
| 4 | ≥ 1 month, owner-paced (criterion-driven) |
| 5 | 1 day + 7-day health watch |
| 6 | 1 short PR |
