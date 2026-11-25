# 0002 — Server → App: Pulse accepted; the final contract, so you can build now

**From:** Makapix Club server team
**To:** Makapix app team (Makapix Club app)
**Date:** 2026-11-25
**Re:** `0001-app-pulse-proposal.md` (this folder)
**Status:** accepted, being built on `develop` now. Nothing is live yet. We send a short
`0003-server-…` when it is live on `development.makapix.club`, and say there when prod follows
(the plan is the same day).
**Reply expected:** none needed to proceed. Objections to anything below are welcome before
our 0003; after that, changes are a new message.

Hello app team! We take the proposal almost verbatim. This message is sent **before** we have
written the code, so you can build in parallel: everything in §2 to §5 is the contract we are
implementing. The differences from 0001 are listed first.

---

## 1. What differs from your proposal

| Item | 0001 | Final |
|---|---|---|
| `joined` cards | in v1 | **Not in v1** (owner decision). The server never sends `kind: "joined"` for now. Keep your "unknown kind is skipped" rule; it may arrive later. |
| `player` card payload | `name` + `device_model` | **`device_model` only** (owner decision). The name is typed by the owner and is not public anywhere today. |
| Anonymous access | our call | **Signed-in only.** No token → `401` with the usual `/v1` error envelope. |
| History | "never ends" preferred | **30 days** (owner decision). The walk ends there (`next_cursor: null`). |
| `likes` on one's own artwork | not specified | **Not counted.** |

Everything else is as you wrote it. The website gets a Pulse page too, on the same endpoint.

## 2. Endpoint

```
GET /api/v1/pulse?cursor=…&limit=20&kinds=…
Authorization: Bearer …            (required)
→ 200 Page[PulseCard]              { "items": [...], "next_cursor": "…" | null }
```

- `limit`: default 20, min 1, max 50. Newest card first.
- `cursor`: opaque. Pass back `next_cursor` unchanged. An unreadable cursor is treated as "first
  page", not an error.
- `kinds`: optional, comma-separated. Unknown values are **ignored**, not rejected (so asking for
  `joined` today is harmless). If no known value remains, the page is empty.
- `next_cursor` is `null` on the last page. A page may hold fewer than `limit` cards and still
  have a `next_cursor`; only `null` means the end.
- Until the rollout the path returns `404`, as you planned for.
- Data may be up to **60 seconds** stale.

## 3. `PulseCard`

```jsonc
{
  "id": "likes:8f3k2:2026-11-25T11:40:02.123456+00:00",  // opaque; see §5
  "kind": "likes",          // likes | posts | remixes | comments | player | badge | reputation | promoted
  "actor": {                // never null
    "public_sqid": "…",
    "handle": "…",
    "avatar_url": "…"       // nullable
  },
  "started_at": "…",        // oldest event in the card (ISO 8601, UTC)
  "updated_at": "…",        // newest event in the card; the sort key
  "count": 12,              // events in the card, after the visibility rules

  // Kind-specific. Always present in the JSON; null on the kinds that do not use it.
  "posts": [ Post, … ],     // likes · posts · remixes · promoted — newest first, max 6
  "comments": [             // comments — newest first, max 3
    { "id": "<uuid>", "preview": "…", "is_reply": false, "created_at": "…", "post": Post }
  ],
  "player": { "device_model": "…" },                                  // player; device_model nullable
  "badges": [ { "badge": "…", "label": "…", "icon_url_64": "…" } ],   // badge — newest first, all of them
  "reputation": { "delta": 15, "total": 240 }                         // reputation
}
```

Per kind:

| `kind` | `actor` | Event | Event time | Payload |
|---|---|---|---|---|
| `likes` | who reacted | a post the member reacted to (several emoji on one post = one event) | their **first** reaction on that post | `posts` |
| `posts` | the artist | an artwork with no parent | the post's **listing time** | `posts` |
| `remixes` | the artist | an artwork with at least one parent (a deleted parent still counts) | the post's listing time | `posts` |
| `comments` | the author | a comment or reply | comment creation | `comments` |
| `player` | the owner | one registered player (**one card per device**, `count` is always 1) | registration | `player` |
| `badge` | the member | a badge grant | grant time | `badges` |
| `reputation` | the member | a reputation change | change time | `reputation` |
| `promoted` | the artist | an artwork currently in Recommended | promotion time | `posts` |

- **`Post` is the full feed `Post`**, the same schema `/post/recent` returns, including
  `user_has_liked`, `reaction_count` and `comment_count` for the caller. (Your §7.2.)
- `count` can exceed the list length (`posts` max 6, `comments` max 3): show "+N more".
- `comments[].preview`: plain text, mentions resolved to `@handle`, cut to 140 characters with a
  trailing `…`.
- `reputation.delta` is the sum over the card and is always **> 0**; cards with a net of zero or
  less are not sent. `reputation.total` is the member's total **right after the card's last
  event**, not today's total. The reason text is never sent.
- The caller's own activity is included, like in any other feed.
- Grouping is as you specified: same member + same kind, each event within **6 hours** of the
  previous one. `player` is the exception (never grouped).

## 4. Visibility (we own these)

Applied on every request, for the calling member:

- **Posts**, in every kind: artwork posts that are publicly approved, visible, not hidden by user
  or moderator, not deleted, not non-conformant. Exactly the Recent feed's rule.
- **Comments**: signed-in authors only; not hidden, not deleted; on a post that passes the rule
  above.
- **Actors**: no banned, deactivated or hidden members. No anonymous activity of any kind.
- **Blocks**: no cards from members the caller blocked, and no posts or comments authored by
  them inside other members' cards (a comment on a blocked member's post is dropped as well).
- **Monitored hashtags**: posts carrying a monitored hashtag the caller has not opted into are
  dropped, as in Recent.
- **Removal**: unlike, deleted comment, deleted or hidden post, demotion, revoked badge: gone on
  the next fetch. No tombstones.
- A card left with no events is not sent. `count`, `started_at` and `updated_at` describe what
  the caller can see.

"Who reacted to what" is already public (the profile Reacted tab, `reacted_by` on `/post`), so
we see no privacy problem with `likes` cards.

## 5. Paging, ids, and the rest of your §7

- **A card is never split across pages and never returned twice in one walk.** Cards are grouped
  over the whole 30-day window on every request, then paged.
- **`id`** is `kind:actor_sqid:started_at`. Treat it as opaque. It is stable while a card grows
  at its newest end, which is the normal case. It changes if the card's oldest event disappears
  (an unlike, a deletion), and for a card that straddles the 30-day edge.
- A growing card moves to the top on refresh, as you intended.
- **Feed bump (§7.3): yes.** `posts` and `remixes` use the listing time, which a bump (and a
  moderator's first approval) resets. A bumped post therefore leaves its old card and shows as
  new activity. The existing 7-day bump cooldown limits how often.
- **`joined` (§7.4):** not in v1, see §1.
- **Automation (§7.5):** no automated badge or reputation grants exist today; if they come, they
  use the same cards.
- **Indexes (§7.7):** ours to handle, nothing for you.
- **Naming (§7.8):** `/pulse` is free. The moderator endpoint stays at `/admin/pulse`.
- **Live updates:** not in v1, as agreed. A separate thread when you want the "new activity" chip.

## 6. What we ask of you

Nothing blocks you. Build against §2 to §5; when 0003 arrives you can test on
`development.makapix.club`.

Thanks for the careful research in 0001. It made this an easy yes.
