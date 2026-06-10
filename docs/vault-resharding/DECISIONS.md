# Decision Log — Vault Resharding

Append-only. Decisions D1–D5 were made by the project owner (fab) on
2026-06-10 in response to direct questions; D6+ are architectural decisions
made during planning, recorded here with rationale so they can be challenged
explicitly rather than re-litigated implicitly.

## D1 — Scope: artwork + avatars + blog images (owner, 2026-06-10)

All three asset classes reshard to 2-level. Artwork follows the full
copy → verify → flip → observe → delete pipeline because players cache
artwork URLs persistently. Avatars (43 files) and blog images (1 file) have
no persistent URL consumers, but for uniformity they follow the same pipeline
and are deleted in the same Phase 5 sweep — the marginal cost is near zero
and it avoids a second, different procedure.

## D2 — Player firmware behavior: unknown, assume worst (owner, 2026-06-10) — RESOLVED same day

Initially unknown whether any fielded firmware derives vault paths locally
from `sha256(storage_key)` or validates the shard format. **Owner confirmed
later the same day: no firmware validates or parses `storage_shard`; all use
the server-provided value verbatim.** Consequences: a 5-char v2 shard flows
through fielded players cleanly (R8 downgraded to a routine G3 sanity check),
and legacy traffic should decay naturally as players re-sync after the flip.
The empirical Phase 4 gate (observed zero traffic before deletion) stays —
it still guards against cached payloads on long-offline devices and any
non-player consumers.

## D3 — Duplication mechanism: full byte copies, not hardlinks (owner, 2026-06-10)

Step 1 makes physical copies (`copy → fsync → atomic rename`). Costs ~1 GB of
extra disk (trivial). Benefits: Phase 2 verification is a real, meaningful
sha256 comparison of two independent byte sequences; the mental model matches
the literal plan ("duplicate", "delete copies"); no backup-tool hardlink
surprises.

## D4 — Retirement criterion: manual trigger, bots excluded (owner, 2026-06-10)

Phase 5 (deleting 3-level copies) is triggered **manually** after the
dashboard shows **0 non-bot legacy downloads for ≥ 14 consecutive days**
(across all asset classes). Bot/crawler traffic (per
`app/utils/bot_detection.py`) is displayed separately and does not block
retirement — crawlers may re-fetch stale indexed URLs indefinitely. No
automation ever deletes vault files.

## D5 — Dashboard granularity: aggregate trend + straggler drill-down (owner, 2026-06-10)

The Downloads tab gains (a) a daily trend of 2-level vs 3-level downloads
with human/bot split, and (b) a "legacy stragglers" list showing which
artworks were recently fetched via 3-level URLs and how often — the tool for
chasing down consumers that haven't moved.

## D6 — Shard rendering: two lowercase hex chars, range `00`–`3f` (planning)

The 6-bit values `sha256_digest[0] & 0x3F` and `digest[1] & 0x3F` are rendered
as zero-padded lowercase hex (`f"{v:02x}"`), giving directory names `00`–`3f`.
Rationale: visually consistent with the existing layout, regex-friendly, and
*path depth* (2 components vs 3 before the filename) unambiguously
distinguishes the schemes — names alone do not, since v1 names `00`–`3f`
also exist. The hash input convention is unchanged:
`sha256(str(uuid).encode())` over the lowercase hyphenated UUID string.

Worked example, key `a1b2c3d4-e5f6-7890-abcd-ef1234567890`:
hexdigest starts `a447ee…` → v1 shard `a4/47/ee`; digest bytes
`0xa4, 0x47` → masked `0x24, 0x07` → v2 shard `24/07`. Note v2 is **not** a
prefix or substring of v1 in general.

## D7 — New uploads switch to 2-level at Phase 0 deploy (planning)

The same deploy that ships dual-location support also flips
`compute_storage_shard()` (and the avatar/blog equivalents) to v2. This
freezes the set of 3-level assets *before* the Phase 1 copy starts, so the
backfill has no moving target. `posts.storage_shard` remains the opaque
source of truth ("aa/bb/cc" = v1, "aa/bb" = v2; column is `String(8)`, v2
values are 5 chars).

## D8 — Download counting includes 304/206 and HEAD (planning; amended after critique)

The existing rollup counts only `GET` + status 200. A player or browser
revalidating a cached legacy URL gets a 304 — that is still a live legacy
*reference* and must keep the retirement clock at zero. **All** new counters
(aggregate trend, streak, and per-post straggler rows) uniformly count
`GET`/`HEAD` with status 200, 206, or 304; 404s are counted separately as
`misses`. The pre-existing `download_stats_daily` table keeps historical
comparability by being left completely untouched (see D13). *Amendment
rationale: the original split (200-only per-post columns, D8-semantics
aggregate) made the straggler table blind to 304-only revalidators — exactly
the consumers it exists to find.*

