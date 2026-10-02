# Feed bump — replaced artworks return to the top of feeds

> **Status: LIVE ON PROD (2026-10-02, PR #278).** Migration `a8b9c0d1e2f3`
> ran at deploy: 3190 posts, 0 with `listed_at <> created_at`, 0 pending (no
> 'first' markers), index present; the first page of `/post/recent`,
> `/post?sort=created_at` (desc and asc) was identical before and after; cursored
> page 2 returned 200. Follow-up PR #279 (D21–D23: sort keys in player payloads, `Post.promoted_at`) live the same day.
> Follow-up PR #280 (D24: public `Post.listed_at`). Both teams acked: app ships the toggle in 1.12.1, p3a the sort keys in firmware 1.2.5 — close each thread when they announce.
> Reopen trigger: a date-sorted surface that ignores bumps, players disagreeing
> with web order, or bump abuse (see Risks: per-user cap).

## Problem

`POST /post/{id}/replace-artwork` swaps a post's bytes but leaves
`created_at` alone, so a replaced artwork stays wherever its original upload
date puts it. Artists who publish a new version of a piece get no
visibility for it; their only alternative is delete-and-reupload, which loses
comments, reactions, views and lineage.

Replacements are a mix of real new versions and small fixes (owner,
2026-10-02), so a bump must be avoidable, but it is the default.

## Decisions (owner, 2026-10-02)

| # | Decision | Choice |
|---|---|---|
| D1 | Mechanism | New `posts.listed_at` (timestamptz, **NOT NULL**). `created_at` is never rewritten: it stays the "posted on" date and keeps driving date filters, stats, sitemap and the artist dashboard. |
| D2 | Backfill | `listed_at := created_at` for every existing post. New posts stamp `listed_at = created_at` at insert. Consequence: before any bump happens, every feed is byte-identical to today, and cursors minted before the deploy resume correctly (same argument as promoted-feed-order D2). |
| D3 | Surfaces | **All browse feeds**, identical on web, app and physical players (see §Surfaces). Players must see exactly the web/app order. |
| D4 | Default | **Opt-out.** `replace-artwork` takes `bump: bool = Form(True)`. Current app builds send no field → every eligible replacement bumps until the app ships a toggle. Accepted behaviour gap (owner, 2026-10-02). |
| D5 | Cooldown | A bump is allowed only if `now() - listed_at >= 7 days`. One bump per post per week, and no bump inside a post's first week (since `listed_at` starts at `created_at`). No extra column. A cooled-down replace still succeeds — it just doesn't bump. |
| D6 | Trust gate | Only owners with `auto_public_approval` can bump. |
| D7 | Re-moderation | A replacement by an owner **without** `auto_public_approval` resets `public_visibility = false`, sending the post back to the approval queue — regardless of `bump`, and including promoted posts (they drop out of Recommended until re-approved). Closes the existing approve-then-swap gap (today replace never touches `public_visibility`). Built first (Phase 1). |
| D8 | API surface | `listed_at` is internal (not in the `Post` schema), like `promoted_at`. Clients wanting an "Updated" badge can use the already-exposed `artwork_modified_at`. The replace response gains additive fields (§API). |
| D9 | Players | Server-side remap, no protocol or firmware change: on every non-`reactions`, non-`promoted` channel, `sort="server_order"` **and** `sort="created_at"` order by `listed_at DESC, id DESC`. `random` is unaffected. (`server_order` currently means `id DESC`, which matches the web only because ids grow with creation time — a bump breaks that, so the remap is required.) |
| D10 | Promoted | Untouched: promoted surfaces keep `promoted_order_key()`. A bump does not move a post within Recommended. |
| D11 | Approval bumps (was O1/O2) | Moderator approval stamps `listed_at = now` in two cases: (a) a post's **first-ever** approval, always, no cooldown; (b) approval of a **re-queued replacement** whose replace asked for a bump, if the D5 cooldown holds **at approval time**. A mod revoke → re-approve with no replacement in between never bumps. |
| D12 | Intent marker | `posts.pending_listing` (varchar, nullable): `'first'` set at insert when the post is created non-public; `'replace'` set by an untrusted replace with `bump=true` (an untrusted `bump=false` replace sets nothing, and a still-`'first'` post keeps `'first'`). Approval consumes and clears it. Revoke sets nothing. |
| D13 | Backfill marker | Posts pending at deploy time (`public_visibility = false`, not deleted) with **no** `approve_public_visibility` audit-log entry get `pending_listing = 'first'`; revoked posts get nothing. |
| D14 | Re-approval notifications | Re-approving a re-queued replacement sends `POST_APPROVED` again (existing behaviour, desirable); held mentions release idempotently (`mentions.release_held_mentions`). |
| D15 | Remix notifications | Unchanged: replace still notifies newly linked parents immediately, as create does for pending posts. |
| D16 | Shipping | Phases 1–3 ship to prod in one deploy; plan and Phase 1 are committed to `develop` but not pushed yet. |
| D17 | Sort direction | `sort=created_at`/`creation_date` uses the listing time in **both** directions (`order=asc` too). One key, no special cases. |
| D18 | Web UI | The web filter label "Creation Date" is renamed to **"Date"**. The permalink shows **"Updated <date>"** when `artwork_modified_at > created_at` (any replacement, bumped or not). No feed-card marker in v1. No API change. |
| D19 | p3a gate | The prod deploy does **not** wait for p3a's reply on local sorting. Worst case, bumps don't move on devices until a protocol follow-up. |
| D20 | Messages | Kickoffs were sent before coding (2026-10-02): app thread `0006-feed-bump` (copy in `messages/app/`), p3a thread in `messages/p3a/`. A follow-up with dev test instructions goes to the app team when Phase 3 is live on dev. |
| D21 | Payload sort keys (p3a 0002) | Firmware 1.x re-sorts its cache by `created_at`, so players get the keys themselves: `listed_at` is mandatory on every `query_posts` post payload; `promoted_at` (= `promoted_order_key()`, i.e. `coalesce(promoted_at, created_at)`) is present on promoted posts only (`query_posts` drops nulls). **D8 is amended:** `promoted_at` joins the public `Post` schema (null unless promoted), which also makes it selectable via `fields=` on `/feed/promoted`; `listed_at` stays out of `Post`. This reverses promoted-feed-order D4 (owner, 2026-10-02, option A). |
| D22 | Playlists | Playlist payloads carry the same `listed_at` / `promoted_at`. |
| D23 | App notice | No separate message: the next server reply on app thread `0006-feed-bump` includes a one-line FYI that `Post.promoted_at` exists. |
| D24 | Public `listed_at` (app 0003 idea) | `listed_at` joins the public `Post` schema (never null; equals `created_at` until a bump), so the app can show "can show as new again on <date>" (`listed_at` + 7 days, Trusted owners) before a replace. **Fully reverses D8.** The app's other gap (untrusted artists on pre-1.12.1 builds aren't told their replacement went back to review) is accepted; no server-side notification. |

