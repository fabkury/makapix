# 0003 — app → server: Apple sign-in verified on device — GO for the prod flip

**From:** app team (makapix-app) · **Date:** 2026-07-09
**Re:** 0002 (grant live on dev)

## Verification

Done, same day. TestFlight build **1.0.9 (2)** (Codemagic build #6, commit `4fce67c` —
main + `CLUB_ENV=dev`) installed on the physical iPhone against
**development.makapix.club**:

1. **First sign-in with "Hide My Email"** — native sheet → relay address → the server
   minted a session on a fresh account, exactly per your relay policy. ✅
2. **Second sign-in** (Apple sends no name/email) — returning-user path, session minted. ✅

No errors surfaced on either path; the whole flow felt native (no browser leg).

## GO

Please carry the grant to prod (`develop` → `main`). App-side state, for the record:

- `kAppleSignInEnabled=true` is already on `main` (commit `42753c8`) — prod iOS builds
  will show the button as soon as makapix.club accepts the grant, no app release needed
  beyond our next TestFlight build.
- The temporary dev-env build branch is deleted; future builds are prod-pointing again.

Reply here (0004) when prod is live and we'll run the prod TestFlight build the same day.
This closes the last hard gate (guideline 4.8) before our App Store submission.
