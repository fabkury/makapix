# 0001 — Server → App: notification plane separation — SSE stream offered, FCM decision requested (kickoff)

**From:** Club server team
**To:** Makapix app team (Makapix Club app)
**Date:** 2026-08-10
**Status:** Implemented on develop; deploying to development.makapix.club, prod to follow the normal develop → main dance

## Summary

We have restructured notification delivery around one principle: **HTTPS is
the human plane, MQTT is the device plane** (assessment + rationale in
`docs/notification-architecture/` in the server repo). Concretely:

- The website no longer talks to the MQTT broker; it consumes a bearer-
  authenticated **SSE stream**. The shared-password browser MQTT path is
  deleted (broker account, WebSocket listener, Caddy `/mqtt` route).
- The MQTT topics `makapix/social-notifications/user/{id}` and
  `makapix/post/new/*` are **removed**. Your STATUS.md lists MQTT live
  notifications as "phase C5, not started" — consider C5 obsolete; the SSE
  stream below is its replacement, and SPEC-CLUB §31.1's open MQTT-auth
  question dissolves with it.

**Nothing you use today breaks.** The app consumes notifications via
`/api/v1/social-notifications/` REST polling, which is unchanged (one
improvement: `next_cursor` is now an opaque string with a keyset tiebreaker —
you already echo it verbatim, and old timestamp cursors remain accepted).
The unread count is also now block-filtered and always consistent with the
list.

## Offer: the SSE stream (live channel, replaces the 60 s poll when foregrounded)

```
GET /api/v1/realtime/notifications
Authorization: Bearer <access_token>
Accept: text/event-stream
```

Events:

| Event | Data | Meaning |
|-------|------|---------|
| `connected` | `{"unread_count": N}` | Greeting on every (re)connect — authoritative; reconcile your badge to it. |
| `notification` | full REST item (same shape as the list, incl. `id`, `is_read`) | New notification — dedupe by `id`. |
| `: keepalive` | — | Comment frame every ~15 s of silence. |
| `timeout` | `{"message": ...}` | Bounded-lifetime close (~300 s); reconnect immediately. |

Delivery is push-based server-side (no polling cost — hold it open as long as
the app is foregrounded). REST remains your offline catch-up; full contract in
`docs/http-api/notifications.md`. The website's client
(`web/src/hooks/useNotificationsSSE.ts`) is a working reference: fetch-
streaming (headers, so no EventSource), immediate reconnect on `timeout`,
exponential backoff on errors.

## Decision requested: FCM push

The server half of mobile push exists and is dormant: `POST /v1/me/push-tokens`
(+ delete), per-type prefs at `/v1/me/notification-preferences`, and a Celery
delivery task gated on an unset `FCM_CREDENTIALS_FILE`. The app has no
`firebase_messaging` dependency. A permanent half-integration is the worst of
both worlds, so please pick a direction:

1. **Build it** — you add the FCM client half (token registration on login,
   handlers, deep links); we wire the service-account credentials on prod and
   keep the server half. Wake-up notifications with the app closed become real.
2. **Drop it** — we delete the server half (endpoints, prefs, task) and
   re-add it properly if/when push becomes a priority.

## Questions for you

1. SSE adoption: interested, and roughly when? (No urgency — polling keeps
   working indefinitely.)
2. FCM: build or drop (above)?
3. Any objection to the removed MQTT topics? (As far as we can tell you never
   adopted them; flagging in case anything unreleased depends on them.)

Reply as `0002-app-…` in the server repo `docs/notification-architecture/messages/` when convenient.
