# 0004 — Server → App: everything from 0003 is live on prod; eight differences from 0003

**From:** Makapix Club server team
**To:** Makapix app team (Makapix Club app)
**Date:** 2026-10-05
**Re:** `0003-server-localized-text-plan-and-email-copy.md` (same folder)
**Status:** **live on prod (makapix.club) and dev**, deployed 2026-10-05.
**Reply expected:** still the email translations (0003 §6.3), whenever ready. Please also
tell us about anything below that doesn't work for you.

Everything in 0003 is built and live. The full list of codes is the `ErrorCode` enum in
`api/openapi.json` (`/api/v1/openapi.json` on dev). Where the build differs from 0003, or
0003 didn't say:

## 1. Differences you should know about

1. **`pending_verification`: the message is still the literal `"pending_verification"`**, so
   your 1.12.0 substring match keeps working. The code is `pending_verification` (409).
   Switch to the code when you can; we will make the message human after your release
   reaches users. Tell us when it has.
2. **`invalid_credentials` replaces `unauthorized` on the password grant.** 1.12.0 maps
   `unauthorized` there to "Wrong email or password", so until your next release a
   non-English 1.12.0 user sees your generic headline with our English line instead. If that
   gap matters to you, say so and we'll hold this one code back until your release ships.
3. **Handle availability `reason` is never `reserved`** today: the server has no reserved
   handles. The value stays defined for later.
4. **`mod_hashtags_limit` and `hashtag_too_long` stay 422** (their existing status).
5. **The 413s:** both an oversized artwork (`file_too_large`) and an oversized avatar now
   return **413** with `details.max_bytes`.
6. **`dimensions_invalid` details** are `width`, `height`, `max`. `max` (256) is the
   largest canvas; below 128 only certain sizes are allowed (the message lists them).
7. **Admin ban/hide (your §7.1):** one route now accepts the user's UUID **or** sqid, at
   `/api/admin/user/{id}/…` and `/api/v1/admin/user/{id}/…`.
   - Ban takes the JSON body or `?duration_days=` (body wins).
   - A permanent ban returns `until: "9999-12-31T23:59:59Z"` (our permanent-ban marker),
     not `null`. This is unchanged from before.
   - Hide now returns `{"status": "hidden"}`.
8. **`weak_password` details:** `field`, `reason` (`required` | `too_short` | `no_letter` |
   `no_digit`), `min_length`.

## 2. Details 0003 didn't spell out

- **`email_taken.details.provider`** is present only when the existing account has exactly
  one sign-in method.
- **`format_not_available`** also covers a format whose file is missing or still being
  converted (same 404).
- **Comment `deleted`** is also `true` for comments anonymized when their author deleted
  their account (body `"[deleted comment]"`).
- **Player owner commands** gained two codes beside `detail`:
  - `unsupported_command` (`details.feature`) when the player lacks the feature;
  - `invalid_value` (`details.feature` plus `min`/`max` or `allowed`) for an out-of-range
    value.
- **BDR `items[].error_code`** is `user_not_found` | `no_posts` | `internal`. Older failed
  rows report `internal`.
- **Firmware-facing player endpoints** (player-token auth) are unchanged apart from the extra
  `code` key. A banned owner's player still gets 401 there.

## 3. Emails

All three emails already use the copy from 0003 §6.3, in English, and read `locale`. Each
translation file you send goes live the day we merge it.

Thanks!
