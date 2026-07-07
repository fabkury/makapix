# Feed animation sync — server-side contract (messages 0008–0011)

**Status: CLOSED 2026-07-07.** Archived exchange with the app team about their
wall-clock-synchronized animation playback (`frame = f((now − epoch) mod totalLoopDuration)`).
Everything here shipped to prod on 2026-07-07 (PR #222). Read `messages/` for the full record.

## Contract pins (still binding — do not break without a new message exchange)

1. **`art_url` serves the upload payload verbatim, forever** (0009 §1). Never re-encode, re-time,
   optimize, or transform the native artwork file — at ingest or later. Frame delays are the
   author's. Holds for all historical posts. Combined with URL immutability + rotation-on-replace
   (message/0003, 2026-07-04), the bytes behind a given `art_url` never change.
   - Scope: the exact `art_url` (native format) only. Converted format variants and
     `{key}_upscaled.webp` are Pillow re-encodes and NOT timing-safe (the upscale is also
     frame-capped at 256) — fine for downloads/previews, never for synced playback.

2. **`total_duration_ms` clamp policy** (0010 §2, confirmed byte-identical to the app's playback
   constants in 0011): per frame, a missing stored delay or one ≤ 10 ms counts as 100 ms;
   whole-loop totals ≤ 30 ms are stored as 30 ms; `null` for static posts. Deliberately the
   *played* duration, not the raw sum — clients comparing their clamped decoded loop against the
   column can use `==`. Constants live in `api/app/amp/metadata_extraction.py`; if the policy ever
   changes, change it in lockstep with the app team and re-run `backfill_animation_durations`
   (idempotent; bumps `metadata_modified_at` only on rows that change).

`min/max_frame_duration_ms` remain raw stored file delays (positive entries only, no clamping).

## Bug fixed alongside (0009 §3)

Animated WebP frame durations extracted as NULL: Pillow only populates `info["duration"]` on
`load()`, and the extractor read it after `seek()` alone. Fixed in `collect_frame_durations`;
both environments backfilled (dev 1,359 / prod 1,542 animated posts, 0 errors).
