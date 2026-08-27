# Zero-Tap Sign-In — server leg (Android Restore Credentials / WebAuthn)

**Status:** planned (kickoff 2026-08-27, message 0001) · **Deadline:** April 2027 (Google Play
device-migration requirement) · **Priority:** near-term — the server leg is the long pole.

App-side counterpart: `makapix-app: docs/zero-tap-signin/DESIGN.md`. Message exchange in
`messages/` (0001 = app kickoff, 0002 = server decisions/reply).

## Goal

When a user migrates to a new Android device (cloud restore or D2D transfer), the app signs them
back in silently on first launch. Mechanism: Android Restore Credentials, which is passkey-shaped —
the server side is ordinary WebAuthn.

## Decisions (owner, 2026-08-27 — see messages/0002)

| Decision | Choice |
|---|---|
| Scope | **General WebAuthn machinery**, restore credentials as its first consumer. User-facing passkey login on the website is explicitly *not* in scope (separate product decision). |
| Endpoint paths | Keep the app team's proposed `/api/v1/auth/restore/*` + `restore_credential` grant verbatim (internals are generic; paths are the contract the app spec'd against). |
| `userHandle` | **New dedicated random handle** — `users.webauthn_user_handle`, 32 random bytes, unique, nullable, minted lazily on first registration-options call. Not `public_sqid` (public) and not `user_key` (appeared in legacy URLs, semi-public). |
| Revocation (v1) | **Minimal**: credentials cascade-delete with the account; authenticated list/delete endpoint for one's own credentials. Coupling to session revocation deferred — a restored sign-in mints an ordinary session, revocable through existing means. |
| Sign count | **Store + log, never block.** Restore credentials legitimately assert from cloned backups, so a strict monotonic check causes false lockouts. Counter regressions are logged as an anomaly signal only. |
| RP IDs | prod `makapix.club` (apex — credentials valid across subdomains, future web passkeys possible); dev `app-dev.makapix.club` (isolates dev credentials from prod; already serves assetlinks without basic auth — `development.makapix.club` cannot, it's behind basic auth). |
| Multiple credentials | Allowed — one per device is normal; upsert on `credential_id`. The app may retry registration after `E2eeUnavailableException` (see 0001), so re-registration must be idempotent-friendly. |

## Architecture

### New dependency
`webauthn` (py_webauthn, Duo Labs) in `api/pyproject.toml`.

### Database (one Alembic migration)
- `users.webauthn_user_handle` — `LargeBinary(32)` (or base64 `String`), unique, nullable, indexed.
- `webauthn_credentials` table: `id`, `user_id` FK → users (CASCADE), `credential_id` bytes unique,
  `public_key` bytes, `sign_count` int, `transports` (nullable), `created_at`, `last_used_at`.

### Challenge storage
Redis, TTL ~5 min, single-use (delete on consume). Registration challenges keyed to the
authenticated user; assertion challenges keyed by the challenge value itself (the get leg is
userless by design — user identified only by the `userHandle` in the assertion).

### Endpoints (contract from message 0001, adopted verbatim)
1. `POST /api/v1/auth/restore/options` — authenticated → `PublicKeyCredentialCreationOptionsJSON`
   (`rp.id` per env, challenge, `user.id` = webauthn_user_handle, `residentKey: "required"`).
2. `POST /api/v1/auth/restore/register` — authenticated; verify attestation via py_webauthn, store
   credential.
3. `POST /api/v1/auth/restore/challenge` — **unauthenticated** → `PublicKeyCredentialRequestOptionsJSON`
   with **empty `allowCredentials`** (discoverable-credential flow).
4. `POST /api/v1/auth/token` with `grant_type: "restore_credential"` — **unauthenticated**; verify
   assertion, look up user by `userHandle`, mint the standard token envelope. Slots beside the
   `apple_identity_token` grant (`api/app/routers/auth.py` — see the `grant_type` dispatch).
5. Revocation surface (v1-minimal): authenticated `GET`/`DELETE` under `/api/v1/auth/restore/credentials`.

Error codes (standard v1 envelope): `restore_credential_invalid` (verification failed),
`restore_credential_unknown` (no such credential — app treats as ordinary signed-out start).

### Origin verification
For Android, the WebAuthn origin is `android:apk-key-hash:<base64url(sha256-of-signing-cert)>`.
Derived from the three fingerprints already served in assetlinks (upload / Play app-signing / debug):

```
android:apk-key-hash:RpX73G7gdpWZgU6dTRIL-UKnIKVkV6z_NEAxVsW-JX8   (upload)
android:apk-key-hash:ksgu8yhwE2IvYyOSbbmD7QdF2sWaOEZQvuP_-omrwkU   (Play app-signing)
android:apk-key-hash:XMaQ2xQAHyBwvBfUFbTuJmcTAIF5g-dY11UJAdWVom0   (debug)
```

`expected_origin` = this list (py_webauthn accepts a list). Add `https://<rp.id>` alongside later
if web passkeys ever ship. App team asked (0002) to confirm these match what their client sends.

### Settings
`WEBAUTHN_RP_ID` (and, if not derivable, `WEBAUTHN_RP_NAME`) per env in `.env.dev` / `.env.prod`.
Fail fast if unset when the endpoints are enabled.

## Digital Asset Links (blocking prerequisite)

- **Apex `makapix.club`** — no assetlinks today (404). Add **`web/public/.well-known/assetlinks.json`**
  (Next.js serves `public/` at the root): single entry, `delegate_permission/common.get_login_creds`,
  package `club.makapix.app`, the three fingerprints. Ships through the normal web deploy — no Caddy
  involvement. Note: apex is served per-env (development.makapix.club gets it too; harmless — dev
  RP is app-dev, and basic auth hides it anyway).
- **`app-dev.makapix.club`** — extend the inline JSON in `deploy/stack/caddy/Caddyfile.global:160`
  with a **second array entry** carrying `get_login_creds` (same fingerprints). The block is shared
  with `app.makapix.club`, so prod's app host gets the entry too — unused (prod RP is the apex) and
  harmless. **Prod-owned change**: goes live only via merge to main + pull in `/opt/makapix` +
  `docker restart caddy`.
- ⚠️ **Do not modify the existing `handle_all_urls` entries** — the GitHub OAuth App-Link return
  depends on them exactly as-is. Changes are purely additive.

## Milestones

1. **M1 — assetlinks**: apex file in `web/public/`; Caddyfile.global additive entry. (Caddy part
   rides the next main merge; can land with M2's PR.)
2. **M2 — server**: dependency, migration, challenge store, 4 endpoints + credentials list/delete,
   `make openapi`, tests (py_webauthn's helpers can mint test credentials), live on
   development.makapix.club → send message 0003.
3. **M3 — app**: platform channel + Dart wiring; app team verifies with their `bmgr`
   backup→uninstall→reinstall→restore harness against dev.
4. **M4 — joint prod flip** (as with Apple Sign-In): merge to main, deploy, restart caddy (for the
   assetlinks entry), app release.

## Testing

- Unit/API: pytest — registration + assertion round-trip using py_webauthn-generated credentials;
  challenge single-use; unknown credential → `restore_credential_unknown`; sign-count regression
  logs but succeeds; credentials gone after account deletion.
- E2E: app team's real-migration harness (their step 3 in 0001).
