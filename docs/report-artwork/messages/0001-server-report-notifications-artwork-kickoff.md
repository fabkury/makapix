# 0001 — Server → App: report notifications carry the reported artwork / user (kickoff)

**From:** Club server team
**To:** Makapix app team (Makapix Club app)
**Date:** 2026-09-02
**Re:** ugc-safety `0003` §4(b) (superseded by this message), your A15 / R9
**Status:** LIVE on prod (2026-09-02, PR #270) — awaiting app reply

## Summary

The first real report on prod (a copyright claim on an artwork) showed us how
bare the report surfaces are: the moderator notification said "New post report:
copyright" with nothing to tap, and the dashboard card showed a raw post id. We
are fixing that end to end. On the website, report cards and `new_report`
notifications now show the reported artwork (or the reported user's avatar) and
link to it. This message asks the app to do the same for the notification —
the reports queue itself stays web-only.

This **supersedes ugc-safety `0003` §4(b)** ("post_id, content_sqid and
content_art_url are always null on new_report"). They are populated now, and
your open question from `0002`/A15 — *what does content_sqid carry for a
user-target report?* — is answered below: **content_sqid is always a post sqid
or null; a reported user rides in new `target_user_*` fields.** So the
"forced inert" guard on `new_report` can go.

## Payload shapes

Four **additive, nullable** fields on every social notification item (REST list
+ SSE stream, identical shape). They are null on every type except `new_report`
and `report_resolved`:

| Field | Type | Meaning |
|---|---|---|
| `reason_code` | `string \| null` | The report's reason code — the same D3 set you submit in `POST /report` (`spam`, `harassment`, `hate`, `sexual_explicit`, `violence_gore`, `illegal_csam`, `self_harm`, `copyright`, `other`) |
| `target_user_handle` | `string \| null` | User-target reports: the reported user's handle |
| `target_user_public_sqid` | `string \| null` | … their public sqid (your profile route takes it) |
| `target_user_avatar_url` | `string \| null` | … their avatar URL (absolute) |

And the existing fields are now filled in on `new_report` and `report_resolved`
depending on what was reported:

| Report target | `post_id`, `content_title`, `content_sqid`, `content_art_url` | `comment_id`, `comment_preview` | `target_user_*` |
|---|---|---|---|
| **post** | the reported post (`content_title` = its title) | null | null |
| **comment** | the comment's **parent post** | the reported comment (100-char excerpt in `comment_preview`) | null |
| **user** | null | null | the reported user |

Everything else is unchanged: `actor_*` remain the impersonal system user
(never the reporter — ugc-safety D18), `emoji` null, `notification_type`
values unchanged, delivery/unread/mark-read/retention unchanged.

Semantics / notes:

- **`content_title` no longer carries a summary sentence.** It used to be
  `"New {target_type} report: {reason_code}"`; it is now the post title (or
  null). Compose your copy from `reason_code` + the target fields (suggested
  copy below). Your current build renders `content_title` raw for `new_report`,
  so until you adopt this, a post report will read as just the post title —
  acceptable for the handful of moderators who receive these, but worth a
  prompt release.
- `target_user_*` are resolved **at read time**, like `actor_public_sqid`:
  rename-safe, and all three go null together once the account is deleted.
  Historical `new_report` rows (pre-2026-09-02) have all the new fields null
  and their old summary in `content_title`.
- A `new_report` for a target that vanished between report and notification
  is a bare notification (all target fields null) — keep the no-tap fallback.
- `report_resolved` (sent to the logged-in reporter when a moderator resolves
  their report) carries the **same** fields, so the reporter can see which
  report was reviewed. Still **no action details** (D22).
- Purely additive; ignore-unknown-keys safe; no version gating in either
  direction.

## Suggested UX (mirror of the website — your call on details)

The website `new_report` card: 🚩 glyph in the icon slot (no actor avatar —
same impersonal presentation as your shield), copy built from the fields,
thumbnail on the right. For post/comment reports the thumbnail is
`content_art_url` and opens the post; for user reports it is
`target_user_avatar_url` and opens the profile. The card body opens the
Moderator Dashboard's Reports tab; since the app has no queue, we suggest the
whole tile opens the post / profile.

Copy the website uses:

- post: `New report: "{content_title}" was reported for {reason label}`
- comment: `New report: A comment on "{content_title}" was reported for {reason label}` + the `comment_preview` as a second line
- user: `New report: {target_user_handle} was reported for {reason label}`
- `report_resolved`: `Thanks — we've reviewed your report ({same subject phrase})`

Reason labels (same as the report form): spam → "Spam or misleading",
harassment → "Harassment or bullying", hate → "Hate or discrimination",
sexual_explicit → "Sexual or explicit content", violence_gore → "Violence or
gore", illegal_csam → "Illegal content or child endangerment", self_harm →
"Self-harm or suicide", copyright → "Copyright or IP violation", other →
"Something else". Unknown/legacy codes: show the code, or "Something else".

Concretely in your code: `canTap = x.hasContentLink && x.type != 'new_report'`
(`notifications_page.dart`) becomes `x.hasContentLink || hasTargetUser`, with
the tap target chosen by which is present; `_shieldTypes` can stay as is.

## Status on our side

- Server + website are **LIVE on prod** (2026-09-02, PR #270). Historical
  rows are unaffected (see notes); new reports populate the fields from now on.
- Reference docs updated in the same change: `docs/http-api/notifications.md`
  (fields + table), `docs/ugc-safety/API-CONTRACT.md` §6 (pointer to this
  amendment). Effort doc: `docs/report-artwork/README.md`.
- To test on dev: file a report from the app against any post / comment /
  user on development.makapix.club while signed in as a moderator, then pull
  the notifications list. (Alerts are throttled to one per target per 6 h, so
  pick a fresh target each time.)

## Questions for you

1. Any objection to `content_title` becoming the plain post title on these
   two types (vs. keeping a pre-formatted summary)? We prefer one convention
   across all post-bearing types.
2. Do you want the parent-post `content_*` on **comment** reports (as
   specified), or would you rather have those null and only the excerpt?

Reply as `0002-app-…` in the server repo `docs/report-artwork/messages/` when
convenient, with the build the change ships in.
