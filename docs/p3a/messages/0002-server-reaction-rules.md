# 0002 — Server → p3a: player reactions now follow the same rules as web/app reactions

**From:** Makapix Club server team
**To:** p3a player firmware team
**Date:** 2026-11-16
**Re:** `submit_reaction` / `revoke_reaction` (MQTT and the HTTPS player RPC)
**Status:** server side live on prod since 2026-11-16, no deploy dependency on your side
**Reply expected:** none — this is an FYI. Reply only if something below breaks an assumption in the firmware.

Hello p3a team! A bug fix on our side that slightly widens what
`submit_reaction` can answer. No firmware change is required.

## 1. What was wrong

A reaction sent from a player was stored and counted, but the artist never
got a notification for it — unlike the very same reaction sent from the
website or the mobile app. The player path had its own copy of the "add a
reaction" logic, and that copy had fallen behind.

## 2. What changed

Player reactions now run through the same server code as every other
reaction. The request and the success response are **unchanged**. Three
behaviours are new:

1. **The post owner is notified.** Every newly created reaction from a
   player produces a social notification for the artist (not for a reaction
   to the player owner's own post, and not when the reaction already
   existed — a repeated `submit_reaction` is still an idempotent success).
2. **Hidden posts can no longer be reacted to.** If the player's owner
   cannot see the post (hidden by its author or by a moderator), the answer
   is the existing `not_found` — deliberately the same as for a post that
   does not exist. Deleted posts keep answering `deleted`, as before.
3. **Blocks are enforced.** If a block exists in either direction between
   the player's owner and the post's owner, nothing is stored and the
   answer is a **new error code**:

   ```json
   {
     "request_id": "req-003",
     "success": false,
     "error": "You cannot interact with this user.",
     "error_code": "blocked"
   }
   ```

   Over the HTTPS player RPC the same envelope comes with HTTP 403.

`revoke_reaction` is unchanged: idempotent, always succeeds.

## 3. What this means for the firmware

- Nothing to change if an unknown `error_code` on `submit_reaction` is
  already treated as "the reaction failed" — `blocked` is then just another
  failure.
- `blocked` and `not_found` are **permanent** for that post and account:
  please do not retry them. If the firmware keeps a local "reacted" state,
  it should roll it back on these, as it does for any other failure.
- `not_found` should be rare: every source a player gets posts from
  (`query_posts`, the Promoted feed, the `/player/...` lookups) already
  leaves out hidden posts, so it only arises for a post that was hidden
  after the device cached it.
- `blocked` is different: player channels are **not** filtered by blocks,
  so a device keeps receiving posts from an account its owner has blocked
  (or that has blocked its owner). `blocked` can therefore come back for any
  such post, freshly served or cached — uncommon, since it needs a block
  between the two accounts, but not a caching artefact.

Reference: `docs/mqtt-protocol/02-player-protocol.md` (`submit_reaction`
and the error-code table) and `docs/mqtt-api/player-requests.md`.
