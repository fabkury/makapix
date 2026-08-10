# Notification Architecture Assessment

**Date:** 2026-08-10 · **Status:** assessment only — no implementation decided
**Scope:** social notifications (the `social_notifications` inbox and its delivery channels).
Out of scope: new-post/category MQTT fan-out (`makapix/post/new/*`), player command/status/RPC
(control plane), email campaigns. Both are referenced only where they constrain the design.

**Judging criteria (owner-selected):** security & isolation, simplicity (one path a solo
maintainer can hold in their head), reliability & offline catch-up. Explicitly *not* judged on
future capabilities. **Hard constraint:** single VPS, self-hosted, no new paid services.

Cross-references: `docs/appraisal-2026-07/` items **S1** (shared `webclient` password +
broker ACL exposure), **D24** (pagination fragmentation), **D27** (synchronous MQTT fan-out);
`docs/notification-actor-sqid/` (current app-facing contract).

---

## 1. Current architecture (as built, develop @ 2026-08-10)

### 1.1 The inbox (source of truth) — sound

- `social_notifications` table (`api/app/models.py:1738`): per-recipient rows with denormalized
  snapshots (`actor_handle`, `actor_avatar_url`, `content_title/sqid/art_url`, `comment_preview`),
  read state (`is_read`, `read_at`), good indexes including partial
  `(user_id, created_at) WHERE is_read = false`.
- Written by `SocialNotificationService.create_notification` / `create_system_notification`
  (`api/app/services/social_notifications.py`) from **12 call sites, all inline in request
  handlers** (reactions, comments, comment likes, follow, mod actions, reports). The service
  commits the caller's session mid-request.
- 12 `notification_type` strings in use — free-form literals, no shared enum.
- REST surface (`api/app/routers/social_notifications.py`): list (keyset pagination on
  `created_at`), unread-count, mark-read, mark-all-read, delete. Bearer-auth only.
  List applies the block filter; **unread-count does not**.
- Unread badge counter: Redis write-through (`INCR` on create, `DECRBY` on read/delete,
  `SET 0` on mark-all-read), 7-day TTL, DB fallback only on key miss. No reconciliation task.
- Retention: **none** — rows accumulate forever (only account purge / post hard-delete cascade
  remove them).

### 1.2 The delivery channels — four built, ~1.5 in use

| Channel | Server side | Client side | Actually used? |
|---|---|---|---|
| **MQTT over WSS** (web) | publish to `makapix/social-notifications/user/{id}` inside the request (`_broadcast_notification`) | `web/src/lib/mqtt-client.ts` + `SocialNotificationsContext`, shared `webclient` account, password baked into the JS bundle (`NEXT_PUBLIC_*`) | **Yes** — sole live channel for the website (badge bump + list prepend; no toasts) |
| **SSE** `/v1/realtime/notifications` | `api/app/routers/realtime.py` — bearer-auth, 3 s DB poll per client, 300 s lifetime | none | **No — zero consumers** (web and app both; only openapi.json + one auth test reference it) |
| **FCM push** | `services/push.py` + Celery `send_push_notification`; token registry `POST /v1/me/push-tokens`; per-type prefs `users.notification_prefs` | none — the Flutter app has **no firebase_messaging dependency at all** | **No** — server half only; also gated on `FCM_CREDENTIALS_FILE` |
| **REST polling** | list/unread-count endpoints | Web: one-shot unread-count at page load. App: 60 s `Timer.periodic` unread-count + list on page open | **Yes** — the actual workhorse; the app's *only* channel |

Physical players are **not** consumers of social notifications: player ACL patterns grant only
`makapix/player/%u/*` topics, so players cannot subscribe to the notification topics even in
principle. The MQTT broker's role in *social* notifications is purely "transport for browsers".

### 1.3 How each audience experiences it

- **Website:** live-ish while a tab is open and MQTT connects; badge seeded once per page load
  from REST; **no fallback when MQTT is down** (badge frozen until reload). Opening
  `/notifications` fetches history and mark-all-reads.
- **App:** unread badge lags up to 60 s; list on open (+ mark-all-read); no notification when
  the app is closed (no push).
- **Players:** nothing (correctly — out of their role).

---

## 2. Verdict

**The inbox core is the right design and would be rebuilt the same way from zero.** Persisted
per-recipient rows with denormalized snapshots + keyset-paginated REST + read state is exactly
what a notification system on one VPS should look like.

