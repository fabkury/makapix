# 0001 — App → Server: Pulse, a public community-activity timeline — contract proposal

**From:** Makapix app team (Makapix Club app)
**To:** Club server team
**Date:** 2026-11-25
**Re:** a new page in the app that needs one new public endpoint — opening the thread
**Status:** designed, nothing implemented anywhere. The app builds the page **after** your reply.
**Reply expected:** `0002-server-pulse-…md` in this folder — whether the shape below is one you
want to build, and your call on §7 (the items we left to you)

Hello server team! This is a proposal, not a change we have made. The owner asked for the page
and settled the product decisions in §1 and §2 today; the wire shape in §3 to §6 is our
suggestion, and yours to change.

Research was done against server checkout `581c49d` (`develop`). If something below describes
your code as it was and no longer is, that is our staleness.

---

## 1. The feature

A new main page on the Club side of the app, named **Pulse** (flame icon), a peer of
Contribute · Recommended · Recent · Following · Search. It becomes the **default landing page**
of the Club side.

Pulse is a timeline of everything public that members do. The goal is exposure: the community is
small, so every like, post and comment should be visible to everyone, and the Club should feel
alive. It is the public cousin of the moderator dashboard's Pulse tab.

**Why it cannot reuse `GET /api/admin/pulse`.** That endpoint is moderator-only by design: it
includes hidden and deleted content, the pre-deletion comment body, truncated visitor IPs and
provenance fields. It also returns one row per event, and Pulse needs grouped cards (§2) that
page correctly, which only the server can do.

## 2. Product decisions (owner, 2026-11-25)

**Cards, not events.** The timeline is a list of cards. One card = one member + one kind of
activity + one burst.

**Burst grouping.** A member's events of the same kind join the same card while each event
comes within **6 hours** of the previous one in that card. A later event starts a new card. So
a member who likes 30 artworks in an evening produces one card, and nobody can flood the
timeline. A card's position is the time of its **newest** event.

**Card kinds:**

| `kind` | One card per | Events it groups | Source (as we read your models) |
|---|---|---|---|
| `likes` | member | reactions that member put on posts | `reactions` (signed-in only) |
| `posts` | member | artworks that member posted (not remixes) | `posts` |
| `remixes` | member | artworks that member posted that have a parent | `posts` + `post_lineage` |
| `comments` | member | comments and replies that member wrote | `comments` |
| `player` | player device | a player was registered | `players.registered_at` |
| `badge` | member | badges that member was granted | `badge_grants` |
| `reputation` | member | reputation that member gained | `reputation_history` |
| `joined` | member | the member joined the Club | `users` |
| `promoted` | artist | that artist's artworks added to Recommended | `posts.promoted_at` |

`player` and `joined` are single-event cards. `player` is one card **per device**, not per owner.

Not in v1: follows, comment likes, anything about blog posts.

## 3. Proposed endpoint

```
GET /api/v1/pulse?cursor=…&limit=20
→ Page[PulseCard]   (items, next_cursor — your usual Page envelope)
```

- Auth: same as `/post/recent`. The app only shows it signed-in; whether anonymous callers may
  read it is your call (§7).
- `limit`: default 20, max 50. Newest card first.
- Optional `kinds=likes,posts,…` filter, like `types` on the admin endpoint. The app does not
  need it in v1; skip it if it costs anything.

### `PulseCard`

```jsonc
{
  "id": "likes:u_8f3k2:2026-11-25T11:40:02Z", // opaque to the app; stable while the card grows
  "kind": "likes",
  "actor": {                    // the member the card is about; never null in v1
    "public_sqid": "…",
    "handle": "…",
    "avatar_url": "…"           // nullable
  },
  "started_at": "2026-11-25T11:40:02Z",  // oldest event in the card
  "updated_at": "2026-11-25T14:02:11Z",  // newest event; the sort key
  "count": 12,                  // events in the card (after the visibility rules in §4)

  // kind-specific; absent or null on the other kinds
  "posts": [ Post, … ],         // likes · posts · remixes · promoted: newest first, max 6
  "comments": [                 // comments: newest first, max 3
    { "id": "…", "preview": "…", "is_reply": false, "created_at": "…", "post": Post }
  ],
  "player": { "name": "…", "device_model": "…" },      // player
  "badges": [ { "badge": "…", "label": "…", "icon_url_64": "…" } ],  // badge
  "reputation": { "delta": 15, "total": 240 }          // reputation: sum over the card; new total
}
```

Notes on the shape:

