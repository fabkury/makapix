# notification-actor-sqid — Progress

Feature: notifications-page polish — each notification card shows the actor's avatar (left, click → `/u/{actor_public_sqid}`, with a type-glyph badge overlay) and the post artwork (right, click → `/p/{content_sqid}`). Enabler: additive nullable `actor_public_sqid` field on social notification payloads (REST list + MQTT), resolved at read/publish time via the `actor` relationship (no migration; historical rows covered; deleted/anonymous actors → null).

## Log

- **2026-07-20** — Kickoff. App-team message 0001 pushed to app repo (`docs/club-server-cr-notification-actor-sqid.md`, commit 36aa508), mirrored here in `messages/`. Backend: `actor_public_sqid` property on `SocialNotification` model, field on `SocialNotificationBase` schema, `selectinload(actor)` in `list_notifications`, field added to MQTT broadcast dict; MQTT protocol doc updated. Website: notifications page card polish (clickable avatar + badge, clickable artwork).
