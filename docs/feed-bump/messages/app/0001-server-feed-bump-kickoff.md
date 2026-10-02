# 0001 — Server → App: replaced artworks return to the top of feeds (kickoff)

**From:** Makapix Club server team
**To:** Makapix app team (Makapix Club app)
**Date:** 2026-10-02
**Re:** New thread `0006-feed-bump`; server plan in `docs/feed-bump/PLAN.md` (server repo)
**Status:** server work in progress on `develop`; part (1b) is already live on dev. A follow-up with dev test instructions comes when the whole change is live on dev.
**Reply expected:** `0002-app-<slug>.md` in this folder. Please ack, send any questions or objections, and say which app version will ship the toggle in §3.1.

Hello app team! This is a heads-up before we finish building, so you can plan the
app side. It's a small change on your side, but one behaviour changes right away
for current builds (§4).

## 1. What changes

When an artist replaces a post's artwork (`POST /post/{id}/replace-artwork`,
your edit feature), the post now **returns to the top of every date-sorted
feed**, the same way on web, app and physical players. We call this a *bump*.

The server keeps a new internal *listing time* per post. `created_at` is
**not** touched: it stays the "posted on" date in every payload. Feeds sort by
listing time instead.

### 1a. Feeds that change order

| Endpoint | Change |
|---|---|
| `GET /post?sort=created_at` (or `creation_date`), **both** `order=desc` and `order=asc` | Sorted by listing time (all filters: owner, hashtag, category, …) |
| `GET /post/recent` | Sorted by listing time |
| `GET /hashtags/{tag}/posts` | Sorted by listing time |
| `GET /feed/following` | Sorted by listing time |
| `GET /post/{id}/children` | Sorted by listing time |
| `GET /search` | Recency tie-breaks use listing time |
| `GET /feed/promoted` | **Unchanged.** It still sorts by promotion time; a bump doesn't move a post within Recommended. |

**Cursors keep working**, including cursors held across the deploy. At deploy
time every post's listing time equals its `created_at`, so the first page of
every feed is byte-identical until the first bump happens.

### 1b. Untrusted owners' replacements go back to moderation (**live on dev now**)

If the owner doesn't have Trust (`auto_public_approval`), replacing the
artwork sets `public_visibility = false`. The post leaves public feeds,
including Recommended if it was promoted, until a moderator approves it
again. This closes a gap: today, an approved post can be swapped for
unreviewed bytes. When re-approved, the owner gets `post_approved` again.

### 1c. When a bump happens

- **Trusted owner replaces with `bump=true`:** the post moves up at once, if
  its listing time is at least **7 days** old. That means one bump per post per
  week, and none during a post's first week.
- **Untrusted owner replaces with `bump=true`:** no bump at replace time.
  The bump happens when a moderator approves the replacement, if the 7-day
  cooldown holds at that moment.
- **First approval of any new post** by an untrusted owner also moves the post up.
  Today an approved post lands at its upload date, often days deep. Now it
  lands at the top when it's approved.
- A moderator revoking and then re-approving a post never bumps it.

## 2. Contract changes (additive)

`POST /post/{id}/replace-artwork` (multipart):

- **New form field `bump`** (boolean, **default `true`**). Send `false` for
  small fixes that shouldn't move the post.
- Response `post` object gains:

| Field | Type | Meaning |
|---|---|---|
| `public_visibility` | bool | `false` = pending moderator review (§1b). **Live on dev now.** |
| `bumped` | bool | The post moved to the top right now |
| `bump_skipped_reason` | `"opted_out"` \| `"cooldown"` \| `"not_trusted"` \| null | Why it didn't move. `not_trusted` means the bump will be applied at approval, if still eligible |
| `bump_available_at` | ISO 8601 \| null | When the post can be bumped again (set on `cooldown`, and after a bump) |

No other schema changes. `created_at` and `artwork_modified_at` already exist
in the `Post` payload.

## 3. Asks

1. **A "Move to top of feeds" toggle** in the replace flow, **checked by
   default**. When unchecked, send `bump=false`. (Our suggested wording. Yours
   to adjust.)
2. **Use the response:** if `public_visibility` is `false`, tell the
   artist the update was sent for review. If `bump_skipped_reason` is
   `cooldown`, you could show "can move up again on <bump_available_at>".
3. **No client-side re-sorting:** if the app sorts or de-duplicates any feed by
   `created_at`, please stop. The server order is the intended one.
4. **Optional:** the website will show "Updated <date>" on the post page when
   `artwork_modified_at > created_at`. You may want the same.
5. **Optional:** if the app labels its date sort "Creation Date", the website
   is renaming it to "Date", since it now means listing time.

## 4. Behaviour gap we accepted

Because `bump` defaults to `true`, **current app builds will bump every
eligible replacement**, small fixes included, until your toggle ships. The
7-day cooldown limits this to once per post per week. The owner accepted this.

Thanks!
