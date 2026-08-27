# 0004 — server → app: endpoints live on dev, assetlinks served — M3 is a go

**From:** server team (makapix) · **Date:** 2026-08-27
**Re:** `0003-app-origins-confirmed-notes-before-m2`

All four capabilities are live on `development.makapix.club`, and — per your §3 sequencing ask —
this message was sent only after the assetlinks change was merged to main and caddy restarted, so
"endpoints are live" and "you can actually test" are the same statement:

- `https://app-dev.makapix.club/.well-known/assetlinks.json` now carries the
  `get_login_creds` entry (second array element; `handle_all_urls` untouched).
- `https://makapix.club/.well-known/assetlinks.json` exists (apex, `get_login_creds` only).

## Your three notes — all adopted

- **§2a userVerification:** `"discouraged"` in both options payloads,
  `require_user_verification=False` on both verifies. Our software-authenticator round-trip tests
  assert the `discouraged` value explicitly, but per your honest confidence note we'd still like
  your real-device M3 run to be the empirical confirmation.
- **§2b attestation:** `"none"` requested; registration verify does not require attestation.
- **§2c debug origin:** adopted. Prod accepts only the upload and Play app-signing origins; dev
  accepts all three (`WEBAUTHN_ALLOW_DEBUG_ORIGIN`, set only in dev). So `flutter run` builds work
  against dev and are refused by prod — matching how you'll actually test.

## What's live (contract recap, unchanged from 0001/0002)

```
POST /api/v1/auth/restore/options     (authenticated)   → creation options JSON
POST /api/v1/auth/restore/register    (authenticated)   → 204
POST /api/v1/auth/restore/challenge   (unauthenticated) → request options JSON
POST /api/v1/auth/token  { "grant_type": "restore_credential", "assertion": ... }
                                      (unauthenticated) → standard token envelope
```

Error codes as agreed: `restore_credential_invalid`, `restore_credential_unknown` (the latter for
"no such credential / no such account" — your ordinary signed-out start). Also present, from our
v1-minimal revocation decision:

```
GET    /api/v1/auth/restore/credentials                    (authenticated)
DELETE /api/v1/auth/restore/credentials/{credential_id}    (authenticated; id is base64url)
```

Details you'll observe on the wire:

- Challenges are single-use with a 5-minute TTL; a replayed assertion fails with
  `restore_credential_invalid`.
- `rp.id` on dev is `app-dev.makapix.club`; registration options carry
  `residentKey: "required"`, `userVerification: "discouraged"`, `attestation: "none"`.
- The `userHandle` is 32 bytes, minted on first `/restore/options` call, stable thereafter.
- Multiple credentials per account coexist; re-registering the same credential_id upserts, so the
  `E2eeUnavailableException` retry is safe.
- `/restore/challenge` has its own rate bucket (30/5min/IP), deliberately separate from the login
  bucket so a migrating device probing for a credential can never lock out the real sign-in that
  follows.

The full server behavior is covered by 11 software-authenticator round-trip tests
(`api/tests/test_restore_credentials.py`) — registration → migration-style userless assertion,
replay, unknown-credential, wrong-origin, sign-count regression (allowed and logged), revocation.

## One deviation from the letter of 0001

Your item 2 sketched `POST /restore/register` verifying "the attestation". With `attestation:
"none"` (your §2b) there is no attestation statement to check — verification covers challenge,
origin, RP ID hash, and signature. Flagging it only so nobody looks for an attestation check that
deliberately isn't there.

## Prod status

The same code is deployed to prod (it rode the same merge), with `rp.id = makapix.club` and the
debug origin excluded. Nothing asserts against it until you ship, so the "joint flip" from the
plan reduces to your app release whenever M3 satisfies you.

Over to you for M3 — ping us at 0005 with how the bmgr cycle goes, especially whether §2a holds up
on the real device.
