# Mentions — progress

## 2026-09-22
- App proposal `0001` read; owner chose: accept + build now, server + full
  website, through to prod; hold-until-approval for pending posts (description
  and comments); read-time resolution; the app's defaults for §12 items;
  no looser rules for moderator writers.
- Server + website built on `develop`
  - Tests: `api/tests/test_mentions.py` (56), `web/e2e/mention-markup.spec.ts` (31).
  - Found while building: notifications never served `comment_id`
    (only on the internal create schema), so it was added to the wire shape.
- Dev live check passed:
  - The candidates endpoint answered.
  - A comment mentioning a user came back with the plain body, the markup and
    the resolved mention, and the recipient got a `mention` notification with
    a plain preview.
  - In a headless browser, the mention rendered as a `/u/{sqid}` link, and the
    composer showed the candidate list and inserted the handle on Enter.
  - The test data was removed afterwards.
- `make check-full` green → PR #275 merged → `make deploy` on prod
  - The migration ran (all 150 users defaulted to `everyone`).
  - `/config` serves the key.
  - Feed and comment payloads carry the new fields.
  - No API errors in the logs.
- Reply `0002-server-mentions-accepted.md` pushed to the app repo.

## Open
- App reply `0003` (build number); then check a real app-written mention
  renders on the website and vice versa.
- Owner click-test on prod (composer on a post, Settings → Mentions).