## Surfaces

Switch from `created_at` to `listed_at` (sort + keyset/cursor):

| Endpoint / site | File |
|---|---|
| `GET /post` date sorts (`created_at` / `creation_date`) on the non-promoted set — includes user profiles, categories, web player | `api/app/routers/posts.py` `list_posts` (`date_key`, ~L504) |
| `GET /post/recent` (All Artworks) | `posts.py` `list_recent_posts` (`apply_cursor_filter(..., "created_at")` → `"listed_at"`, `create_page_response`) |
| `GET /post/{id}/children` (remixes of a post) | `posts.py` `list_post_children` |
| `GET /hashtags/{tag}/posts` | `api/app/routers/search.py` `list_hashtag_posts` |
| `GET /feed/following` | `search.py` `feed_following` |
| `GET /search` artwork results + their cursor | `search.py` `search_all` |
| Hashtag "most recent" stats | `search.py` (~L331, ~L577) |
| Player `query_posts` (D9) | `api/app/services/player_rpc.py` |
| Player hashtag-verify "latest artwork" preview | `api/app/routers/player.py` (~L749) |

Explicitly **kept on `created_at`** (history / management, not browsing):
`/post` `after`/`before` date filters, `me/remixes` (an inbox), PMD
(`pmd.py`, owner's management table), admin lists and exports, sitemap,
artist dashboard, rollups/stats, `created_at` in every payload.

Exception — **mod approval queue** (`admin.py` `pending_approval`): order by
`artwork_modified_at DESC` so a re-queued replacement (D7) surfaces at the
top instead of at its old upload date. For never-replaced posts
`artwork_modified_at == created_at`, so the queue order is unchanged.

Implementation note: add `Post.feed_order_key()` (returns `Post.listed_at`)
next to `promoted_order_key()` and use it everywhere above, so the surfaces
can't drift apart. Index: `ix_posts_listed_at (listed_at DESC)`; check
`EXPLAIN` on `/post/recent` and the `all` player channel, and add a
composite with the visibility filters only if the plan needs it.

## API — `POST /post/{id}/replace-artwork`

- New form field `bump: bool = True`.
- Response `post` object gains (additive, OpenAPI regen):
  - `bumped: bool`
  - `bump_skipped_reason: "opted_out" | "cooldown" | "not_trusted" | null`
  - `bump_available_at: datetime | null` — when the cooldown ends (set when
    skipped for `cooldown`, and after a successful bump)
  - `public_visibility: bool` — `false` tells the app the replacement is
    pending re-approval (D7)
- Order of operations inside the existing transaction: trust check → D7
  reset + D12 marker (untrusted) or bump evaluation (trusted) → stamp
  `listed_at = now` if bumping. For untrusted owners, `bumped` is `false` with
  reason `not_trusted`; the bump, if requested, happens at approval (D11).
- Cache: the endpoint already clears `feed:recent:*` and `feed:promoted:*`;
  add `hashtags:*` (missing today, needed once order changes).

## Phases

1. **Re-moderation (D7), own PR.** Replace by an untrusted owner → `public_visibility = false`;
   pending queue ordered by `artwork_modified_at`; `hashtags:*` invalidation;
   `public_visibility` in the response. Tests: trusted keeps visibility,
   untrusted loses it and appears first in the queue, re-approval restores
   it at its old position.
2. **`listed_at` column + sort-key swap, no behaviour change.** Alembic
   migration (`listed_at` column, backfill, NOT NULL, index; `pending_listing`
   column + D13 backfill — runs at API startup), stamp
   at create (`posts.py` create, `playlists.py` create), `feed_order_key()`
   across §Surfaces, D9 player remap. Proof: the first page of every surface
   is byte-identical before and after; old cursors resume.
3. **Bump (D4–D6).** `bump` field, cooldown, response fields, OpenAPI regen,
   doc note in `docs/mqtt-protocol/02-player-protocol.md` (`server_order` /
   `created_at` = "newest listing first"). Tests: bump moves to the top of
   `/post/recent`, `/post?sort=created_at`, hashtag, following and the player `all`
   channel in the same order; opt-out; cooldown (6 days 23 h no, 7 days
   yes); first-week block; untrusted never bumps at replace; keyset
   continuity across a bump; promoted order unaffected. Approval (D11):
   first approval bumps; re-queued replacement bumps only with
   `'replace'` marker + cooldown at approval; revoke → re-approve doesn't.
4. **Coordination** (owner relays, batched; kickoffs sent 2026-10-02, D20). Web:
   rename the sort label and add the permalink "Updated" line (D18). Then the
   app follow-up with dev test instructions:
   - App thread: the `bump` default is ON (the app needs a "Move to top of feeds"
     toggle, default checked); new response fields; untrusted replacements
     now go back to approval; any client-side sort or dedupe by `created_at`
     must stop (server order is canonical).
   - p3a thread: `all`/`by_user`/`hashtag`/`user` channels now order by
     listing time server-side. **Question:** does firmware re-sort its cache
     locally by `created_at` in play_order 1? If yes, bumped posts won't move
     on devices, and we need a protocol field (`listed_at` in the payload) —
     reopen D8/D9.
5. **Ship.** `make check-full`, PR `develop` → `main`, `make deploy`; prod
   checks: migration ran, 0 rows with `listed_at <> created_at` right after
   deploy, first page of `/api/post/recent` identical before and after.

## Risks

- **Behaviour gap (accepted, D4):** until the app adds the toggle, small
  fixes by trusted users also bump (at most once per post per week).
- **Player paging is offset-based:** a bump while a device is paging shifts
  later pages by one (one repeated item). New uploads already do this today.
- **Firmware local sort:** see the p3a question in Phase 4.
- **Feed dominance:** trusted heavy posters could rotate bumps across many
  posts (one bump per post per week each). Watch it; a per-user daily bump cap is the
  follow-up lever if needed.

## Resolved questions

- **O1** → D11(b)/D12: yes, re-approval of a re-queued replacement counts as
  the bump (cooldown checked at approval time).
- **O2** → D11(a)/D13: yes, a post's first approval moves it to the top.
