# Report artwork — reports show what was reported

> **Status: CLOSED 2026-09-02.** Server + website live on prod (PR #270);
> app adopted on `main` (`936469bb`), shipping with its next regular
> release. Residual: the app's build stamp + on-device pass (to be noted in
> `messages/0002`), and the owner's click-test of both cards on prod.
> Reopen trigger: a `0004-app-…` message from the release pass.

Follow-up to `docs/ugc-safety/` (the report pipeline). Started 2026-09-02
after the first real copyright report on prod landed as a card reading only
"post - Copyright or IP violation · post 3591" and a notification reading
"New post report: copyright" — the moderator had to look the post up by hand.

Goal: every surface that shows a report shows **the thing reported** (artwork
thumbnail, or the reported user's avatar) and links to it:

1. **Website — Moderator Dashboard → Reports tab**: card gets the artwork
   thumbnail + title + author, all linking to the post page (`/p/{sqid}`);
   comment reports quote the comment under the parent post; user reports show
   the avatar + handle linking to the profile.
2. **Website — /notifications**: `new_report` cards carry the artwork like a
   reaction card does. Card body → the dashboard's Reports tab
   (`/mod-dashboard?tab=reports`, new deep link); thumbnail → the post; user
   reports show the avatar → profile. `report_resolved` (to the reporter) gets
   the same artwork/avatar; its card opens the post/profile.
3. **App**: adopt the now-populated notification fields (thumbnail + tap),
   dropping its "forced inert" guard on `new_report`. Reports queue stays
   web-only.

## Contract change (server authority)

Social notification items (`GET /v1/social-notifications/` and the SSE
stream) gain four **additive, nullable** fields, null on every type except
`new_report` / `report_resolved`:

| Field | Meaning |
|---|---|
| `reason_code` | The report's reason code (ugc-safety D3 set) |
| `target_user_handle` | User-target reports: the reported user's handle |
| `target_user_public_sqid` | … their public sqid (→ `/u/{sqid}`) |
| `target_user_avatar_url` | … their avatar URL |

And the existing fields are now **populated** on those two types:

| Target | `post_id` / `content_title` / `content_sqid` / `content_art_url` | `comment_id` / `comment_preview` | `target_user_*` |
|---|---|---|---|
| post | the reported post | null | null |
| comment | the comment's **parent post** | the reported comment (100-char excerpt) | null |
| user | null | null | the reported user |

`content_title` is now the **post title** (it used to carry a pre-formatted
"New {type} report: {reason}" summary). The app must compose its copy from
`reason_code` + the target fields. `target_user_*` are resolved at read time
(rename-safe; null once the account is deleted), like `actor_public_sqid`.
Actor stays the system user (ugc-safety D18 — never the reporter).

Moderator listings (`GET /v1/report`, web-only) gain `target` — a resolved
summary of the report target (`schemas.ReportTarget`); `null` when the target
no longer exists.

The full message to the app team: [`messages/0001-server-report-notifications-artwork-kickoff.md`](messages/0001-server-report-notifications-artwork-kickoff.md).

## Decisions (owner, 2026-09-02)

- **R1** All three target types carry something: post → post, comment →
  parent post + comment excerpt, user → the reported user's avatar/handle.
- **R2** Website `new_report` click: card → Reports tab, thumbnail → post
  (mirrors reaction cards' two tap targets). The app, which has no queue,
  opens the post/profile from the whole tile.
- **R3** App scope is the notification only; no in-app reports queue.
- **R4** `report_resolved` gets the same treatment so the reporter sees which
  report closed. Still no action details (ugc-safety D22).
- **R5** New columns (`social_notifications.target_user_id`, `.reason_code`)
  rather than overloading `actor_*` for the reported user — the app team had
  explicitly flagged that ambiguity (their A15 / R9).

## Progress

- **2026-09-02** — Server + website implemented (migration `b2c3d4e5f6a7`,
  `_notification_target` / `_target_summary` in `routers/reports.py`,
  `create_system_notification` grew `post`/`comment`/`target_user`/
  `reason_code`; dashboard card + `?tab=` deep link; notifications page).
  Alert email links `/p/{sqid}`. Tests in `tests/test_reports.py`.
  Verified live on dev (one report per target type), `make check-full`
  green, **PR #270 merged and deployed to prod the same day**. Message
  `0001` sent to the app team (copy committed to the app repo as
  `docs/club-server-cr-report-notifications-artwork.md`). Open: app reply
  `0002` with the adopting build; owner click-test of both cards on prod.
- **2026-09-02** — App reply `0002` received: adopted on makapix-app `main`
  (commit `936469bb`) — whole tile opens the post / profile, artwork or
  avatar thumbnail, copy composed client-side with live `report_reasons`
  labels, legacy rows keep their summary; both questions answered (plain
  post title: accepted; comment reports keep the parent post). Ships on the
  app's next regular release (live is 1.7.0+35); build to be stamped in
  `0002`. Still open: owner click-test of both cards on prod; app on-device
  pass on dev.
- **2026-09-02** — Closing ack `0003` sent; website `new_report` glyph
  switched to the shield to match the app (one moderation glyph across both
  clients). Effort CLOSED (see status banner).
