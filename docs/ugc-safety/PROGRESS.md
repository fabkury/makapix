# UGC safety — progress

Update after every work session, newest first.

## 2026-07-13 — mod deletions no longer misattributed to authors

- Found while reviewing prod data: BOTH moderator deletion paths set
  `deleted_by_owner=true` on comments. The report take-down path at least
  stamped the body `"[deleted by moderator]"`; a direct moderator
  `DELETE /comments/{id}` was byte-for-byte identical to a self-delete and
  wrote no audit log. Deletion also destructively overwrote the body, so
  mod undelete resurrected a literal `"[deleted]"` husk.
- Fix (comments + blog_post_comments symmetrically):
  - New `deleted_by_mod` flag (additive; app/web contracts unchanged for
    existing fields). Migration backfills rows whose body is
    `"[deleted by moderator]"` (2 rows on prod, from the 2026-07-07 manual
    PII cleanup).
  - New `original_body` column preserves the pre-deletion text (mod-visible
    via the Pulse feed preview); undelete restores it. New mod-only
    `POST /comments/{id}/purge-original` permanently scrubs it for
    PII/illegal content (audit-logged `purge_comment_body`; 🧹 button on
    deleted-comment Pulse items).
  - Direct moderator deletes now audit-log `take_down_comment`, and every
    visibility filter / count treats `deleted_by_mod` like `deleted_by_owner`.
  - Tombstone text is public: `"[deleted]"` for self-deletes,
    `"[deleted by moderator]"` for mod deletes (owner decision).
- Tests in `api/tests/test_comment_mod_deletion.py` (12 cases).

## 2026-07-07 — report action "delete" renamed to "take_down"

- Incident: post 3647 (`5PpX`) vanished from feeds — the app team's prod
  smoke-test report ("please ignore") was resolved with action "delete" in
  the mod dashboard, which sets `visible=false` (no hard delete). Post
  restored by hand (`visible=true`).
- Root cause was wording: the reports-queue "Delete" button sat next to a
  real permanent-delete elsewhere in the dashboard but only takes content
  down. Renamed the action to `take_down` end to end: schemas + router
  (with `delete` kept as a deprecated write alias, normalized on write;
  legacy rows still readable), audit log now `take_down_post` /
  `take_down_comment`, dashboard button relabeled "Take down" with a
  tooltip. Tests added for both the new value and the alias.

## 2026-07-06 — app team adopted terms_url (0007)

- App reply `0007`: first-run gate now links BOTH guidelines_url and
  terms_url with an explicit agree line (adaptive to config contents);
  existing installs re-prompted once (their local gate version 1→2); ships
  on their next Play build (inert until terms_url in config — already live
  on prod, so it activates on release). No server action needed.
- Note: server-side acceptance recording already covers app users — they
  sign up through the same /v1 endpoints, so `terms_version_accepted` is
  stamped regardless of client. Their client-side gate is an extra signal.
- ToS-change protocol confirmed both sides: material change → bump
  effective date + TERMS_VERSION → numbered message → they re-show gate.

## 2026-07-06 — D26 closed: formal ToS live

- Owner interview → notice-line acceptance (no checkbox), continued-use for
  existing users, standard plain-English content, server-side acceptance
  record. Decisions appended to D26 in DECISIONS.md.
- Shipped: `/terms` page (privacy-page voice/styles); consent lines on the
  email signup form + under the GitHub button; cross-links from /privacy and
  About; `users.terms_version_accepted` (migration `b7f2c9d4e1a8`) stamped
  at all three self-signup paths (email register + both GitHub OAuth
  creation paths; moderator-created placeholder accounts intentionally not
  stamped); `terms_url` added to the /v1/config moderation block (additive).
- Message `0006-server-ugc-safety-terms-url.md` → app team (informational;
  they may point their first-run gate at terms_url instead of
  guidelines_url).
- Maintenance rule: bump the page effective date and
  `api/app/constants.py:TERMS_VERSION` **together** on material changes.

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
  trusted-IP helper (D23b). The pre-existing new-post MQTT notification
  bug found during deploy verification (`PostNotificationPayload.owner_id`
  UUID vs int, broken since ~2025-10) was FIXED same day — PR #218,
  deployed to prod 2026-07-06, wire-verified on the prod broker; see
  docs/mqtt-protocol/03-notifications.md "Resolved Issues".

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
