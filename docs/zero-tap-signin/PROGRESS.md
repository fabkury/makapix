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

## Next
- [ ] M3: app team e2e via bmgr harness against prod (their choice, unblocked) — report at 0006
- [ ] Optional: a dev-RP device pass if we ever want app-dev.makapix.club config device-verified
- [ ] M4: app release (server side already live on prod; no further joint flip needed)
