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

## Next
- [ ] M1: `web/public/.well-known/assetlinks.json` (apex, get_login_creds) + additive entry in
      Caddyfile.global app-hosts block
- [ ] M2: py_webauthn dep, migration (users.webauthn_user_handle + webauthn_credentials),
      Redis challenge store, 4 endpoints + credentials list/delete, tests, `make openapi`
- [ ] Live on development.makapix.club → send 0003
- [ ] M3: app team e2e via bmgr harness (their side)
- [ ] M4: joint prod flip (main merge + deploy + `docker restart caddy`)
