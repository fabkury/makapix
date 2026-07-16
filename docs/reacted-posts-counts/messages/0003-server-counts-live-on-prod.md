# 0003 — server → app: reacted-posts counts are live on makapix.club (prod)

**From:** server team (makapix) · **Date:** 2026-07-16
**Re:** 0002 (dev confirmation), 0001 (request)

## Deployed

PR #237 merged and deployed to production today. `ReactedPostItem` on
`GET /api/v1/user/u/{public_sqid}/reacted-posts` now carries
`reaction_count`, `comment_count`, and `user_has_liked` on **makapix.club**.

Verified on prod post-deploy:

- Anonymous fetch of `/user/u/t5/reacted-posts` returns the fields; counts
  cross-checked against the database (post 3648: 4 reactions, 0 comments).
- Cursored pages carry the fields.
- Viewer-relative `user_has_liked` semantics were device-independent and
  verified on dev (0002); the code path is identical.

Same-day request → prod. Clear to verify on device — existing app versions
should light up immediately, per your §4. Reply if anything looks off;
otherwise we consider this closed.
