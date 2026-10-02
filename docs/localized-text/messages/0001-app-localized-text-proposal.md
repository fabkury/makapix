# 0001 — App → Server: text the server composes, now that the app speaks eight languages

**From:** Makapix app team (Makapix Club app)
**To:** Club server team
**Date:** 2026-10-02
**Re:** opening the thread
**Status:** the app is translated into English, Spanish, Brazilian Portuguese, French, German,
Russian, Japanese, and Simplified Chinese (not yet released; it ships when the work in
`docs/i18n/` is done). Nothing below blocks that release.
**Reply expected:** `0002-server-localized-text-…md` in this folder: which of the items in §3
you want, in what form, and when (or that you would rather not)

Hello server team! This is a request for your opinion, not a change we need before we ship.
Research was done against server checkout `9489af9` (2026-09-02); if something below describes
your code as it was and no longer is, that is our staleness.

---

## 1. What the app already does on its own

- **Your stable error codes** (`api/app/errors.py`, `ErrorCode`): the app now shows its own
  translated message for every specific code (`handle_taken`, `artwork_duplicate`,
  `quota_exceeded`, `blocked`, `lineage_cycle`, … 26 in all, plus `rate_limited`). For these,
  your `message` is no longer displayed. Thank you for the envelope: it made this a one-file
  change.
- **Email sign-in:** a 401 `unauthorized` from the password grant is shown as the app's own
  "Wrong email or password."
- **Handle availability:** the app writes "available" and "already taken" itself (it matches
  `available` and the words "already taken" in your `message`). The "Invalid handle: …" reasons
  stay English in English and read "This username can't be used" elsewhere; the app checks the
  same format rules on the device first, so users rarely see them.
- **Report reasons:** matched by `code`; the app's own translation wins outside English (your
  `label` still wins in English, so a new reason you add shows up right away).
- **Notifications:** composed by the app from `type` and the payload fields. No server text.

## 2. What still reaches users in English

1. **Generic codes with specific prose.** About 400 plain `HTTPException`s map to
   `bad_request`, `conflict`, `not_found`, `forbidden`, or `internal_error`, and their `detail`
   is the only thing that says what went wrong. The app shows that text as is.
2. `POST /auth/check-handle-availability`: the app depends on the words "already taken" in
   `message` (see §1).
3. `POST /player/register` failures: the app currently picks a translated message by matching
   your English wording ("invalid", "expired", "already registered", "maximum … player").
   That breaks the day the wording changes.
4. `GET /pmd/bdr` → `error_message` on a failed download request.
5. `quotas.uploads.window` on `/auth/me` (the period's name), on the account page.
6. `GET /badge` → badge names and descriptions; `tag_badges[].label` on profiles.
7. `GET /license` → license titles. (Probably fine as they are: they are proper names.)

## 3. What we propose

In order of value to users:

- **(a) Codes where the user needs to act.** For the `HTTPException` sites a user can actually
  hit from the app (sign-in, registration, upload, publish, edit, comment, report, player
  registration), raise `AppError` with a specific code instead. We can send you the list of the
  ones we see in the app if that helps. The `details` field is ideal for numbers ("max 5").
- **(b) Player registration:** codes such as `player_code_invalid`, `player_code_expired`,
  `player_already_registered`, `player_limit_reached` (item 3).
- **(c) Handle availability:** a `reason` code when `available` is false (`taken`,
  `invalid_format`, `reserved`, …), so the app stops matching your wording.
- **(d) Download failures (bdr):** an `error_code` next to `error_message`.
- **(e) Badges and quota windows:** stable keys (`badge.key`, `window: "day" | "week" | …`) so
  the app can name them. Names of badges you add later can fall back to your text.

**Alternative we considered:** the app sending `Accept-Language` and the server translating.
We don't recommend it: it puts eight languages of copy on your side for text the app already
knows how to say, and the app's translations go through a review process that would have to be
duplicated.

## 4. What does not change

Your `message` / `detail` text stays exactly as useful as today: the app keeps showing it
whenever it does not know a code, and English users keep seeing it for generic codes.

Thanks!
