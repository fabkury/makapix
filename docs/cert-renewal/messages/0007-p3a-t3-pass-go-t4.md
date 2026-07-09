# 0007 — p3a → server — cert-renewal: T3 PASS — GO for T4 (revoke current serial)

**From:** p3a player firmware team
**To:** Makapix Club server team
**Date:** 2026-07-08
**Re:** Your 0006 (token deleted) — T3 results + T4 trigger
**Reply expected:** `0008-server-…` with the revoked serial + timestamp

## T3: PASS

Power-cycled after your 0006. Log sequence, exactly the designed recovery:

```
I (11631) makapix_renewal: Attempting certificate renewal (window; cert valid, 1094 day(s) until expiry)
W (13551) makapix_renewal: renew-cert failed: ESP_ERR_NOT_ALLOWED (HTTP 401)
W (13551) makapix_renewal: renew-cert returned 401/403; rotating token and retrying once
I (13555) makapix_renewal: Refreshing bearer token via token/rotate
I (15518) makapix_store:   Saved Makapix API token (52 bytes)
I (17919) makapix_store:   Saved renewed certificates: 1823/1514/1705 bytes (CA/cert/key)
I (17919) makapix_renewal: Certificate renewed; server reports expiry 2029-07-07T22:12:27Z
```

Exactly one rotate; the fresh token was persisted before use (your new
`player_tokens` row should be timestamped ~22:12:25 UTC). A connect-kick
renewal followed (~22:12:30) — the always-due dev-window behavior — so the
budget is ~5/10.

## GO for T4

Please **revoke the player's CURRENT `cert_serial_number`** (read it from the
dev DB at action time — it advanced again with the kick renewal) via
`cert_generator.revoke_certificate()`, and reply with the serial + timestamp.
The watcher should reload the broker within ~2 s.

On your confirmation we power-cycle. Expected device behavior — the pass
criterion is `REGISTRATION_INVALID` never appearing:

- Boot reconnect with the revoked cert fails at the handshake.
- Recovery races between two designed paths and either is a pass: the
  periodic check (~11 s after boot) renews proactively and the reconnect
  loop picks the fresh PEMs from NVS, or three failures accumulate first and
  the one-shot self-heal renews. (The self-heal path already proved itself
  live during the SAN incident.)
- Fresh serial connects; the revoked one stays on the CRL.

After T4 we'll let the hourly loop run into the 10/day cap overnight for T5
(clean 429 handling) and report everything in a final results message.
