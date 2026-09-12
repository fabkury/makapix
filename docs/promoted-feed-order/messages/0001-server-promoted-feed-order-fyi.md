# 0001 — Server → App: the promoted feed now sorts by promotion time (FYI)

**From:** Club server team
**To:** Makapix app team (Makapix Club app)
**Date:** 2026-09-12
**Re:** docs/promoted-feed-order/ (server repo)
**Status:** on `develop`, verified on dev; prod deploy imminent
**Reply expected:** none required — an optional `0002-app-…` ack in this folder if you want to note anything

Hello app team! Pure FYI, nothing to change on your side.

## What changed

`GET /feed/promoted` (your Recommended tab — `feed_api.dart` calls it directly)
now returns promoted posts ordered by **the moment a moderator promoted them**,
newest promotion first, instead of by upload date. The same order applies to
`GET /post?promoted=true&sort=created_at` and to the physical players'
`promoted` channel, so every promoted surface agrees.

- **Contract unchanged.** Same endpoint, same `Page[Post]` shape, same cursor
  mechanics, same `fields=` filter. No new field is exposed on `Post`; the
  promotion time is a server-internal sort key.
- **Cursors keep working.** A cursor you already hold resumes correctly after
  the deploy (existing promoted posts were grandfathered so their promotion
  time equals their upload time). Your feed cache, if any, will simply show
  the new order on its next refresh.
- **No visible change on deploy day.** Because of the grandfathering, the
  first page looks identical right after the deploy; the order diverges only
  as moderators promote from now on. A newly promoted 6-month-old artwork
  will now appear at the top of Recommended, which is the whole point.
- **Re-promotion bumps.** If a moderator demotes and later re-promotes a post,
  it comes back at the top (and the owner gets the usual `post_promoted`
  notification again).

## Anything to do?

No. If the app ever sorts or de-duplicates the Recommended list client-side
by `created_at`, stop — the server order is now the intended one. Otherwise
carry on.
