# 0002 — server → app: reacted-posts counts are live on development.makapix.club

**From:** server team (makapix) · **Date:** 2026-07-16
**Re:** 0001 (request)

## Done

`ReactedPostItem` (on `GET /api/v1/user/u/{public_sqid}/reacted-posts`) now
carries all three requested fields, live on **development.makapix.club**:

- **`reaction_count: int`** — total reactions on the post (all emoji).
- **`comment_count: int`** — visible comments only (excludes `hidden_by_mod`,
  `deleted_by_owner`, `deleted_by_mod`), same rule as every other feed.
- **`user_has_liked: bool`** — whether the **requesting viewer** has a 👍
  reaction on the post; `false` for anonymous callers.

Population is batched per page via the shared `annotate_posts_with_counts`
service (the same one the main feeds use — three grouped queries per page,
no per-row subqueries), so semantics are identical to the regular feed
payloads by construction, not by parallel implementation.

Sample from dev (`/user/u/t5/reacted-posts`, authenticated as t5):

```json
{
  "id": 3405,
  "title": "r e p r e s s i o n",
  "emoji": "👍",
  "reaction_count": 2,
  "comment_count": 2,
  "user_has_liked": true
}
```

## Verified on dev

- Counts cross-checked against the database for the sampled posts.
- **Viewer-relative check:** the same page fetched with a *different* user's
  token shows `user_has_liked: false` on all of the profile owner's 👍-reacted
  posts — it tracks the viewer, not the profile being browsed, per your §3.3.
- Anonymous fetch: fields present, `user_has_liked: false`.
- Cursored pages (the spot fixed in `3de67de`) carry the fields too.
- `make openapi` regenerated; the committed contract includes the three
  fields with defaults (`0 / 0 / false`), matching your tolerant parser.

## Rollout

Live on dev now; ships to prod with the next develop→main deploy. We'll send
0003 when it's on prod so you can verify on device. As you noted, no app
release is needed — existing versions light up on deploy.
