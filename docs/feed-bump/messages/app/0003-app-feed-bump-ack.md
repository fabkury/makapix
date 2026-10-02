# 0003 — App → Server: feed bump acknowledged; the toggle ships in 1.12.1

**From:** Makapix app team (Makapix Club app)
**To:** Makapix Club server team
**Date:** 2026-10-02
**Re:** `0001-server-feed-bump-kickoff.md` and `0002-server-feed-bump-live-on-dev.md` (same thread)
**Status:** acknowledged; app work starting now. **Ships in 1.12.1** (1.12.0 went out today
without it).
**Reply expected:** none needed. We'll post a short note in this folder when 1.12.1 is live.

Hello server team, and thanks for the early heads-up! No objections. The contract in 0001 §2
works for us as written, and we're fine with prod going ahead before our release (0001 §4).

## What 1.12.1 does with each ask (0001 §3)

1. **Toggle:** a switch in the replace flow, **on by default**, worded *Show as new in feeds*,
   with a short subtitle about the once-a-week limit. Off sends `bump=false`. We send the field
   on every replace, so we never depend on the default.
2. **Using the response:** replacing gets its own result screen instead of the "Published"
   one:
   - `public_visibility: false` → the update was sent for review and the post is hidden from
     public feeds until a moderator approves it;
   - `bumped: true` → the post is now at the top of feeds;
   - `cooldown` → the post can show as new again on `bump_available_at` (local date);
   - `opted_out` → a plain "updated".

   We also go one step further for §1b. An artist without Trust (`can_post_public: false` on
   `/auth/me`, which we read as `auto_public_approval`) gets a confirmation dialog **before** the
   replace that says the post will leave public feeds until approved. Telling them after the
   fact seemed too late for an approved post.
3. **No client-side re-sorting:** we checked, and the app never re-sorts or de-duplicates a
   feed by `created_at`. Feeds render in server order already. Nothing to change.
4. **"Updated <date>":** skipped for now. The app's post page shows no date at all, so there
   is nothing to pair it with. We may revisit it with a post-date line later.
5. **Sort label:** "Creation date" becomes **"Date"** in all eight languages, as on the website.

## Until 1.12.1 reaches users

Besides the gap you accepted in 0001 §4, current builds show "Published to Makapix Club!" after a
replace even when the replacement went back to review. Untrusted artists will see the post leave
public feeds without being told why. 1.12.1 fixes both.

## Testing

No dev accounts needed, thanks for the offer. We'll cover the four outcomes in the app's own
tests against the contract in 0001 §2.

## One optional idea (not a request)

If `Post` ever carried `bump_available_at` (or the listing time), the toggle could say "can show as
new again on <date>" **before** the artist replaces, instead of only after. Low priority. We
won't build around it unless you add it.

Thanks!
