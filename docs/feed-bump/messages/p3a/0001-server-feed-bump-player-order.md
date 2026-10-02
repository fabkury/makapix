# 0001 — Server → p3a: replaced artworks return to the top of the player feeds (kickoff + one question)

**From:** Makapix Club server team
**To:** p3a player firmware team
**Date:** 2026-10-02
**Re:** New feature thread (server `docs/feed-bump/`); not part of the standing `docs/p3a/` thread
**Status:** server work in progress; no firmware change required, no deploy dependency on your side
**Reply expected:** `0002-p3a-<slug>.md` in this folder, answering §3

Hello p3a team! A heads-up plus one yes/no question.

## 1. What changes

When an artist replaces a post's artwork, the post now returns to the top
of every date-sorted feed, on the website, the app and the players alike.
The server keeps a new internal *listing time* per post. `created_at` in
your payloads is **unchanged** (still the original posting date).

## 2. What this means for `query_posts` (MQTT)

- Channels `all`, `artwork`, `user`, `by_user`, `hashtag`: both
  `sort="server_order"` and `sort="created_at"` now order by **listing time,
  newest first**. Today `server_order` means post id, which matches upload order.
  It's a server-side remap with no protocol change, the same approach as
  the promoted-feed-order change.
- `promoted`: **unchanged**, still newest promotion first. The HTTP
  `GET /feed/promoted` catalog sync is unchanged too.
- `reactions` and `random`: unchanged.
- Offset paging: a bump that happens while a device is paging shifts later
  pages by one, so you may see one post twice. New uploads already cause this today. We
  consider it harmless.

At deploy time every listing time equals `created_at`, so the order is the
same as before until the first bump happens.

## 3. Question

With `play_order = 1` ("created_at order"), or any other mode, **does the
firmware re-sort its local cache by the `created_at` field**, or does it
play in the order the server returned?

- If it plays the server order, nothing is needed. Bumped posts move on devices
  automatically.
- If it re-sorts locally, bumped posts won't move on devices. We'd then
  propose adding the listing time to the payload as a new optional field
  in a follow-up. No deadline, and nothing breaks either way.

Thanks!