**The delivery layer is where "rebuilt from zero" diverges sharply from what exists.** It is a
sediment of three eras, none retired:

1. *MQTT-everything era* — the website piggybacked on the player broker because it existed,
   requiring a shared credential shipped to every browser.
2. *Native-app change-request era (2026-06)* — SSE + FCM built server-side to give the app a
   proper channel; the app never adopted either.
3. *REST-polling reality* — what both clients actually rely on.

A from-zero design would have **one** live channel (an authenticated stream over the HTTP stack
that already carries auth, TLS, and Caddy routing) and would never have pointed browsers at the
device broker. The broker detour is the root of the S1 security exposure *and* most of the
"fuzziness" this assessment was asked about.

### 2.1 Scoring against the three priorities

**Security & isolation — poor (driven entirely by the web channel).**
The shared `webclient` password is public by construction (`NEXT_PUBLIC_*` → JS bundle) and the
ACL grants that account `topic read makapix/social-notifications/#` — any visitor can subscribe
to **every** user's notification stream (handles, comment previews, art URLs). The S1 quick fix
removed the `topic read #` wildcard, but this per-feature exposure remains live and is
acknowledged in the ACL comment: a shared credential can never scope
`social-notifications/user/{id}`. Meanwhile the properly bearer-authenticated per-user SSE
channel sits unused. Secondary: `comment_preview` keeps deleted comments' original text
verbatim, and deleted users' handle/avatar snapshots persist on the actor-`SET NULL` path
(the full account-purge path does clean them).

**Simplicity — poor.**
Six moving parts (DB, Redis counter, MQTT broadcast, SSE, FCM, REST) for one feature, of which
DB+REST do nearly all real work. Two channels are consumer-less. The web client carries a full
MQTT client plus dead surface (`onNotification`, `markAsRead`, `connected`, an orphaned hook
shim, two `post/new` subscriptions whose messages are parsed and dropped). `notification_type`
has a three-way mismatch: 12 types created, 7 documented, 10 titled for push (`new_report`,
`report_resolved` fall back to a generic title). The web calls the legacy bare-root `/api/*`
mounts, not `/api/v1`.

**Reliability & catch-up — mediocre, rescued by the inbox.**
Offline catch-up fundamentally works because the DB is the source of truth. But:
- Unread badge drift is unbounded: blind Redis `INCR`/`DECRBY` with no reconciliation; post
  hard-delete cascades remove unread rows without decrementing; badge is not block-filtered
  while the list is; web double-counts QoS-1 duplicate deliveries (no id dedupe) and never
  re-syncs after load; multi-tab counts diverge.
- The MQTT publish is **synchronous in the request handler** — up to 3 attempts ×
  `wait_for_publish(timeout=5 s)` ≈ 15 s of blocking on a broker outage, inside
  `POST /reactions` etc.
- Web has no live fallback when MQTT is down; app latency is fixed at 60 s.
- Keyset cursor has no `id` tiebreaker — rows sharing a `created_at` across a page boundary can
  be skipped (same class as appraisal D24). The SSE watermark has the identical flaw.
- SSE (if it ever gained users) holds one DB session per client for 300 s and polls per-client
  every 3 s; it also ignores the block filter.
- No retention → unbounded table growth (benign at current scale, unbounded on principle).

### 2.2 Finding index

| # | Severity | Finding |
|---|---|---|
| N1 | HIGH | Shared browser-shipped MQTT credential + `social-notifications/#` read grant = cross-user notification eavesdropping (appraisal S1 residue) |
| N2 | HIGH | Two consumer-less delivery channels (SSE, FCM server halves) — complexity with zero payoff today |
| N3 | MED | Synchronous MQTT publish inside request handlers (≤ ~15 s block on broker outage) |
| N4 | MED | Unread counter drift class (no reconciliation; cascade deletes; block mismatch; web double-count; multi-tab) |
| N5 | MED | No retention policy for `social_notifications` |
| N6 | LOW | Cursor + SSE watermark lack `id` tiebreaker (row skips on equal timestamps) |
| N7 | LOW | `notification_type` free-form strings; 5 types undocumented; 2 missing push titles |
| N8 | LOW | Deleted-comment text survives verbatim in `comment_preview`; deleted-actor snapshots persist outside the purge path |
| N9 | LOW | Web notification client dead code (unused callbacks/state/hook; `post/new` subscriptions parsed-and-dropped); legacy `/api/*` paths |
| N10 | LOW | `mark-read` (per-item) endpoint has zero callers on any client; unread badge on `/notifications` never re-marks live arrivals |

