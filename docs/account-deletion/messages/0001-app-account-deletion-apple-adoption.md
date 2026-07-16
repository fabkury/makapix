# 0001 — app → server — app adopts `POST /v1/user/delete-account` (Apple 5.1.1(v) rejection)

**From:** Makapix Club app team
**To:**   Makapix Club server team
**Date:** 2026-07-16
**Re:**   Account deletion — Apple App Store rejection, app-side adoption, prod-readiness asks
**Reply expected:** yes — §4 confirmations before we resubmit to Apple (planned within days)

## 1. Context

Apple rejected the app's first App Store submission (v1.0.9 build 5) under **Guideline 5.1.1(v) —
Data Collection and Storage**: an app that supports account creation must offer in-app account
deletion. We are adding the flow and resubmitting as **1.0.11** with a screen recording of the
complete deletion flow, as Apple requires.

## 2. What the app now does

New signed-in flow: ☰ → Account → Manage account → **Danger zone → Delete account** → a warning
page (permanence, sign-out, async data removal) → user types `DELETE` → the app calls:

- `POST /v1/user/delete-account` (bearer auth, no request body), expecting **202 Accepted**
  per the committed OpenAPI contract (`request_account_deletion_v1_user_delete_account_post`).

On 202 the app shows a confirmation dialog, clears local tokens, and returns to the signed-out
welcome screen. On any error it surfaces the server's error message and does nothing locally
(e.g. the owner-role refusal). The app treats the 202 body as opaque — no fields are read.

## 3. What we verified from our side

- The route is live and auth-gated on both environments: unauthenticated `POST` returns 401 on
  `development.makapix.club` and `makapix.club` (checked 2026-07-16).
- We saw commit `8cbd1f7` — *fix(tasks): make account deletion + BDR + unverified reaper actually
  complete [A1/A2/A3]* — with `api/tests/test_account_deletion.py`, merged to `main` via PR #236
  on 2026-07-15. This appears to close the "delete_user_account_task untested / fails on FK
  blockers" finding from the July codebase review. Good timing — thank you.

## 4. Asks (please confirm)

1. **Prod deployment**: confirm production is deployed at (or past) PR #236, i.e. the A1/A2/A3
   deletion fix is actually running on `makapix.club`, not just merged. Apple's reviewer may
   exercise the deletion flow against prod during review.
2. **One end-to-end verification**: if not already done as part of A1/A2/A3, run one real
   deletion of a throwaway account on dev (and ideally prod) via `POST /v1/user/delete-account`
   and confirm the background task completes: user gone, vault artifacts removed, login refused.
3. **User-facing copy check**: the app's warning page says the profile, posts, comments,
   reactions, followers, and settings are *permanently deleted* and unrecoverable. If anything
   user-visible survives deletion (e.g. anonymized reports, comment tombstones), tell us and
   we'll adjust the copy — Apple reads these screens closely.
4. **Demo account caution**: the App Review demo account (`fhi@kury.dev`) can now delete itself.
   Our review notes will ask the reviewer to create a fresh account for the deletion demo, but
   be aware the demo account may need re-creation if a reviewer deletes it.

## 5. Timeline

App-side work is complete and tested (249 Dart tests green, incl. the new deletion-flow widget
tests). We plan to cut the 1.0.11 iOS build and resubmit as soon as §4.1–4.2 are confirmed.
