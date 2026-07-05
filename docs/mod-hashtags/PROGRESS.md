# Moderator Hashtags — Progress

Update this file after every work session. Newest entries first.

## 2026-07-05 — Implementation (Phases 1–3)

- Backend: `posts.mod_hashtags` column + hand-written migration
  (`b3d9a1c40f21`), shared `normalize_hashtags` helper adopted in create /
  upload / PATCH / import job, PATCH rewritten (FOR UPDATE lock, mod-tag
  merge, `hidden_by_mod` mod-only, cache invalidation), new
  `PUT /post/{id}/mod-hashtags` endpoint (audit + notification +
  invalidation), `mod_hashtags` on `schemas.Post`, `ModHashtagsUpdate`,
  `max_mod_hashtags_per_post` in config, push title, export metadata.
- Tests: `api/tests/test_mod_hashtags.py` (24 tests) — full suite green
  (41 files, 4 chunks OK).
- Web: shared `MONITORED_HASHTAGS` constant (`web/src/lib/constants.ts`),
  post page (shield markers, owner edit form excludes mod tags + read-only
  chips, mod editor with monitored quick-pick chips, kebab menu item),
  notifications branch, MQTT type union, about-page rules sentence.
- Docs: `docs/http-api/posts.md` updated.
- Dev stack rebuilt; migration applied at startup.

## 2026-07-05 — Planning

- Explored codebase (hashtag storage, monitored-tag filtering, moderation
  roles/audit, notification plumbing, web UI surfaces, message/ convention).
- Collected owner decisions (D1–D7) and made engineering decisions (D8–D16) —
  see DECISIONS.md.
- Wrote PLAN.md and froze API-CONTRACT.md v1.
- Plan reviewed by two independent review agents (backend-correctness lens +
  product/contract lens). All verified findings incorporated — headline items:
  row-locking both write paths (D17), artwork-only target (D18), config-key
  discovery signal for the app (D19), hand-written migration (D20),
  `hidden_by_mod` PATCH fix in passing (D21), monitored quick-pick chips in
  the mod editor (D22), and a wire-level contract fix (notification diff is
  delivered in `comment_preview`, not `extra_preview`).
- Next: send kickoff message to app team (`message/0001-server-mod-hashtags-kickoff.md`),
  then implement Phase 1 (backend) on `develop` after owner go-ahead.

## Status

| Phase | Status |
|-------|--------|
| Plan + contract | ✅ done |
| Message to app team | ⏳ pending |
| Phase 1 — backend | not started |
| Phase 2 — web UI | not started |
| Phase 3 — docs/http-api | not started |
| Phase 4 — dev verification | not started |
| Prod flip | not started |
