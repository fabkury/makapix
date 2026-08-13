# Artwork Views Redesign — Progress

## 2026-08-13 — design session
- Audit report delivered (six definitions of "1 view", five verified bugs).
- Grilled design session settled D1–D16 (DECISIONS.md); glossary at repo-root CONTEXT.md.

## 2026-08-13 — implementation (develop)
- B1 `1856ced` — salted IP hashes (MAKAPIX_IP_HASH_SALT), worker REDIS_URL fix.
- B2 `83b3efd` — posts.view_count, total_impressions columns, rollup_watermarks,
  services/view_metrics.py, migration `c1d2e3f4a5b6` (recompute + watermark seed),
  manual backfill_view_counts task.
- B3 `9d45af4` — single ingestion door: intent field, 'artwork' accepted (app healed),
  per-day dedup, 201/204, bot gate (views + site events), GET-door removal, p3a
  mapping, view_count increment, dead code removed, D23b keying fix.
- B4 `3835f29` — watermark rollup (single owner incl. site player slice +
  reconciliation + retention-gated delete); rollup_site_events consumes site_events
  only; manual cleanup watermark-guarded.
- B5 `d13cfaf` — all readers on view_count / the watermark stitch; artist dashboard
  daily series + authenticated 8–30d fix; site-events watermark for the sitewide reader.
- B6 `7d60c1c` — 422 counter at the /view door + check_view_ingestion_health (02:30 ET,
  heartbeat-monitored).
- B7 `8d8e261` — 50 new backend tests; superseded/adapted legacy tests. All green.
- F1–F4 `56d13a0` — Web Player one-Impression-per-appearance, permalink View POST,
  SPO 201-only increment, typed stats API layer, KpiGrid/ChartGrid extraction.
- F5–F6 `cbe5882` — StatsPanel + Artist Dashboard rebuilt on the metrics kit.
- F7 `1437ce2` — Playwright specs + .env.e2e loading fix.
- Docs — this file, PLAN.md, DECISIONS appendix I1–I12, message/0001 to the app team,
  blog deprecation banners (D16).

## 2026-08-13 — dev verification (all green)
- `make check-full`: OpenAPI drift + black + full suite, 74 test files, all chunks pass.
- `make rebuild`: migration `c1d2e3f4a5b6` ran at startup — watermark seeded to
  2026-08-12, view_count backfill = 300 (exactly the Σ intentional pre-check), 84 posts.
- Live door checks (api container, browser UA): body-less 201 → dedup 204;
  channel:'artwork' 201; impression 204 → same-IP burst 429; bot UA 204;
  bad intent 422; GET /p/ 200 with no event. Async writes exact (2 views +
  1 impression, view_count 3+2=5); all four viewobs counters incremented once.
- Manual rollup: correct no-op (today's events post-watermark); health watchdog
  correctly went critical on the 422 the contract test itself injected (day-keyed,
  self-clears; expect one dev alert log at the next 02:30 ET run).
- `make e2e`: 46/46 after stub-shape fixes (`c65a9ab`).

## 2026-08-13 — SHIPPED TO PRODUCTION
- PR #256 develop→main merged 18:13 UTC; `MAKAPIX_IP_HASH_SALT` added to
  /opt/makapix/.env.prod; `make deploy` clean, all containers healthy.
- Prod migration verified: head `c1d2e3f4a5b6`, watermark seeded 2026-08-05
  (oldest surviving raw day − 1 — tonight's 01:00 rollup processes the ~7-day
  backlog, per-day loop bounds memory), view_count backfilled: 3,209 Views
  across 559 posts; >7d player backlog hygiene-deleted, 6,966 raw events retained.
- Prod door checks: GET /p/ records nothing; body-less POST 201 (view_count
  3→4, one event) → dedup 204; bot UA 204. Site 200, worker+beat ready.
  (422 probe deliberately NOT run on prod — it would trip the watchdog.)

## Pending
- [ ] Next-morning check: 01:00 ET rollup processed the Aug 6–12 backlog clean;
      02:30 ET watchdog OK; healthchecks auto-created `check-view-ingestion-health`
      (set period/grace in the UI). NOTE: dev's watchdog will alert once at its
      next 02:30 run from the 422 injected during dev verification — expected.
- [ ] App team ack of messages/0001 (no action required on their side).
