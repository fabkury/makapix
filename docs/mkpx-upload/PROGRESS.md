# mkpx-upload — Progress

Update this file as work lands. One line per event, newest last.

## Status: LIVE ON DEV, guards fully deployed — awaiting app-team E2E (message #4)

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
- [x] 2026-07-02 — **GATE passed**: owner go-ahead; app team building in parallel

## Phase 1 — Server core (develop) + Caddy guard (main)

- [x] models.py columns + has_mkpx property; migration 2ca55835e75a (single head verified,
      hand-trimmed to exclude unrelated autogen drift; applied on dev)
- [x] errors.py: mkpx_invalid, mkpx_too_large
- [x] vault.py: magic/size validation (streaming), ensure_vault_headroom (also wired into
      artwork save), mkpx path/save/delete helpers, write_stream_atomic
- [x] vault_serving.py: mkpx/ guard post-normalization (+ encoded-variant tests)
- [x] posts.py: upload mkpx field (validate-first, orphan cleanup); attach/replace
      (artwork-kind guard); detach; replace-artwork drop; permanent-delete removal
- [x] tasks.py: cleanup_deleted_posts + delete_user_account_task delete mkpx (independent
      of `if formats:`); check_vault_free_space beat task (every 6h)
- [x] artwork.py: GET /d/{sqid}.mkpx (auth, can_access_post, declared before generic route)
- [x] storage_quota.py: separate SUM(posts.mkpx_file_bytes) aggregate
- [x] schemas.py + system.py: post fields + config advertisement
- [x] Compose overlays: request_body max_size 64MB on /api/* labels (dev + prod)
- [x] Tests green: 25 in api/tests/test_mkpx.py; full suite 372 passed (2026-07-02)
- [x] 2026-07-02 — **Caddy guard DEPLOYED**: PR #206 merged to main, prod checkout
      pulled (fast-forward, Caddyfile only), `docker restart caddy`. Canary-verified:
      vault-dev/mkpx/06/0b/57e48b27-….mkpx → 404 while on disk; dev + prod artwork
      positive controls 200; prod /mkpx/ probe 404; makapix.club + both API healths 200;
      dev basic auth intact. The leak window is closed.

## Phase 2 — Web UI (develop)

- [x] Config gate (upload.mkpx.enabled) via getMkpxConfig() for all mkpx menu items
- [x] SelectedPostOverlay menu items (download; owner attach/replace/detach); CardGrid
      forwards owner_id/has_mkpx
- [x] /p/[sqid] menu items; post state refreshed from attach/detach responses
- [x] api.ts helpers (getMkpxConfig/downloadMkpx/attachMkpx/detachMkpx)
- [x] editor.tsx replace flow warns that the layers file will be dropped
- [x] typecheck + lint clean; dev web image rebuilt (`make rebuild` 2026-07-02)

## Phase 3 — Joint testing (development.makapix.club)

- [x] 2026-07-02 server smoke (curl, public dev URL): config advertises mkpx; upload+mkpx
      201; authed download 200 byte-identical (application/x-mkpx, no-store); unauth 401;
      detach/re-attach OK; bad magic → 422 mkpx_invalid; /api/vault/mkpx/* → 404
- [x] 2026-07-02 — vault-dev.makapix.club/mkpx/* → 404 (Caddy guard live, see Phase 1)
- [x] 2026-07-02 — Concurrency/memory test: 4 parallel ~45 MB uploads, all 201 in 2.5 s
      wall; api peak 161 MiB / 768 MiB cap (streaming path holds). Test posts detached
      (files removed) + soft-deleted; vault mkpx/ back to 48 K (CXRi canary only)
- [x] 2026-07-02 — Backup check: **NO backup cron installed on the host** (crontab empty,
      /etc/cron.d has none) — docs/deployment.md's suggested vault backup was never set
      up. mkpx/ rides under the vault root, so any future whole-vault backup includes it
      automatically. GAP: users' irreplaceable layer sources currently have no backup;
      flagged to owner 2026-07-02
- [ ] Web UI manual pass (behind dev basic auth) — menus, attach/detach, download
- [ ] App team E2E confirmed (via message/)
- [x] 2026-07-02 — Contract FROZEN: app ack in 0002, all §11 questions answered; cap
      stays 50 MB (owner call, relayed in 0003)

## Phase 4 — Flip

- [ ] PR develop → main; prod deploy; prod Caddy guard canary re-check
- [ ] Prod config advertises mkpx; prod smoke test; app confirms against prod
- [ ] Announce in message/

## Message log

| # | File | Direction | Summary |
|---|------|-----------|---------|
| 0001 | message/0001-server-mkpx-upload-kickoff.md | server → app | Kickoff: contract, decisions, what they can build now, timeline, questions Q1–Q6 |
| 0002 | message/0002-app-mkpx-upload-ack.md | app → server | Contract ack (freeze), answers Q1–Q6, build status, 16 MiB cap suggestion |
| 0003 | message/0003-server-dev-live.md | server → app | Re: 0002 (frozen, cap stays 50 MB); dev advertises enabled:true; E2E can start; smoke results; test post CXRi |