## D9 — Flip re-verifies per row immediately before flipping (planning; amended after critique)

Between the global verify gate (Phase 2) and the DB flip (Phase 3), artwork
files can change (pixel edits rewrite files; format-regeneration and upscale
tasks create **brand-new sibling files**). The flip script therefore
re-checks the **full sibling set** (every `post_files` format plus
`_upscaled`) for each post *in the same run* that flips it — copying missing
twins, not just repairing stale ones. Combined with D10's dual-write, this
makes staleness and late-created siblings non-events.

## D10 — During the dual window, writes and deletes touch both locations (planning; amended after critique)

From Phase 0 until Phase 6, the vault write/delete **primitives** (in
`vault.py`, `avatar_vault.py`, `blog_vault.py` — never at call sites)
operate on both locations. The twin rule is decided at the **asset level**,
not per file: the canonical side is whatever `storage_shard` (or the stored
URL) says; the derived twin path is computed via the explicit v1/v2
derivation functions, and writes mirror to it **unconditionally** — a
brand-new file (e.g. a freshly generated format variant or upscale) gets a
twin even though none pre-existed. Deletes remove both candidate paths
(including avatar replacement — otherwise the twin keeps serving a
supposedly-deleted image, a privacy regression). All writes go through
temp-file + fsync + atomic rename. *Amendment rationale: the original
per-file "where the twin exists" condition silently exempted new sibling
files, producing post-flip 404s.*

## D11 — URL rewrites are pattern-scoped, never blind (planning; amended after critique)

The flip rewrites only URLs that match `(vault-base-URL or /api/vault)` +
optional `avatar/`|`blog_image/` + a 3-level shard path + UUID filename —
and only after confirming the v2 target file exists (else skip + log).
Everything else (GitHub avatar URLs, empty strings, external URLs) is left
untouched and logged. Columns in scope: `posts.art_url`,
`posts.storage_shard`, `users.avatar_url`, `blog_posts.image_urls[]`,
**`blog_posts.body`** (markdown embeds vault image URLs — critique catch),
`social_notifications.actor_avatar_url`,
`social_notifications.content_art_url`. Every rewrite is recorded in a flip
manifest (table, row, column, old, new) **before** the DB write; `unflip` is
manifest-driven, never a blind inverse rewrite (a blind v2→v1 rewrite would
break v2-born assets that have no v1 files).

## D12 — Full-vault backup before Phase 5; retained ≥ 90 days (planning)

Immediately before deleting legacy copies, take a tarball of the entire vault
(~2 GB during the dual window) and store it outside the vault mount. This is
the only rollback path after deletion. (A `pg_dump` similarly precedes the
Phase 3 flip — the only phase that mutates the database across many columns.)

## D13 — Single stats store: `vault_sharding_stats_daily` with nullable `post_id` (planning, post-critique)

Instead of adding legacy columns to `download_stats_daily` *and* a new
aggregate table, one new table holds both: aggregate rows (`post_id NULL`,
one per class×level, **upserted every day including all-zero days**) and
per-post rows for level-3 artwork hits (the straggler drill-down). Uniform
D8 semantics; `UNIQUE NULLS NOT DISTINCT` (PostgreSQL 17). The existing
`download_stats_daily` is untouched. Zero-row upserts make "rollup didn't
run" distinguishable from "quiet day", and the streak counter additionally
requires nonzero 2-level traffic per day (liveness) — a dead log mount or
broken beat must block the retirement gate, not satisfy it.

## D14 — Phase 0 ships as two PRs: refactor first, v2 cutover second (planning, post-critique)

PR-A makes `storage_shard` a required parameter of all vault path/URL
builders (the silent v1-hash fallback is *live code*: the artwork download
endpoints call it shard-less today) and ships dual helpers, stats, dashboard,
tooling. PR-B flips new writes to v2. This ordering makes each step
independently revertible: reverting PR-B never strands v2-born assets,
because PR-A guarantees every consumer resolves paths from the stored shard.

## D15 — Destructive tooling operates inside an explicit subtree allowlist (planning, post-critique)

The tool recognizes exactly: 2-hex-char shard directories at the vault root,
`avatar/`, `blog_image/`. The vault root also holds live non-asset data —
`bdr/` (batch-download zips referenced by `batch_download_requests.file_path`)
and `lost+found` — which delete/prune/orphan logic must treat as out of
scope: reported, never touched.
