# 0002 — App → Server: the translations shipped; a ranked list of codes, and a language for emails

**From:** Makapix app team (Makapix Club app)
**To:** Club server team
**Date:** 2026-10-02
**Re:** `0001-app-localized-text-proposal.md` in this folder (it had no reply yet; this one
supersedes its §3 with concrete items)
**Status:** the app shipped in eight languages on 2026-10-02: Google Play 1.12.0 (39) in
production, App Store 1.12.0 (32) in review. Server English now reaches Spanish, Portuguese,
French, German, Russian, Japanese, and Chinese users.
**Reply expected:** `0003-server-localized-text-…md` in this folder: which items you take
(§2–§5), in what order, and any code names you would rather spell differently. Nothing blocks
the app; each item lights up in the app the day you ship it.

Hello server team! Research for this message was done against `develop` @ `48b3b49`
(2026-09-30); every `file:line` below is at that commit and relative to `api/app/`. Since then
`posts.py` moved (feed-bump), so its line numbers are approximate.

---

## 1. What the app does now (no change needed from you)

- **Your specific codes** keep showing the app's own translated sentence, as 0001 said.
- **Everything else you say is still shown, in every language, under a translated headline.**
  A failed save reads, in Spanish: "No se pudo guardar tu perfil." with your `message` /
  `detail` on a second, smaller line in English. English users see the same two lines. So your
  prose stays user-facing: please keep it short, human, and free of `str(e)` dumps (§5.4).
- An HTML error page (a proxy 502) is never shown; FastAPI's 422 list is shown as its `msg`
  lines; text over 300 characters is cut.
- **422 schema errors need nothing from you:** `details.errors[].type` / `ctx` are
  machine-readable already.
- **429 needs nothing on `/v1`:** every plain 429 arrives as `rate_limited` by your status
  fallback (`errors.py:111`).

## 2. Seven codes you declare, the app translates, and nothing raises

`token_expired`, `account_banned`, `forbidden_role`, `not_owner`, `handle_taken`,
`dimensions_invalid`, `quota_exceeded`. Most are one change in a shared helper:

| # | Code | Where | Reach |
|---|---|---|---|
| 1 | `account_banned` (`details.banned_until`, `permanent`) + new `account_deactivated` | `auth.py:131/137` (`check_user_can_authenticate`) | **Today a banned user signing in is told "Wrong email or password."** (the plain 401 becomes `unauthorized`), and an already signed-in banned user is silently signed out. Please also use **403, not 401**: the app answers every 401 with refresh-and-retry, so a 401 never reaches the screen as itself. |
| 2 | `not_owner` | `auth.py:536` (`require_ownership`, 30 callers); `users.py:532, 641`; `posts.py:2014`; `stats.py:59`; `users.py:1196` | Edit/delete post, comments, avatar, stats on a stale screen. |
| 3 | `forbidden_role` (`details.required: "moderator"\|"owner"`) | `auth.py:446` (`require_moderator`, 57 uses), `auth.py:458`; `posts.py:1708`; `pmd.py:63` | The moderation suite after a role is revoked. |
| 4 | `handle_taken` | `routers/auth.py:1167, 1184, 1210`; `users.py:559` | Onboarding and Change username. |
| 5 | `quota_exceeded`, see §2.1 | `posts.py:660, 1497, 2062` (`format_quota_error`) | Publish, replace, layers. |
| 6 | `dimensions_invalid` (`details.width`, `height`, `max`) | `posts.py:705-714, 2103-2110` already read AMP's `error.message` and drop its `error.code` (`INVALID_DIMENSIONS`, `FILE_TOO_LARGE`, `UNSUPPORTED_FORMAT`, …) | Publish / replace. Forwarding AMP's code is a two-line mapping. |
| 7 | `token_expired` | `auth.py:317-368` | Not user-visible (the app refreshes on 401); hygiene only. |

### 2.1 Storage quota currently says "The file is too large."

`HTTPException(413, format_quota_error(...))` gets `file_too_large` from the 413 fallback
(`errors.py:109`), so a user with a full storage quota is told their file is too large. Two
options, your call:

- **(a)** raise `quota_exceeded` with `details.used_bytes` / `limit_bytes`; the app rewords its
  `quota_exceeded` sentence to storage ("You've used all your storage.") the day you ship.
- **(b)** a new `storage_quota_exceeded`, keeping `quota_exceeded` for something else.

We lean to (a) unless `quota_exceeded` was meant for the hourly upload limit (that one already
arrives as `rate_limited`).

## 3. A prerequisite: the envelope on the unversioned paths the app calls

`_is_v1()` (`errors.py:169-172`) only wraps `/v1/*`. The app's **players**
(`/api/player/register`, `/api/u/{sqid}/player*`), **Post Management** (`/api/pmd/*`), and
**User Management** (`/api/admin/user/*`) get FastAPI's `{"detail": …}`, and an `AppError`
there loses its code (`errors.py:184-191`). The dict details in `player.py:1766, 1837, 1869,
1900` arrive as `{"detail": {"code": …}}`, which nothing reads. Until those paths get the
envelope (or move under `/v1`), codes added there do nothing. Item 3 in 0001 (player
registration) depends on this.

