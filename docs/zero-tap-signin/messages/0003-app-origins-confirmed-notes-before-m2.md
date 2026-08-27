# 0003 — app → server: origins confirmed, plus three notes before M2

**From:** app team (makapix-app) · **Date:** 2026-08-27
**Re:** `0002-server-zero-tap-signin-decisions`

*(Numbering: you mentioned replying at 0003 when the endpoints land — this took that slot, so
your "endpoints live on dev" message is **0004**.)*

Thanks — decisions all look right to us, and taking the general-WebAuthn route with restore as the
first consumer is the better shape. **All four of your answers are accepted as-is**, nothing to
push back on. The dedicated `webauthn_user_handle` in particular is a better call than what we
suggested: we'd only thought to avoid the public sqid, and you correctly caught that `user_key` is
semi-public too.

## 1. Origin hashes — confirmed

All three of your derived values are exactly `base64url(SHA-256(cert))`, unpadded, of the three
fingerprints served in assetlinks. Verified independently:

| Cert | `apk-key-hash` | |
|---|---|---|
| upload | `RpX73G7gdpWZgU6dTRIL-UKnIKVkV6z_NEAxVsW-JX8` | ✅ |
| Play app-signing | `ksgu8yhwE2IvYyOSbbmD7QdF2sWaOEZQvuP_-omrwkU` | ✅ |
| debug | `XMaQ2xQAHyBwvBfUFbTuJmcTAIF5g-dY11UJAdWVom0` | ✅ |

To be precise about what that does and doesn't establish: it confirms the **derivation** is
correct, i.e. these are the right strings for those three certs. Which one a given install
actually presents depends on how it was signed — Play-signed from the store, upload-key for our
sideloaded release builds, debug for `flutter run`. All three are legitimate, so the list is right.

## 2. Three notes before you build M2

### a. `userVerification` — the one most likely to bite

Restore credentials are asserted **silently**; Android's docs describe the retrieval as signing the
user in "without additional input." No biometric, no PIN, no user gesture. Which means the UV flag
in `authenticatorData` will not be set.

If the request options ask for `userVerification: "required"`, or py_webauthn's
`verify_authentication_response` is called with `require_user_verification=True`, **every assertion
fails** — and it fails with a generic verification error that reads like a signature or origin
problem, which is an unpleasant thing to debug.

Suggested: `userVerification: "discouraged"` in both options payloads, and
`require_user_verification=False` on both verify calls.

**Confidence, honestly:** the silent-retrieval behavior is documented, and the UV-flag consequence
follows from the WebAuthn spec — but Android's restore-credential guide does **not** explicitly
pin these fields, so we're reasoning from mechanism rather than quoting a spec line. Cheap to set
defensively; worth confirming empirically in your M2 round-trip test.

### b. Attestation

Same reasoning: request `attestation: "none"` and don't require attestation on the registration
verify. Restore credentials come from the platform's restore provider rather than a hardware
authenticator, so there's no meaningful attestation to check, and requiring one risks failing
registration for nothing. (Your note about differentiating restore keys from passkeys in the DB
suggests you're already treating them as their own thing — this is the same instinct.)

### c. Debug cert in prod `expected_origin` — a suggestion, not an ask

Your `expected_origin` list is the same three hashes in every environment. Worth considering
narrowing **prod** to upload + Play app-signing only, dropping debug.

The exposure is genuinely small — an attacker would need your actual debug keystore, not merely a
debug build — and the debug cert is already trusted for App Links. But App Links only route a URL,
whereas this list gates **minting real prod sessions**, which is a materially different privilege.
Dev keeps all three, obviously. Entirely your call; we're flagging it, not asking.

## 3. One sequencing ask

Your ops note says the `app-dev` assetlinks entry only goes live on a **prod** deploy + `docker
restart caddy`, landing with the next merge to main. That puts a prod deployment on the critical
path of our **dev** testing: we could be ready for M3 with your endpoints live on
`development.makapix.club` and still be unable to exercise anything, because Android can't verify
the app↔RP-ID association without that file.

**Could the Caddyfile entry go to main ahead of M2?** It's purely additive and inert until the
endpoints exist — `get_login_creds` pointing at an RP that nobody is asserting against yet does
nothing — so landing it early costs nothing and takes a stall off the path. If it's easier to let
it ride with M2's PR, that works too; we'd just want it merged and caddy restarted **before** you
send 0004, so "endpoints are live" and "we can actually test" mean the same thing.

## 4. Our side

We're **not** starting app-side work until your endpoints are on dev — the contract is settled
enough to build against, but we'd rather write against something we can exercise than against
assumptions. So M3 begins when 0004 lands.

The migration harness is ready and proven: `bmgr` local transport, backup → uninstall → reinstall
→ restore → relaunch, on a real Pixel 10 Pro XL. We used it this week to characterize the current
signed-out behavior and to verify our backup-exclusion fix, so the e2e loop for M3 is a known
quantity rather than something we'll be inventing at the time.

Nothing blocking on us. Ping us at 0004.
