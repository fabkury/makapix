# 0002 — server → app: `apple_identity_token` grant is live on development.makapix.club

**From:** server team (makapix) · **Date:** 2026-07-09
**Re:** 0001 (kickoff) · **Contract:** `docs/apple-signin/API-CONTRACT.md`

## Done

`POST /api/v1/auth/token` now accepts `grant_type=apple_identity_token` exactly
as specified in 0001, deployed on **development.makapix.club**. Success returns
the standard token envelope (`access_token`, `token_type=Bearer`,
`expires_in=3600`, `refresh_token` in the body, plus a `user` object — same
shape as the password/GitHub grants).

Verification implemented per the contract:

- RS256 against Apple's JWKS (cached ~1h, auto-refetch on unknown `kid`).
- `iss == https://appleid.apple.com`, `aud == club.makapix.app`, `exp`/`iat`.
- **Nonce:** recompute `hex(sha256(raw nonce))` — lowercase hex, as pinned in
  0001 — and constant-time-compare to the JWT `nonce` claim.
- Identity key is `(provider='apple', sub)`; `given_name`/`family_name`/`email`
  are persisted on first sign-in (name lands in the identity's provider
  metadata — the user model has no name fields; the visible profile identity
  is the generated handle, same as GitHub sign-ups).
- We took your recommendation: the optional `authorization_code` exchange is
  **skipped for v1**. The field is accepted and ignored, so keep sending it if
  you like — no Apple keys/secrets live on the server.

## Errors

- Verification failure (bad signature/claims/nonce/expired):
  **401** `{ "error": { "code": "apple_token_invalid", "message": "…" } }`.
- Missing `identity_token`/`nonce`: **400** `validation_error`.
- Same per-IP throttle as the other login grants (20 / 5 min) → **429**
  `rate_limited`.
- Note the error envelope is the project-standard nested form
  (`error.code`/`error.message`), same as every other v1 endpoint — listing it
  here since 0001's sketch showed a flat `{"error": "...", ...}`.

## Your open questions

1. **Email collision / linking** — GitHub parity, as requested:
   - If Apple supplies a **verified, non-private-relay** email that matches an
     existing account's email, the Apple identity is **linked** to that account
     (same behavior as the GitHub native flow). The user signs into their
     existing account.
   - **Private relay addresses never link.** A user who picks "Hide My Email"
     gets a fresh, separate account (the relay address becomes that account's
     email — it's a working, Apple-verified inbox). So for UX copy: *share
     email → same account if it matches; hide email → new separate account.*
   - Edge cases: a relay/unverified email that collides with an existing
     account → **409** `conflict` ("account with this email already exists");
     a brand-new Apple `sub` whose token carries **no email at all** (should
     not happen on a true first sign-in, but can if Apple treats the app as
     already-authorized) → **400** `bad_request` with a message telling the
     user to remove the app under *Settings → Apple ID → Sign-In & Security →
     Sign in with Apple* and retry, which makes Apple resend the email. You may
     want to surface that message as-is.
2. **Anything else from the app side?** No — the 0001 payload is sufficient.
   Two notes:
   - `aud` is pinned to `club.makapix.app` (env-overridable server-side if a
     second bundle id ever appears).
   - Returning-user sign-ins ignore `given_name`/`family_name`/`email` in the
     payload by design; only the JWT is trusted after the first sign-in.

## Rollout

Step 1 of 0001's plan is complete. Over to you: flip `kAppleSignInEnabled`,
point a TestFlight build at development.makapix.club, and verify first +
second sign-in mint sessions. Reply here (0003) and we'll do the joint prod
flip (`develop` → `main`).
