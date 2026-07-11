# 0001 — app → server: comments payload — please add `author_public_sqid`

**From:** app team (makapix-app) · **Date:** 2026-07-11
**Reply expected:** message `0002-server-…` when the field is live on dev (or if you
see a problem with the ask). Small change — batching it with whatever you ship next
is fine.

## Context

While fixing an app-side bug (the app expected a nested `author` object on comments
and rendered every author as "guest"; fixed by parsing your flat `author_*` fields —
no server action needed for that), we noticed the comments payload is the one
user-reference surface **without the public sqid**:

`GET /post/{id}/comments` items today (verified against prod, post 3645):

```json
{
  "author_id": 1281,
  "author_handle": "guarino",
  "author_display_name": "guarino",
  "author_avatar_url": "https://vault.makapix.club/avatar/…jpg"
}
```

Contrast `GET /post/{id}/reaction-users`, which sends `user_public_sqid` alongside
`user_handle` / `user_avatar_url`. `author_id` is the internal integer id, which
clients can't use: the profile endpoint (`/user/u/{sqid}/profile`) resolves public
sqids only (we checked — handles 404).

## The ask

Add **`author_public_sqid`** (string, null for anonymous/IP-attributed comments) to
comment items in `GET /post/{id}/comments`, both `view=flat` and `view=tree` —
mirroring the `user_public_sqid` precedent from reaction-users. Purely additive, so
no versioning concern. If `GET /post/comments/{commentId}/like-users` has the same
gap, the same fix there would be welcome, but comments are the priority.

## What it unblocks (app side is already wired)

1. **Tap a comment author → their profile.** Currently a silent no-op because there
   is nothing to navigate with.
2. **Block-the-offender from a comment report.** Comment reports currently go out
   without an offender sqid, so the block affordance can't target the author.

The app parses `author_public_sqid` opportunistically as of today's build — the
moment the field appears on prod, both features light up with **zero app-side
changes and no rollout coordination needed**. No config gate required; absent field
= current behavior.

## Rollout

1. Server adds the field (dev first per your usual flow) and replies here (0002).
2. We smoke-test tap-to-profile against dev, then it rides your normal dev → prod
   promotion. Nothing to flip on our side.
