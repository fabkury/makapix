# 0002 — server → app: Zero-Tap Sign-In — decisions, answers, green light

**From:** server team (makapix) · **Date:** 2026-08-27
**Re:** 0001-app-zero-tap-signin-kickoff

Kickoff received and verified against our codebase. We're in, and we're slotting it **near-term**
rather than deadline-driven. Server-side design is captured in `docs/zero-tap-signin/PLAN.md`;
highlights and your four open questions below.

## Scope: general WebAuthn, your contract verbatim

We're taking your "this generalizes" invitation: we'll build ordinary WebAuthn machinery
(py_webauthn) with restore credentials as its first consumer. **Your four proposed endpoints and
the `restore_credential` grant are adopted verbatim** — paths, payloads, and both error codes
(`restore_credential_invalid`, `restore_credential_unknown`) as you spec'd them. The
`apple_identity_token` grant precedent slots it in cleanly. User-facing passkey login on the
website remains out of scope, as you framed it.

One addition beyond your four: an authenticated list/delete surface under
`/api/v1/auth/restore/credentials` (see Q2).

## Answers to your open questions

1. **userHandle** — a **dedicated random handle**: new `users.webauthn_user_handle` column,
   32 random bytes, minted lazily on first `/restore/options` call. Not the public sqid (as you
   advised) and not our internal `user_key` either (it appeared in legacy URLs, so it's
   semi-public). Opaque, stable, used for nothing else.
2. **Revocation** — **minimal in v1**: credentials cascade-delete with the account, plus an
   authenticated endpoint to list/delete one's own restore credentials. We're not coupling to
   session revocation yet — a restored sign-in mints an ordinary session, revocable through
   existing means. Keep calling `clearCredentialState` on sign-out as planned.
3. **Sign count** — **stored and logged, never enforced.** Agreed that restore credentials
   legitimately assert from cloned backups; a strict monotonic check is the wrong default here.
   Counter regressions become an anomaly log line, not a rejection.
4. **iOS** — the machinery is general WebAuthn, so both platforms are served by the same
   endpoints at no extra cost. We're not scoping any iOS-specific work; adopt it there whenever
   (or if ever) it makes sense on your side.

## RP IDs and assetlinks — accepted, with serving details

Your proposed RP IDs are confirmed: **prod `makapix.club`**, **dev `app-dev.makapix.club`**.
Good catch making dev `app-dev` — `development.makapix.club` sits behind basic auth, which would
break Android's assetlinks fetch.

- Apex: we'll serve `/.well-known/assetlinks.json` as a static file from the website build
  (single `get_login_creds` entry, your three fingerprints).
- `app-dev.makapix.club`: additive second array entry in our shared Caddy config. Heads-up: that
  block is shared with `app.makapix.club`, so prod's app host will carry the `get_login_creds`
  entry too — unused (prod RP is the apex) and harmless. The existing `handle_all_urls` entries
  are untouched, per your warning.
- Ops note for the rollout: the Caddy change only goes live on a prod deploy + caddy restart, so
  the dev assetlinks entry lands with our next merge to main, slightly decoupled from the dev API
  endpoints.

## Origin verification — please confirm

We'll verify assertions against `android:apk-key-hash` origins derived from your three
fingerprints:

```
android:apk-key-hash:RpX73G7gdpWZgU6dTRIL-UKnIKVkV6z_NEAxVsW-JX8   (upload)
android:apk-key-hash:ksgu8yhwE2IvYyOSbbmD7QdF2sWaOEZQvuP_-omrwkU   (Play app-signing)
android:apk-key-hash:XMaQ2xQAHyBwvBfUFbTuJmcTAIF5g-dY11UJAdWVom0   (debug)
```

Please confirm these match what your client actually sends (any of the three should appear,
depending on install type).

## Registration semantics

Multiple credentials per account are allowed (one per device is normal); registration upserts on
`credential_id`, so your `E2eeUnavailableException` retry re-registering is fine — no surprise on
our side.

## Rollout

Your proposed sequence is accepted as-is (assetlinks → server on dev → app + bmgr harness →
joint prod flip, as with Apple Sign-In). We'll reply here (0003) when the four endpoints are live
on `development.makapix.club`.
