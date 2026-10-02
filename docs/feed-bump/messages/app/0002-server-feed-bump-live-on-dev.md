# 0002 — Server → App: feed bump is live on dev, test instructions

**From:** Makapix Club server team
**To:** Makapix app team (Makapix Club app)
**Date:** 2026-10-02
**Re:** `0001-server-feed-bump-kickoff.md` (same thread). Everything there still holds; this adds where and how to test it.
**Status:** **live on dev** (`https://development.makapix.club/api`), not yet on prod. Prod follows soon and doesn't wait on an app release (the behaviour gap in 0001 §4 is accepted).
**Reply expected:** `0003-app-<slug>.md` in this folder. It replaces the `0002-app-…` reply that 0001 asked for, and should cover the same points: ack, questions, and the app version that ships the toggle.

## What's on dev

Exactly the contract in 0001 §2, nothing renamed:

- `POST /post/{id}/replace-artwork` accepts the `bump` form field (default
  `true`) and returns `public_visibility`, `bumped`, `bump_skipped_reason`
  and `bump_available_at` in `post`.
- Every feed listed in 0001 §1a sorts by listing time. `created_at` in
  payloads is unchanged.

Live check we ran on dev (trusted test account):

| Step | Result |
|---|---|
| Upload, then replace within the first week | `bumped: false`, `bump_skipped_reason: "cooldown"`, `bump_available_at` = upload + 7 days |
| Replace a post whose listing is > 7 days old | `bumped: true`; the post leads `/post/recent` and `/post?sort=created_at`; its `created_at` still shows the original date |

## How to test from the app

1. **Toggle on (default):** use a Trusted account with a post older than 7 days.
   Replace it → expect `bumped: true`, and the post is first in Recent.
2. **Toggle off:** send `bump=false` → expect `bump_skipped_reason: "opted_out"`;
   the post stays where it was.
3. **Cooldown:** replace the same post again → expect `"cooldown"` and
   `bump_available_at` 7 days after the bump.
4. **Untrusted account:** replace an approved post → expect
   `public_visibility: false` and `bump_skipped_reason: "not_trusted"` (or
   `"opted_out"` with `bump=false`). The post leaves public feeds. After a moderator
   approves it, the post is back, and at the top if the bump was requested
   and its last listing is more than 7 days old.

Dev accounts can't be backdated from the app. If you need an "older than 7
days" post or a Trusted or untrusted account set up on dev, tell us which
handles and we'll arrange it.

Thanks!
