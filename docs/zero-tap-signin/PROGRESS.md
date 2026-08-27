# Zero-Tap Sign-In — progress

## 2026-08-27
- Received app kickoff (messages/0001): Play requires Android Restore Credentials by April 2027;
  server leg = WebAuthn endpoints + assetlinks. Verified claims against the codebase
  (apple_identity_token grant precedent exists; no WebAuthn machinery yet; assetlinks served
  inline from Caddyfile.global for app.* hosts; apex has none).
- Owner decisions recorded in PLAN.md: general WebAuthn machinery (restore = first consumer),
  dedicated random userHandle column, minimal v1 revocation, sign-count store+log-never-block,
  RP IDs prod=makapix.club / dev=app-dev.makapix.club, near-term priority.
- Sent reply (messages/0002) answering all four open questions + derived apk-key-hash origins
  for the app team to confirm.

## 2026-08-27 (later) — M1 + M2 built
- Received 0003 (app): origin hashes confirmed; adopted their three notes — UV "discouraged" +
  `require_user_verification=False` everywhere, attestation "none", debug-cert origin excluded
  from prod (`WEBAUTHN_ALLOW_DEBUG_ORIGIN`, dev-only). Their sequencing ask granted by riding the
  Caddy change with M2's develop→main merge, restarting caddy before sending 0004. (0003 took the
  slot planned for our endpoints-live reply, which is now 0004.)
- M1: apex assetlinks at `web/public/.well-known/assetlinks.json` (get_login_creds); additive
  second entry in the Caddyfile.global app-hosts block.
- M2: `webauthn` dep (+ `soft-webauthn` dev dep); migration `a1b2c3d4e5f6`
  (users.webauthn_user_handle + webauthn_credentials); services/webauthn_service.py (Redis
  single-use challenges); endpoints /v1/auth/restore/{options,register,challenge},
  restore_credential grant on /v1/auth/token, credentials list/delete; `WEBAUTHN_RP_ID`
  fail-fast setting (both .envs written: dev=app-dev.makapix.club, prod=makapix.club);
  11 round-trip tests green (tests/test_restore_credentials.py), targeted auth suites green.

## 2026-08-27 (evening) — shipped to dev AND prod, 0004 sent
- `make check-full` green (7 chunks, 81 files); pushed develop; PR #268 merged to main.
- Prod deployed (`make deploy` auto-ran migration a1b2c3d4e5f6), `docker restart caddy`.
- Verified live: app-dev assetlinks carries both relations, apex assetlinks serves
  get_login_creds, prod + dev `/api/v1/auth/restore/challenge` return correct rpId /
  empty allowCredentials / UV discouraged.
- Sent 0004 (endpoints live, notes adopted, M3 is a go).

## 2026-08-27 (night) — 0005: dev TLS outage, fixed
- App team reported (0005) development.makapix.club failing TLS entirely (alert 80, no cert).
  Root cause: the afternoon's `make rebuild` aborted at `up -d` when the api crash-looped
  (pre-migration), leaving makapix-dev-web in **created** (never started) state — caddy-docker-proxy
  dropped the site block, so Caddy had no cert for that SNI. Our 0004 "live-verify" ran inside the
  container network and bypassed Caddy, which is why it was missed (their guess was exactly right).
- Fix: `docker start makapix-dev-web`; verified from the public path — valid LE cert, and
  `POST /api/v1/auth/restore/challenge` returns rpId app-dev.makapix.club / allowCredentials [] /
  UV discouraged over real TLS.
- No reply sent (their 0006 stays reserved for the M3 report); prod-account testing is fine as-is
  (owner decision). They verified prod on the wire themselves in 0005, including §2a.

## 2026-08-27 (late) — 0006/0007: M3 done, ship decision
- 0006 (app): registration confirmed e2e on prod (Blockstore escrow observed); assertion leg
  physically unverifiable by their bmgr harness (restore key lives in GMS Blockstore, purged on
  uninstall — needs device-setup restore or D2D). Dev-TLS fix confirmed from their side too.
- Verified in prod DB: 3 credential rows for the owner account matching their test window;
  last_used_at NULL everywhere (no assertion, as they said). Deleted superseded rows 1–2, kept 3.
- 0007 sent: positive registration confirmation; owner decision = SHIP (their option 1) — server
  assertion leg is soft-authenticator-tested, §2a set defensively on both sides, failure mode is
  status quo; flagged orphan-row accumulation if the app registers every launch (app-side
  register-once preferred; server-side pruning only if numbers demand).
- §2a's real confirmation now arrives with the first genuine migration: watch for a
  webauthn_credentials row gaining last_used_at / sign_count, and restore_credential grants in logs.

## Next
- [ ] App release ships zero-tap (their 0008 will carry the version)
- [ ] Watch for first real-world assertion (last_used_at set) → report back in the exchange
- [ ] Optional: dev-RP device pass if we ever want app-dev.makapix.club config device-verified
- [ ] Server-side orphan pruning only if row counts ever warrant it
