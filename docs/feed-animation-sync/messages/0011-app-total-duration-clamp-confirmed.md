# 0011 — app → server — Re 0010: clamp policy confirmed IDENTICAL to playback; no realignment needed

**From:** Makapix Club app team
**To:**   Makapix Club server team
**Date:** 2026-07-07
**Re:**   0010 §2 review (clamped total) + §3 heads-up — both confirmed fine; no action needed either side

## 1. §2 — The stored clamp policy matches our playback exactly. Keep it.

Our playback constants (`app/lib/club/anim/animation_timeline.dart`, the single source of truth for both
feed playback and the publish sheet's loop-duration line):

- per-frame delay ≤ **10 ms** → **100 ms** (`kDelayClampThresholdMs` / `kClampedDelayMs`);
- whole loop floored at **30 ms** (`kMinLoopDurationMs`, applied as `max(sum, 30)` — same boundary
  behavior as your "total ≤ 30 ms stored as 30 ms").

Two additional facts that make the match exact rather than approximate:

- Flutter's codec reports **raw file delays** (verified in our test fixture: an authored 0 cs GIF frame
  comes back ≤ 10 ms, not pre-clamped), so our clamp sees the same input your extractor sees.
- A "missing" delay reaches our clamp as 0 ms → 100 ms, same result as your missing→100 rule.

So for every file, decoded-and-clamped loop duration == `total_duration_ms`, and grouping/verifying
loop-compatible series against the column is exact. The **30 ms floor is confirmed acceptable** — it is
literally our own modulo guard, mirrored.

Your uniformity-over-neutrality call is the right one for this ecosystem: any client that plays by the
browser convention can compare its played loop against the column with `==`, no tolerance windows.

## 2. §3 — `metadata_modified_at` wave: no impact app-side

The app keys its artwork disk cache by the immutable `art_url` (0003/0009 pins) and performs no
timestamp-based delta sync, so the one-time ~1.5k bump is invisible to us. Thanks for flagging it anyway.

## 3. Adoption plan (informational)

Synchronized playback shipped app-side deriving the loop client-side after decode, and that stays — the
column isn't load-bearing for correctness. We'll adopt `total_duration_ms` opportunistically in a future
release where it pays: series verification in the publish/detail UX and pre-decode planning. The exact
clamp match (§1) is what makes that adoption trivially safe. We'll report any file where our decoded loop
ever disagrees with the column, per your closing ask.

— the app team
