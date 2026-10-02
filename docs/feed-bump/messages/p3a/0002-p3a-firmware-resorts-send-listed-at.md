# 0002 - p3a -> server - feed-bump: the firmware re-sorts, please send `listed_at` (and `promoted_at`)

**From:** p3a player firmware team
**To:** Makapix Club server team
**Date:** 2026-10-02
**Re:** Your 0001 in this folder, section 3
**Reply expected:** `0003-server-<slug>.md` confirming the field spec in section 3, or a counter-proposal, plus when it is live on dev

Thanks for the heads-up and for asking before assuming.

## 1. Answer: yes, the firmware re-sorts locally

Every 1.x release, up to the current 1.2.4, plays Makapix channels in
`created_at` order, newest first, whatever order the server returned. The
refresh asks for `sort="server_order"`, but the server's order only decides
*which* posts land in the cache. The device keeps no rank:

- Each post is cached with its parsed `created_at`, and the list of
  downloaded artworks is kept sorted on that field.
- When an artwork is replaced, the device sees the new `artwork_modified_at`,
  deletes its copy and downloads the new file. The new file goes back to its
  original `created_at` position.
- When the cache is over its size limit, the posts dropped first are the ones
  with the oldest `created_at`.

So a bumped post gets its new artwork on devices, but not its new position.
Your proposed follow-up is the right fix, and we'd like to take it.

## 2. Everything else in 0001 is fine with us

- Additive fields are safe on every shipped firmware: the parser looks up
  fields by name and ignores anything it does not know.
- The duplicate from offset paging is harmless. The device merges posts by
  id, so a post seen twice in one refresh is stored once.
- No objection to the remap or the deploy timing. Until devices run the
  release in section 4, bumps simply don't move on players.

## 3. Proposed field spec

**`listed_at`** on artwork posts in `query_posts` responses:

1. ISO 8601 UTC string, same format as `created_at`.
2. Always present in the default payload, not behind `include_fields`. The
   device needs it on every post to sort, and asking for it explicitly would
   tie the sort to a request flag that older builds don't send anyway.
3. Equal to `created_at` for a post that was never bumped (your
   `listed_at follows created_at` rule). The device falls back to
   `created_at` when the field is absent, and the two must agree for that
   fallback to be seamless.
4. On every channel where the server orders by listing time (`all`,
   `artwork`, `user`, `by_user`, `hashtag`). Sending it on the other channels
   too is fine; the device ignores it where it does not apply.

We read that PLAN.md D8 keeps `listed_at` internal today. This asks to expose
it to players only; we have no view on whether the `Post` schema or the
website needs it.

**`promoted_at`**, for a separate gap we found while answering you. The
`promoted` channel has the same problem today: devices play it by posting
date, not newest promotion first, both on the MQTT path and on the HTTP
`GET /feed/promoted` catalog sync (devices without a registration use the
latter). To fix that in the same release we'd like:

1. `promoted_at` on artwork posts in `promoted` channel responses over MQTT,
   always present, ISO 8601 UTC.
2. `promoted_at` selectable through `fields=` on `GET /feed/promoted`. The
   device requests `?fields=id,storage_key,created_at,artwork_modified_at`
   today and would add `promoted_at`.
3. The value the server actually sorts on, that is
   `coalesce(promoted_at, created_at)`, so the device never has to guess for
   legacy promotions with no timestamp.

If `promoted_at` is more work than it is worth on your side, say so and we'll
ship `listed_at` alone; the promoted gap predates feed-bump and is not
urgent.

## 4. On our side

We target firmware 1.2.5. The device will store the listing time in a field
it already has room for in its cache entry, so existing caches carry over
without a migration. We'll start once the fields are live on dev and tell
you here which release ships it.
