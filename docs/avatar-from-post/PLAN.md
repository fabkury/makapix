# Use as profile photo (avatar-from-post)

**Status:** Implemented on `develop` 2026-07-19 (backend + web). App integration requested via `messages/0001`.

## What it is

A user picks any viewable artwork post → a confirmation dialog previews the artwork rendered as their avatar next to their handle → on confirm, the artwork becomes their profile photo. The web menu item ("Use as profile photo" in the post overlay's ⋮ menu) existed as a disabled placeholder since the overlay was built; this feature enables it end-to-end and adds the server endpoint the app will also use.

## Owner decisions (2026-07-19)

1. **Any viewable artwork** may be used, not just your own — with server-side **attribution**: `users.avatar_source_post_id` records which post the avatar came from. Internal-only (never in API payloads); moderators query the DB. Survives post soft-deletion (that is the traceability window); hard purge SET-NULLs it.
2. **BMP-native artworks are transcoded to PNG** (the avatar vault rejects BMP). The server prefers an existing PNG variant in `post_files`, else converts in memory with PIL.
3. **Animation preserved** — GIF/WebP bytes are copied unmodified, so animated artworks become animated avatars.
4. **Preview UI** = a single avatar+name row (32×32 pixelated artwork next to `@handle`), matching the post-header style.

Additional semantics: the avatar is a **snapshot** — the bytes are copied into the avatar sub-vault (`avatar/`), so the avatar survives later deletion or replacement of the source post.

## API

`POST /user/{user_key}/avatar/from-post` — body `{"post_sqid": "<public_sqid>"}` → **201** `UserFull` (same response as the existing avatar upload). Sits beside `POST/DELETE /user/{id}/avatar` in `api/app/routers/users.py` and shares:

- **Auth policy** (`_authorize_avatar_edit`): self, or owner-role, or moderator (except on owners/other moderators).
- **Rate limit**: the `ratelimit:avatar:{user_id}` bucket, 20/hour — both paths write files into the avatar vault, so they share one budget.
- **Old-avatar cleanup**: replacing best-effort-deletes the previous vault avatar file.

Errors (legacy root-path `{detail}` style): 400 (playlist post / no image / too large), 401, 403, 404 (bad sqid, not viewable — visibility is checked against the *acting* user via `can_access_post`, and soft-deleted posts are 404), 429, 507 (vault at free-space floor).

Attribution is set to the post id on success and **cleared** by the plain avatar upload and by DELETE avatar.

## Implementation map

- `api/app/models.py` — `User.avatar_source_post_id` (FK posts.id, `ondelete=SET NULL`, `use_alter=True` to break the users↔posts FK cycle). Migration `114d77aaf3d8`.
- `api/app/routers/users.py` — `_authorize_avatar_edit`, `_read_post_bytes_for_avatar`, `set_avatar_from_post`.
- `api/app/schemas.py` — `AvatarFromPostRequest`.
- `api/tests/test_avatar_from_post.py` — 17 tests (snapshot copy, attribution set/clear, BMP transcode, animated byte-equality, visibility/auth/rate-limit errors, old-file cleanup).
- `web/src/lib/api.ts` — `getMe()`, `setAvatarFromPost()`.
- `web/src/components/UseAsAvatarDialog.tsx` — confirm dialog with preview row; dispatches `makapix:user-updated` on success so the navbar avatar refreshes live.
- `web/src/components/SelectedPostOverlay.tsx` — menu item enabled for signed-in users (stays disabled-looking when logged out).

## App integration

Requested in `messages/0001-server-avatar-from-post-kickoff.md` (mirrored into the app repo as `docs/club-server-cr-avatar-from-post.md`). Suggested hooks: the `PopupMenuButton` in `ui/artwork_detail_page.dart` and the `HandleAvatar` widget for the preview row.