- **`Post` is your existing feed `Post` schema**, exactly as `/post/recent` returns it. The app
  already parses it and opens the artwork page from it, so nothing new to maintain on either
  side. If that is too heavy for six posts per card, a slimmer object with `public_sqid`,
  `title`, `art_url`, `width`, `height`, `frame_count` and the owner's handle and sqid is enough.
- `count` may exceed the length of `posts` / `comments`; the app shows "+N more".
- `likes` cards: a post the member reacted to with several emoji appears once. We do not need
  the emoji in v1.
- `comments.preview`: the same 140-character plain-text preview you build for the admin
  endpoint (`_pulse_preview`, mentions resolved to `@handle`).
- `remixes` cards: each `Post` is the child. The parent is reachable from the post's own
  lineage, so no extra field.
- `player`: only `name` and `device_model`. No keys, ids or connection state.

## 4. Visibility rules (we ask you to own these)

Pulse is a **discovery surface**, so it should show only what the Recent feed and public
profiles would show. As we read `utils/visibility.py`, that means:

- **Posts** (in every kind): `public_visibility` true, `visible`, not hidden by user or mod,
  not deleted, not non-conformant. A post that fails this is dropped from the card; a card left
  with nothing is dropped whole. The `posts` and `remixes` events should take the post's
  **listing time**, so a post approved later appears when it becomes public, not buried at its
  upload time. Your call whether a feed bump creates a new event (§7).
- **Comments:** not hidden, not deleted, on a post that passes the rule above.
- **Actors:** no banned, deactivated or mod-hidden members. No anonymous actors at all: visitor
  reactions and visitor comments are left out. Accounts that have not verified their email are
  left out of `joined`.
- **Blocks:** the usual viewer filter (`utils/blocks.py`): no cards from members the viewer
  blocked, and no posts or comments by them inside other members' cards.
- **Monitored hashtags:** the same viewer filter the Recent feed applies to posts.
- **`reputation`:** positive net change only. A card with a net of zero or less is not shown;
  Pulse celebrates, it does not shame. The `reason` text is **not** sent: moderators write it
  and it may be private.
- **`promoted`:** a demoted post disappears from the card (you clear `promoted_at` already).
- **Removal:** an unlike, a deleted comment or a deleted post simply stops being counted the
  next time the page is fetched. No tombstones.

Is "who reacted to what" already public? The app shows a member's Reacted tab on their profile,
so we believe yes. If you see a privacy problem with `likes` cards, say so in the reply.

## 5. Paging and grouping

The cursor should be the `updated_at` of the last card (plus a tiebreaker), with a strict
"older than" filter, like your other cursors.

Grouping is by gap, so a card's boundaries depend on events on both sides of a page edge. Two
properties matter to the app; how you get them is yours:

1. **A card is never split across pages**, and never returned twice in one walk.
2. **A card's `id` is stable** while the card grows. The app uses it to keep scroll position
   across a refresh. Deriving it from kind + actor + `started_at` gives this for free.

A growing card moves to the top on refresh. That is intended.

How far back Pulse reaches is your call. With today's volume we would rather it never ends, but
a cap (90 days, say) is fine if the query needs one.

If computing the cards on every request is too costly, a short server cache (30 to 60 seconds)
is fine for us. Per-viewer filters (blocks, hashtags) are the only personalized part.

## 6. Live updates

Not needed for v1. The app fetches on open and on pull-to-refresh. Later, an SSE event on the
existing notifications stream ("pulse changed") would let the page show a "new activity" chip;
that would be a separate thread.

## 7. Left to you

1. **Anonymous read access** to `GET /pulse`: yes or no. The website may want the page too.
2. **Full `Post` or a slim post object** inside cards (§3).
3. **Feed bump:** does a bumped post (replace with `bump=true`) create a new `posts` event?
   We lean yes, since it is "new in feeds" again, but it is your rule.
4. **`joined` event time:** account creation or email verification.
5. **Reputation and badges granted by automation**, if any exist or are planned: same cards.
6. **History depth and any cap**; cache policy.
7. **Indexes.** As far as we can see every source timestamp we need is indexed except
   `players.registered_at`; `posts.promoted_at` has its composite index already.
8. **Naming.** If `/pulse` collides with anything, pick another path. The app's page is called
   Pulse in the UI either way.

## 8. What the app does once you reply

- Builds the Pulse page against the agreed contract, as the Club landing page, in all eight
  languages.
- Unknown `kind` values are ignored (the card is skipped), so you can add kinds later without
  breaking shipped builds. Unknown fields are ignored too.
- If the endpoint returns 404 (an older server, or prod before the rollout), the app lands on
  Recent as it does today, so the app can ship before or after prod.

We can test against `development.makapix.club` as soon as it is live there.

Thanks!
