# Sign in with Apple — server-side progress

Effort docs: `API-CONTRACT.md` (authoritative, mirrored from the app repo) ·
`messages/` (exchange with the app team).

## Status

- **2026-07-09** — Kickoff received (0001). Server leg implemented on `develop`:
  - `POST /api/v1/auth/token` accepts `grant_type=apple_identity_token`
    (`identity_token` + raw `nonce`; optional `authorization_code`,
    `given_name`, `family_name`, `email`).
  - Verification in `api/app/services/apple_signin.py`: RS256 against Apple's
    JWKS (PyJWKClient, 1h cache), `iss`, `aud == club.makapix.app`
    (env-overridable via `APPLE_APP_BUNDLE_ID`), `exp`/`iat`, and constant-time
    compare of the JWT `nonce` claim to lowercase-hex `sha256(raw nonce)`.
  - Account mapping: `(provider='apple', sub)` in `auth_identities`, GitHub
    parity. First sign-in persists `given_name`/`family_name` (identity
    `provider_metadata`) and email. Linking policy: a provider-verified,
    **non-private-relay** email that matches an existing account links the
    Apple identity to it; relay addresses never link.
  - New error code `apple_token_invalid` (401) for verification failures.
  - The optional `authorization_code` server↔Apple exchange is **skipped for
    v1** (per 0001's recommendation) — no Apple secrets on the server.
  - Tests: `api/tests/test_apple_signin.py` (12 tests, local RSA keypair with
    the JWKS lookup patched).
- Reply sent: `messages/0002-server-apple-signin-live-on-dev.md`.
- **2026-07-09** — App team verified on device against dev (0003: first
  sign-in with Hide My Email + returning sign-in both minted sessions) and
  gave GO. PR #228 merged `develop` → `main`, deployed to prod, smoke-tested
  live on makapix.club (grant + JWKS reachability + regression on the other
  grants). Reply sent: `messages/0004-server-apple-signin-live-on-prod.md`.

## Remaining

- None server-side. App team runs the prod TestFlight build and proceeds to
  App Store submission (guideline 4.8 satisfied). Reopen on a 0005 message.
