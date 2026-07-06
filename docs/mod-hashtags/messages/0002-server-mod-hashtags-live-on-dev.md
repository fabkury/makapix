# 0002 — server → app — Moderator hashtags: live on development.makapix.club

**From:** Makapix Club server team
**To:**   Makapix Club app team
**Date:** 2026-07-05
**Re:**   Moderator hashtags (mod-hashtags)
**Reply expected:** message `0003-app-…` (this supersedes 0001's "reply as 0002" — batch your ack to 0001 and anything else into one 0003)

## 1. It's live

The full server + website implementation from message 0001 is now deployed to
**development.makapix.club**. You can build and test against it today.

- `GET /v1/config` now returns `max_mod_hashtags_per_post: 16` on dev — that's
  the feature-discovery key from contract §2, live and verified.
- `PUT /v1/post/{id}/mod-hashtags` is live, exactly as frozen in
  `docs/mod-hashtags/API-CONTRACT.md` (no contract changes were needed during
  implementation — v1 stands as written).
- `mod_hashtags` is present on all full Post objects.
- Notification type `mod_hashtags_updated` is live (diff in
  `comment_preview`, FCM `data.type` set, push title "A moderator updated
  tags on your artwork").

## 2. Verified end-to-end on dev

- Moderator PUT with `" #NSFW "` → normalized to `nsfw`, post immediately
  hidden from the anonymous/non-opted feed, visible again after revert.
- 401 without token, 403 for non-moderators, 404 for playlist/soft-deleted
  posts, 422 for >16 tags after normalization — all per the contract's error
  table.
- Artist edits (PATCH) preserve mod tags server-side; audit rows and artist
  notifications confirmed.

You can also see the reference UI on the dev website (post page: shield
markers, read-only chips in the owner edit form, "🛡️ Edit mod hashtags" with
monitored-tag quick-picks in the moderator menu) if you want to mirror it.

## 3. What we'd like back (one `0003-app-…` reply)

1. Everything asked in 0001 §6 (contract ack, whether the app has a
   moderator UI surface, rough ETA).
2. Anything you hit while testing against dev.

We're ready to flip prod whenever you are — the config key appearing on
makapix.club will be your launch signal.
