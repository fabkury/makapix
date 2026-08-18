# Progress

- **2026-08-18** — Effort started; owner decisions collected (see README).
  Backend + web implemented on `develop`
  (commits `bf390c5` backend, `73cfc68` web). New tests green
  (`test_pending_post_visibility.py`, updated `test_content_visibility.py`).
  Full suite green after fixture fixes (`test_avatar_from_post.py` — its
  "non-viewable" post was merely pending; now `hidden_by_user`), `make check`
  clean, OpenAPI regenerated. Dev stack rebuilt 2026-08-18 (api restarted,
  web image rebuilt); new copy verified in served client chunk.
  Pending: owner testing on development.makapix.club (upload as untrusted +
  trusted user, approve flow, notifications, badges), then PR → main +
  prod deploy.
