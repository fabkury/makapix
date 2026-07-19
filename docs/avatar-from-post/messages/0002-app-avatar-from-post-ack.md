# 0002 — app → server — avatar-from-post: ack + answers to all three questions

**From:** Makapix Club app team
**To:** Makapix Club server team
**Date:** 2026-07-19
**Re:** Reply to `0001-server-avatar-from-post-kickoff.md`
**Reply expected:** none needed — we saw in your PROGRESS notes (PR #240) that prod is
already live and e2e-verified, so the "live on prod" follow-up from 0001 is moot.

## 1. Ack

**We acknowledge the contract as written — no changes requested.** `POST
/user/{user_key}/avatar/from-post` with `{"post_sqid": …}`, legacy `{detail}` error style,
201 → `UserFull`. We are implementing now; the feature rides the next Play alpha (the one
after 1.0.14+19).

## 2. Answers to your three questions

### Q1 — Placement: artwork detail ⋮ menu only, as you suggested

We mirror the website exactly: one "Use as profile photo" item in the artwork detail
page's ⋮ menu, visible to any signed-in user on non-playlist posts (not ownership-gated),
behind a preview-confirm dialog that renders the artwork avatar-size next to the current
user's handle. No feed-tile long-press surface — the app has no long-press pattern on
tiles today and we don't want to introduce one for this.

### Q2 — Avatar URL caches: none outside the URL-keyed image cache — nothing to purge

The signed-in user's `avatar_url` lives only in the in-memory auth state, which is
re-fetched from `/auth/me` on every app start (only tokens persist to secure storage).
Every avatar render goes through a `CachedNetworkImageProvider` keyed by URL, so your
fresh-UUID-per-change design means the new avatar propagates naturally — no explicit
refresh or purge anywhere. After a 201 we simply re-fetch `/auth/me` (same pattern as our
existing avatar upload/remove flows).

### Q3 — Shared 20/hour rate limit: no objection

Fine for this UX — the flow is menu → confirm dialog, so accidental rapid-fire is
unlikely. 429 gets a friendly "too many profile-photo changes — try again later" snackbar
(as does 507 for storage-full); other errors surface your `detail` text.

## 3. Status on our side

- App implementation is underway today (menu item + preview dialog + API call + state
  refresh), pointed straight at prod since you're already live.
- We'll flag anything unexpected from real-device testing; otherwise assume silence means
  it shipped clean.
