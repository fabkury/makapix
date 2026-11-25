# Pulse — the public community-activity timeline

A page (app and website) that shows what members have been doing, so a small
Club feels alive: likes, new artworks, remixes, comments, promotions, badges,
reputation and newly registered players. It is the public cousin of the
moderator dashboard's Pulse tab (`GET /admin/pulse`), which is a different
endpoint with different rules and stays moderator-only.

- Proposal from the app team: `messages/0001-app-pulse-proposal.md`
- **The wire contract: `messages/0002-server-pulse-contract-accepted.md`** —
  read it before changing anything here; the app is built against it.

## Owner decisions (2026-11-25)

| # | Decision |
|---|---|
| P1 | **Cards, not events.** One card = one member + one kind + one burst; events join a card while each comes within **6 hours** of the previous one. |
| P2 | **Kinds in v1:** `likes`, `posts`, `remixes`, `comments`, `player`, `badge`, `reputation`, `promoted`. **`joined` is left out** (a new account on everyone's landing page is a spam incentive). The app skips unknown kinds, so it can be added without an app release. |
| P3 | **`player` cards carry the device model only**, never the owner-typed name. One card per device. |
| P4 | **Signed-in members only**, on the API and on the website. |
| P5 | **30 days of history.** |
| P6 | **A feed bump re-surfaces a post.** `posts`/`remixes` events are timed by `posts.listed_at`. |
| P7 | **Website:** `/pulse`, in the main nav, and the landing page for signed-in members (`/` redirects there; the Recent feed moved from `/` to `/recent`). |

Server-side choices on top (ours): a like on one's own artwork is not
activity; a `likes` event is timed at the member's *first* reaction on that
post; `reputation.total` is the total right after the card, not today's.

## How it is built

- `api/app/services/pulse.py` — everything. `api/app/routers/pulse.py` is the
  thin `GET /pulse` route; schemas are `PulseCard` and friends in `schemas.py`.
- **Computed on read, nothing stored.** Each request loads the events of the
  last 30 days from the source tables as small tuples, applies every
  visibility rule *per viewer*, groups them into cards, sorts, pages in
  memory, and only then loads the full `Post`/`Comment` rows the page shows.
  No migration, no write-path hooks, no cache.
- This is affordable because volume is tiny (prod, 2026-11-25: about 460
  member reactions, 50 comments and 70 posts per 30 days). If it stops being
  cheap: cache the viewer-independent event list for 30–60 s (the contract
  already allows 60 s of staleness), or materialize an events table. Neither
  changes the contract.
- Grouping happens over the whole window before paging, which is what
  guarantees a card is never split across pages. The cursor is
  `(updated_at, card id)`.
- Visibility for posts is the Recent feed's rule plus the viewer's blocks and
  monitored hashtags (`_discoverable_posts`). Actors are filtered like the
  public user listing (`_load_actors`).
- Website: `web/src/pages/pulse.tsx`. Cyan accent only (palette rule). A kind
  the page does not know is skipped, like the app does.

## Adding a kind later

Add it to `PULSE_KINDS` and the `PulseCard.kind` literal, emit its events in
`_collect_events`, hydrate its payload in `_hydrate`, teach
`web/src/pages/pulse.tsx` (`cardVerb`), run `make openapi`, and tell the app
team in a new message. Shipped app builds ignore it until they learn it.

## Not built

- `joined` cards (P2).
- Live updates. The app fetches on open and on pull-to-refresh; an SSE
  "pulse changed" event on the notifications stream would be a new thread.
- An index on `players.registered_at`: the table is a few hundred rows.
