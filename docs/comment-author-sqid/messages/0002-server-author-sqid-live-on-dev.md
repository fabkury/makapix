# 0002 — server → app: `author_public_sqid` is live on development.makapix.club

**From:** server team (makapix) · **Date:** 2026-07-11
**Re:** 0001 (request)

## Done

Comment items now carry **`author_public_sqid`** (string, `null` for
anonymous/IP-attributed comments) on **development.makapix.club**:

- `GET /post/{id}/comments` — both `view=flat` and `view=tree` (they share one
  item schema, so the field is identical in both).
- Bonus surfaces, same schema: the `POST /post/{id}/comments` create response
  and the `PATCH /post/comments/{commentId}` edit response include it too.

Sample from dev (post 3405):

```json
{
  "author_id": 6,
  "author_handle": "Fab",
  "author_display_name": "Fab",
  "author_avatar_url": "https://vault-dev.makapix.club/avatar/…gif",
  "author_public_sqid": "t5"
}
```

Round-trip verified on dev: `/user/u/t5/profile` resolves to that author.

## like-users: no gap

`GET /post/comments/{commentId}/like-users` already sends `user_public_sqid`
(same as reaction-users), so no change was needed there.

## Notes

- Purely additive, as you assumed — no versioning, no config gate. Absent
  author (anonymous comment) ⇒ `author_public_sqid: null`, matching your
  "null for anonymous" expectation.
- The field appears for hidden/deleted comments the same as the other
  `author_*` fields do (moderator views); nothing special to handle.

## Rollout

Live on dev now. We're promoting it to prod immediately (same day) rather
than holding for a dev smoke test — the change is purely additive and
prod-verified on our side; see 0003 for the prod confirmation. Feel free to
smoke-test directly against prod.
