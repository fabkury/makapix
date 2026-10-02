# 0004 — Server → App: `Post.listed_at` is live (your idea), plus an FYI on `Post.promoted_at`

**From:** Makapix Club server team
**To:** Makapix app team (Makapix Club app)
**Date:** 2026-10-02
**Re:** `0003-app-feed-bump-ack.md` (same thread)
**Status:** both fields **live on prod** (and dev)
**Reply expected:** none. Your planned 1.12.1 note (`0005-app-…`) is still welcome.

Thanks for the thorough reply! The pre-replace confirmation for untrusted artists is a
nice touch. Everything in your 0003 matches our side. Three short items:

## 1. Your optional idea: done

`Post` now carries **`listed_at`**: when the post was last placed at the top of the
date-sorted feeds, which is the exact key they sort on. It's never null. It equals
`created_at` until the post is bumped, either by a replace with `bump=true` or by its
first moderator approval.

To show "can show as new again on <date>" before a replace:

- **Trusted owner** (`can_post_public: true`): the date is `listed_at + 7 days`. If
  that's in the past, a replace with the toggle on will bump right away.
- **Untrusted owner:** the bump happens at moderator approval, and only if
  `listed_at + 7 days` has passed **by then**. A date is still a fair hint, but it's
  checked at approval time, not at replace time.
- After a replace, the response's `bump_available_at` is authoritative.

The value is as of when you fetched the post. Like any `Post` field, it can also be
selected with `fields=` on `/feed/promoted`.

## 2. FYI: `Post.promoted_at`

`Post` also gained **`promoted_at`**: when a moderator last promoted the post, which is
the key Recommended (`/feed/promoted`) sorts on. It's `null` unless `promoted` is
true. Physical players asked for it; you don't need to do anything with it.

## 3. The pre-1.12.1 gap

We confirm `can_post_public` = Trust (`auto_public_approval`); your reading is right.
We accept that until 1.12.1, untrusted artists on older builds aren't told why a
replaced post left public feeds. The existing `post_approved` notification still tells
them when it's back.

Thanks!
