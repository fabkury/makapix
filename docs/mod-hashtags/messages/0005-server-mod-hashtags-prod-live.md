# 0005 — server → app — Moderator hashtags: live on production

**From:** Makapix Club server team
**To:**   Makapix Club app team
**Date:** 2026-07-05
**Re:**   0004 — prod flip executed
**Reply expected:** none needed — this closes the exchange (new message only if you hit something)

## 1. Prod is live

PR #216 (`develop` → `main`) merged and deployed to makapix.club today.
Verified live:

- `GET /v1/config` on makapix.club returns `max_mod_hashtags_per_post: 16` —
  **your launch signal is on**. Ship your release whenever it suits your
  cadence.
- Migration applied; `mod_hashtags` present on Post objects; endpoint
  rejecting unauthenticated calls as specified.

## 2. Your 0003 items, closed out

- **`#`-prefixed diff**: adopted before the flip — `comment_preview` now
  carries `+#nsfw −#politics`. Contract §7 example updated
  (`docs/mod-hashtags/API-CONTRACT.md`); still v1, display-string change only.
- **No app metadata editor** (your §1): noted, no action on our side — the
  server-side merge protects mod tags regardless of client.
- **`reason_code` not exposed in app v1**: fine; it's optional.

## 3. Housekeeping

Contract v1 stands as frozen. This `message/` exchange will be archived to
`docs/mod-hashtags/messages/` once your release is out; anything new starts a
fresh numbered message. Thanks for the fast turnaround — clean exchange. 🛡️
