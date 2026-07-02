# mkpx-upload — Progress

Update this file as work lands. One line per event, newest last.

## Status: PLANNING

- [x] 2026-07-02 — Recon (API upload flow, web menus, .mkpx format in reference/app/)
- [x] 2026-07-02 — Owner decisions D1–D10 collected (PLAN.md §2)
- [x] 2026-07-02 — PLAN.md + API-CONTRACT.md drafted
- [ ] Fresh-eyes review (2 agents) + plan revision
- [ ] Message #1 (kickoff + contract) committed to message/ and pushed
- [ ] **GATE: owner go-ahead to start implementation**

## Phase 1 — Server core (develop) + Caddy guard (main)

- [ ] Alembic migration (posts.mkpx_file_bytes, posts.mkpx_attached_at)
- [ ] vault.py: constants + validate/save/delete/path helpers
- [ ] vault_serving.py + main.py: mkpx/ guard on public static mounts
- [ ] posts.py: upload mkpx field; attach/replace; detach; replace-artwork drop;
      permanent-delete + cleanup task deletions
- [ ] artwork.py: GET /d/{sqid}.mkpx (auth-required)
- [ ] storage_quota.py: count mkpx bytes
- [ ] schemas.py + system.py: post fields + config advertisement
- [ ] Tests green (api/tests/test_mkpx.py)
- [ ] Caddy guard (respond /mkpx/* 404, both vault blocks) landed in main + caddy restarted
      — **required before joint testing with real files; blocking for prod flip**

## Phase 2 — Web UI (develop)

- [ ] SelectedPostOverlay menu items (download; owner attach/replace/detach)
- [ ] /p/[sqid] menu items
- [ ] api.ts helpers; post state refresh after attach/detach

## Phase 3 — Joint testing (development.makapix.club)

- [ ] Server smoke checklist (curl): upload+mkpx, attach, detach, download 401/200,
      vault-dev.makapix.club/mkpx/* → 404, /api/vault/mkpx/* → 404
- [ ] App team E2E confirmed (via message/)
- [ ] Contract frozen (app team ack in message #2, open questions §9 resolved)

## Phase 4 — Flip

- [ ] PR develop → main; prod deploy; prod config advertises mkpx
- [ ] Prod smoke test; app confirms against prod
- [ ] Announce in message/

## Message log

| # | File | Direction | Summary |
|---|------|-----------|---------|
| 0001 | (pending) | server → app | Kickoff: contract, decisions, questions |
