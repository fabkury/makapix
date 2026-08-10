# Progress — Notification Architecture

## 2026-08-10 — Plane separation IMPLEMENTED (Phases 1+2, one change set)

Owner approved implementing the principle "HTTPS = human plane, MQTT = device
plane" production-grade. Owner decisions: delete the `makapix/post/new/*`
fan-out entirely (audience-less after `webclient` removal; also closes
appraisal D27 by deletion); keep the FCM server half dormant + ask the app
team to build-or-drop it (messages/0001); retention = read > 90 d, all >
365 d; riders = delete `/demo` + `/mqtt/demo` + `/mqtt/bootstrap`, migrate
web's notification REST calls to `/api/v1`, badge e2e, gen-passwd self-heal.

**Backend:** `services/event_bus.py` generalizes the player_events bus into
`UserEventBus` ×2 (`player_bus`, `notification_bus` — isolated instances, the
plane invariant). `_dispatch_notification` replaces the MQTT broadcast:
block-gated (D10) bus publish of the full REST payload + FCM enqueue; the
~15 s blocking broker publish in request handlers is gone. Unread count is a
block-filtered DB COUNT (partial index); the Redis counter and its whole
drift class (cache_incr/decr/get_int/set_int) are deleted. List cursor gains
a `(created_at, id)` tiebreaker via the shared pagination helper (legacy ISO
cursors still accepted). `/v1/realtime/notifications` is push-based (subscribe
→ greeting with count → bus events; DB connection released after the
greeting; 300 s lifetime kept). `NotificationType` StrEnum (12 types) in
constants.py; push titles completed. Comment deletion scrubs
`comment_preview` (N8). Nightly `cleanup-social-notifications` beat task
(04:45 ET) + healthchecks heartbeat slug.

**Deleted MQTT surface:** `mqtt/notifications.py` + posts.py publish calls,
`PostNotificationPayload`, `mqtt_legacy.py`, `worker/mqtt_player_stub.py`,
`/mqtt/bootstrap` + `/mqtt/demo` (router renamed `rate_limit.py`), broker WS
listener 9001, `webclient` ACL stanza + svc_backend notification write
grants, gen-passwd webclient lines (+ active `mosquitto_passwd -D` self-heal
of the persisted passwords file), compose build args/env + Caddy `/mqtt`
labels (handles renumbered), `.env.example` entry.

**Web:** `hooks/useNotificationsSSE.ts` (fetch-streaming, modeled on
usePMDSSE); `SocialNotificationsContext` reworked — `enabled` (token) prop
instead of `userId`, id-dedupe registry, authoritative `connected`-greeting
reconciliation, refetch-on-focus/online, `/api/v1/*` paths, dead members
(`markAsRead`, `clearNotifications`) dropped. Deleted `lib/mqtt-client.ts`,
`hooks/useSocialNotifications.ts`, `pages/demo.tsx`, the `mqtt` npm dep,
transpilePackages entry, and both Dockerfile MQTT build args. `/p/undefined`
guard on sqid-less notification rows.

**Tests:** actor-sqid broadcasts rewritten against the bus; new
`test_event_bus.py` (incl. bus-isolation invariant) +
`test_notification_architecture.py` (dispatch block gating, unread count,
cursor incl. legacy format, retention, preview scrub); deleted
`test_mqtt_post_notifications.py`; Playwright `notification-badge.spec.ts`
(stubbed-SSE spec + real-login smoke gated on E2E creds).

**Docs:** new `docs/http-api/notifications.md` (REST + SSE contract);
mqtt-protocol 01/03, MQTT_PROTOCOL index, mqtt-api README, deployment.md,
security README/operations (H1 → Resolved by deletion), appraisal BACKLOG
S1/D24/D27 annotated; openapi.json regenerated (bootstrap/demo removed).

**Owner follow-ups:**
- [ ] Remove `MQTT_WEBCLIENT_PASSWORD=` from `/opt/makapix/deploy/stack/.env`
      (prod) and `/opt/makapix-dev/deploy/stack/.env.dev` (harmless until
      then — nothing reads it anymore).
- [ ] healthchecks.io: confirm the auto-created `cleanup-social-notifications`
      check after first prod run; set period 1 day + grace.
- [ ] After prod deploy: restart `makapix-prod-mqtt` (bind-mounted config;
      entrypoint self-heal removes the `webclient` passwd entry), then verify
      9001 closed.
- [ ] Optional hygiene: the `web_next_static` named volume accumulates chunks
      from every historical build (dev copies date to 2026-01), so old bundles
      containing the now-dead webclient password remain fetchable by hash on
      both envs. The served HTML references only the current build. The
      password is worthless (account deleted); prune the volume's stale
      chunks at leisure on prod + dev.

**Awaiting:** app team reply to messages/0001 (SSE adoption + FCM
build-or-drop).

## 2026-08-10 — Assessment delivered (no implementation decided)

- First-principles assessment of social-notification handling written to `README.md`,
  commissioned by the owner ("would we have built it differently from zero?").
- Scope locked by owner: social notifications only; judged on security & isolation,
  simplicity, reliability & catch-up; hard constraint single VPS / no new paid services.
- Method: three parallel code explorations (web consumption, native-app snapshot
  consumption, backend inventory) over develop @ 145bdf2; findings N1–N10 verified with
  file:line evidence during exploration.
- Headline: inbox/REST core is sound; delivery layer is sediment of three eras — browser
  MQTT (shared credential, live cross-user exposure = appraisal S1 residue), consumer-less
  SSE + FCM server halves, and REST polling doing the real work.
- Recommendation: plane separation (HTTPS = humans, MQTT = devices); Phase 1 core fixes →
  Phase 2 adopt hardened SSE + delete browser MQTT and the `webclient` broker account →
  Phase 3 app-team alignment on SSE/FCM.
- **Next step (owner decision):** whether to green-light Phase 1 and/or Phase 2.
  Nothing implemented yet.
