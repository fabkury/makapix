# avatar-from-post — PROGRESS

- **2026-07-19** — Feature designed and implemented on `develop`:
  - Owner decisions locked (any viewable artwork + internal attribution; BMP→PNG transcode; animation preserved; avatar+name preview row).
  - Backend: `users.avatar_source_post_id` (migration `114d77aaf3d8`, applied on dev), `POST /user/{id}/avatar/from-post`, attribution cleared on manual upload/delete, shared auth helper `_authorize_avatar_edit`. OpenAPI regenerated.
  - Tests: `api/tests/test_avatar_from_post.py` — 17/17 passing.
  - Web: `UseAsAvatarDialog` + enabled menu item in `SelectedPostOverlay` + `setAvatarFromPost`/`getMe` in `lib/api.ts`. Typecheck/lint clean.
  - Kickoff message 0001 sent to app team (committed in app repo as `docs/club-server-cr-avatar-from-post.md`).

## Open items

- [ ] Manual e2e on development.makapix.club (set avatar from another user's animated post; navbar updates live; DB attribution recorded).
- [ ] PR `develop` → `main`, prod deploy.
- [ ] App reply 0002 (integration timeline / questions).
- [ ] Optional follow-up (out of scope): surface avatar attribution in the mod dashboard.
