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

## Next
- [ ] `make check-full`, push develop, PR develop→main, merge
- [ ] Prod: pull /opt/makapix, `make deploy`, `docker restart caddy`; verify
      app-dev assetlinks serves get_login_creds + apex assetlinks 200
- [ ] Live-verify /v1/auth/restore/challenge on development.makapix.club → send 0004
- [ ] M3: app team e2e via bmgr harness (their side); confirm §2a empirically in their round-trip
- [ ] M4: app release / joint flip (server side will already be live)
