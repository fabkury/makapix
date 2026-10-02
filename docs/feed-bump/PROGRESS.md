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
  `0005-feed-bump` (app repo commit `4efb93d5`, not pushed), p3a in
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
