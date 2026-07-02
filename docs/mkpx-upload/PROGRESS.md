# mkpx-upload — Progress

Update this file as work lands. One line per event, newest last.

## Status: PLANNED — awaiting owner go-ahead (gate below)

- [x] 2026-07-02 — Recon (API upload flow, web menus, .mkpx format in reference/app/)
- [x] 2026-07-02 — Owner decisions D1–D10 collected (PLAN.md §2)
- [x] 2026-07-02 — PLAN.md + API-CONTRACT.md drafted (v1)
- [x] 2026-07-02 — Fresh-eyes review, 2 independent agents (soundness; production/VPS fit)
- [x] 2026-07-02 — Findings adjudicated, plan + contract revised to v2. Key fixes:
      singular `/post` paths; soft-delete 404s owner too; account-deletion task deletes
      mkpx; artwork-kind guard; frozen error table (new codes mkpx_invalid/mkpx_too_large);
      separate quota aggregate; vault free-space floor + daily disk beat task; canary-based
      guard verification; rollback paragraph; upload-failure artwork cleanup; Caddy
      request_body cap; web gated on config; detach costs no rate-limit token
- [x] 2026-07-02 — Message #1 (kickoff + contract) committed to message/ and pushed
- [ ] **GATE: owner go-ahead to start implementation**

## Phase 1 — Server core (develop) + Caddy guard (main)

- [ ] models.py columns + has_mkpx property; Alembic migration (single head verified)
- [ ] errors.py: mkpx_invalid, mkpx_too_large
- [ ] vault.py: magic/size validation (streaming), ensure_vault_headroom (also wired into
      artwork save), mkpx path/save/delete helpers
- [ ] vault_serving.py: mkpx/ guard post-normalization (+ encoded-variant tests)
- [ ] posts.py: upload mkpx field (validate-first, orphan cleanup); attach/replace
      (artwork-kind guard); detach; replace-artwork drop; permanent-delete removal
- [ ] tasks.py: cleanup_deleted_posts + delete_user_account_task delete mkpx (independent
      of `if formats:`); daily vault free-space beat task
- [ ] artwork.py: GET /d/{sqid}.mkpx (auth, can_access_post, declared before generic route)
- [ ] storage_quota.py: separate SUM(posts.mkpx_file_bytes) aggregate
- [ ] schemas.py + system.py: post fields + config advertisement
- [ ] Compose overlays: request_body max_size 64MB on /api/* labels (dev + prod)
- [ ] Tests green (api/tests/test_mkpx.py — full list in PLAN §6.12)
- [ ] Caddy guard (respond /mkpx/* 404, both vault blocks) landed in main + caddy
      restarted at low traffic — **canary-verified on dev** (404 while canary file exists
      + positive control 200) — required before joint testing; blocking for prod flip

## Phase 2 — Web UI (develop)

- [ ] Config gate (upload.mkpx.enabled) for all mkpx menu items
- [ ] SelectedPostOverlay menu items (download; owner attach/replace/detach)
- [ ] /p/[sqid] menu items
- [ ] api.ts helpers; post state refresh after attach/detach
- [ ] Replace-artwork flow warns that the layers file will be dropped

## Phase 3 — Joint testing (development.makapix.club)

- [ ] Server smoke checklist (curl): upload+mkpx, attach, detach, download 401/200
- [ ] Leak canaries: vault-dev.makapix.club/mkpx/* → 404 and /api/vault/mkpx/* → 404
      while canary exists; artwork positive control 200
- [ ] Concurrency/memory test: scripted parallel 50 MB uploads, watch docker stats
      (dev api 768 MB cap = canary)
- [ ] Backup cron verified; mkpx/ confirmed included (or gap documented)
- [ ] App team E2E confirmed (via message/)
- [ ] Contract frozen (app team ack in message #2, open questions §11 resolved)

## Phase 4 — Flip

- [ ] PR develop → main; prod deploy; prod Caddy guard canary re-check
- [ ] Prod config advertises mkpx; prod smoke test; app confirms against prod
- [ ] Announce in message/

## Message log

| # | File | Direction | Summary |
|---|------|-----------|---------|
| 0001 | message/0001-server-mkpx-upload-kickoff.md | server → app | Kickoff: contract, decisions, what they can build now, timeline, questions Q1–Q6 |
