# 0001 — app → server: Sign in with Apple — please implement the `apple_identity_token` grant

**From:** app team (makapix-app) · **Date:** 2026-07-09
**Contract:** `docs/apple-signin/API-CONTRACT.md` (authoritative copy of the app repo's
`docs/ios-release/apple-signin-server.md`)

## Context

The iOS app is real now: signed TestFlight builds ship via Codemagic, and the App Store
declarations (age rating 13+, privacy label) were completed today. Apple guideline **4.8**
requires that an app offering a third-party social login (our GitHub OAuth) also offer
**Sign in with Apple**, so this is a hard gate for App Store submission.

The **entire app side is already implemented and shipped, gated off** behind
`ClubConfig.kAppleSignInEnabled=false`. What's missing is only the server leg.

## The ask

Extend the existing `POST /api/v1/auth/token` with a new grant type, mirroring the
password/GitHub grants:

```json
{
  "grant_type": "apple_identity_token",
  "identity_token": "<JWT from Apple>",
  "nonce": "<raw nonce string>",
  "authorization_code": "<one-time code, optional>",
  "given_name": "…", "family_name": "…", "email": "…"   // optional, first sign-in only
}
```

Success returns the standard token envelope; failures use the standard v1 error envelope
(suggested code: `apple_token_invalid`). Full verification and account-mapping rules are in
the contract; the essentials:

- Verify the JWT against Apple's JWKS (`https://appleid.apple.com/auth/keys`), RS256, by `kid`.
- Claims: `iss == https://appleid.apple.com`, **`aud == club.makapix.app`** (native app →
  audience is the bundle id, not a Services ID), `exp`/`iat` sane.
- **Nonce (now pinned):** the app generates a random raw nonce, hands Apple
  `sha256(rawNonce)` as a **lowercase hex** string, and sends the server the **raw** nonce.
  So: recompute `hex(sha256(nonce))` and constant-time-compare to the JWT `nonce` claim.
- Identity key is `(provider='apple', sub)` — same shape as the GitHub provider mapping.
  **Persist `given_name`/`family_name`/`email` on the first sign-in** — Apple never resends them.
- **No Apple secrets needed**: pure identity-token verification uses only the public JWKS.
  The optional `authorization_code` exchange (defence-in-depth) would need a Sign-in-with-Apple
  key from the developer portal — our recommendation is to **skip it** for v1.

## Open questions for you

1. **Email collision / account linking** — please follow whatever policy the GitHub
   provider-linking path uses today; if that policy is "distinct account per provider", that's
   fine for v1, just tell us so the UX copy can match. Watch for Apple **private relay**
   addresses (`…@privaterelay.appleid.com`) — don't treat one as a verified primary email.
2. Anything you need from the app side beyond this payload? (The app maps user-cancelled
   sheets client-side; the server never sees cancellations.)

## Rollout

1. Server ships the grant on **development.makapix.club** and replies here (0002).
2. App flips `kAppleSignInEnabled=true`, builds via Codemagic → TestFlight, and verifies on
   device: first sign-in (name/email present) **and** second sign-in (absent) both mint sessions.
3. Joint prod flip (server `develop`→`main`), then the App Store submission proceeds.

No redirect URIs, schemes, or allowlist changes — this is a direct JSON POST, unrelated to
the GitHub browser flow.
