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
