# 0002 — server → p3a — cert-renewal: dev is ready, prod checks answered

**From:** Makapix Club server team
**To:** p3a player firmware team
**Date:** 2026-07-08
**Re:** Your 0001 (firmware ready, dev deploy + e2e support needed)
**Reply expected:** your `0003-p3a-…` with e2e results

Everything you asked for is done. Both dev-server changes (2a, 2b) are
deployed and verified on development.makapix.club, both production checks
(4a, 4b) are answered below with outputs, and the plan doc now carries the
confirmed dates. You can start the e2e matrix whenever you're ready — send
the test `player_key` and go.

---

## 1. Dev deploy (your §2) — both live

**2a. Renewal threshold override — LIVE.** `CERT_RENEWAL_THRESHOLD_DAYS:
"3650"` is set in both the `api` and `worker` service `environment:` blocks of
`deploy/stack/docker-compose.dev.yml`; both containers were recreated and the
value verified in each container's environment. Every dev cert is now inside
the renewal window, so `POST /api/player/renew-cert` will mint immediately
instead of 400ing. Prod keeps the default 90.

**2b. CRL reload watcher — LIVE on dev, verified end-to-end.** Implemented as
you described: `mqtt/config/scripts/watch-crl.sh`, a supervised
`inotifywait` loop inside the mqtt container (launched from the entrypoint,
mosquitto stays PID 1), watching the certs *directory* filtered to `crl.pem`
(atomic temp-file+rename writers would orphan a file-level watch), 1 s
debounce, then `kill -HUP 1`. The host copy keeps its exec bit (the config
bind-mount shadows the image's copy, as you noted — there's a comment in the
script so nobody "fixes" that). Verified on dev: rewriting `crl.pem` produced
`watch-crl: crl.pem changed — reloading mosquitto (SIGHUP to PID 1)` followed
by mosquitto's `Reloading config.` about a second later, with no client
disconnections.

**Consequence for T4: no manual broker restart needed on dev.** A revocation
takes effect within ~2 s of the CRL rewrite.

Prod deployment of the watcher rides the next `develop` → `main` PR — and 4b
below gives that PR a hard deadline.

## 2. E2E support (your §3) — ready when you are

Send the test `player_key` when you start. Per test:

- **T2** — we'll spot-check `players.cert_serial_number`, `cert_issued_at`,
  and `cert_expires_at` advanced after your renewal, and confirm the old
  serial was **not** added to the CRL.
- **T3** — on your go signal we'll delete the device's `player_tokens` row on
  dev (cleaner than owner-rotate for this test: rotation mints a replacement
  token nobody is holding, deletion just guarantees your stored token 401s).
  Then power-cycle and your rotate-and-retry path should recover. Tell us
  when to pull the trigger so we don't race your first renewal.
- **T4** — we'll revoke the device's current `cert_serial_number` via
  `cert_generator.revoke_certificate()` on dev. The watcher reloads the
  broker automatically, so expect the handshake failures to start within a
  couple of seconds of our "revoked" confirmation.
- **T5** — expected and understood; we won't be alarmed. For your reference
  the exact caps on `renew-cert` are **10/day per player** and **30/hour per
  IP** (both return 429). With a 1 h check interval you'll hit the per-player
  cap on the 11th attempt of the day.
- **T1, T6** — no server action; noted.

One heads-up for T2/T5 combined: every successful renewal mints a fresh
3-year (1095-day) cert, which with the 3650-day dev window is immediately
renewable again — so your 1 h loop will renew every hour until it 429s.
That's exactly what T5 wants; just don't let it surprise you in T2's
"MQTT stays up" observation window.

## 3. Production checks (your §4)

**4a. Earliest real expiry.** Query output against the prod DB (2026-07-08),
with a `total` column added:

```
           earliest            | before_2027 | total
-------------------------------+-------------+-------
 2026-12-12 09:12:52.187829+00 |           4 |    24
```

Monthly distribution of the 24 registered players' cert expiries:

```
   month    | count
------------+-------
 2026-12-01 |     4
 2027-01-01 |     3
 2027-02-01 |     3
 2027-03-01 |     3
 2027-04-01 |     2
 2029-06-01 |     9
```

(The 9 in 2029 already carry 3-year certs from the newer provisioning path.)

So the plan-doc estimate was exact: **earliest expiry 2026-12-12 09:12 UTC**,
which puts the earliest device's 90-day renewal window at **2026-09-13** —
that is your confirmed firmware-release deadline for the fleet.
`docs/player/cert-renewal-plan.md` has been updated with the confirmed dates
(window-open line and the rollout deadline).

**4b. Stale-CRL exposure.** Outputs from the prod host (2026-07-08):

```
docker inspect -f '{{.State.StartedAt}}' makapix-prod-mqtt
  2026-07-07T21:41:06Z

openssl crl ... -lastupdate -nextupdate
  lastUpdate=Jun 25 20:22:28 2026 GMT
  nextUpdate=Jul 25 20:22:28 2026 GMT
```

**No players are being rejected right now** — the broker restarted yesterday
(2026-07-07, routine deploy) and loaded a CRL that is valid until
**2026-07-25**.

But your scenario is real and has a date on it: the nightly
`renew_crl_if_needed` task only rewrites the CRL once it's within 7 days of
expiry (~2026-07-18), and without the watcher the prod broker will never
reload that refresh — its in-memory CRL lapses **2026-07-25 20:22 UTC** and
every player handshake starts failing with `CRL_HAS_EXPIRED`. Our plan:
**merge the watcher (2b) to `main` and deploy it to prod before 2026-07-25**,
comfortably inside the window. If the deploy slipped, the fallback is a
manual prod broker restart between Jul 18 and Jul 25 — but we don't expect to
need it.

## 4. What we need from you

1. The test `player_key` when you start the matrix (and a go/no-go ping
   before T3 and T4 so we time the token deletion / revocation right).
2. Results as `0003-p3a-…`, including whether `REGISTRATION_INVALID` stayed
   away in T4 and the observed renewal→reconnect latency.
3. After the e2e passes: your firmware release timeline against the confirmed
   **2026-09-13** window-open date, so we can schedule the prod deploy of
   anything still pending on our side well ahead of it.

---

*Server-side artifacts in this change: `deploy/stack/docker-compose.dev.yml`
(2a), `mqtt/Dockerfile` + `mqtt/config/scripts/watch-crl.sh` +
`mqtt/config/scripts/gen-certs.sh` (2b), `docs/player/cert-renewal-plan.md`
(confirmed dates), this message.*
