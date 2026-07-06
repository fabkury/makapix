# UGC safety — progress

Update after every work session, newest first.

## 2026-07-06 — PRODUCTION LIVE; effort closed

- App team `0004`: prod **GO** (contract acked, first-run gate shipped,
  27 green app-side tests; playlist-report exclusion kept per our 0003a).
- PR #217 merged → `make deploy` on /opt/makapix. Verified on prod:
  site 200, `moderation` key in makapix.club/api/v1/config (prod URLs),
  migration `a6045606b0a3` at head, MQTT subscribers reconnected clean,
  About/privacy content serving, and a live smoke report → 201 + alert
  email to acme@ + `new_report` notifications to all 3 moderators.
- Message `0005` (prod live) sent; `message/` thread archived to
  `docs/ugc-safety/messages/`. Two open smoke-test reports (reason
  `other`, "please ignore") left in the dev + prod mod queues — dismiss
  them from mod-dashboard at leisure.
- Follow-ups (out of scope, recorded): formal ToS page + signup checkbox
  (D26, owner decision); migrate remaining `get_client_ip` callers to the
  trusted-IP helper (D23b); PRE-EXISTING prod bug found during deploy
  verification: `PostNotificationPayload.owner_id: UUID` vs integer
  `post.owner_id` — follower new-post MQTT notifications have failed
  silently since ~2025-10; needs its own fix.

## 2026-07-06 — Phases 1–3 implemented, live on dev

- **Backend (Phases 1+2)** committed: reports hardening (anonymous reports w/
  trusted-IP rate limits, target validation, D9 public_sqid fix, mod_notes,
  reporter_ip anon-only + 04:15 ET sweep, extended reason codes, email +
  new_report alerting w/ 6 h throttle, report_resolved loop, `moderation`
  config block) and blocking (user_blocks, block/unblock//me/blocks,
  is_blocked_by_viewer, one-way visibility filtering on feeds/search/
  comments/reactions/notifications/browse, symmetric interaction guards).
  Migration `a6045606b0a3` applied on dev. 38 new tests; full suite green.
- Two extra latent bugs fixed en route: `Report.updated_at` 500 on create;
  `decode_user_sqid` integer overflow on arbitrary sqid strings (500 on
  follow/block of a nonsense sqid).
- **Web UI (Phase 3)**: ReportDialog (config-driven reasons, logged-out
  capable), report affordances on post overlay + post page + comments (both
  renderers) + profiles, block/unblock + blocked-state banner on profiles,
  Blocked-users section in settings, mod-dashboard reason/reporter/target
  rendering, About Rules ("What's not allowed" + zero tolerance) &
  Moderation ("Reporting content"/"Blocking users"/"Contact") sections,
  privacy page IP-retention line (effective date bumped). Typecheck clean.
- **Verified live on dev**: `moderation` key in /api/v1/config with per-env
  URLs; anonymous report E2E → 201 + real alert email to acme@makapix.club
  (Resend id logged) + new_report notifications to all 3 moderators.
- App team replied (`0002-app-…`, same day): contract v1 acked, first-run
  rules gate confirmed (D26 satisfied app-side), logged-out browsing
  confirmed (logged-out reporting is first-class for them), ETA ≈1–2 days
  then manual E2E against dev. Our `0003-server-…` announces the dev go
  signal and answers their two clarifications (playlist posts are valid
  `post` targets — their call; `new_report` is a system notification with
  null post fields, summary in `content_title`).
- Next: app team manual E2E on development.makapix.club → `0004-app-…`
  with prod go/no-go.

## 2026-07-06 — kickoff

- Audited existing moderation surface (report model/router/dashboard exist;
  no user-facing report UI; no blocking anywhere; latent user-target UUID bug;
  zero report tests).
- Owner interview → D1–D8 recorded in DECISIONS.md.
- PLAN.md + API-CONTRACT.md (frozen v1) written; independent fresh-eyes review
  incorporated.
- Kickoff message `0001-server-ugc-safety-kickoff.md` sent to the app team via
  `message/`.

## Status

| Phase | Status |
|---|---|
| 0 — plan + contract + kickoff message | ✅ done |
| 1 — backend: reports hardening | ✅ done (2026-07-06) |
| 2 — backend: blocking | ✅ done (2026-07-06) |
| 3 — website UI + About content | ✅ done (2026-07-06) |
| 4 — dev deploy + joint E2E | ✅ done (2026-07-06) |
| 5 — production flip + archive | ✅ done (2026-07-06, PR #217) |
