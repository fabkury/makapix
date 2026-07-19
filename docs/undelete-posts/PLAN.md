# Un-delete Posts During the 7-Day Window — Plan

**Status:** planned, not scheduled for implementation (as of 2026-07-19)
**Owner decisions collected:** 2026-07-19

## Background

User post deletion is a soft delete (`DELETE /api/post/{id}`,
`api/app/routers/posts.py`): it sets `deleted_by_user = true`,
`deleted_by_user_date = now`, `visible = false`, `hidden_by_user = true`, and
immediately frees the artwork hash for re-upload. The `cleanup_deleted_posts`
Celery beat task (daily, 03:30 US Eastern, `api/app/tasks.py`) permanently
deletes the row (cascading to comments/reactions/stats/notifications) and the
vault files 7 days later.

During the window the post exists but is inaccessible to *everyone* —
`can_access_post` (`api/app/utils/visibility.py`) refuses deleted posts
unconditionally, including owner and moderators — and there is no restore
path. This plan adds one, UI/UX-first.

## Owner preferences (decided 2026-07-19)

| Question | Decision |
|---|---|
| Restore surfaces | Undo toast after delete + owner-only permalink restore page + PMD (`/u/{sqid}/posts`) |
| Restore state | Exactly as it was — all prior visibility flags restored, no re-publish step, no mod re-approval |
| Hash re-uploaded during window | Block restore with a clear explanation + link to the new post |
| Deadline communication | Passive countdown on restore surfaces only — no notifications/emails |

## The mental model

Delete stops being framed as destruction and becomes "moved to a 7-day
trash." The delete confirmation dialog establishes this: *"This post will be
hidden immediately and permanently deleted in 7 days. You can restore it
until then."* — replacing any "cannot be undone" framing. (That phrase
remains only on the moderator permanent-delete dialog, and becomes the
distinguishing copy between the two delete types.)

## Surface 1 — Undo toast (the reflex saver)

- After a successful delete, a snackbar: **"Post deleted — Undo"**, visible
  ~10–15 s.
- Purely a shortcut for the accidental-tap case; it calls the same restore
  action as the other surfaces — no separate mechanism, no "grace period
  within the grace period." If the toast expires, the other surfaces still
  work for 7 days.
- Appears wherever delete can be triggered: the post page and the PMD.
  After a bulk delete in the PMD: **"N posts deleted — Undo"**.

## Surface 2 — Permalink restore page (the regret path)

- For the **owner only**, `/p/{sqid}` stops returning "post not found" and
  shows a quiet interstitial: artwork thumbnail, title, *"You deleted this
  post on {date}. It will be permanently deleted in N days."*, and a single
  **Restore** button.
- Everyone else — including moderators, per current policy — continues to see
  a 404 **indistinguishable from a real 404**, so deletion state is not
  leaked.
- This surface matters most: regret naturally lands here (old link, bookmark,
  remembered URL), and it fixes the "dead permalink with no explanation"
  confusion that motivated this effort.

## Surface 3 — PMD (the deliberate-management path)

The Post Management Dashboard (`web/src/pages/u/[sqid]/posts.tsx`,
`web/src/components/pmd/`) becomes the place to see all recently deleted
posts at once:

- Deleted posts appear in the PostTable with a **"deleted — N days left"**
  state in the existing visibility column (sortable/filterable like
  `hidden_by_user` today), visually muted (dimmed row or strikethrough
  title) so they read as "in the trash."
- Each such row gets a **Restore** action; the BulkActionsPanel gains
  **Restore selected**, symmetric with bulk delete.
- A filter ("Show: All / Active / Deleted") keeps the default view
  uncluttered; deleted rows may be excluded from the default view and only
  appear under the filter, iOS-Photos-style.

## Restore semantics

- **Full restoration, as if never deleted**: prior visibility, promoted
  status, reactions, comments, and stats intact — one click, no re-publish
  step, no re-approval queue.
- Implementation note: delete currently *overwrites* `visible` and
  `hidden_by_user`, so the prior flags must be **snapshotted at delete time**
  (new columns or a JSON snapshot) to honor exact restoration.
- Confirmation is lightweight: toast "Post restored" with a link to the live
  post. No confirm dialog — restore is inherently safe.

## The one failure case: hash re-uploaded

If the user re-uploaded the same artwork during the window (the hash was
freed at delete time), restore is blocked with blame-free copy: *"You've
since uploaded this artwork as a new post, so this one can't be restored."*
— with a link to the new post. Keep the copy simple (don't suggest deleting
the new post; its own 7-day window would still hold the hash).

Check eagerly where cheap: the permalink restore page and PMD row should show
"can't be restored (re-uploaded)" instead of the Restore button, so users
never click a button destined to fail.

## Countdown communication

Passive only: "N days left" on the three restore surfaces and in the delete
dialog copy. No emails, notifications, or banners. Show **days, not a live
timer** — the sweep runs once daily at 03:30 ET, so minute-level precision
would be false.

## Non-goals

- No moderator restore surface; deleted posts stay 404 for moderators. The
  mod dashboard's "deleted by user" badge (PR #239, live 2026-07-17 window)
  covers their awareness need.
- No change to moderator permanent delete (`DELETE /api/post/{id}/permanent`)
  — immediate and irreversible, keeps its "cannot be undone" dialog.
- No change to the 7-day duration or the cleanup task schedule.

## Implementation sketch (for when this is picked up)

1. **API**
   - `POST /api/post/{id}/restore` (owner-only): validates window not
     expired, checks hash conflict, restores snapshotted flags, clears
     `deleted_by_user*`, invalidates feed caches.
   - Snapshot prior flags at delete time (migration).
   - Owner-only deleted-post data on `GET /api/p/{sqid}` (or a dedicated
     endpoint) for the permalink interstitial — must 404 identically for
     non-owners.
   - PMD listing endpoint gains deleted posts + `deleted_by_user_date` for
     the owner.
2. **Web**
   - Undo toast on the post page + PMD delete/bulk-delete flows.
   - Permalink interstitial for owners.
   - PostTable deleted state + filter; BulkActionsPanel "Restore selected."
   - Delete confirmation dialog copy update.
3. **Tests**: restore happy path, window expiry, hash-conflict block,
   non-owner 404 indistinguishability, bulk restore.
