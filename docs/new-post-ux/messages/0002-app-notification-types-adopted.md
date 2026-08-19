# 0002 — App → Server: `post_approved` and `trust_granted` adopted

**From:** Makapix app team (Makapix Club app)
**To:** Club server team
**Date:** 2026-08-19
**Status:** Implemented app-side (committed to `main`, ships with the next release). Answers the two questions from 0001. Nothing pending on your side.

## Summary

Both types are adopted. The change was small because the app's notification
pipeline was already type-agnostic end-to-end; what shipped is proper copy and
presentation for the two types, plus model tests pinning the payload shapes
from 0001.

## Answers to your questions

**1. What does the app do with an unrecognized `notification_type`?**
Renders a **generic fallback tile** — never drops, never crashes. The model
parses `notification_type` as a free-form string, the SSE handler and REST
list don't filter by type, and the tile switch falls through to
`"{actor_handle} · {type}"`. Unread counts and mark-read already worked for
these types too. So users on current app builds have been *seeing* both
notifications since your 2026-08-18 deploy, just with ugly copy — and because
`post_approved` carries `content_sqid`, its tap-to-open-post even worked
through the fallback. No missed notifications; adoption was cosmetic, not
corrective.

**2. Null `post_id` on `trust_granted` — any objection?**
None. It matches `moderator_granted`, which is already tap-inert in the app.
The tile's tap is a no-op; the actor avatar still links to the granting
moderator's profile. Please keep it as is.

## What the app now renders

- **`post_approved`** — presented **impersonally**, mirroring your choice: the
  tile uses the app's moderation shield avatar (the same treatment as
  `mod_hashtags_updated` / report types), so the approving moderator is not
  identified anywhere on the tile. Copy:
  `Your artwork "{content_title}" was approved by a moderator and is now
  publicly released`. Tap opens the post; the artwork thumbnail shows on the
  right, as with other post-bearing types.
- **`trust_granted`** — mirrors the website: names the actor, shows their
  avatar (tap → their profile). Copy:
  `{actor_handle} granted you Trust — your posts are now auto-approved for
  public release`, with a `You were granted Trust — …` fallback when
  `actor_handle` is null (deleted account / legacy row).

## Notes

- The pending-review upload messaging you flagged as out of scope (heads-up on
  submit, pending tiles on own profile) is indeed not in this change. The app's
  publish flow does surface success copy, so we may pick that up later as its
  own effort — we'll open a message if it needs anything from the server.
- No app-side version gating, matching yours. Historical notifications of both
  types render correctly in the REST list.
