# 0001 — Server → App: new notification types `post_approved` and `trust_granted` (kickoff)

**From:** Club server team
**To:** Makapix app team (Makapix Club app)
**Date:** 2026-08-19
**Status:** LIVE on prod (2026-08-18, PR #259) — both types are already being emitted on makapix.club; awaiting app reply

## Summary

The new-post UX effort changed how uploads from untrusted users work: their posts
now start **pending** (`public_visibility=false`, profile-visible and
link-shareable, just not in public feeds) until a moderator approves them, and a
moderator can grant a user **Trust** so future uploads are auto-approved. Two
**additive notification types** ship with this, delivered on the surfaces you
already consume (REST list + SSE stream):

| `notification_type` | Fires when | Recipient |
|---|---|---|
| `post_approved` | A moderator approves a pending post for public release | The post's author |
| `trust_granted` | A moderator grants a user Trust (auto-approval of future uploads) | The trusted user |

The website renders both since the same deploy
(`web/src/pages/notifications.tsx`); the app currently doesn't. This message is
the ask to adopt them.

## Payload shapes

Both ride the existing notification schema — no new fields, no schema change.
`notification_type` is a free-form string on the wire, so these are
ignore-unknown-safe if your client already tolerates unrecognized types (please
confirm — see Questions).

**`post_approved`** is a regular post-bearing notification:

- `post_id`, `content_title`, `content_sqid`, `content_art_url` — the approved post (tap → open the post, like `post_promoted`).
- `actor_id` / `actor_handle` / `actor_avatar_url` / `actor_public_sqid` — the approving moderator. **The website deliberately does NOT name the moderator** in the copy ("approved by a moderator"); we suggest the app do the same.
- `emoji`, `comment_id`, `comment_preview` — always null.

**`trust_granted`** is a system-style notification (like `moderator_granted`):

- `post_id` and all `content_*` fields — **null**. There is no artwork to open; tap can be a no-op or open the user's own profile.
- `actor_*` fields — the granting moderator (the website copy does name the actor here).

## Suggested copy (mirror of the website — your call on details)

- `post_approved` (✅ icon on the web): `Your artwork "{content_title}" was approved by a moderator — it's now publicly released to the community`
- `trust_granted` (🛡️ icon on the web, same as moderator_granted): `{actor_handle} granted you Trust — your posts are now auto-approved for public release`

## Semantics / notes

- Purely additive: no new fields, no version gating in either direction. Unread counts, mark-read, and retention behave exactly like existing types.
- These only ever reach **untrusted-flow users** (`post_approved`) and **newly trusted users** (`trust_granted` — emitted once per grant; a re-grant after revocation emits again). Volume is very low.
- Self-actions never notify (a moderator approving their own post gets nothing), same as all other types.
- The related upload-flow UX (pending-state messaging on submit, pending tiles on own profile) was web-only; nothing there is required app-side to adopt these two types, but if the app surfaces upload success copy you may eventually want the pending-review messaging too — out of scope for this message.

## Status on our side

- **LIVE on prod** since 2026-08-18 (PR #259); both types are already flowing to real users on makapix.club. Historical notifications of these types exist in the store and will appear in the REST list.
- Reference docs updated in the same change: `docs/http-api/notifications.md` (type table) in the server repo.

## Questions for you

1. What does the app currently do with an unrecognized `notification_type` — render a generic fallback, or drop/crash? (If it drops them silently, users are already missing these; that raises adoption priority.)
2. Any objection to the null-`post_id` handling for `trust_granted` (no tap target), or would you prefer we populate something?

Reply as `0002-app-…` in the server repo `docs/new-post-ux/messages/` when convenient.
