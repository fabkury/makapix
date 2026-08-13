# Artwork Views Redesign — Plan

> Effort docs: [DECISIONS.md](./DECISIONS.md) (D1–D16 + implementation appendix) is the
> design record; [PROGRESS.md](./PROGRESS.md) tracks execution. Vocabulary lives in the
> repo-root `CONTEXT.md` glossary.

## Why

The 2026-08-13 audit found six coexisting definitions of "1 view" and five bugs:

1. The anonymous web-view rate limit keyed on `request.client.host` — always the reverse
   proxy — putting ALL anonymous viewers in one global 3-second bucket (the D23b
   regression, predating the 2026-07 sweep).
2. Player view events were aggregated by the 01:00 ET rollup but deleted by the 02:00 ET
   site rollup with its own cutoff: a 1-hour band was permanently lost from post stats
   daily, and a failed 02:00 run double-counted the next night.
3. The mobile app's `POST /view` with `channel:"artwork"` had been silently 422-rejected
   since launch (missing from the Literal).
4. Public profile view totals summed `post_stats_daily` only — a permanent ~7-day lag
   (new artists showed 0 views for their first week).
5. "Lifetime views" was stitched four incompatible ways (appraisal D8), with a crack at
   the 7-day boundary that made displayed counts visibly DECREASE.

Plus semantic chaos: a permalink GET, a 2s SPO dwell, 30 seconds of Web Player screen
time, an app data fetch, and a p3a rotation slot all counted as "1 view"; feeds/search
counted nothing.

## What shipped

- **One vocabulary** (D2): Artwork View (deliberate look, ≥2s, non-author, deduped once
  per Visitor per artwork per UTC day) vs Impression (playback exposure, undeduped).
  Never summed. Public counters show Views only (D3).
- **One human door** (D4/D5): `POST /post/{id}/view` with explicit `intent`;
  `channel:"artwork"` heals the app with no release; GET routes stopped recording;
  201 = counted / 204 = accepted. Bots never recorded (D9). p3a intent maps server-side
  (D6), with the player's owner as the Visitor.
- **One pipeline** (D10): `rollup_view_events` is the sole owner of `view_events`,
  rolling complete UTC days past a persisted watermark into `post_stats_daily` AND the
  player slice of `site_stats_daily`, reconciling `posts.view_count`, and deleting only
  rolled-AND-past-retention rows — one transaction.
- **One display source** (D11): denormalized `posts.view_count` read by every surface;
  windowed stats stitch daily-rows-≤-watermark + raw-events-after everywhere.
- **History recomputed** (D12) from the stored `views_by_type` breakdowns, silently.
- **Hardening**: salted IP hashes (D14), 422/bot/dedup counters + a 02:30 ET health
  watchdog (D15), exact-per-day uniques labeled approximate beyond (D13).
- **Frontend**: Web Player fires one Impression per appearance (D8); permalink registers
  Views; StatsPanel + Artist Dashboard rebuilt on the recharts metrics kit with separate
  Views/Impressions metrics; Playwright specs for all three behaviors.
- **Excluded**: the Blog pipeline (D16 — deprecated legacy, comments only).

## Rollout

Single PR develop→main after `make check-full` + live dev verification (including the
startup migration's recompute against the dev DB); prod deploy requires
`MAKAPIX_IP_HASH_SALT` in `/opt/makapix/.env.prod` BEFORE `make deploy` (compose fails
loudly without it). Healthchecks auto-creates the new `check-view-ingestion-health` slug
on first beat run.
