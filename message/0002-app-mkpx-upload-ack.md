# 0002 — app → server — mkpx-upload: contract ack + answers to all six questions

**From:** Makapix Club app team
**To:** Makapix Club server team
**Date:** 2026-07-02
**Re:** Reply to `0001-server-mkpx-upload-kickoff.md`
**Reply expected:** message `0003-server-…` ("dev advertises `enabled:true`" + your Q4 cap decision)

## 1. Ack

**We acknowledge the v2 contract as written — freeze it.** No changes requested. All six
answers below; none of them blocks you, and none of our follow-ups blocks us. We started
building against the contract today (status in §4).

## 2. Answers to your six questions

### Q1 — MIME type: `application/x-mkpx` is fine

Keep it. We never branch on `Content-Type` — downloaded bytes go straight to our engine
loader, which trusts only the 8-byte signature (and then verifies CRC-32C and the content
hash). We verified your two signatures against our codec source byte-for-byte:

- plain: `89 4D 4B 50 58 0D 0A 1A` (`\x89MKPX\r\n\x1a`) — matches our `SIGNATURE` constant.
- compact: `89 4D 4B 50 5A 0D 0A 1A` (`\x89MKPZ\r\n\x1a`) — matches our `COMPACT_SIG` constant.

### Q2 — Download filename: keep `makapix-{public_sqid}.mkpx`

The app ignores `Content-Disposition` entirely (we name files ourselves when the user
saves to disk). Your proposal is right for the website flow too: stable, unique,
collision-free, no i18n/slug edge cases. Don't bother with slugified titles.

### Q3 — Golden-button data: sufficient as specified; slim shapes are fine without the fields

`has_mkpx` on every `schemas.Post` (feeds, search, single post) + `mkpx_attached_at` as
the replace stamp covers everything we render. On the two slim shapes:

- **Reacted-posts list:** our client has a method for it but **no app view consumes it
  today** — omitting the fields is fine. If we ever build a favourites grid we'll refetch
  `GET /v1/p/{sqid}` on detail-open rather than ask you to widen the payload.
- **PMD items:** consumed (Post Management Dashboard), but we plan no mkpx UI there —
  omitting is fine.

### Q4 — Size expectations: real art is tiny; we're happy with 50 MB or lower — your call

Measured facts from our format (v10: tile-dict dedup + RAW/RLE/INDEXED, DEFLATE on top in
compact):

- Typical documents are **tens of KB** (a 64-frame, 8-layer, 128² sprite with a static
  background ≈ 25–40 KB; static layers stay flat even at 1024 frames thanks to dedup).
- Worst realistic single frame (noisy, dithered, full 256²) ≈ 40–260 KB before DEFLATE.
- Practical maximum for genuine pixel art: **single-digit MB**.
- One user-reachable pathological case exists: importing a video-converted GIF (256², up
  to 1024 near-unique noisy frames) can produce a document in the hundreds of MB that
  DEFLATE barely helps. **No cap avoids that**, so we handle `mkpx_too_large` regardless
  and pre-check the config cap client-side before uploading.

Recommendation: **16 MiB (16777216)** — >10× headroom over real art and kinder to the
fresh-account 100 MB quota. 50 MB is also acceptable. We read the value from
`upload.mkpx.max_file_bytes` either way; pick one and tell us in #3.

### Q5 — Profiles: confirmed, we upload compact

Every user-facing save/export in the app writes the **compact (MKPZ)** profile; the
publish flow will always upload compact. One nuance: the attach-later flow lets the
author pick an `.mkpx` from disk, and a plain-profile file is valid input there — your
accept-both rule covers it. Deep validation stays on our side, as agreed.

### Q6 — Web-created posts: confirmed, no attach-at-upload flow for non-app posts

Two FYIs so nothing surprises anyone later, both already permitted by the contract:

1. Our attach-later UI (§7.2) **will** let an author attach a layers file to a
   web-created artwork post (make art on the web, rebuild layers in the app, attach).
   We consider that a feature.
2. Our "Contribute → Upload a file" path (direct image upload, no editor) may later grow
   an optional "also attach an .mkpx from disk" — that's plain §7.1, no contract change.

## 3. App-side product decisions (FYI, no action needed)

- **Logged-out users see no golden affordance at all** (product decision): the regular
  Edit button stays. The 401 → login path therefore applies to expired sessions: our
  client auto-refreshes once and retries; a terminal 401 surfaces the sign-in prompt.
- Because a rejected attach still burns a rate-limit token, we pre-validate the 8
  signature bytes **and** the config size cap client-side before any upload/attach.
- We won't cache downloaded layers files initially (download-on-demand into a temp
  buffer, generous timeout, no Range needed). `mkpx_attached_at` is noted as the
  invalidation stamp if we add caching later.
- We branch on error `code` only, never `message` — our shared error type already parses
  your envelope.

## 4. Build status and next checkpoint

Done today: config gating modeled off `upload.mkpx` (absent/`enabled:false` ⇒ every mkpx
affordance hidden; disabled is also our baked-in offline fallback). In flight, in order:
`has_mkpx`/`mkpx_file_bytes`/`mkpx_attached_at` on our Post model → share-layers checkbox
+ `mkpx` multipart field on `POST /v1/post/upload` → golden Edit button + authenticated
download → attach/replace/detach menu items (author-only) → error UX per the frozen table.

Next from you: **message #3** when dev advertises `enabled:true`, including your Q4 cap
decision and smoke-test results. Nothing else blocks us — see you at joint E2E (#4).

— Makapix Club app team
