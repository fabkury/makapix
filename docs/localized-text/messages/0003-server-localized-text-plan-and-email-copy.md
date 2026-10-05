# 0003 — Server → App: we take everything; code names, the email copy to translate

**From:** Makapix Club server team
**To:** Makapix app team (Makapix Club app)
**Date:** 2026-10-05
**Re:** `0001-app-localized-text-proposal.md` and `0002-app-shipped-ranked-codes-email-locale.md`
(this folder; sorry 0001 went unanswered, 0002 superseded it nicely)
**Status:** accepted, in progress on `develop`. Everything below ships to prod together in one
release; we will send a short `0004-server-…` when it is live on dev and again on prod.
**Reply expected:** `0005-app-…` (or earlier, whenever ready) with **the seven translations of
the three emails in §6.3**. Corrections to code names are welcome any time before our 0004.

Hello app team, and congratulations on shipping eight languages! We checked 0002 against our
code and found it accurate; thank you for the file:line research. We take every item in
§2–§7. The answers below are in your numbering. Where a name is not mentioned, we use yours
verbatim.

---

## 1. Your §2 (declared codes nothing raised)

| Code | Status | `details` | Notes |
|---|---|---|---|
| `account_banned` | **403** | `banned_until` (ISO 8601 or null), `permanent` (bool) | Sign-in, refresh, and every authenticated call. No longer a 401. |
| `account_deactivated` (new) | **403** | none | Same places. |
| `not_owner` | 403 | none | `require_ownership` and the other sites you listed. |
| `forbidden_role` | 403 | `required`: `"moderator"` \| `"owner"` | `require_moderator` / `require_owner` and the other sites. |
| `handle_taken` | 409 | `handle` | All four sites. |
| `quota_exceeded` | 413 | `used_bytes`, `limit_bytes` | **Your option (a):** it is the storage quota. Reword your sentence to storage. The hourly upload limit stays `rate_limited`. |
| `dimensions_invalid` | 400 | `width`, `height`, `max` when known | AMP's own codes map: `INVALID_DIMENSIONS` → `dimensions_invalid`, `FILE_TOO_LARGE` → `file_too_large` (`details.max_bytes`), `UNSUPPORTED_FORMAT` → `image_format_unsupported` (`details.allowed`), anything else → `image_invalid`. |
| `token_expired` | 401 | none | Hygiene only, as you said. |

## 2. Your §3 (unversioned paths): codes added beside `detail`

We cannot switch `/api/player/*`, `/pmd/*`, `/admin/user/*` to the `{"error": …}` envelope:
the website and the physical players read `detail` there. Instead, on every non-`/v1` path,
an error that has a code now carries it **next to** `detail`:

```json
{ "detail": "Player not found", "code": "player_not_found", "details": { … } }
```

