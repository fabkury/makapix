# New-Post UX: review-status messaging & pending-post visibility

**Started:** 2026-08-18 · **Owner ask:** inform users, at posting time, what
happens to their post depending on Trust (`users.auto_public_approval`).

## Decisions (owner, 2026-08-18)

1. **Code matches message** — a pending post (`public_visibility=false`) is
   visible on the author's profile to *every* viewer and reachable by *anyone*
   via direct permalink. Moderation approval gates **discovery surfaces only**
   (Recent feed, search, hashtags, sitemap, reacted-posts channel). This makes
   the long-standing `/about` "Post Approval" copy true (it previously
   contradicted the code, which returned 404 to everyone but author+mods).
2. **Message before + after upload** — untrusted users see a heads-up on the
   upload form; the success screen distinguishes "awaiting review" vs.
   "auto-approved and live".
3. **Follow-up surfaces** — author-visible "Pending approval" badge on own
   post page and profile-grid tiles; `post_approved` notification when a mod
   approves; `trust_granted` notification when a mod grants Trust.
4. **Scope** — /submit, divoom-import (single + batch), /about copy fix.

## Implementation map

Backend:
- `api/app/utils/visibility.py:can_access_post` — pending posts pass; only
  `visible`/`hidden_*`/`deleted_by_user` gate link access.
- `api/app/routers/posts.py` — GET /post profile views (owner_id filter, no
  reacted_by) no longer filter `public_visibility`; upload response message
  explains review + profile/link visibility; `approve_public_visibility`
  sends `post_approved`.
- `api/app/routers/umd.py` + `admin.py` — trust grant sends `trust_granted`.
- `api/app/constants.py:NotificationType` — new `POST_APPROVED`,
  `TRUST_GRANTED`.

Web:
- `web/src/components/PostReviewNotice.tsx` — shared notice
  (pre-upload / pending / approved variants; Copy-link on pending).
- `web/src/pages/submit.tsx` — pre-upload notice (untrusted), variant-aware
  success card; fetches `/api/auth/me` capabilities (`can_post_public`).
- `web/src/lib/api.ts` — `MeResponse.capabilities` (previously discarded).
- `web/src/pages/divoom-import.tsx` — variant-aware single-upload message,
  batch completion pending-count summary, pre-upload notice.
- `web/src/pages/p/[sqid].tsx` — "Pending approval" badge now for author too.
- `web/src/components/CardGrid.tsx` — ⏳ chip on own pending tiles (author/mod).
- `web/src/pages/notifications.tsx` — renders the two new types.
- `web/src/pages/about.tsx` — Post Approval copy mentions direct-link sharing.

Tests: `api/tests/test_pending_post_visibility.py` (new);
`api/tests/test_content_visibility.py` updated (its "hidden" fixtures now use
`hidden_by_user` since pending posts are deliberately reachable).

## Notes

- The Flutter app was NOT part of this effort; the new notification types are
  additive (free-form string on the wire).
- Comments/reactions on pending posts are allowed (they're reachable posts).
- `total_posts` profile stat always counted pending posts; now consistent
  with the visible grid.
