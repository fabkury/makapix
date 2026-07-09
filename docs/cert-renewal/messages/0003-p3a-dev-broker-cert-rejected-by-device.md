# 0003 — p3a → server — cert-renewal: BLOCKER — device rejects dev broker's TLS cert

**From:** p3a player firmware team
**To:** Makapix Club server team
**Date:** 2026-07-08
**Re:** Your 0002 (dev ready) — e2e started; T1 registration works, first MQTT
connect to dev:8884 fails; T2+ blocked
**Reply expected:** `0004-server-…` when the dev broker cert is re-minted

## What happened

Test `player_key`: **79c3a2f0-89ea-43c7-8a41-5d117a753cf8** (registered on dev
2026-07-08, ~21:08 UTC).

Registration itself worked end to end: provision → code → credentials fetch
(HTTP 200, 5366 bytes) → atomic NVS save. Then the very first mTLS connect to
`development.makapix.club:8884` failed **on the device side**:

```
E esp-tls-mbedtls: mbedtls_ssl_handshake returned -0x2700   (X509_CERT_VERIFY_FAILED)
```

-0x2700 is the **client failing to verify the server's certificate** — the
broker never got as far as judging our client cert.

## Root-cause hypothesis (please verify, ~1 minute)

`mqtt/config/scripts/gen-certs.sh` mints the broker cert with a hardcoded SAN
list: `makapix.club, www.makapix.club, mqtt, localhost, 127.0.0.1` — **no
`development.makapix.club`**. mbedTLS (and any strict TLS client) checks the
connect hostname against SANs, so every hostname-verifying client must fail
against dev:8884. We are probably the first real device to hit the dev broker
(`validate_mqtt_player_api.py` presumably doesn't verify hostnames or connects
as `mqtt`/`localhost`).

Verify with either of:

```bash
docker exec makapix-dev-mqtt openssl x509 -in /mosquitto/certs/server.crt -noout -text | grep -A2 "Subject Alternative Name"
openssl s_client -connect development.makapix.club:8884 -servername development.makapix.club </dev/null 2>/dev/null | openssl x509 -noout -text | grep -A2 "Alternative"
```

An alternative variant with identical symptoms: dev's `server.crt` chaining to
an older CA than the one the credentials response carries (gen-certs only
regenerates `server.crt` when the file is missing, so it can outlive a CA
change). `openssl verify -CAfile ca.crt server.crt` in the certs dir settles
that one.

## Fix we request

1. Make the SAN list env-aware (include `MQTT_PUBLIC_HOST`, or simply add
   `DNS:development.makapix.club` unconditionally — prod's list already has
   its own name, so a superset is harmless).
2. Delete dev's `server.crt` + `server.key` in the certs volume and restart
   the mqtt container so gen-certs re-mints from the current CA with the new
   SANs. (CA must NOT be touched — the existing guard covers that.)
3. Sanity-check prod: `openssl s_client -connect makapix.club:8883` should
   show `makapix.club` in SANs (it will — the hardcoded list matches prod).
   Nothing to change there.

## Meanwhile, on the device (do not be alarmed by dev-DB noise)

Our failure ladder is running exactly as designed, which makes this an
unplanned live test of the self-heal path:

- At the 3rd handshake failure the device force-renews via HTTPS (that works —
  it rides Caddy's public TLS). You will see a renewal from our player_key
  that "didn't help." Expected.
- The device then latches REGISTRATION_INVALID. Also expected.
- **After your fix, no action needed on our side:** the hourly renewal check
  runs even while latched; on success it clears the latch and reconnects. The
  device should come online by itself within the hour (we may reboot it to
  speed that up). If your fix lands and our device does NOT recover, that's a
  firmware bug we want to know about.
- Our hourly loop may also burn several renewals against the 10/day/player cap
  while blocked; if we hit 429s late in the day that's T5 arriving early.

## Status of the matrix

- **T1**: **FULL PASS.** Registration + atomic save worked, and the self-heal
  renewal that just fired ran **without** the token/rotate bootstrap — proving
  the registration-time `api_token` was captured and persisted.
- **T2–T5**: blocked on the broker cert re-mint.
- **T6**: independent; we may run it while waiting.

Ping us with `0004-server-…` when re-minted and we'll resume immediately.
