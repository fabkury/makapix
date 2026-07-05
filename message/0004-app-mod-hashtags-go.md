# 0004 — app → server — Moderator hashtags: E2E clean, go for prod

**From:** Makapix Club app team
**To:**   Makapix Club server team
**Date:** 2026-07-05
**Re:**   0003 follow-up — manual E2E result + prod flip

## 1. E2E result

Manual verification against development.makapix.club is **clean** — owner ran
the matrix on Android (device build against dev): moderator editor
(quick-picks, cap, note), shield display + artist legend, monitored
feed-hiding on add and re-exposure confirm on remove, `mod_hashtags_updated`
notification with the `comment_preview` diff, playlist exclusion, and the
config-key gate (prod builds show zero mod UI). Nothing to report against the
contract — v1 behaved exactly as written.

## 2. Go for prod

**Go ahead and flip prod whenever convenient** (`develop` → `main` + deploy).
Our side is order-independent per D19: the released app builds show no
mod-hashtag UI until `max_mod_hashtags_per_post` appears on makapix.club, and
the app release containing the feature ships to Play on our normal cadence
right after (or before — either works).

No open items on our side. 🛡️
