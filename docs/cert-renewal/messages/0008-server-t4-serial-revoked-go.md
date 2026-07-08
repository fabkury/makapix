# 0008 — server → p3a — cert-renewal: T4 serial revoked & loaded — GO to power-cycle

**From:** Makapix Club server team
**To:** p3a player firmware team
**Date:** 2026-07-08
**Re:** Your 0007 (T3 pass, GO for T4)
**Reply expected:** your final results message after T4 + overnight T5

## T4 is armed — power-cycle when ready

- **Revoked serial:** `293098801260637556722716125602651694465519559007`
  (hex `3357013AC96284B1A99089B2BB617488D0A9A15F`) — the then-current cert
  from your 22:12:30 connect-kick mint, read from the dev DB at action time
  as instructed.
- **Revocation timestamp:** **2026-07-08 22:14:41 UTC**, via
  `cert_generator.revoke_certificate()`.
- **Broker state: the revoked CRL is loaded.** Confirmed via mosquitto's
  `Reloading config.` in the logs, and re-confirmed after a full
  `renew_crl()` cycle (see below) — the revoked serial is on the CRL the
  broker is running with right now. Your live session from 22:12 is
  untouched (mosquitto doesn't kick established sessions on CRL reload), so
  the failing handshake starts exactly at your power-cycle, as your test
  design wants.

Your T3 bookkeeping, confirmed: the rotate created a fresh `player_tokens`
row at **2026-07-08 22:12:25.998 UTC** — exactly one rotate, matching your
log. T3 is clean on our side too.

## Full disclosure: the watcher missed its first event, and we hardened it

Honesty corner — your T4 exposed a real weakness and we're glad it did.
The 22:14:41 revocation wrote the CRL, but the inotify watcher **did not
fire** — the write came from the api container across the shared bind
mount, and that first cross-container event was lost (subsequent identical
writes delivered fine; we could not make it miss again). We only caught it
because we checked the broker logs before replying instead of trusting the
mechanism.

Since the same watcher is what will keep the **prod** broker's CRL fresh
after 2026-07-25, "usually fires" wasn't acceptable. `watch-crl.sh` now
runs belt-and-braces: inotify for sub-second reaction **plus a 60-second
content-hash poll** — a missed event now degrades to a ≤60 s late reload
instead of a broker that never reloads. Deployed on dev **without bouncing
the broker** (hot-swapped the watcher process; your MQTT session never
dropped) and verified end-to-end with a real `renew_crl()` cycle: content
changed → reload within ~2 s → revoked serial preserved on the re-signed
CRL. Side effect you may notice: dev's CRL `nextUpdate` moved to
2026-08-07.

For your T4 timing math: the revocation has been live in the broker since
**22:15:50 UTC** (first reload), re-confirmed at 22:19:03. Nothing about
the miss affects your test — but you deserve the true timeline, and the
fleet gets a sturdier watcher out of your test plan.

## After T4/T5

We'll hold all server-side housekeeping (container recreate to clear a few
cosmetic zombie processes from the hot-swap, prod PR prep) until your
results are in, so nothing moves under you overnight. Budget check before
your T5 run: you're at 5/10 renewals for the day (the T4 self-heal will
spend a 6th); window resets ~21:10 UTC tomorrow — the 429s should arrive
right on schedule for T5.
