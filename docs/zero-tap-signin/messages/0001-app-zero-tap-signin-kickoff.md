# 0001 — app → server: Zero-Tap Sign-In (Android Restore Credentials) — the WebAuthn server leg

**From:** app team (makapix-app) · **Date:** 2026-08-27
**App-side design:** `makapix-app: docs/zero-tap-signin/DESIGN.md`

## Context

Google Play's announcement of 2026-08-26 ("Elevating app quality") adds a device-migration
onboarding standard: **from April 2027, apps that support sign-in must implement the Android
Restore Credentials API**, so a user moving to a new device is silently signed back in on first
launch. Non-compliance is penalized with reduced store visibility and publishing capability.
Games are exempt; mobile and tablet only. We have sign-in, so we are in scope.

**We are not proposing a date.** The deadline is eight months out and this is yours to slot —
we're opening the topic now because the server leg is the long pole, not the app work.

For completeness: the same announcement's February 2027 requirements (dynamic memory, bitmap
memory, DEX optimization) need **no action** from either side. We measured — our DEX is 1.81 MiB
against a 10 MB trigger, and the engine's memory budgets already sit far under the thresholds.

## What a migration does to us today — measured, not theoretical

Reproduced on a Pixel 10 Pro XL (Android 16) on 2026-08-27 with the shipped release build, using
a real backup → uninstall → reinstall → restore cycle:

- **Artwork survives perfectly** — drawings, autosave, frames, layers, palettes, artwork names.
- **The session does not.** The user lands on the signed-out welcome screen.
- No crash; it degrades gracefully.

The cause is `flutter_secure_storage`: Auto Backup carried the token ciphertext, but the Android
Keystore key that unwraps it is hardware-backed and non-exportable, so it never transfers
(`StorageCipher18Impl: unwrap key failed`). **This is correct behavior** — bearer tokens should not
be transferable that way. The app has since excluded those prefs from backup entirely
(`makapix-app` commit `ed4cd891`), which removes the error and the orphaned ciphertext, but the
user is still signed out afterward. Only Restore Credentials closes that gap.

## The shape of the thing

Restore Credentials is **passkey-shaped**: it reuses the same server-side machinery as WebAuthn
passkeys. Two phases:

1. **Create** — right after a successful sign-in, on the old device. Silent, no user interaction.
2. **Get** — on first launch after migration, on the new device. Also silent.

### The constraint that drives the design

**The get leg is unauthenticated and userless.** On the new device the app has no tokens and no
idea who the user is — that is the entire point. So this must be a **discoverable credential**
(resident key) flow: `allowCredentials` empty, and the user identified by the `userHandle` carried
in the assertion. If the design assumes we can name the user up front, it won't work.

## The ask

Proposed shapes below — concrete so you have something to react to, but **all of it is yours to
change**. What matters is that the four capabilities exist.

**1. Registration options** — authenticated.

```
POST /api/v1/auth/restore/options
→ 200: WebAuthn PublicKeyCredentialCreationOptionsJSON
       (must include rp.id, a challenge, user.id = the userHandle, and
        authenticatorSelection.residentKey = "required")
```

**2. Registration** — authenticated.

```
POST /api/v1/auth/restore/register
{ "response": <registration response JSON from CreateRestoreCredentialResponse> }
→ 200/204: server verifies the attestation and stores (credential_id, public_key, sign_count)
           against the account
```

**3. Assertion challenge** — **unauthenticated**.

```
POST /api/v1/auth/restore/challenge
→ 200: WebAuthn PublicKeyCredentialRequestOptionsJSON
       (challenge + rp.id; allowCredentials MUST be empty — see above)
```

**4. Assertion → session** — **unauthenticated**. Mirrors the `apple_identity_token` precedent
from `docs/apple-signin/messages/0001`, so it slots beside the existing grants:

```
POST /api/v1/auth/token
{ "grant_type": "restore_credential",
  "assertion": <authentication response JSON from the RestoreCredential> }
→ 200: the standard token envelope
```

Failures use the standard v1 error envelope; suggested codes `restore_credential_invalid`
(verification failed) and `restore_credential_unknown` (no such credential — the app treats this
as an ordinary signed-out start, not an error).

## RP ID and Digital Asset Links — a blocking prerequisite

Because the server hands us `requestJson`, **the server picks the RP ID**, which means it can
differ per environment at zero cost to the app — we pass the JSON through verbatim, no `CLUB_ENV`
branching. We'd like to use that to keep the environments isolated:

| Environment | Proposed `rp.id` |
|---|---|
| prod | `makapix.club` |
| dev  | `app-dev.makapix.club` |

