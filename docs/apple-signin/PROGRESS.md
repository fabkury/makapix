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

## Remaining

1. App flips `kAppleSignInEnabled=true`, verifies on device against
   development.makapix.club (first + second sign-in).
2. Joint prod flip: PR `develop` → `main`, deploy prod, then App Store
   submission proceeds.
