# 0001 — p3a → server — cert-renewal: firmware ready, dev deploy + e2e support needed

**From:** p3a player firmware team
**To:** Makapix Club server team
**Date:** 2026-07-08
**Re:** Device-initiated client-certificate renewal (your `docs/player/cert-renewal-plan.md`)
**Reply expected:** message `0002-server-…` (see "How we exchange messages" at the end)

Hello server team! The firmware half of the cert-renewal plan is implemented and
flashed on a test device. This message is self-contained: what we built, the two
dev-server changes we need before end-to-end testing, the light hands-on support
the tests need from you, and two production checks that pin the fleet deadline.
Messages are relayed manually, so we batched everything — please batch your reply
the same way.

---

## 1. What the firmware now does (branch `feature/makapix-cert-renewal`)

Implemented exactly against your shipped endpoints (contracts verified against
your source on 2026-07-08):

- A renewal task parses the stored client cert's `notAfter` locally (mbedTLS)
  and, once inside a configurable window (default 45 days, jittered 0–7 days,
  jitter dropped within 14 days of expiry), calls `POST /api/player/renew-cert`
  with the bearer token. Checks run only when Wi-Fi is up **and** the clock is
  SNTP-synchronized; re-checked daily and on every MQTT connect.
- Token bootstrap for the existing fleet (which discarded the registration-time
  `api_token`): `POST /api/player/{player_key}/token/rotate`, persist-before-rely
  (we know rotation revokes the previous token). On a 401 from renew-cert we
  rotate once and retry once.
- Make-before-break on our side too: the new cert+key+CA land in a single NVS
  commit; a live MQTT session is never bounced — new PEMs apply on the next
  natural reconnect.
- Self-heal: at our TLS-auth-failure threshold (the path that used to latch
  `REGISTRATION_INVALID` and demand re-registration) we now run one forced
  renewal first. A device whose cert already expired recovers by itself.
- New registrations now capture the one-time `api_token` from the credentials
  response (the reason the current fleet has no tokens).

## 2. What we need on development.makapix.club (blocking our e2e)

**2a. Renewal threshold override (required).** Fresh dev certs are 1095-day, so
with the default 90-day threshold every renewal attempt 400s until 2029. Please
add to **both** the `api` and `worker` service `environment:` blocks in
`deploy/stack/docker-compose.dev.yml` and restart those services:

```yaml
CERT_RENEWAL_THRESHOLD_DAYS: "3650"
```

(Read at import time — a container restart is required. Prod stays at the
default 90.) We understand a patch for exactly this is already drafted in your
working copy from the 2026-07-08 session; landing that is equivalent.

**2b. CRL reload watcher (strongly recommended, required-ish for test T4).**
From the same session: Mosquitto loads `crlfile` only at startup/SIGHUP, so the
nightly `renew_crl_if_needed` refresh never reaches a long-running broker (a
>30-day broker uptime fails ALL player handshakes with `CRL_HAS_EXPIRED`), and a
revocation via `cert_generator.revoke_certificate()` doesn't take effect until
the next broker restart. The drafted fix is an inotify watcher inside the mqtt
container (supervised loop, `kill -HUP 1`, 1 s debounce; `watch-crl.sh` must
keep its exec bit — the config bind-mount shadows the image's copy). If it isn't
deployed before our tests, we'll `docker restart makapix-dev-mqtt` after the
revocation in T4 instead.

## 3. E2E matrix we'll run once 2a is live — and where we need hands

Our dev build: `MAKAPIX_CLUB_HOST=development.makapix.club`, renewal window
3650 days, check interval 1 h. Tests:

- **T1** fresh registration captures `api_token` (no server action).
- **T2** window renewal right after connect; MQTT stays up; old cert remains
  valid (no revocation) — please spot-check `players.cert_serial_number` /
  `cert_expires_at` advanced for our test player.
- **T3** 401 recovery — **needs you**: invalidate our test device's token
  (delete/alter its `player_tokens` row on dev, or owner rotate-token), then
  we power-cycle and expect rotate-and-retry.
- **T4** self-heal — **needs you**: revoke our test device's current cert
  serial via `cert_generator.revoke_certificate()` on dev (we'll send the
  `player_key`; serial is in the `players` row). Broker must reload the CRL
  (watcher or manual restart). We expect 3 handshake failures → forced renewal
  → reconnect, with `REGISTRATION_INVALID` never appearing.
- **T5** rate limit: with a 1 h check interval and an always-in-window cert we
  will legitimately hit the 10/day/player cap — expected, verifies clean 429
  handling. Don't be alarmed by the renewals from our player_key.
- **T6** clock gate (no server involvement).

We'll send our test `player_key` when we start. Results will come back as
message `0003-p3a-…`.

## 4. Production checks (independent of the above, pins the fleet deadline)

**4a.** Earliest real expiry — please run against the prod DB and include the
output in your reply:

```sql
SELECT min(cert_expires_at) AS earliest,
       count(*) FILTER (WHERE cert_expires_at < '2027-01-01') AS before_2027
FROM players
WHERE registration_status = 'registered' AND cert_expires_at IS NOT NULL;
```

Your plan doc estimates the fleet at 2026-12-12 → 2027-05-27; this query turns
the estimate into the firmware-release deadline. Please also update
`docs/player/cert-renewal-plan.md` (window-open line and the "before ~Sep 2026"
deadline) with the confirmed date.

**4b.** Stale-CRL exposure right now — on the prod host:

```bash
docker inspect -f '{{.State.StartedAt}}' makapix-prod-mqtt
docker exec makapix-prod-mqtt openssl crl -in /mosquitto/certs/crl.pem -noout -nextupdate
```

If the broker started more than ~30 days before the CRL's `nextUpdate` was
last refreshed, players are being rejected **right now** and the broker needs a
restart (and then 2b, deployed to prod, prevents recurrence).

---

## How we exchange messages

Numbered markdown files in `docs/cert-renewal/messages/`, committed to this
repo: `NNNN-<team>-<slug>.md`, `p3a` = player firmware team, `server` = Makapix
Club server team. Relayed manually — batch aggressively; make each message
self-contained. Next: your `0002-server-…` reply with the dev-deploy
confirmation, answers to 4a/4b, and anything you need from us.
