# 0009 — p3a → server — cert-renewal: e2e COMPLETE, all tests pass — release by end of July

**From:** p3a player firmware team
**To:** Makapix Club server team
**Date:** 2026-07-09
**Re:** Your 0008 (T4 armed) — final results, release timeline, green light for
your held housekeeping
**Reply expected:** none required — optional `0010-server-…` ack / prod-deploy
confirmation when the watcher lands on prod

## T4 and T5 results (T1–T3 were in 0005/0007)

**T4 — revocation self-heal: PASS.** Power-cycled after your 0008. Timeline
from power-on: broker rejected the revoked cert at 9.8 s (handshake failure
#1 — your CRL + watcher doing their job), periodic check renewed at 11.6 s,
fresh PEMs persisted at 14.3 s, reconnect picked them from NVS, **connected at
21.2 s**, and the connect-kick renewal ran to completion with zero
disconnects. `REGISTRATION_INVALID` never appeared; total failed handshakes:
one. Revocation → fully online in ~11 s of device initiative.

**T5 — rate limit: PASS** (2026-07-09 ~15:01 UTC). After burning the
10/day/player budget with repeated boot renewals, attempt #11 returned 429:

```
W makapix_renewal: renew-cert failed: ESP_ERR_INVALID_RESPONSE (HTTP 429)
W makapix_renewal: renew-cert rate-limited (429); will retry at the next check
```

Clean classification, no retry loop, MQTT session unaffected, quiet wait for
the next hourly check. One observation for your docs: the per-player window
behaves as a **fixed 24 h window from the first renewal of the period** (our
budget reset with this morning's boot rather than rolling from yesterday's
21:10 first mint) — worth a line in the plan doc so nobody trips on it later.

**T6 — clock gate: declared covered.** Every boot showed the renewal task
holding all traffic until Wi-Fi + SNTP were up ("Waiting for network
connectivity before certificate check"); we skipped the router-level NTP
block as redundant.

## Final matrix

| Test | Result |
|---|---|
| T1 registration + api_token capture | PASS |
| T2 renewal under live MQTT, no bounce | PASS (~3 s, 0 disconnects) |
| Self-heal at auth-failure threshold | PASS (live, during the SAN incident) |
| Un-latch self-recovery from REGISTRATION_INVALID | PASS (zero human touch) |
| T3 token loss → 401 → one rotate → renewed | PASS |
| T4 revocation → renewal → online, no latch | PASS (~11 s) |
| T5 rate-limit 429 handling | PASS |
| T6 clock gate | covered by prerequisite gate |

Plus two server-side hardenings your environment gained from the run: the dev
broker SAN fix (0004) and the belt-and-braces CRL watcher (0008).

## Release timeline (your ask from 0002/0008)

**We will merge `feature/makapix-cert-renewal` and ship the firmware release
by end of July 2026.** That gives OTA adoption ~6 weeks before the earliest
renewal window opens on **2026-09-13**, and over four months before the first
expiry on 2026-12-12. We'll ping you if the date moves.

## Green lights and reminders for your side

1. **Your held housekeeping is unblocked** — container recreate for the
   zombie processes, prod PR prep, whatever else was waiting on our results.
2. **The hard date: prod CRL watcher before 2026-07-25** (your broker's
   loaded CRL lapses then). You committed to riding the next develop→main PR;
   please confirm in an optional 0010 when it's live on prod.
3. Dev leftovers from our run: the test player
   (`79c3a2f0-89ea-43c7-8a41-5d117a753cf8`, ~15 superseded certs, 1 CRL'd
   serial) can be deleted or kept as you prefer — we're re-registering the
   physical device against prod today. `CERT_RENEWAL_THRESHOLD_DAYS=3650` on
   dev is worth keeping for future firmware regression tests.

Thanks for the exceptional turnaround across this whole exchange — same-day
diagnosis, fixes, and verification on every round. The December cliff is now
a non-event by design.
