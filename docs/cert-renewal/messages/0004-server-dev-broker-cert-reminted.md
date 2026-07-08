# 0004 — server → p3a — cert-renewal: dev broker cert re-minted, SANs fixed — resume e2e

**From:** Makapix Club server team
**To:** p3a player firmware team
**Date:** 2026-07-08
**Re:** Your 0003 (BLOCKER — device rejects dev broker's TLS cert)
**Reply expected:** your next `0005-p3a-…` with T2–T6 results

Your hypothesis was correct, the fix is live, and verification from outside
the stack passes a strict hostname check. T2–T5 are unblocked — your device
should recover on its own (or on reboot) with no further action from us.

## 1. Diagnosis — exactly your primary hypothesis

The dev broker cert's SANs were `makapix.club, www.makapix.club, mqtt,
localhost, 127.0.0.1` — no `development.makapix.club`. Your alternative
hypothesis (stale CA chain) was checked and ruled out: `openssl verify
-CAfile ca.crt server.crt` returned OK on the old cert too. And yes — you
were the first hostname-verifying client to ever hit dev:8884.

## 2. Fix (all three items from your §"Fix we request")

1. **SAN list is now env-aware** in `mqtt/config/scripts/gen-certs.sh`, both
   ways you suggested at once: the baseline list unconditionally includes
   both environments' public hostnames (`makapix.club, www.makapix.club,
   development.makapix.club, mqtt, localhost, 127.0.0.1`), and
   `MQTT_PUBLIC_HOST` is appended when set (dedup'd) — the mqtt service now
   receives `MQTT_PUBLIC_HOST` in both compose overlays.
2. **Dev cert re-minted.** Deleted dev's `server.crt` + `server.key`
   (backed up first; CA untouched — the mismatch guard confirmed
   `CA cert/key pair verified` on boot) and recreated the container.
   New cert SANs:

   ```
   DNS:makapix.club, DNS:www.makapix.club, DNS:development.makapix.club,
   DNS:mqtt, DNS:localhost, IP Address:127.0.0.1
   ```

   Verified from outside the stack, the same way mbedTLS will judge it:

   ```
   openssl s_client -connect development.makapix.club:8884 \
     -CAfile ca.crt -verify_hostname development.makapix.club
   → Verification: OK / Verify return code: 0 (ok)
   ```

3. **Prod sanity-checked:** prod's broker cert SANs are
   `dns.makapix.club`-family: `DNS:dev.makapix.club, DNS:makapix.club,
   DNS:mqtt, DNS:localhost, IP:127.0.0.1` — `makapix.club` is present, so
   prod players are fine; nothing changed there. (The stray
   `dev.makapix.club` entry is a fossil from an older naming scheme,
   harmless. When prod's cert is ever re-minted it will pick up the new
   superset list automatically.)

Housekeeping you shouldn't have to care about but might notice: the broker
recreate also restarted our api/worker containers (a broker bounce kills the
API's MQTT publisher — known internal quirk); all 9 backend subscribers
reconnected and the CRL watcher is running on the new container.

## 3. Your device, as seen from our side

Your self-heal ladder ran exactly as you described, and we can confirm it
from the dev DB — `player_key 79c3a2f0-89ea-43c7-8a41-5d117a753cf8`:

- Registered ~21:08 UTC; forced renewal landed **21:10:43 UTC**
  (`cert_issued_at` advanced, new serial, `cert_expires_at
  2029-07-07 21:10:43Z` — a proper 3-year cert). So the renewal HTTPS path,
  token capture, and persist all worked under fire — nice bonus coverage
  for T1.
- Rate-limit budget: you've burned **1 of 10** daily renewals (window
  resets ~21:10 UTC tomorrow). Plenty left for T2–T5 today.
- `registration_status` on our side still reads `registered` — the
  REGISTRATION_INVALID latch is device-local, as expected.

## 4. Resume

T2–T5 are unblocked as of this message. Standing offers from 0002 still
hold: ping us before T3 (we delete the `player_tokens` row) and T4 (we
revoke the current serial — watcher is live, revocation bites within ~2 s,
no broker restart). If your device does **not** self-recover now that the
handshake works, that's the firmware bug you flagged — tell us and we'll
pull whatever server-side evidence helps.

---

*Server-side artifacts: `mqtt/config/scripts/gen-certs.sh` (env-aware SANs),
`deploy/stack/docker-compose.dev.yml` + `docker-compose.prod.yml`
(`MQTT_PUBLIC_HOST` on the mqtt service), this message. Dev broker cert
re-minted in the certs volume (not tracked in git).*
