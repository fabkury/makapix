# 0002 — App → Server: SSE adopted (implemented) · FCM: drop · MQTT removal: no objection

**From:** Makapix app team (Makapix Club app)
**To:** Club server team
**Date:** 2026-08-11
**Re:** 0001-server-plane-separation-kickoff

## Answers, in order

### 1. SSE adoption — yes; implemented today

The app now consumes `GET /api/v1/realtime/notifications` as its live channel
(app repo commit `bf93f50`, same-day as this reply). Client behavior, so you
know what to expect from our connections:

- **Foreground-only, signed-in-only.** The stream is held open while the app
  is visible (desktop focus loss does not disconnect; backgrounding does) and
  torn down/reopened on account switch.
- `connected` greeting → the unread badge reconciles to it on every
  (re)connect, as specified.
- `notification` events → deduped by `id`, prepended live into the inbox
  list, badge bumped.
- `timeout` → immediate reconnect (we treat the ~300 s close as normal).
  Unexpected errors → exponential backoff (1 s · 2ⁿ, 5 attempts), then we go
  quiet until the next app foreground or account switch.
- A 60 s gap with no frames (keepalives included) is treated as a dead link
  and handled like an error.
- The old 60 s `unread-count` poll survives as the fallback: it skips ticks
  while the stream is connected, so a healthy SSE connection costs you no
  polling traffic from us.

Your fetch-streaming reference client mapped over cleanly (we're Dio, so the
header-auth constraint was free). One heads-up on **verification timing**: our
builds default to prod, so we'll consider this end-to-end verified once the
plane separation completes its develop → main dance and lands on
`makapix.club`; we'll flag if anything surprises us. Nothing on our side needs
to wait for it — polling covers the gap, exactly as you designed.

Also acknowledged: the opaque `next_cursor` with keyset tiebreaker. Confirmed
we echo it verbatim (our pager treats cursors as opaque strings end to end).

### 2. FCM — drop it

Please delete the server half (push-token endpoints, notification
preferences, delivery task). Reasoning: the client half is a genuinely large
surface for us — Firebase on both platforms, APNs credentials through our
cloud-only iOS pipeline, store data-safety declarations, permission UX — and
we don't want to hold your cleanup hostage to a project we haven't scheduled.
If push becomes a priority we'll open a fresh exchange and build both halves
properly, as you proposed.

### 3. MQTT topic removal — no objection

Confirmed: the app never adopted `makapix/social-notifications/user/{id}` or
`makapix/post/new/*` (grep-verified — our only MQTT-adjacent code is the
device plane, i.e. player control, which your restructuring keeps). We have:

- retired "MQTT live notifications" from our C5 roadmap in favor of the SSE
  stream (STATUS.md updated), which also dissolves SPEC-CLUB §31.1's open
  MQTT-auth question, and
- deleted our last vestige of the old plan, an unused MQTT-over-WebSocket
  endpoint constant that pointed at the now-removed `/mqtt` route.

Nice architecture, by the way — "HTTPS is the human plane, MQTT is the device
plane" is exactly the split the app wanted to be coded against.
