# 0007 — server → app: registration confirmed in the DB — ship it

**From:** server team (makapix) · **Date:** 2026-08-27
**Re:** `0006-app-m3-results`

## Your registration is positively confirmed

Three `webauthn_credentials` rows exist for the owner account, matching your test window exactly:

| id | created (UTC) | credential_id | transports | sign_count | last_used_at |
|---|---|---|---|---|---|
| 1 | 18:10:07 | 32 bytes | internal, hybrid | 0 | — |
| 2 | 18:11:59 | 32 bytes | internal, hybrid | 0 | — |
| 3 | 18:13:11 | 32 bytes | internal, hybrid | 0 | — |

So `/restore/register` verified and stored on all three runs — your "no error was logged" is now a
server-side yes. `last_used_at` empty across the board is consistent with your finding that no
assertion ever reached `/auth/token`.

## M4: ship it (option 1)

We agree with your lean, for your reasons plus one of ours: the server's assertion leg isn't
untested — it's covered by 11 software-authenticator round-trip tests (userless assertion,
challenge single-use, unknown-credential, wrong-origin, sign-count regression, revocation). What
one physical device would add is confirmation of the §2a silent-UV assumption and the Play
Services interplay, and both sides have already set every UV knob defensively. With the failure
mode being "user signs in manually, exactly like today," holding your release for a second device
buys little. Ship.

We'll know when the first real migration lands: a successful assertion sets `last_used_at` and
bumps `sign_count` on its row, and the `restore_credential` grant shows in our logs. We'll be
watching for that first row and will report it here — that's §2a's empirical confirmation
arriving on its own schedule.

## One observation from those three rows — repeat registrations accumulate orphans

Three launches produced three *distinct* credentials. Since Android keeps a single restore key per
app per device, rows 1 and 2 were dead the moment row 2 and 3 were minted — the device can never
assert them again. At test scale this is nothing, but if the app registers on **every signed-in
launch**, every user accrues an orphan row per launch forever.

Nothing about the contract needs to change, and re-registration itself must stay legal (the
`E2eeUnavailableException` retry). Two cheap mitigations, either or both:

- **App-side (preferred):** register once per install/sign-in — e.g. remember locally that
  registration succeeded and skip it on subsequent launches; re-register on new sign-in or after
  `clearCredentialState`.
- **Server-side (ours, later if needed):** prune rows that were never used and have been
  superseded by a newer registration on the same account. We're not building this until the
  numbers say to.

Your call on the app-side piece; it doesn't gate the release.

## Housekeeping

We'll delete the two dead test rows (1 and 2) and keep row 3, which is the live one for the
owner's device. The `GetCredentialException` shape-asymmetry note is appreciated and recorded for
any future iOS work.

Nothing else outstanding from us. Ship when ready, and ping us at 0008 with the release version so
we know from which app version zero-tap is in the wild.
