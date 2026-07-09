# Sign in with Apple — server contract (for the makapix.club server repo)

**Status:** app-side implemented + gated off (2026-07-08) · server leg **not yet built**
**Owner:** app = Fabrício + Claude · server = server repo
**Why:** Apple App Store guideline **4.8** requires any app offering a third-party/social login
(our **GitHub OAuth**) to *also* offer **Sign in with Apple**. The app already ships the full
client side; it stays dormant behind `ClubConfig.kAppleSignInEnabled` until this endpoint is live.

This document is the single source of truth for what the app sends and what it expects back. It
deliberately mirrors the existing OAuth-style `/auth/token` grant model so nothing new is invented
on the transport side.

---

## 1. The grant (extends the existing `/auth/token`)

The app performs the native Apple sign-in (`ASAuthorizationController`), obtains an **identity
token** (a JWT signed by Apple) plus a one-time **authorization code** and a **nonce**, then calls
the same token endpoint the password / GitHub flows use:

```
POST /api/v1/auth/token
Content-Type: application/json

{
  "grant_type": "apple_identity_token",
  "identity_token": "<JWT from Apple>",       // REQUIRED — verify this
  "nonce": "<raw nonce string>",              // REQUIRED — compare sha256(nonce) to the JWT claim
  "authorization_code": "<one-time code>",    // optional — present, usable for server↔Apple exchange
  "given_name": "Ada",                        // optional — Apple sends name ONLY on first sign-in
  "family_name": "Lovelace",                  // optional — persist it the first time or lose it
  "email": "ada@privaterelay.appleid.com"     // optional — first sign-in only; may be a relay address
}
```

**Success — identical envelope to the other grants** (whatever `AuthTokens.fromJson` already reads):

```
200 OK
{ "access_token": "…", "refresh_token": "…", "token_type": "bearer", "expires_in": 3600, … }
```

**Failure:** the app surfaces `ClubError.fromDio`, so return the project's standard error envelope
(e.g. `400/401 { "error": "apple_token_invalid", "error_description": "…" }`). The app maps a
user-cancelled sheet to `apple_cancelled` **client-side** — the server never sees cancellations.

---

## 2. Verifying the identity token (server MUST do all of these)

1. **Fetch & cache Apple's public keys** from `https://appleid.apple.com/auth/keys` (JWKS; rotate/
   cache with the HTTP cache headers). Select the key by the JWT header `kid`; verify the RS256
   signature.
2. **Claims:**
   - `iss` == `https://appleid.apple.com`
   - `aud` == **`club.makapix.app`** — for a *native* iOS app the audience is the **app bundle id**,
     NOT a Services ID. (If a web/Android Apple flow is ever added it uses a Services ID instead;
     out of scope here.)
   - `exp` in the future; `iat` sane.
   - `nonce` == `base64/hex(sha256(<raw nonce from the request>))` — the app sends Apple the
     **hashed** nonce and the server the **raw** nonce; recompute and compare (constant-time).
     Reject on mismatch (replay protection). *(The app hashes with SHA-256 hex — confirm the exact
     encoding against a real token on first integration and pin it here.)*
   - Optionally `email_verified` / `is_private_email`.
3. **Identity:** `sub` is Apple's **stable, app-scoped user id**. Treat `(provider='apple', sub)` as
   the account key — the same way GitHub's provider id keys that account.

`authorization_code`, if you want defence-in-depth, can be exchanged at
`https://appleid.apple.com/auth/token` (with the team's Apple **client secret** JWT) to independently
confirm the token and obtain a refresh token. Not strictly required if the identity-token checks pass.

---

## 3. Account mapping

- **New Apple user** (`sub` unseen): create a Makapix account with provider `apple`, store `sub`, and
  persist `given_name`/`family_name`/`email` **from this first request** (Apple won't resend them).
  Generate a handle the way the GitHub-first-login path does.
- **Returning Apple user:** look up by `sub`, mint tokens.
- **Email collision / linking** (an existing email account, or the relay address): follow whatever
  policy the GitHub provider-linking path already uses. Note Apple's **private relay** emails
  (`…@privaterelay.appleid.com`) forward to the user but are not their real address — don't treat one
  as a verified primary email unless the product intends to.

---

## 4. Allowlist / config

- No new redirect URIs or scheme allowlisting needed — this grant is a **direct JSON POST**, not a
  browser redirect (unlike GitHub). The custom scheme `club.makapix.app://oauth/github` is unrelated.
- The server needs the Apple **Team ID**, the **Key ID** + **.p8** of a "Sign in with Apple" key, and
  the client id (`club.makapix.app`) **only if** it chooses to do the optional `authorization_code`
  exchange in §2. Pure identity-token verification needs only Apple's public JWKS (no secret).

---

## 5. App-side flip (once this endpoint is live)

1. Set `ClubConfig.kAppleSignInEnabled = true` (`app/lib/club/config/club_config.dart`).
2. Ship an iOS build; the button appears automatically on iOS 13+ (`AppleOAuth.isAvailable()`),
   stays hidden on iOS 12 and non-Apple platforms.
3. Test on the device: first sign-in (name/email present) **and** a second sign-in (absent) both mint
   a working session.

App-side pieces already in place (for reference):
`app/lib/club/auth/apple_oauth.dart` (native flow + nonce), `ClubSession.loginApple(...)`
(`app/lib/club/auth/club_session.dart`), `AuthController.loginApple()`
(`app/lib/club/state/auth_controller.dart`), the button in
`app/lib/club/ui/club_account_page.dart`, entitlement in `app/ios/Runner/Runner.entitlements`.
