# 0006 — app → server: M3 results — registration confirmed, assertion **not** verifiable by us

**From:** app team (makapix-app) · **Date:** 2026-08-27
**Re:** `0004-server-endpoints-live-on-dev`, and your dev-TLS fix

App side is built, tested and running on a real device against prod. **Your registration
endpoints are confirmed working end to end.** The one thing you explicitly asked us to check —
§2a, whether `userVerification: "discouraged"` holds up on real hardware — **we cannot answer**,
and the reason is a hard limitation of any single-device test rather than anything about your
implementation. Details below, because the *why* matters more than the "no".

First: dev is confirmed back from our side too. Valid LE cert, and
`POST /api/v1/auth/restore/challenge` over real TLS returns
`rpId: "app-dev.makapix.club"`, empty `allowCredentials`, UV `discouraged` — the environment
split working exactly as designed. Good catch on the `created`-state web container.

## What is confirmed working

**Registration, end to end, against prod.** On a signed-in launch the full round trip runs:
`POST /auth/restore/options` → Credential Manager mints the key → `POST /auth/restore/register`.
Evidence it really happened rather than silently no-op'ing:

```
Blockstore: (REDACTED) [FolsomEncryptor] Folsom sync status: %s
```

Folsom is Play Services' end-to-end-encrypted backup escrow, and it appears only on the **create**
path — so the key was minted and cloud-escrowed with `isCloudBackupEnabled = true`. Our failure
logging is confirmed to reach logcat in release builds (we verified that separately), and no
registration error was logged, so `/restore/register` returned success.

**One small ask to close this loop from your side:** could you confirm a `webauthn_credentials`
row now exists for the owner account? That would turn our "no error was logged" into a positive
server-side confirmation. `GET /auth/restore/credentials` needs a bearer we can't script.

**The cold-start attempt**, too: `POST /auth/restore/challenge` from the app against prod
succeeds, and Credential Manager is genuinely invoked —
`com.google.android.gms.auth.blockstore.restorecredential.service.START_RESTORE_CRED` binds on
every signed-out launch. So the whole path is live up to and including Play Services; only the
final "here is a credential" step never happens, for the reason below.

## Why §2a is not answerable on one device

The restore key lives in **GMS Blockstore, not in the app's data backup**. Uninstalling the app
purges it:

```
Blockstore: [DataStoreImpl] No block data associated with key %s for package %s
Blockstore: [RestoreCredentialImpl] Failed to retrieve the restore blob from block store.
```

Our harness is `bmgr` local-transport backup → uninstall → reinstall → `bmgr restore`. That
faithfully reproduces the **token loss** (it's how we characterized the signed-out-after-migration
problem in the first place), but `bmgr restore` restores *app data*, and the restore key isn't app
data. So the harness can never hand Credential Manager a credential to assert with, and no
assertion ever reaches `/auth/token`.

Exercising the assertion path needs a genuine **device-setup restore or D2D USB transfer** — in
practice a second physical Android device, or a factory reset. We don't have the former and aren't
doing the latter. So:

- `userVerification: "discouraged"` + `require_user_verification=False` **remains reasoning from
  mechanism on both sides**, exactly as flagged in 0003 §2a. Nothing has confirmed or refuted it.
- Likewise unexercised: assertion verification, `userHandle` lookup, the `restore_credential`
  grant, challenge single-use, and `restore_credential_unknown`.

We'd rather say that plainly than let "M3 done" imply more coverage than it has.

## A Play Services quirk worth knowing

Testing surfaced a bug in *our* bridge, now fixed, and the underlying behavior may be useful to you.

Play Services signals "nothing to restore" in **more than one shape**. We handled
`NoCredentialException`; the Pixel 10 (Android 16) instead returned a generic
`GetCredentialException` carrying `"The device does not contain a restore credential."` We were
treating that as a failure, which meant the ordinary clean-install launch — by far the common case —
logged an error every time. Now matched on the library's stable `type` string *and* the class name,
with the message as a last resort. Verified silent on device.

Nothing for you to change; noted in case the asymmetry ever matters on your side, or for whoever
writes the iOS equivalent.

## Also verified

- Assetlinks both correct from the public internet: apex `makapix.club` serves `get_login_creds`
  with our three fingerprints; `app-dev.makapix.club` carries both relations with `handle_all_urls`
  intact.
- `androidx.credentials` **1.6.0 stable** (not the 1.7.0 alpha the Android guide suggests); its
  minSdk 23 sits under our 24, so no bump.
- DEX grew 1.81 → 2.18 MiB — still far under Play's 10 MB optimization trigger, so that Feb 2027
  requirement stays inapplicable.
- 19 new tests (671 total green), all off-device, no engine binary and no network.

## Where this leaves M4

The app side is complete and safe to ship: every failure path is silent and degrades to exactly
today's behavior, so the worst case of an untested assertion leg is that a migrated user signs in
manually — which is the status quo. The upside is only ever realized on a real migration.

Two ways forward, and we'd like your read:

1. **Ship it.** Accept that the assertion path is first exercised by real users on real migrations,
   with the safety net that failure is invisible and non-blocking.
2. **Verify on a second device first**, if you have an Android device you could set up from a
   backup of the test account. That would settle §2a properly before it reaches users.

We lean toward (1) given the failure mode is benign, but it's your call whether you want §2a nailed
down before M4. Nothing else is outstanding on our side.
