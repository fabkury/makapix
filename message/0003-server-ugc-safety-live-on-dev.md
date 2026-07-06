# 0003 — server → app — UGC safety: live on dev + answers to your 0002

**From:** Makapix Club server team
**To:**   Makapix Club app team
**Date:** 2026-07-06
**Re:**   UGC safety — content reporting, user blocking (ugc-safety)
**Reply expected:** message `0004-app-…` (E2E results + prod go/no-go)

## 1. Dev go signal is ON

The full server + website implementation of the `0001` contract is live on
**development.makapix.club**. `GET /api/v1/config` there now carries the
`moderation` block — that's your gate to build and test against.

Everything shipped exactly per the frozen contract (v1, 2026-07-06). No
contract changes. Highlights verified end-to-end on dev:

- `POST /api/v1/report` — logged-in and anonymous (IP rate-limited); a live
  anonymous test report produced the moderator alert email and the
  `new_report` notifications.
- `POST/DELETE /api/v1/user/u/{public_sqid}/block`, `GET /api/v1/me/blocks`,
  `is_blocked_by_viewer` on profile responses.
- Server-side filtering of blocked users' content (feeds, search, comment
  threads incl. reply collapse, who-reacted, notifications) and symmetric
  `403 blocked` interaction guards on comment/reply/reaction/comment-like/
  follow.
- New notification types `new_report` (mods) and `report_resolved`
  (reporter).

## 2. One fix worth knowing about

While implementing, we fixed a latent server bug: unknown/garbage
`public_sqid` values used to 500 on sqid-addressed endpoints (integer
overflow); they now 404 cleanly. No contract impact — just don't be
surprised if you'd previously seen 500s there.

## 3. Website reference implementation

The website now has: report dialogs on posts/comments/profiles (logged-out
capable), block/unblock + blocked-state on profiles, a "Blocked users"
manager in settings, and the updated About → Rules ("What's not allowed",
zero-tolerance statement) and About → Moderation ("Reporting content",
"Blocking users", "Contact: acme@makapix.club, 24 h") pages that
`guidelines_url` / `moderation_policy_url` point at. Feel free to crib UX.

## 4. Answers to your 0002 clarifications

**(a) Playlist targets:** the server accepts any post row — including
playlist posts — as `target_type: "post"` (they share the posts table), so
you may drop your exclusion if the shared code path is simpler. Keeping the
exclusion is equally fine; the playlist owner stays reportable via their
profile either way. Your call, no contract change.

**(b) `new_report` payload:** it's a system notification — `post_id`,
`content_sqid`, and `content_art_url` are always null; the human-readable
summary rides in `content_title` (format: "New {target_type} report:
{reason_code}"). The actor is the system user, not the reporter. Your
generic no-tap tile is exactly right — the moderation queue is web-only
(mod-dashboard), so there's nothing in-app to deep-link to.

**(c)** Dialog-with-block-offer instead of a toast: nice touch, no notes.

## 5. What we need from you (one `0004-app-…` reply)

Your §5 plan works as-is — the dev key is live now, so your manual E2E can
start whenever you're ready. Send E2E results + prod go/no-go + any final
questions.

Prod flip happens as usual: server PR `develop` → `main` + deploy; the
`moderation` key appearing on `https://makapix.club/api/v1/config` is your
production launch signal. Order-independent on your side thanks to the gate.
