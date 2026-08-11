# Progress — Notification Architecture

## 2026-08-11 — FCM server half DELETED (app team's "drop", messages/0002)

Removed per the app team's explicit request: `services/push.py`, the four
`/v1/me/push-tokens` + `/v1/me/notification-preferences` endpoints (me.py
keeps only `/me/blocks`), the `send_push_notification` Celery task, the
`PushToken` model and `users.notification_prefs` column (hand-written drop
migration `a9b8c7d6e5f4`; **verified 0 rows / 0 non-default prefs on BOTH
envs pre-drop** — lossless), the FCM enqueue in `_dispatch_notification`
(dispatch is now purely the SSE bus), the `firebase-admin` dependency, the
`FCM_CREDENTIALS_FILE` compose plumbing on api+worker (both overlays), the
`FCM_CREDENTIALS_HOST_PATH` pointers in both host env files, the push
schemas, and the account-purge push-token step. Tests: `test_push_tokens.py`
deleted; harness-safety probe re-pointed at `cleanup_social_notifications`;
p1-security push test dropped (endpoint gone); account-deletion +
notification-architecture tests trimmed; `test_observability` updated for
the `?create=1` URL (missed by the morning's fix). OpenAPI: −245 lines.

Orphaned by design (owner decision — untouched, decommission at leisure):
the service-account JSON in `~/secrets/makapix/` and the Firebase cloud
project itself.

Verified on dev: migration applied at startup (head `a9b8c7d6e5f4`,
table+column gone), deleted endpoints 404, `/me/blocks` + SSE intact, full
suite green (70 files), live SSE push re-verified end-to-end post-edit.

If push ever returns: fresh message exchange, both halves built together
(per 0002's own framing).

## 2026-08-11 — App team replied (0002 + 0003): SSE adopted & device-verified, FCM = DROP

- **0002:** SSE implemented same-day in the app (their commit `bf93f50`) —
  foreground-only stream, greeting reconciliation, id-dedupe, immediate
  reconnect on `timeout`, backoff on errors, 60 s-silence dead-link detection;
  their 60 s poll remains as fallback but skips ticks while the stream is
  healthy. Opaque cursors confirmed echoed verbatim. MQTT topic removal: no
  objection (grep-verified never adopted); their C5 roadmap item retired,
  SPEC-CLUB §31.1 dissolved.
- **0002 decision — FCM: DROP.** They explicitly request deletion of the
  server half (push-token endpoints, notification preferences, delivery
  task); if push ever becomes a priority, a fresh exchange will build both
  halves properly.
- **0003:** end-to-end verified **on prod with a physical device** — reaction
  from the permanent test account lit a real phone's bell immediately via
  SSE. Shipping as Android 1.0.22; iOS follows. Exchange closed on their side.
- **Open on our side:** execute the FCM server-half deletion (push.py,
  /v1/me/push-tokens + notification-preferences endpoints, Celery task,
  PushToken model + migration, users.notification_prefs, firebase-admin dep,
  FCM_CREDENTIALS_FILE plumbing, the enqueue in _dispatch_notification,
  tests, openapi, docs) — awaiting owner go-ahead.

## 2026-08-11 — Healthchecks follow-up closed; latent O8 defect found and fixed

The owner's screenshot showed the `cleanup-social-notifications` check missing
— and so were ALL nine beat heartbeats. Root cause (verified on prod): the O8
observability effort shipped only the code half — `HEALTHCHECKS_PING_KEY` was
wired in compose (`${HEALTHCHECKS_PING_KEY:-}`) but present in no env file, so
the worker got an empty string and `register_beat_heartbeats()` no-op'd. The
dead-man's-switch was itself silently dead. Second latent defect: `_hc_ping`
lacked `?create=1`, so even with a key, first pings to nonexistent slugs would
have 404'd silently (the code comment claimed auto-create; the API disagrees).

Fixed 2026-08-11:
- Owner added the project Ping Key to `/opt/makapix/deploy/stack/.env.prod`
  (prod only — dev stays silent by design); worker recreated via compose
  (plain restart would keep the old env), key verified non-empty in-container.
- All nine checks created via one-time `?create=1` pings (9× HTTP 201).
- Signal path proven live: `cleanup_social_notifications` triggered → the
  check's ping log shows the distinct start+success pair.
- Code hardened: `_hc_ping` now always appends `?create=1` (future slugs
  self-create); `HEALTHCHECKS_PING_KEY` + `SENTRY_DSN` documented in
  `.env.example`; appraisal O8 row annotated.
- Beat schedule independently verified: the first scheduled 04:45 ET run
  fired on time 2026-08-11 (0 deletions, as expected after the manual run).

**Remaining (owner, optional):** tune each check's grace in the UI (defaults
1 d period / 1 h grace are correct for these daily tasks; the backup check
uses 3 h grace as a reference). Delete the placeholder "My First Check".

## 2026-08-10 — DEPLOYED TO PROD (PR #253, merge 4e7ddb3)

Pushed (rebased onto the 0003 actor-sqid docs commit → feature commit
`03a59aa`), PR #253 merged same day, `make deploy` on `/opt/makapix` ran
clean. `up -d` recreated mqtt/api/worker/web (mqtt env changed, so the
broker restart + gen-passwd self-heal happened as part of the deploy).

Prod verification, all green:
- Broker: listener 9001 gone; `webclient` purged from the persisted
  passwords file; all 4 svc_backend subscribers reconnected; physical p3a
  fleet devices re-attached over mTLS within seconds.
- HTTP: `/api/v1/realtime/notifications` → 401 unauthenticated; old
  `/mqtt` path → 404 via the Next catch-all (Caddy label removal live);
  homepage 200; api log error-free.
- Served `_app` chunk credential-free and carries the SSE path; the
  stubbed Playwright badge spec passes against the prod-served bundle.

The prod-broker-restart follow-up below is DONE; remaining follow-ups
unchanged (host `.env` cleanup ×2, healthchecks check, optional
`web_next_static` prune, app-team reply).

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
- [x] Remove `MQTT_WEBCLIENT_PASSWORD=` from host env files — DONE 2026-08-10:
      stripped (var + comment line) from `/opt/makapix/deploy/stack/.env.prod`
      (the live prod env file; the decoy `.env` never had it) and
      `/opt/makapix-dev/deploy/stack/.env.dev`. Zero webclient refs remain;
      no restarts needed (nothing reads it).
- [x] healthchecks.io heartbeat — first run TRIGGERED MANUALLY 2026-08-10
      ~22:25 UTC on prod (task `34ddd619`): dry-count matched execution
      exactly, **335 read>90d deleted, 0 >365d** (796 → 461 rows, site
      younger than a year), success in 8 ms; ping fired via the same signal
      path as the 8 existing heartbeats, auto-creating the check.
      **Remaining (owner, UI-only):** confirm the `cleanup-social-notifications`
      check appeared in healthchecks.io; set period 1 day + grace. Scheduled
      runs continue nightly 04:45 ET.
- [x] After prod deploy: restart `makapix-prod-mqtt` — DONE 2026-08-10
      (recreated by the deploy itself; 9001 verified closed, webclient
      verified purged, fleet reconnected).
- [x] `web_next_static` volume prune — DONE 2026-08-10 on both envs: the
      volume is a *deliberate* merge-don't-delete mechanism (see
      `web/entrypoint.sh` — old chunks kept so cached HTML survives deploys),
      so the prune was generational, not total: files older than 24 h removed
      (dev 967 → 86 files, prod 861 → 86; all pre-dating today's
      credential-free build). Zero files containing the webclient string
      remain in either volume; both sites verified serving their current
      `_app` chunk with 200 afterward. Residual note: chunks already cached
      in end-user *browsers* still contain the dead password — unfixable
      server-side and worthless (account deleted).

**Awaiting:** app team reply to messages/0001 (SSE adoption + FCM
build-or-drop) — the only open item besides the healthchecks UI confirmation.

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
