# 0001 — app → server — `reacted-posts` items lack reaction/comment counts (profile ⚡ Reacted tab shows zeros)

**From:** Makapix Club app team
**To:**   Makapix Club server team
**Date:** 2026-07-16
**Re:**   Add `reaction_count`, `comment_count`, `user_has_liked` to `ReactedPostItem`
**Reply expected:** yes — confirmation + dev/prod availability so we can verify on device

## 1. Context

The app's profile **⚡ Reacted** tab (live since app 1.0.9) renders each artwork tile with a
likes/comments info bar, exactly like every other feed grid. Users report the bar shows
**"👍 0 · 💬 0" for every artwork** in that tab. We diagnosed it on 2026-07-16: it's not an app
parsing issue — the payload simply doesn't carry the fields.

## 2. The gap

`GET /api/v1/user/u/{public_sqid}/reacted-posts` returns `ReactedPostItem`
(`api/app/schemas.py`, currently: `id, public_sqid, title, art_url, width, height, owner_id,
owner_handle, owner, reacted_at, emoji, created_at, frame_count, files`).

Unlike the other post-shaped feed payloads, it has **no `reaction_count`, no `comment_count`,
and no `user_has_liked`**. The app's tolerant parser defaults them to `0 / 0 / false`, so the
tiles faithfully render zeros — and, ironically, nothing in the Reacted tab shows as liked even
when the viewer's own 👍 put it there.

## 3. Ask

Please add to `ReactedPostItem`, with the same semantics as the regular feed/post payloads:

1. **`reaction_count: int`** — total reactions on the post.
2. **`comment_count: int`** — non-deleted comment count (whatever the other feeds report).
3. **`user_has_liked: bool`** — whether the **requesting viewer** (`current_user`, when
   authenticated) has a 👍 reaction on the post — viewer-relative, *not* relative to the profile
   being browsed. `false` for anonymous callers.

Population presumably wants a batched per-page query rather than per-row subqueries —
`api/app/routers/pmd.py` (the `reaction_counts` map built for a page of posts) looks like the
exact precedent; `get_user_reacted_posts` in `api/app/routers/users.py` builds its `items` list
in one place, so the three fields slot in there.

## 4. Compatibility

This is a **backward-compatible contract addition**: the app already parses all three fields
from any post-shaped payload, so no app release is needed — existing app versions light up the
moment the server ships. Player firmware doesn't consume this endpoint. Remember the
`make openapi` regeneration for the committed contract.

## 5. Not in scope / FYI

- No urgency beyond normal flow; there's no app release gated on this.
- Unrelated to the reacted-posts **cursor 500** fixed 2026-07-12 (`3de67de`) — pagination is
  confirmed healthy.
- The crash users experienced in this tab was diagnosed as a Flutter engine (Impeller/Vulkan)
  bug on Pixel-10-class GPUs, mitigated app-side — nothing server-related. Details live in the
  app repo (`docs/reacted-tab-investigation/REPORT.md`) if you're curious.
