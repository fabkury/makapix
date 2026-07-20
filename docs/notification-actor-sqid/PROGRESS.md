# notification-actor-sqid — Progress

Feature: notifications-page polish — each notification card shows the actor's avatar (left, click → `/u/{actor_public_sqid}`, with a type-glyph badge overlay) and the post artwork (right, click → `/p/{content_sqid}`). Enabler: additive nullable `actor_public_sqid` field on social notification payloads (REST list + MQTT), resolved at read/publish time via the `actor` relationship (no migration; historical rows covered; deleted/anonymous actors → null).

## Log

- **2026-07-20** — Kickoff. App-team message 0001 pushed to app repo (`docs/club-server-cr-notification-actor-sqid.md`, commit 36aa508), mirrored here in `messages/`. Backend: `actor_public_sqid` property on `SocialNotification` model, field on `SocialNotificationBase` schema, `selectinload(actor)` in `list_notifications`, field added to MQTT broadcast dict; MQTT protocol doc updated. Website: notifications page card polish (clickable avatar + badge, clickable artwork).
- **2026-07-20** — Implemented on `develop` (495b41d) and verified on dev:
  - 5 new tests in `api/tests/test_social_notification_actor_sqid.py` + blocks suite pass; `make check` clean; web typecheck/lint clean.
  - Live REST verified: `GET /v1/social-notifications/` on dev returns `actor_public_sqid` for historical rows (read-time resolution — no backfill needed).
  - Live MQTT verified end-to-end: real notification published via the service through the dev broker, received by a `webclient` subscriber with correct `actor_public_sqid`; test row deleted afterward.
  - Note found during verification: the `MQTT_WEBCLIENT_PASSWORD` line in `deploy/stack/.env.dev` ends with a CR (`\r`, CRLF line ending). Docker Compose strips it so real clients work — but tooling that reads the file raw (grep/cut) gets a wrong password. Cosmetic; consider normalizing line endings.
  - Remaining: owner click-test of the UI on dev; app-team reply 0002; then PR develop → main + prod deploy.
