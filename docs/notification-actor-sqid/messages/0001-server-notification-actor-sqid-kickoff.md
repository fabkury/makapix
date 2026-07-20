# 0001 — Server → App: `actor_public_sqid` on social notifications (kickoff)

**From:** Club server team
**To:** Makapix app team (Makapix Club app)
**Date:** 2026-07-20
**Status:** Sent — awaiting app reply

## Summary

We are polishing the notifications surface: each notification card gets the **acting user's avatar as a tap target that opens their profile** (alongside the existing artwork thumbnail that opens the post). To make that possible, social notification payloads gain one **additive, nullable field**:

- `actor_public_sqid` (`string | null`) — the acting user's public sqid, the same id you already use for profile routes (`/u/{sqid}` on the website; your profile page takes the same sqid).

It is added in **both** places notifications are delivered, in lockstep:

1. **REST:** items of `GET /api/v1/social-notifications/` (the paginated list).
2. **MQTT:** the JSON payload on `makapix/social-notifications/user/{user_id}`.

## Semantics

- Present on **all notification types** (reaction, comment, comment_reply, comment_like, post_promoted, mod_hashtags_updated, follow, moderator_granted, moderator_revoked, reputation_change) whenever the actor still exists.
- `null` when: the action was anonymous (`actor_handle` is `"Anonymous"`), the actor's account has since been deleted, or (rare legacy rows) the actor has no sqid. In that case there is nothing to link — fall back to whatever you show today.
- The field is resolved at read/publish time, so **historical notifications get it too** — no backfill window to wait out.
- Purely additive; ignore-unknown-keys safe. No version gating in either direction.

## Suggested UX (mirror of the website — your call on details)

The website's notification card now shows the actor's avatar (from the existing `actor_avatar_url`) as a 32px circle with a small notification-type badge overlaid; tapping the avatar opens the actor's profile, tapping anywhere else on the card (including the artwork thumbnail) opens the post as before. When `actor_public_sqid` is null the avatar is not tappable (or the type icon shows instead).

## Status on our side

- Implementation starting now on `develop`; live on development.makapix.club shortly, prod expected within days. We'll follow up when it's on prod.
- The MQTT protocol doc (`docs/mqtt-protocol/03-notifications.md` in the server repo) is updated in the same change.

## Questions for you

1. Any objection to `null` semantics above, or do you need a distinguishing marker for "anonymous" vs "deleted actor"? (We currently don't distinguish; `actor_handle` is `"Anonymous"` for the former and the last known handle for the latter.)
2. Does your notifications UI already render `actor_avatar_url`? If not, note that avatar URLs may be relative (`/api/vault/avatar/...`) — prefix with the API origin.

Reply as `0002-app-…` in the server repo `docs/notification-actor-sqid/messages/` when convenient.
