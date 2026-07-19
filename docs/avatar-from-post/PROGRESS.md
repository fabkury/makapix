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
- **2026-07-19** — App reply 0002 received: contract acked as-is, no changes requested. App implementation underway same day (artwork-detail ⋮ menu + preview-confirm dialog, mirroring web), riding the next Play alpha after 1.0.14+19, pointed at prod. No avatar-cache purge needed on their side (URL-keyed image cache + `/auth/me` re-fetch). No reply expected — silence from them means it shipped clean.

## Status: CLOSED (server/web side)

All server and web work is live on prod and verified; the message exchange is complete. Reopen only if the app team flags something from real-device testing.

## Open items

- [ ] Optional follow-up (out of scope): surface avatar attribution in the mod dashboard.