---

## 3. Alternative architectures

The inbox (DB + REST) is invariant across all options — no alternative improves on it under the
constraints. The design space is the **live channel** and the **wake-up channel**.

### Option A — Status quo, hardened (per-user MQTT credentials)
Keep browser MQTT; mint per-user broker credentials (mosquitto dynamic security or an auth
plugin) so ACLs can scope `social-notifications/user/{id}`.
- **Pros:** keeps real-time web; no client-side rearchitecture.
- **Cons:** adds a credential-lifecycle system (issue/rotate/revoke on logout) to the broker,
  the single most operationally sensitive component (mTLS player fleet); browser keeps a full
  MQTT stack for a one-way feed; app still has no channel; broker outage still silently kills
  web liveness.
- **Cost:** medium. **Risk:** medium-high — broker config fragility, and history here (CA
  clobber incident, paho callback wedge) argues against making the broker *more* load-bearing.
- **Judgment:** solves N1 only, worsens simplicity. Rejected.

### Option B — Consolidate on the authenticated SSE stream (recommended)
Web (and eventually app) consume `/v1/realtime/notifications`; browser MQTT for social
notifications is retired; since the web's `post/new` subscriptions feed dead code, the entire
`webclient` broker account can be deleted and the password removed from the bundle.
- **Pros:** one per-user, bearer-authenticated live channel over infrastructure that already
  exists (Caddy + FastAPI + three working SSE precedents: player bar, PMD/BDR, player SSE with
  its query-ticket auth pattern). Browser↔broker coupling drops to zero; MQTT returns to being
  a pure device plane. Kills N1, N2 (SSE side), N9 in one move.
- **Cons:** SSE is one-way (irrelevant — notifications are one-way); the current per-client
  3 s DB poll needs hardening before adoption (shared poller or Postgres LISTEN/NOTIFY);
  EventSource cannot send Bearer headers, so it needs the ticket-auth pattern already proven on
  the player SSE endpoint.
- **Cost:** low-medium. **Risk:** low — every ingredient has a working precedent in this repo.

### Option C — Native WebSocket endpoint in FastAPI
- **Pros:** bidirectional, single connection.
- **Cons:** bidirectionality is unneeded; no WS precedent in the API (new connection-lifecycle
  code, new Caddy behavior to verify); strictly more machinery than SSE for the same payoff.
- **Cost:** medium. **Risk:** medium. Rejected — SSE dominates it for this use case.

### Option D — Pure polling everywhere (delete all live channels)
Web adopts the app's model: interval + on-focus unread-count polling; delete web MQTT, SSE, and
the FCM server half.
- **Pros:** radically simple — DB + REST and nothing else; fully authenticated; N1/N2/N3/N9
  vanish by deletion.
- **Cons:** loses the website's real-time feel (a real product regression — reactions/comments
  land live today); polling tighter than ~30 s to compensate is strictly worse than one SSE
  connection.
- **Cost:** lowest. **Risk:** none technical; product regression.
- **Judgment:** the honest minimalist option; viable fallback if Option B's SSE hardening ever
  feels heavy, but B is barely more expensive and keeps liveness.

### Option E — Wake-up layer: FCM (app) now, Web Push (VAPID) later
Not a competitor to B/D but the missing third leg: nothing today notifies a user whose app/tab
is closed. FCM server half exists and is free; the gap is entirely app-side (their deferred
C5/§4 work). Web Push via VAPID (`pywebpush`) is self-hosted-friendly and free.
- **Judgment:** keep the FCM server half **only if** the app team commits to a client; delete
  it otherwise (it is currently dead weight guarded behind an unset env var). Web Push is
  explicitly out of the owner's priority set — note it as future work, do not build now.

---

## 4. Recommendation ("effort is not an issue", single VPS)

**Target: one inbox, one live channel, one (eventual) wake-up channel — and MQTT returns to
being a pure device plane.** The organizing principle that removes the fuzziness:

> **HTTPS (bearer-auth) is the human plane; MQTT (mTLS, per-device ACL) is the device plane.**
> Humans — web or app — never touch the broker. Devices never receive social notifications.

### Phase 1 — Correctness fixes to the core (channel-independent)
1. Move the broadcast out of the request path: enqueue a Celery `dispatch_notification(id)`
   after commit (the notification row itself is the outbox entry); the request never waits on
   the broker or FCM. (Fixes N3; same shape appraisal D27 prescribes for post fan-out.)
