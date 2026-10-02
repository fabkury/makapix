# Feed bump — progress

## 2026-10-02

- PLAN.md written and owner-approved (D1–D16); O1/O2 resolved as "yes" (D11–D13).
- **Phase 1 done on `develop` (not pushed, not deployed — D16 bundles phases 1–3):**
  - `replace-artwork`: an owner without `auto_public_approval` resets
    `public_visibility = false` (D7), promoted posts included; response `post`
    gains `public_visibility`; `hashtags:*` cache now invalidated too.
  - `GET /admin/pending-approval` orders by `artwork_modified_at DESC, id DESC`
    (keyset on the same), so re-queued replacements surface first.
  - `pagination.py`: `apply_cursor_filter` / `create_page_response` handle any
    timestamp sort column (needed again for `listed_at` in Phase 2).
  - Tests: `api/tests/test_feed_bump.py` (6). Related suites green; `make check` clean.
- Next: Phase 2 (`listed_at` + `pending_listing` migration, sort-key swap).
- Decisions D17–D20 added (sort both directions, web label "Date", permalink
  "Updated", no p3a gate, kickoffs sent first). Kickoff messages: app thread
  `0006-feed-bump` (app repo `messages/0006-feed-bump/`; renumbered from 0005, which the app took for localized-text), p3a in
  `messages/p3a/0001-…`.
- **Phase 2 done:** migration `a8b9c0d1e2f3` (listed_at backfill + NOT NULL +
  `ix_posts_listed_at (listed_at DESC, id DESC)`; pending_listing + D13
  backfill). Dev: 2703 posts, 0 with listed_at ≠ created_at, 1 marked 'first';
  downgrade/upgrade round-trip OK. `Post.feed_order_key()` used by `/post` (both
  directions), `/post/recent`, children, hashtag posts, following, search,
  hashtag stats' most_recent, player hashtag-verify preview, and `query_posts`
  (`server_order` + `created_at` on every channel but promoted/reactions). A
  `before_insert` hook copies an explicit created_at into listed_at.
- **Phase 3 done:** `bump` form field (default true), 7-day cooldown
  (`FEED_BUMP_COOLDOWN`), response fields, approval bumps (D11). Web: sort label
  "Date"; permalink "Updated <date>" when artwork_modified_at − created_at > 60 s
  (the two stamps differ by up to ~1 s at upload — prod: 15 of 3190 artworks
  qualify). Docs: MQTT protocol, player querying guide, HTTP API posts.md.
  Tests: `test_feed_bump.py` 30 total.
- **Shipped to prod (2026-10-02, PR #278, merge `90f8730`).** Prod checks: alembic
  head `a8b9c0d1e2f3`; 3190 posts, 0 listed_at ≠ created_at, 0 pending; index
  present; first pages of `/post/recent` and `/post?sort=created_at` (both orders)
  byte-identical to the pre-deploy snapshot; page 2 via cursor 200.
- App thread renumbered **0005 → 0006-feed-bump** (the app took 0005 for
  localized-text); 0001 + 0002 pushed to the app repo (`89ac261a`). p3a kickoff
  `messages/p3a/0001-…` needs the owner to relay it.
- Open: app reply `0003-app-…` (toggle + release version); p3a reply on local
  sorting; watch for bump abuse (per-user daily cap is the lever).
- **p3a 0002 (2026-10-02):** firmware 1.x re-sorts its cache by created_at →
  owner chose option A (D21–D23): `listed_at` (always) + `promoted_at` (promoted
  posts) on every `query_posts` payload, artworks and playlists; `Post.promoted_at`
  public (null unless promoted) → selectable via `fields=` on `/feed/promoted`.
  Tests +5 (35 in `test_feed_bump.py`); full suite green; live on dev. Reply
  `messages/p3a/0003-server-sort-keys-live.md`; awaiting p3a 0004 (release).
  **Owe the app a one-line FYI on `Post.promoted_at` in our next 0006 reply (D23).**
- **D21–D23 shipped to prod (2026-10-02, PR #279).** Prod: `/feed/promoted` order
  identical to pre-deploy; `fields=…,promoted_at` returns real promotion times;
  `query_posts` payloads carry `listed_at` everywhere and `promoted_at` on promoted
  posts. Feed caches invalidated after deploy (pre-deploy cached pages lacked
  `promoted_at`). p3a 0003 sent with this status.
- **p3a 0004 (2026-10-02):** ack; firmware side written (untested on hardware),
  targets 1.2.5. Regular channels sort by `listed_at`, promoted by `promoted_at`
  (MQTT + HTTP catalog via `fields=`), fallback `created_at`; playlists and
  eviction use the same key. Their choice, **accepted by the owner:** a bump
  without new artwork (first approval) moves on the device only at the next
  channel load (typically reboot). No reply sent (none expected). When p3a
  announces 1.2.5, just close the p3a thread — no server-side check needed.
