# 0003 - server -> p3a - feed-bump: `listed_at` and `promoted_at` are live (spec confirmed, three notes)

**From:** Makapix Club server team
**To:** p3a player firmware team
**Date:** 2026-10-02
**Re:** Your `0002-p3a-firmware-resorts-send-listed-at.md`
**Status:** **live on dev** (`development.makapix.club`); **prod the same day** (we'll confirm in a follow-up only if something changes)
**Reply expected:** `0004-p3a-<slug>.md` when you know which firmware release ships it (1.2.5, per your §4); questions any time

Thanks for the clear answer, and for catching the promoted gap. We took both.

## 1. Your spec, as built

**`listed_at`** follows your §3 exactly:

- ISO 8601 UTC, the same format as `created_at`.
- **Always present** on every post in `query_posts` responses, on every
  channel, over both MQTT and HTTPS `/player/rpc`. It is not behind `include_fields`.
- Equal to `created_at` until the post is bumped (see note 2).
- It is the exact value `server_order` and `created_at` sort on, for the channels
  `all`, `artwork`, `user`, `by_user` and `hashtag`.

**`promoted_at`**:

- **MQTT / `/player/rpc`:** present on every **promoted** post, on any
  channel, with value `coalesce(promoted_at, created_at)`. That's the value the
  `promoted` channel sorts on. On posts that aren't promoted the key is
  **absent**, because `query_posts` drops null fields.
- **HTTP `GET /feed/promoted`:** `promoted_at` is now selectable via `fields=`.
  For example: `?fields=id,storage_key,created_at,artwork_modified_at,promoted_at`.
  It has the same coalesced value and the same format.

## 2. Notes

1. **`listed_at` can change without the artwork changing.** A post's first
   moderator approval also lists it at the top. An untrusted user's upload is
   approved hours or days after posting, and it lands at the top on approval,
   not at its upload date. So `listed_at` can differ from `created_at` on a
   post that was never replaced, and `artwork_modified_at` doesn't move when
   that happens. On refresh, please take each post's `listed_at` from the
   response even when its artwork is unchanged, rather than only when you
   re-download. Your fallback still holds: absent `listed_at` = `created_at`.
2. **Playlists carry the same keys.** Channels mix playlist posts in with
   artworks, and they're ordered by the same keys. Playlist payloads now carry
   `listed_at` (always) and `promoted_at` (when promoted) too. Ignore them if
   you don't play playlists.
3. **Eviction.** Since you evict the oldest `created_at` first today, you may
   want to evict by the same key you sort by (`listed_at`, or `promoted_at`
   on the promoted channel). Otherwise a freshly bumped old post is the first to go. Your call.

## 3. Compatibility

Additive only. Shipped firmware ignores both fields (your §2), and nothing
else in the payload changed. The protocol docs are updated:
`docs/mqtt-protocol/02-player-protocol.md` (field tables) and
`docs/player/querying-artwork.md`.

Thanks!
