# 0005 — App → Server: the email translations; keep `invalid_credentials`; what 1.12.0 does now

**From:** Makapix app team (Makapix Club app)
**To:** Club server team
**Date:** 2026-10-05
**Re:** `0003-server-localized-text-plan-and-email-copy.md` and
`0004-server-localized-text-live-on-dev.md` (this folder)
**Status:** email translations delivered (§1). The app is adopting everything in 0003/0004 for
its next release (§4).
**Reply expected:** none needed. A short `0006-server-…` when the translations are live would be
welcome. We will write again when our next release has reached users (§4).

Hello server team, and thank you: everything we asked for, live on prod in three days, and
the ban/hide clash fixed on the way!

## 1. The email translations

`email-copy/` beside this thread holds one file per locale, with the same keys and key order
as your `api/app/email_copy/en.json`: `es.json`, `pt-BR.json`, `fr.json`, `de.json`,
`ru.json`, `ja.json`, `zh-Hans.json`. Per your README they can be dropped into
`api/app/email_copy/` as they are. Spanish ships as plain `es`, so `es-419`, `es-ES`, and
`es-MX` all find it through your base-language step.

- Every placeholder survives (checked by script), and the footer is identical to English.
- They went through the same independent review as the app's strings (18 findings, all
  applied). The terms match the app screens that send the emails.
- Three choices you might wonder about:
  - **German** greets with "Hallo {handle}!" and an exclamation mark, not a comma, so the next
    line may start with a capital however your layout places it. German letter convention
    lowercases the line after a comma.
  - **Japanese** keeps a half-width space where Latin text meets Japanese ("Makapix Club の…",
    "{handle} さん", "有効期限は {expires} です"), as every app string does.
  - **Russian** calls the download "архив работ" (an archive of artworks) throughout. A
    literal "batch download" reads as translationese.

If you change a key or add one later, send us the English and we will return the seven.

## 2. `invalid_credentials`: keep it

No need to hold it back. 1.12.0 users who type a wrong password see your English sentence
until our next release, which maps `invalid_credentials` to the app's own "Wrong email or
password." We accept that gap.

## 3. What 1.12.0 does with your new responses (checked, nothing for you to do)

- **`account_banned` as 403:** 1.12.0 already translates the code, so a banned user now reads
  "This account is banned." in their language: at sign-in, and on any action while their
  access token lasts. When it expires, the refresh grant's 403 signs them out without a
  message. The next release signs them out at the first 403 and shows the reason, with the
  date from `banned_until`.
- **`quota_exceeded`:** 1.12.0 still says "You've reached your upload limit for now." for a
  full storage quota; the next release says storage, with the numbers from `details`.
- **Moderator ban/hide by sqid** now works from 1.12.0 (it sends `?duration_days=`, which you
  kept).
- Everything else is additive for 1.12.0 (extra `code`/`details`/`reason`/`error_code` keys
  are ignored), and the two wording matches it relies on (`pending_verification`, and
  "already taken" in the handle check) still hold.

## 4. What the next app release does

It reads every code in your `ErrorCode` enum that a user can meet. That includes `code` and
`details` beside `detail` on the unversioned paths, and the numbers in `details` (the
`max_bytes` limit, `banned_until`, the comment and download limits). It also reads the handle
check's `reason`, the badge slugs (labels and descriptions in eight languages), `window_seconds`,
the download `error_code`, the comments' `deleted` flag, and GitHub's `error_code=`. It sends
`locale`:
on register and the two code requests, and through `PATCH /user/{key}` after every sign-in
and whenever the user changes the app's language. The value is always the language the app
is showing (`en`, `es`, `pt-BR`, `fr`, `de`, `ru`, `ja`, `zh-Hans`), never null.

When that release has reached users we will tell you here, so you can make the
`pending_verification` message human and retire the root `/api/hashtags/top`.

Thanks!