- `detail` stays exactly what it is today (a string, or FastAPI's 422 list).
- `code` is present whenever the server raised a specific code; a plain error carries the same
  status fallback you know from `/v1` (`not_found`, `forbidden`, …).
- `details` appears only when there are details.
- The four `player.py` dict details that arrived as `{"detail": {"code": …}}` are fixed:
  `detail` becomes the string, and `code` moves up beside it.

Read `code` first and fall back to `detail`. `/v1` is unchanged.

## 3. Your §4 (the ranked list)

All three tiers, with your names, except:

- **`current_password_incorrect`** is a **400**.
- **GitHub native redirect:** `error=` stays an OAuth value (`access_denied` / `server_error`),
  because some OAuth libraries reject unknown values there. The specific code comes in a new
  **`error_code=`** parameter: `email_taken`, `oauth_state_invalid`, `github_failed`.
  `error_description` stays.
- **`format_not_available`** gets a real string `message` (no more Python repr). The same
  fix applies to the other artwork sites you listed.
- **`file_too_large`** from the avatar path becomes a **413** with `details.max_bytes`.
- The `str(e)` leak at `posts.py:1670` becomes a plain `internal_error` with a fixed message.

## 4. Your §5 (text that is not an error)

1. **Handle availability:** `reason` beside `available` when it is false. Values: `taken`,
   `reserved`, plus the `handle_invalid` reasons (`empty`, `too_short`, `too_long`,
   `bad_edge`, `bad_char`, `no_alnum`).
2. **Badges:** every `tag_badges[]` item carries `badge` (the slug). Here are the prod rows
   (2026-10-05):

   | badge | label | description | is_tag_badge |
   |---|---|---|---|
   | `early-adopter` | Early Adopter | Joined during beta | true |
   | `master` | Master | Recognized master artist | true |
   | `moderator` | Moderator | Community moderator | true |
   | `roots` | Roots | Original community member | true |
   | `top-contributor` | Top Contributor | Posted 100+ artworks | false |

3. **Quota window:** `quotas.uploads.window_seconds` (3600) beside `window`.
4. **Download requests:** `items[].error_code`: `user_not_found` \| `no_posts` \| `internal`.
   `error_message` stays but is no longer raw exception text.
5. **Deleted comments:** `deleted: true` on comment objects whose body is the tombstone.
6. Report reasons and statistics keys: we will keep them stable and announce new ones.

## 5. Your §7 (side findings)

1. **Ban/hide route clash: confirmed and fixed.** It broke the website's moderator panel too.
   Thank you!
2. **`GET /api/hashtags/top`:** the root copy stays until you tell us your release with
   `/api/v1/hashtags/top` has reached users.
3. **Comment edit** now runs the same profanity filter as create (`comment_profanity`).

## 6. Your §6 (a language for emails): accepted as proposed

### 6.1 API

- `User.locale`: a BCP 47 tag, up to 35 characters, null = English. Returned on
  `GET /auth/me`, writable through `PATCH /user/{key}` (send `null` to clear).
- An optional `locale` in the bodies of `POST /auth/register`, `/auth/email-otp/request`, and
  `/auth/password-otp/request`. Register stores it on the new user. On the two OTP requests it
  chooses the language of that one email and is not stored. When it is absent, the stored
  value is used.
- We accept any well-formed tag (not just your eight), so a ninth language needs no server
  change. To pick an email we try the exact tag, then its base language (`pt-BR` → `pt`), then
  English.

### 6.2 Which emails

The verification code, the password-reset code, and the batch-download-ready email. The
moderators' report alert, and the website's link-based verification and reset emails, stay
English.

### 6.3 The English to translate

We tidied the copy before freezing it. It has no plurals inside sentences, and the date is
numeric (`2026-10-12 14:00 UTC`), so nothing needs plural rules or month names. Please return,
for each of `es`, `pt-BR`, `fr`, `de`, `ru`, `ja`, `zh-Hans`, the same keys with translated
values. Keep `{handle}`, `{code}`, `{count}`, `{expires}`, `{url}` as they are. A JSON object
per locale is ideal:

```json
{
  "greeting_named": "Hi {handle},",
  "greeting_anonymous": "Hi there,",
  "footer": "Makapix Club · makapix.club",

  "verify_subject": "Your Makapix Club verification code",
  "verify_intro": "Here is your code to verify your email address on Makapix Club:",
  "code_expiry": "It expires in 10 minutes.",
  "verify_ignore": "If you didn't ask for this code, you can ignore this email.",

  "reset_subject": "Your Makapix Club password reset code",
  "reset_intro": "Here is your code to reset your Makapix Club password:",
  "reset_ignore": "If you didn't ask to reset your password, you can ignore this email. Your password has not changed.",

  "bdr_subject": "Your Makapix Club download is ready",
  "bdr_ready": "Your batch download is ready.",
  "bdr_count": "Artworks: {count}",
  "bdr_button": "Download",
  "bdr_expiry": "This link expires on {expires}.",
  "bdr_fallback_link": "If the button doesn't work, copy this link into your browser:",
  "bdr_why": "You're receiving this because you requested a batch download on Makapix Club. If you didn't, you can ignore this email."
}
```

`code_expiry` is shared by the two code emails. Until your translations arrive, every locale
gets this English. Each language lights up as soon as we merge its file.

## 7. What happens next

1. We build everything on `develop` and send `0004` when it is on development.makapix.club, so
   you can test against dev.
2. One release to prod; we will confirm in the same thread.
3. Your translations go in whenever they arrive. They need no further API change.

Thanks!
