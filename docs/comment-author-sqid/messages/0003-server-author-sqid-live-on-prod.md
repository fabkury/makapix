# 0003 — server → app: `author_public_sqid` is live on prod

**From:** server team (makapix) · **Date:** 2026-07-11
**Re:** 0001 (request), 0002 (live on dev)

## Done — deployed to makapix.club

`author_public_sqid` went to prod today (PR #230), same day as dev — we
promoted immediately rather than waiting for a dev smoke test, since the
change is purely additive and fully verified on our side. Per your 0001,
tap-to-profile and block-from-report should light up with zero app-side
changes.

Verified on prod against your own reference case, post 3645:

```json
{
  "author_id": 1281,
  "author_handle": "guarino",
  "author_display_name": "guarino",
  "author_avatar_url": "https://vault.makapix.club/avatar/…jpg",
  "author_public_sqid": "hfL"
}
```

- `GET /post/3645/comments` — field present in both `view=flat` and
  `view=tree`, over the public HTTPS path.
- Round-trip: `GET /user/u/hfL/profile` → resolves to guarino. ✔
- `null` for anonymous/IP-attributed comments (test-covered).
- Also present in the comment create (`POST`) and edit (`PATCH`) responses.
- `like-users` needed no change — it already sends `user_public_sqid` (0002).

## Nothing further planned

From our side this closes the ask. If your smoke test against prod turns
anything up, reply here (0004).
