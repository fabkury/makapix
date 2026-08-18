# Progress

- **2026-08-18** — Effort started; owner decisions collected (see README).
  Backend + web implemented on `develop`
  (commits `bf390c5` backend, `73cfc68` web). New tests green
  (`test_pending_post_visibility.py`, updated `test_content_visibility.py`).
  Full suite green after fixture fixes (`test_avatar_from_post.py` — its
  "non-viewable" post was merely pending; now `hidden_by_user`), `make check`
  clean, OpenAPI regenerated. Dev stack rebuilt 2026-08-18 (api restarted,
  web image rebuilt); new copy verified in served client chunk.
  Owner tested on development.makapix.club (trusted + untrusted flows) — OK.
- **2026-08-18** — **Deployed to production** (PR #259, merged + `make deploy`).
  `make check-full` green pre-merge. Post-deploy: site 200, recent feed 200,
  new copy present in prod web build (about/submit chunks), no new errors in
  api logs (the `feed:recent` datetime cache-set warning was pre-existing,
  also on dev — fixed same day in PR #260: `CacheJSONEncoder` now serializes
  datetimes, so the recent feed actually caches again; verified key+TTL in
  prod Redis). Effort complete; possible follow-ups: pending badge on
  `/u/{sqid}/posts` manage page, app-side adoption of the new notification
  types.