2. Replace the Redis unread counter with a direct `COUNT` on the existing partial index
   `(user_id, created_at) WHERE is_read = false`, block-filtered, optionally cached ~30 s.
   Deletes the entire drift class (N4) and ~100 lines of counter bookkeeping.
3. Add `(created_at, id)` tiebreakers to the list cursor and any stream watermark (N6).
4. Introduce a `NotificationType` enum/constants module; document all 12 types; add the two
   missing push titles (N7).
5. Add a retention task in the existing beat convention (e.g. read > 90 d and everything
   > 365 d, nightly, staggered into the 01:00–05:00 ET window) (N5).
6. Scrub `comment_preview` on comment deletion; null actor snapshots when the actor FK goes
   NULL (N8).

### Phase 2 — Harden and adopt the SSE channel (Option B)
1. Rework `/v1/realtime/notifications`: ticket-based auth for EventSource (player-SSE
   precedent), block filter applied, `(created_at, id)` watermark, and a **single shared
   poller** (one 2–3 s query for all connected users — or Postgres LISTEN/NOTIFY fired by the
   Phase-1 dispatcher) instead of one session+query-loop per client.
2. Point the web at it: SSE tail + `connected {unread_count}` greeting for badge reconciliation
   + REST backfill; dedupe by notification id; drop to interval polling if SSE errors.
3. Delete the web MQTT path: `mqtt-client.ts` social wiring, the dead `post/new` handling, the
   hook shim; migrate the four REST calls to `/api/v1/*` (N9).
4. Delete the `webclient` account from the broker ACL and the `NEXT_PUBLIC_MQTT_WEBCLIENT_PASSWORD`
   build arg entirely. This — not credential rotation — is the real close-out of appraisal S1.

### Phase 3 — App alignment (coordination, not code here)
1. Offer the hardened SSE stream to the app team (replaces the 60 s poll when foregrounded);
   REST polling remains their offline-tolerant fallback.
2. Decide FCM's fate with them: either they build the client half (then wire
   `FCM_CREDENTIALS_FILE` on prod and keep `push.py`), or the server half is deleted. A dead
   half-integration is the worst of both.

### What deliberately does *not* change
- The `social_notifications` schema and REST contract (only additive tweaks above).
- Player MQTT (out of scope; already correctly isolated by mTLS + per-device ACL patterns).
- No new infrastructure: no message queue, no Redis Streams, no external push relay beyond the
  already-chosen FCM. Every recommended piece runs on the existing VPS stack.

### Sequencing note
Phases 1 and 2 are independent of the app team and fully local to this repo. Phase 2 step 4
(deleting `webclient`) also requires the shared-Caddy/prod deployment dance for the broker
config only insofar as `mqtt/config/acls` ships with the compose stack — it is a normal
develop → main deploy, no Caddy involvement.

---

## 5. Answers to the owner's three questions, in one paragraph each

**1. How good is the current architecture?** The persistence/REST core is genuinely good —
built from zero it would look the same. The delivery layer is not in its best form: four
channels for three audiences, of which two channels have no consumers, the busiest audience
(web) rides the least appropriate channel (a shared-credential device broker with a live
cross-user read exposure), and the app quietly ignores all real-time machinery in favor of a
60-second poll. Reliability is carried by the inbox, not by the channels.

**2. Could other architectures be considered?** Yes — the meaningful axis is the live channel:
per-user MQTT credentials (A: rejected — deepens broker coupling), authenticated SSE (B:
recommended — every ingredient already proven in-repo), native WebSockets (C: rejected — SSE
dominates), pure polling (D: viable minimalist fallback), plus FCM/Web-Push as a separate
wake-up layer (E: app-team-dependent / future). Section 3 has pros, cons, costs, risks.

**3. Recommendation with effort not an issue?** Adopt the plane-separation principle (HTTPS =
humans, MQTT = devices), fix the channel-independent correctness issues (async dispatch,
DB-derived unread count, tiebreakers, retention, enum, preview scrubbing), harden and adopt the
existing SSE stream for the web, delete the browser-MQTT path and the `webclient` broker
account outright, and resolve the FCM half-integration with the app team in either direction.
Net effect: fewer moving parts than today, every channel authenticated per-user, and the
S1 exposure closed by deletion rather than mitigation.