## 4. The ranked list: generic codes with prose → specific codes

About 95 raise sites the app can reach collapse to about 45 codes (of 418 `raise
HTTPException` lines; the rest are web-only, admin-only, programmer errors, or 500s that
should stay `internal_error`). Suggested names; spell them as you like. `*` = already declared.

### Tier 1 — every user meets these

| Code | Status | Today's text | Site(s) |
|---|---|---|---|
| `post_not_found` | 404 | "Post not found" (×51) | `utils/visibility.py:83`, `artwork.py:76-101`, `posts.py` (many), `users.py:905`, `stats.py:50` |
| `user_not_found` | 404 | "User not found" (×70) | `users.py:1318-1361` and around |
| `comment_not_found` | 404 | "Comment not found" | `comments.py:341, 409`; `comment_likes.py:91`; mod paths `comments.py:488-591` |
| `invalid_credentials` | 401 | "Invalid email or password." (`AppError(unauthorized)`) | `routers/auth.py:606, 613`. Today it shares `unauthorized` with the ban case (§2 #1). |
| `email_taken` (`details.provider`) | 409 | "An account with this email already exists…" | `routers/auth.py:297, 386, 409` (register), `771, 797` (Apple), `2060` (GitHub) |
| `pending_verification` | 409 | "pending_verification" (the detail *is* a code) | `routers/auth.py:335`. The app substring-matches it today. |
| `apple_email_missing` | 400 | "Apple did not provide an email address…" | `routers/auth.py:758` |
| `weak_password`* (`details.reason`, `min_length`) | 400 | the `validate_password` text | `routers/auth.py:1085` (change password, plain 400), `1664` (reset, `validation_error`); and add `details.reason` at `223` |
| `password_login_unsupported` | 400 | "…This account may not support password login." | `routers/auth.py:1668, 1093` |
| `current_password_incorrect` | **400/403, not 401** | "Current password is incorrect" | `routers/auth.py:1077`. The 401 sends the app through a token refresh first. |
| GitHub redirect `error=` codes (`email_taken`, `oauth_state_invalid`, `github_failed`) | 302 | everything is `access_denied` + `error_description` | `routers/auth.py:2224-2246`; details at `1835/1856, 1883, 1962, 2060` |
| `handle_invalid` (`details.reason: empty\|too_short\|too_long\|bad_edge\|bad_char\|no_alnum`, limits, `position`, `char`) | 400 | "Invalid handle: …" | `routers/auth.py:1140`; `users.py:552`; reasons in `utils/handle_normalize.py:100-131` |
| `email_not_verified`* | 403 | "Email verification required to change handle." | `routers/auth.py:1122` |
| `image_empty`, `image_format_unsupported` (`details.allowed`), `image_invalid` | 400 | "Empty file" / "Invalid image format…" / "File is not a valid image." | `users.py:685, 707, 722`; `avatar_vault.py:101` |
| `file_too_large`* (`details.max_bytes`) | 400 | "File size (X MB) exceeds maximum of Y MB" | `avatar_vault.py:108` via `users.py:745, 932`. Arrives as `bad_request` because of the 400. |
| `storage_full` | 507 | "Storage is temporarily full…" | `users.py:734, 921` |
| `post_has_no_artwork` | 400 | "This post has no artwork image" | `users.py:909` |
| `artwork_duplicate`* (`details.sqid`) | 409 | "Artwork already exists" | `posts.py:2153, 2238` (replace; upload already uses the code) |
| `artwork_unchanged` | 400 | "Artwork is identical to current artwork" | `posts.py:2136` |
| `storage_unavailable` | 503 | "Storage temporarily unavailable…" | `posts.py:945, 1513, 2309` |
| `mkpx_not_attached` | 404 | "Post has no layers file attached" | `posts.py:1548`; `artwork.py:166` |
| `post_deleted` | 400 | "Deleted posts cannot be restored" | `posts.py:1754` |
| `comment_profanity` | 400 | "Comment contains inappropriate language" | `comments.py:188` |
| `comment_cap_reached` (`details.max`) | 409 | "Maximum comments per post (1000) exceeded" | `comments.py:207` |
| `parent_comment_not_found` | 400 | "Invalid parent comment" | `comments.py:222` |

### Tier 2 — less common (players and Post Management need §3 first)

| Code | Status | Today's text | Site(s) |
|---|---|---|---|
| `player_limit_reached` (`details.max`) | 400 | "Maximum 128 players allowed per user" | `player.py:177` |
| `registration_code_invalid` | 404 | "Invalid or expired registration code" | `player.py:195` |
| `player_already_registered` | 400 | "Player already registered" | `player.py:202` |
| `player_not_found` | 404 | "Player not found" (×10) | `player.py:1176…1756` |
| `post_not_visible` | 403 | "Post is not visible" | `player.py:1403, 1551` |
| `posts_not_owned` (`details.missing_ids`) | 400 | "Some posts not found or not owned by target user" | `pmd.py:233, 347, 429` |
| `bdr_daily_limit` (`details.limit`) | 429 | "Daily limit of 8 download requests reached…" | `pmd.py:411` |
| `bdr_not_ready` / `bdr_expired` / `bdr_not_found` | 400/410/404 | "Download not ready…" / "…has expired" / "Download not found" | `pmd.py:542-556` |
| `format_not_available` (`details.formats_available`) | 404 | a dict **without** `code`, which your handler turns into a Python repr string | `artwork.py:247` (also `261`, `398`, `176/329`) |
| `last_auth_method` | 400 | "Cannot unlink the last authentication method" | `routers/auth.py:1718` |

### Tier 3 — moderation screens

`mod_hashtags_limit` (`details.max`, `count`; `posts.py:1384`), `hashtag_too_long`
(`details.max_length`; `posts.py:1393`), `owner_protected` (`umd.py:53`, `admin.py:72…402`,
`pmd.py:79`), `comment_not_deleted` (`comments.py:531`), and please stop leaking `str(e)` in
"Failed to delete post: {e}" (`posts.py:1670`).

## 5. Text that is not an error

1. **Handle availability:** a `reason` next to `available` (the same enum as `handle_invalid`),
   so the app stops matching "already taken" in `message` (`routers/auth.py:1244-1265`).
2. **Badges:** make sure every `tag_badges[]` item carries its `badge` slug. The labels and
   descriptions live only in your database (`badge_definitions`; no seed in the repo). Could
   you send us `SELECT badge, label, description, is_tag_badge FROM badge_definitions`? We will
   translate them keyed by slug, and a badge you add later falls back to your text.
3. **Quota window:** `quotas.uploads.window` is `"1h"`; please add `window_seconds` so the app
   can say "per hour" in each language (`routers/auth.py:2628-2633`).
4. **Download requests:** an `error_code` (`user_not_found | no_posts | internal`) beside
   `items[].error_message`, which today can be any exception text (`tasks.py:3248`).
5. **Deleted comments:** a `deleted: true` flag, so the app can draw its own tombstone instead
   of the stored `"[deleted]"` body (`comments.py:450`).
6. **Report reasons and statistics keys** need nothing: the app keys them already. Please keep
   the codes stable and announce new ones.

## 6. A language for emails (new)

The verification-code, password-reset-code, and download-ready emails the app's users receive
are English f-strings in `services/email.py`, and the server has no idea of a user's language
(no column, no `Accept-Language`). We propose:

- **A stored `locale`** on `User` (BCP 47: `en`, `es`, `pt-BR`, `fr`, `de`, `ru`, `ja`,
  `zh-Hans`; null = English), returned on `/auth/me` and writable through `PATCH /user/{key}`.
  The app sends the language it is *showing* (the user can pick one inside the app, so the
  phone's language is not always it): right after every sign-in, and whenever the user changes
  it.
- **An optional `locale`** in the bodies that send an email before the user exists or signs in:
  `POST /auth/register`, `/auth/email-otp/request`, `/auth/password-otp/request`
  (`schemas.py:1449, 1559, 1572`). Register stores it on the new user.
- **The email functions** take the locale (`send_verification_otp_email`,
  `send_password_reset_otp_email`, `send_bdr_ready_email`) and fall back to English for any
  language they lack.
- **We can supply the copy.** The app's translations go through an independent review in all
  eight languages; send us the final English of those three emails (subject, body, footer) and
  we will return the seven translations in whatever shape suits you (a dict per locale is
  enough). The moderators' report alert stays English.

We do not propose `Accept-Language` on every request: the stored value is simpler for emails
sent later (download-ready), and it keeps the rest of the API language-neutral.

## 7. Side findings (not localization, but you should know)

1. **Possible route shadowing on ban/hide (unverified, worth one curl).** `admin.py` is mounted
   at the bare root (`main.py:308`) before `umd.router` (`main.py:316`), and both define
   `POST/DELETE /admin/user/{id}/ban` and `/hide`: `admin.py` with `id: UUID`, `umd.py:590-684`
   with a sqid. If Starlette matches `admin.py` first, the app's (and the website's) ban/hide
   by sqid fails with a 422.
2. **`GET /api/hashtags/top`** is served only by the legacy root copy of `search.router`
   (`main.py:277-281` says it will go). The app will move to `/api/v1/hashtags/top`; please
   keep the root copy until our next release reaches users.
3. **Comment edit skips the profanity filter** that create applies (`comments.py:328` vs
   `185-191`).
4. **App-side, fixed on our end:** error bodies of byte downloads (`/d/…`, `.mkpx`, BDR) were not
   decoded, so codes such as `not_remixable` never matched. The next app release reads them.

## 8. What the app does as your items land

Each code you ship gets the app's own sentence in eight languages (reviewed) in the next app
release, and its `details` fill the numbers in ("at most 16"). Until then nothing breaks: your
text keeps showing under the translated headline. The player-registration wording match and
the `pending_verification` match go away once their codes exist.

Thanks!
