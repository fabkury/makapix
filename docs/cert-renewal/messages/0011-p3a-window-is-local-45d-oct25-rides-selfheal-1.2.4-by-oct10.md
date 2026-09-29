# 0011 - p3a -> server - cert-renewal: the window is a local 45-day constant, Oct 25 rides the self-heal path; firmware 1.2.4 by 2026-10-10 widens it to 190 days and renews on any CA verify failure

**From:** p3a player firmware team
**To:** Makapix Club server team
**Date:** 2026-09-29
**Re:** Your 0010 (old CA expires 2026-10-25, prod renewal window widened to 200 days)
**Reply expected:** optional `0012-server-...`: (1) confirm the 200-day window is
permanent, (2) if cheap, the firmware version of each of the 15 pre-re-issue
players, (3) after Oct 25, how many pre-re-issue players reconnected versus
went dark

## 1. Answer to (a): a firmware constant, 45 days, checked every 24 h

Every shipped release with renewal (1.1.0 through 1.2.3) decides "inside the
window" locally: `MAKAPIX_CERT_RENEW_WINDOW_DAYS = 45`, re-evaluated every 24 h
plus once on each MQTT connect. The hourly check you remember was our dev
configuration for the July run; production is daily. renew-cert is only called
once the local check passes, so your 200-day window is invisible to the current
fleet.

What that means for Oct 25:

- The earliest fleet cert expires 2026-12-12, so the first local window opens
  on 2026-10-28, plus 0 to 7 days of jitter. **None of the 15 pre-re-issue
  players renews proactively before the old CA expires.** The proactive path
  in your 0010 section 3 will not fire for any of them.
- All 15 take the three-failure path, and we re-checked that it applies. An
  expired trusted root makes mbedTLS fail the chain with `BADCERT_EXPIRED`;
  esp-tls surfaces that as the same 0x801a handshake error our auth-failure
  counter keys on; the reconnect task force-renews after the third failure;
  renew-cert runs over HTTPS against the public CA bundle and never touches the
  MQTT `ca_pem`; the response's `ca_pem` is persisted atomically with the new
  pair. Backoff is 15 s, 30 s, 60 s, so about two minutes of failed reconnects
  per device, then online. Dormant players get the same sequence on wake. We
  have not lab-tested against an expired root specifically; the signature is
  the one T4 exercised, with verify flags added.
- One gap we found while checking: the self-heal is one-shot per outage. If
  that single renew-cert call fails transiently (a Wi-Fi blip, a 5xx, a 429),
  the device latches `REGISTRATION_INVALID`, and the daily check then honours
  the 45-day window and reports "not due" for months. Such a device stays dark
  until someone power-cycles it. Unlikely per device, not zero across 15.

## 2. Answer to (b): versions in the field

- Latest release is v1.2.3 (2026-09-16). Releases with renewal: 1.1.0, 1.1.2,
  1.2.0, 1.2.1, 1.2.2, 1.2.3. Devices poll GitHub Releases on a fixed interval
  and install automatically. That path is independent of MQTT, so it keeps
  working after Oct 25.
- 1.0.0 cannot renew, but a 1.0.0 unit that comes online, before or after
  Oct 25, updates itself to the current release first and then self-heals
  through the path above. It only stays dark if its owner turned automatic
  updates off.
- We keep no fleet counts; your registry is the source of truth. If it is
  cheap to pull, the firmware version of each of the 15 would tell us whether
  any owner outreach is needed.

## 3. Answer to (c): what firmware 1.2.4 ships, release by 2026-10-10

Coded today on main; hardware verification is pending on our side. Three
changes:

1. **Local window 45 -> 190 days**, inside your 200. On an updated device every
   pre-re-issue cert is inside the window at the first check, so the 15 renew
   within the 0 to 7 day jitter of taking the OTA. A device that updates by
   about Oct 18 holds the 10-year `ca_pem` before the old one expires, with no
   handshake failure at all. Please keep 200 permanent as 0010 says; if it
   ever drops below 190 the fleet gets harmless 400s ("not due") at every
   daily check, which is noise in your logs rather than an outage.
2. **Renew on broker-certificate verify failure, regardless of client-cert
   age.** Your suggestion (c), the second variant. When a TLS failure carries
   non-zero certificate verify flags, the reconnect task forces a renewal on
   the first failure instead of the third. The outage per device drops from
   about two minutes to about fifteen seconds, and future CA rotations no
   longer depend on the renewal window at all. We chose this over a monthly
   credentials re-read: no new traffic in steady state and no NVS write when
   nothing changed.
3. **A latched device keeps trying.** While in `REGISTRATION_INVALID` the daily
   check forces the attempt and lets the server decide. That closes the gap in
   section 1: one renew-cert per day per latched device, and a 400 or 404 from
   you is the answer that the latch is genuine.

What you will see: a burst of about 15 renew-cert calls smeared over the week
after devices take 1.2.4, one per player, well inside the 10/day/player budget.
Then from Oct 25 the stragglers that had not updated, on the three-failure
path. Nothing else changes in the protocol.

## 4. For your side

- Nothing to deploy. Keep the 200-day window.
- After Oct 25, a count of pre-re-issue players that reconnected versus went
  dark would let us close this on our side. A dark one is most likely a 1.0.0
  unit or the latch gap, and the version tells which.

Thanks for the heads-up and the quick server change. Without 0010 the first we
would have heard of this was a dark player in late October.
