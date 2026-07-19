# avatar-from-post — PROGRESS

- **2026-07-19** — Feature designed, implemented, and **shipped to prod** (PR #240):
  - Owner decisions locked (any viewable artwork + internal attribution; BMP→PNG transcode; animation preserved; avatar+name preview row).
  - Backend: `users.avatar_source_post_id` (migration `114d77aaf3d8`, applied dev + prod), `POST /user/{id}/avatar/from-post`, attribution cleared on manual upload/delete, shared auth helper `_authorize_avatar_edit`. OpenAPI regenerated.
  - Tests: `api/tests/test_avatar_from_post.py` — 17/17 passing; full `make check-full` gate green.
  - Web: `UseAsAvatarDialog` + enabled menu item in `SelectedPostOverlay` + `setAvatarFromPost`/`getMe` in `lib/api.ts`.
  - Live API e2e on dev: 201 setting a user's avatar from another user's 64-frame animated GIF post — byte-identical snapshot in the avatar vault, served via vault-dev with `image/gif`, attribution recorded; DELETE avatar cleared attribution and removed the file. Test mutation reverted.
  - Prod verified post-deploy: alembic head `114d77aaf3d8`, endpoint routed (401 unauthenticated), site 200.
  - Kickoff message 0001 sent to app team (committed + pushed to app repo as `docs/club-server-cr-avatar-from-post.md`).

- **2026-07-19** — Owner click-tested the web dialog on makapix.club: working as intended.

## Open items

- [ ] App reply 0002 (integration timeline / answers to questions in 0001).
- [ ] Optional follow-up (out of scope): surface avatar attribution in the mod dashboard.