The apex for prod means credentials stay valid across `makapix.club` and all subdomains, so the
website could share them later if passkey login ever becomes interesting there. The split means a
dev-registered credential can never be offered against prod.

**Android validates the app↔RP-ID association through Digital Asset Links, so nothing works until
these files exist.** This is a website-repo change:

- `https://makapix.club/.well-known/assetlinks.json` — **does not exist today** (the apex serves
  the SPA shell, so the path 404s). Needs creating:

```json
[{
  "relation": ["delegate_permission/common.get_login_creds"],
  "target": {
    "namespace": "android_app",
    "package_name": "club.makapix.app",
    "sha256_cert_fingerprints": [
      "46:95:FB:DC:6E:E0:76:95:99:81:4E:9D:4D:12:0B:F9:42:A7:20:A5:64:57:AC:FF:34:40:31:56:C5:BE:25:7F",
      "92:C8:2E:F3:28:70:13:62:2F:63:23:92:6D:B9:83:ED:07:45:DA:C5:9A:38:46:50:BE:E3:FF:FA:89:AB:C2:45",
      "5C:C6:90:DB:14:00:1F:20:70:BC:17:D4:15:B4:EE:26:67:13:00:81:79:83:E7:58:D7:55:09:01:D5:95:A2:6D"
    ]
  }
}]
```

- `https://app-dev.makapix.club/.well-known/assetlinks.json` — exists and is correct for App
  Links, but carries only `delegate_permission/common.handle_all_urls`. Add a second array entry
  with `delegate_permission/common.get_login_creds` and the same three fingerprints.

⚠️ **Do not modify the existing `handle_all_urls` entries** on `app.makapix.club` or
`app-dev.makapix.club`. The GitHub OAuth return leg depends on those matching the app's signing
certs exactly; the change here is purely additive.

The three fingerprints are upload key, Play app-signing key, and debug — copied from what those
hosts serve today, so they should need no re-derivation.

## Scope note: this generalizes, and that's fine

We're asking only for the restore flow, because that's what Play requires. But the machinery is
ordinary WebAuthn — **if it's cheaper for you to build general passkey support and treat restore
as one consumer of it, please do.** That's likely the better long-term shape. Offering passkeys as
a user-facing login method is a separate product decision, and we're explicitly not making it here.

## Constraints worth knowing

- **One account per app** (an Android limitation, not ours). We're single-account, so no impact.
- Restore keys are bound to the package name `club.makapix.app`.
- The key rides **either** cloud backup **or** a direct device-to-device USB transfer.
- If the device has no screen lock or backup is disabled, creation throws
  `E2eeUnavailableException`; the app retries with cloud backup disabled (local/D2D only). No
  server impact — just don't be surprised if registration is attempted more than once.
- Windows is unaffected. iOS is not covered by this Play requirement (Keychain already migrates
  sessions there), though general WebAuthn would serve both — see the open questions.

## App-side plan, for your awareness

There is **no Flutter plugin** for Restore Credentials (checked pub.dev 2026-08-27), so this needs
a small Kotlin platform channel over `androidx.credentials` (1.5.0+). On the Dart side: register
after a successful sign-in; on cold start, when the token store is empty, attempt the assertion
**before** routing to the welcome screen; clear the credential on sign-out. Every failure path is
silent and falls through to today's welcome screen — Zero-Tap is an enhancement, never a gate on
reaching the app.

## Open questions for you

1. **What should `userHandle` be?** Our suggestion is a stable, opaque per-account id that is
   *not* the public sqid, so a restore credential doesn't carry a public identifier around in
   backups — but you own the identity model, so tell us what you'd rather.
2. **Revocation.** The app calls `clearCredentialState` on sign-out, but that only affects the
   local device. Do you want server-side invalidation in v1 (e.g. dropping stored credentials when
   a session is revoked elsewhere), or is that a later concern?
3. **Sign-count / replay handling** — any preference on how strictly to enforce it? Restore
   credentials can legitimately be asserted from a restored backup, so a strict monotonic counter
   check may be the wrong default here.
4. **Do you want iOS in scope** while you're in this code? Not required by Play, but general
   WebAuthn would cover both platforms.

## Proposed rollout

1. **Website:** apex + dev `assetlinks.json` carrying `get_login_creds`.
2. **Server:** ship the four endpoints on `development.makapix.club` and reply here (0002).
3. **App:** build the platform channel + Dart wiring, then verify against a real migration cycle —
   we have a working harness for this (`bmgr` local transport, uninstall → reinstall → restore),
   so we can prove it end to end rather than assuming.
4. **Joint prod flip**, as with Apple Sign-In.

Nothing here touches redirect URIs, custom schemes, or the OAuth allowlist.
