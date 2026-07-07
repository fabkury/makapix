# 0010 — server → app — `total_duration_ms` is live on dev AND prod (re: 0008 §3) — note the clamp policy, it is NOT the raw sum

**From:** Makapix Club server team
**To:**   Makapix Club app team
**Date:** 2026-07-07
**Re:**   Follow-up to 0009 §3 — the §3 proposal from 0008 is adopted, shipped, and backfilled; plus the animated-WebP min/max fix. One deliberate deviation from your request (§2 below) — please review it.

## 1. What shipped (live on development.makapix.club and makapix.club as of today)

- **`total_duration_ms`** (int, ms) on every payload that carries the Post schema — feed lists,
  post detail, and the player endpoints. `null` for static posts, always populated for animated
  ones. Additive; the committed OpenAPI contract is regenerated.
- **The 0009 §3 extractor bug is fixed**: animated WebP per-frame delays are now read correctly at
  ingest, so `min_frame_duration_ms` / `max_frame_duration_ms` are populated for WebP natives too.
  Their semantics are unchanged: raw stored file delays, positive entries only, no clamping.
- **Backfill complete on both environments** — every animated post re-extracted from its native
  vault file: dev 1,359/1,359, prod 1,542/1,542, zero errors, zero NULLs remaining.

## 2. Deviation from 0008 §3: the stored total is CLAMPED, not the raw sum

You asked for the raw sum ("clients apply the browser-convention clamp at playback"). Owner
decision: we store the **played** duration instead, so the server value and what a clamping player
actually loops are the same number — uniformity over neutrality. The pinned policy:

- **Per frame:** a missing stored delay, or one ≤ 10 ms, counts as **100 ms** (the same
  browser-convention clamp you described for your playback path).
- **Whole loop:** a total ≤ 30 ms is stored as **30 ms** (floor, so wall-clock modulo arithmetic
  never divides by a near-zero loop).
- `null` for static posts.

Consequences to note:

- For well-formed files (all frame delays > 10 ms, which is essentially all real pixel-art
  animations), the stored value **equals the raw sum** — the clamps only bite on degenerate files.
- If your playback clamp matches the per-frame rule above, grouping/verifying loop-compatible
  series against `total_duration_ms` is exact, not approximate.
- **If your actual playback clamp differs from this policy in any way** (threshold, clamp value,
  or the absence of a whole-loop floor), tell us — the column is backfilled by an idempotent task
  and the policy is one constant-set in one place, so re-aligning is cheap. Please also confirm
  the 30 ms floor is acceptable for your modulo math.
- If you ever need the true raw sum, it remains derivable client-side after decode, exactly as you
  do today. `min/max_frame_duration_ms` stay raw, so `min > 10` also tells you the clamps didn't
  fire for that file.

## 3. Heads-up: `metadata_modified_at` bumped on all animated posts today

The backfill corrected metadata on every animated post (both envs), and each corrected row's
`metadata_modified_at` was bumped so metadata caches pick up the new values. If you key any cache
or delta-sync on that timestamp, expect a one-time refresh wave of ~1.5k posts dated today.
`artwork_modified_at` and `art_url` are untouched — no artwork bytes changed (0009 §1 pin intact).

## 4. Unchanged

The 0009 pins stand as written: bytes at `art_url` as-uploaded forever, and derived variants
(extension-swapped URLs, `_upscaled.webp`) remain re-encodes that are not timing-safe. Static
posts are unaffected throughout.

Happy to hear how the field behaves against your decoder — especially any file where your decoded
(clamped) loop duration disagrees with `total_duration_ms`.

— the server team
