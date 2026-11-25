# 0003 — Server → App: Pulse is live on dev and on prod

**From:** Makapix Club server team
**To:** Makapix app team (Makapix Club app)
**Date:** 2026-11-25
**Re:** `0002-server-pulse-contract-accepted.md` (this folder)
**Status:** live on `development.makapix.club` and on `makapix.club`.
**Reply expected:** none. Tell us the app version when Pulse ships, if you like.

Hello app team! `GET /api/v1/pulse` is live on both environments, built exactly as 0002
describes. Two small things to know that 0002 did not say:

1. **`badges[].icon_url_64` can be `null`**, for a badge that has no definition row. It should
   not happen with today's data, but please do not crash on it. Everything else in 0002 holds.
2. **Dev has demo activity.** The dev database had nothing newer than August, so Pulse would
   have been empty. We added four members, `pulse_demo_1` to `pulse_demo_4`, with likes,
   comments (one reply, one longer than 140 characters), two badges, reputation changes and one
   registered player. Their cards leave the 30-day window on 2026-12-25. For `posts`, `remixes`
   and `promoted` cards, upload or remix something on dev with your own account.

What we checked on dev: 401 without a token, 200 with one, all eight kinds returned and
grouped as specified, paging walks every card once.

The website has a Pulse page too (`/pulse`, signed-in members land there), in case you want to
compare how a card reads.

Thanks!
