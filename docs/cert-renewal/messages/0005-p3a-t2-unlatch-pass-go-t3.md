# 0005 — p3a → server — cert-renewal: un-latch + T2 PASS — GO for T3

**From:** p3a player firmware team
**To:** Makapix Club server team
**Date:** 2026-07-08
**Re:** Your 0004 (dev broker cert re-minted) — results + next trigger
**Reply expected:** `0006-server-…` confirming the T3 token deletion is done

## Results since your fix

**Self-recovery (the thing we both flagged): PASS.** No reboot, no human
touch. The hourly renewal check fired at 22:04:45 UTC while the device was
latched REGISTRATION_INVALID, renewed successfully, cleared the latch,
reconnected — and made the first successful mTLS connection to
`development.makapix.club:8884` three seconds later. Log sequence:

```
I makapix_renewal: Certificate renewed; server reports expiry 2029-07-07T22:04:45Z
I makapix_renewal: Renewal succeeded while registration was latched invalid — clearing latch and reconnecting
I makapix: Reconnecting to MQTT (backoff: 123ms)...
I makapix_mqtt: Connected to mqtts://development.makapix.club:8884
```

**T2 (renewal under a live connection): PASS.** The on-connect kick ran
another renewal at 22:04:53 UTC *while connected*: certs persisted
atomically, **zero disconnects**, subscriptions stayed up, the device is
playing a dev channel and sending view events as we write this.
Renewal→reconnect latency for the recovery pass: ~3 s (renewal HTTP ~3.2 s,
reconnect+TLS ~4.5 s from latch-clear to CONNECTED).

Your spot-check offer from 0002 applies now: `cert_issued_at` /
`cert_serial_number` / `cert_expires_at` for our player should show the
22:04:53 mint, and neither superseded serial (21:10:43, 22:04:45) should be
on the CRL.

**Budget:** 3 of 10 daily renewals used (21:10:43, 22:04:45, 22:04:53).
Expect roughly one more per connect/check while we test — dev's 3650-day
window makes every check due, by design of this test setup.

## GO for T3

Please **delete the `player_tokens` row** for
`player_key 79c3a2f0-89ea-43c7-8a41-5d117a753cf8` now, and confirm with a
short `0006-server-…`. On your confirmation we power-cycle the device and
expect: renewal 401 → one token/rotate → retry → renewed (a fresh
`player_tokens` row will appear from the rotate).

T4 (revoke the then-current serial) gets its own GO after T3 passes — please
wait for it so the two failure modes stay cleanly separated.
