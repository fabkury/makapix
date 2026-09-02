# Report artwork — reports show what was reported

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
  Alert email links `/p/{sqid}`. Tests in `tests/test_reports.py`. See
  PROGRESS entries below for the rollout.
