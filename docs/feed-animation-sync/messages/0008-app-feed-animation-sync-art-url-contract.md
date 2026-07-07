# 0008 — app → server — Feed animation sync: pin the as-uploaded `art_url` contract (+ optional `total_duration_ms`)

**From:** Makapix Club app team
**To:**   Makapix Club server team
**Date:** 2026-07-07
**Re:**   New app feature (synchronized feed animation playback) — one contract confirmation requested (§2), one optional additive proposal (§3)
**Reply expected:** yes for §2 (confirm or correct); §3 is optional and can be deferred

## 1. Context: what shipped app-side

The app now plays animated posts (GIF / animated WebP) with the displayed frame derived from the wall
clock — `frame = f((now − epoch) mod totalLoopDuration)` — decoded client-side from the bytes at
`art_url`. Artworks authored to the same loop duration stay frame-locked with each other on every feed,
tile, page, and device (a triptych whose panels form one scene never drifts apart). **No server changes are
required** for this to work; this message only pins an assumption and floats an optimization.

## 2. Please pin: bytes at `art_url` are served as uploaded — never re-encoded or re-timed

Message 0003 pinned vault-URL **immutability** (bytes at a URL never change; `art_url` rotates iff the
content changes). Synchronized playback additionally relies on the native file being served **byte-identical
to what was uploaded** — specifically, that per-frame delays are never altered by re-encoding or
"optimization" at ingest or later. If the server ever re-timed frames, artworks uploaded with one loop
duration could silently desync from their series.

Please confirm this is a guarantee we can document (we have provisionally noted it in our `SPEC-CLUB.md`
§7.3), or tell us where it doesn't hold — e.g. for any historical posts.

For the record: encoders that merge equal *sequential* frames into one longer frame (Pillow does this for
animated WebP) are **safe** for our scheme — the total loop duration is preserved and we sync on time, not
frame index. Delay-altering transforms are the only hazard.

## 3. Proposal (optional, purely additive): `total_duration_ms` on post payloads

You already extract `min/max_frame_duration_ms` at ingest. A server-computed **`total_duration_ms`** (sum of
the native file's per-frame delays; absent/null for static posts) on post list/detail payloads would let
clients:

- group and verify loop-compatible series without downloading and decoding files, and
- plan the client-side decode memory budget before fetching a byte.

The app currently derives this client-side after decode, so this is an optimization, not a blocker. If you
adopt it, please store the **raw** sum (no delay clamping) — clients apply the browser-convention clamp
(≤10 ms → 100 ms) at playback time, and raw is the neutral thing to persist.

## 4. Informational: `frame_count` treated as a hint

We treat server-extracted `frame_count` / `width` / `height` as routing hints and re-verify against the
decoded file, so extractor-vs-decoder disagreements (frame-merging encoders, exotic files) degrade
gracefully app-side. No action needed.
