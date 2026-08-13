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

## Pending
- [ ] Dev verification: make check-full, make rebuild, migration sanity numbers,
      live door checks, make e2e, manual rollup run.
- [ ] PR develop→main, merge, prod deploy (salt into .env.prod first).
- [ ] Post-deploy: next-morning check of the 01:00 rollup + 02:30 watchdog;
      healthchecks slug auto-created.
- [ ] App team ack of message/0001 (no action required on their side).
