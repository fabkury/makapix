# 0010 — server → p3a — cert-renewal: old CA cert expires 2026-10-25; prod renewal window widened to 200 days

**From:** Makapix Club server team
**To:** p3a player firmware team
**Date:** 2026-09-29
**Re:** Your 0009 (e2e complete, release by end of July) — long-overdue ack, plus
a heads-up on the CA trust anchor
**Reply expected:** optional `0011-p3a-…` — (a) confirm how shipped firmware
refreshes `ca_pem`, (b) tell us which firmware versions are in the field, and
(c) whether a periodic `ca_pem` refresh is feasible

## 1. Ack on 0009 (sorry for the delay)

Everything you flagged landed: the CRL watcher reached production on 2026-07-09
(PR #224, well before the 2026-07-25 CRL lapse), the nightly CRL refresh has
been rewriting `crl.pem` on schedule since, and your note about the per-player
rate limit behaving as a **fixed 24 h window from the first renewal** is now in
the plan doc (`docs/player/cert-renewal-plan.md`, "Server contract"). The fleet
is running your ≥ 1.1.0 releases (we see 1.0.0 → 1.2.3 in the registry).

## 2. The trust anchor, not the client cert

We re-issued the MQTT CA on 2026-05-27 with a 10-year certificate. It uses the
**same key** as before, so every leaf cert still chains — but the **previous CA
certificate expires 2026-10-25 02:08 UTC**. Devices get `ca_pem` at
provisioning; ours never re-fetch it (zero `GET /player/{key}/credentials` and
zero `renew-cert` calls in production access logs 2026-09-16 → 09-29). mbedTLS
treats an expired trusted root as a verification failure, so from Oct 25 any
player provisioned before 2026-05-27 that still holds the old `ca_pem` will hit
`X509_CERT_VERIFY_FAILED` against the broker.

Population as of today: **15 of 29 registered production players** were
provisioned before the re-issue (client certs expiring 2026-12-12 → 2027-04-16).
Two are active daily; the rest are dormant and could come back at any time.

## 3. Why the renewal ladder alone wasn't enough — and what we changed

Your ladder handles this in principle: third handshake failure → force
`renew-cert` → new `key_pem`/`cert_pem`/**`ca_pem`** → reconnect. But
`renew-cert` returned `400` while the client cert had more than 90 days left,
and the device un-latches only on a `200`. A device with a client cert expiring
in March 2027 would therefore have stayed dark from Oct 25 until mid-December.

**Server change, live on production since 2026-09-29 ~19:30 UTC:**
`CERT_RENEWAL_THRESHOLD_DAYS` raised **90 → 200**. Every pre-re-issue cert is
now inside the window (the furthest was 199 days out today), so:

- a ≥ 1.1.0 device runs its hourly check, sees `notAfter` within 200 days and
  renews **proactively** — receiving the 10-year `ca_pem` before Oct 25, with
  no handshake failure at all (assuming your hourly check compares against the
  server window rather than a hard-coded 90 — see question (a));
- a dormant device that wakes after Oct 25 fails three handshakes, force-renews,
  gets a `200` with the new `ca_pem`, and reconnects (~11 s, per your T4).

No firmware action is required for this rotation. The 200-day window is
permanent; renewed certs are 3-year so the cadence stays low. Devices on
< 1.1.0 firmware cannot renew and stay in the hands of their owners (the
2026-07-24 email).

## 4. Questions / suggestion for the next release

- **(a)** Does the hourly check decide "inside the window" from a firmware
  constant (e.g. 90 days) or by simply attempting `renew-cert` and accepting
  `200`? If it is a constant, the proactive path above won't fire for certs
  90–200 days out and those devices will instead take the three-failure path
  on Oct 25 (still self-healing, just noisier). Please tell us which.
- **(b)** Which firmware versions are currently shipping / in the field? Our
  registry shows 1.0.0, 1.1.0, 1.2.1, 1.2.3 among post-June registrations.
- **(c)** Suggestion: a **periodic `ca_pem` refresh** (e.g. re-read
  `GET /player/{key}/credentials` monthly, or renew on any server-cert
  verification failure irrespective of client-cert age) would make future CA
  rotations independent of the renewal window entirely. Not urgent — the
  current rotation is covered — but worth a line in your backlog.

Nothing else pending on our side. Thanks again for the July run.
