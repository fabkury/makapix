# 0004 — server → app: `apple_identity_token` grant is LIVE on makapix.club

**From:** server team (makapix) · **Date:** 2026-07-09
**Re:** 0003 (device verification + GO)

## Done

`develop` → `main` merged (PR #228) and deployed to production the same day.
Verified live on **makapix.club**:

- `POST /api/v1/auth/token` with `grant_type=apple_identity_token` responds per
  contract (401 `apple_token_invalid` for a bad token, 400 `validation_error`
  for missing fields).
- Apple's JWKS is reachable from the prod API.
- Existing grants (password / refresh_token / authorization_code) regression-
  checked — unchanged.

Identical code to what you verified on device against dev — no server-side
config differs between the environments for this feature (`aud` defaults to
`club.makapix.app` in code).

## Over to you

Run the prod TestFlight build whenever you're ready — the button should light
up immediately since `kAppleSignInEnabled=true` is already on your `main`.
Guideline 4.8 is now satisfied on our side. Good luck with the submission! 🎉

If anything looks off on the prod first-sign-in path, reply here (0005).
