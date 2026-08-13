# Artwork Views Redesign — Decisions

Decisions from the 2026-08-13 design session (owner-grilled, all questions put explicitly). Vocabulary lives in the repo-root `CONTEXT.md` glossary; this file records the trade-offs. Background: the 2026-08-13 audit found six coexisting definitions of "1 view" and five bugs (report in session; summarized in D1's context).

## D1 — Full redesign, not staged fixes

One effort replaces the views system; the five audit bugs (anonymous rate-limit global bucket, player rollup band loss/double-count, app 422, profile 7-day lag, stitching cracks) are fixed by the redesign itself rather than patched first. Rationale: the display-layer bugs live in code the redesign deletes; patching first is double work.

## D2 — View vs Impression are separate first-class metrics

**Artwork View** = deliberate look: ≥2s on screen, non-author Visitor, deduplicated to once per (Visitor, artwork) per UTC day. **Impression** = passive exposure during playback (Player or Web Player rotation), undeduplicated volume ("plays"), guarded by rate limits only. They are never summed. Rejected: single qualified metric (loses playback-reach feedback); weighted blend (unexplainable mixed number).

## D3 — Public counters show Views only

SPO, permalink, feed cards, PMD: deduped Views. Impressions appear only in owner-facing stats. Dwell is enforced client-side (server cannot verify screen time); the per-day server-side dedup is what makes the public number spam- and refresh-proof, so client dishonesty about dwell is capped at 1 View/day/artwork per Visitor anyway.

## D4 — One ingestion door for humans; explicit intent in the contract

`POST /post/{id}/view` is the only human recording path. The payload gains `intent: "view" | "impression"` mirroring p3a's `intent`; channel metadata is orthogonal. Body-less POST remains a View (backward compat). `GET /api/p/{sqid}` and the legacy storage-key GET stop recording views — fetching data is not viewing art (that side effect caused crawler views, moderator-refresh inflation, and the app's double-count-by-design).

## D5 — Server heals the mobile app; no app release required

`channel: "artwork"` becomes accepted and maps to a View (it has been silently 422-rejected since app launch). Must land in the same change as D4's GET-recording removal, or app opens double-count. App team gets an FYI via the message/ protocol.

## D6 — p3a mapping is server-side only

`intent="artwork"` → View (deduped per D2, Visitor = player's owner); `intent="channel"` → Impression. No firmware change; rate limits (1/5s player, 1/3s web) stay as abuse guards.

## D7 — Feeds and search record nothing; dead code deleted

`record_views_batch`, `ViewType.SEARCH`, `ViewType.WIDGET`, `ViewSource.API`, `ViewSource.WIDGET` are removed. Grid-thumbnail exposure is not meaningful "seen" signal, and the write volume on a single VPS buys nothing.

## D8 — Web Player emits one Impression per appearance

The every-30s re-fire ("screen time") is removed (~2,880 events/day from one open tab). Matches p3a's one-event-per-display semantics. Rejected: promote-to-View on pause/interaction (more client logic than the signal is worth).

## D9 — Known bots are never recorded

UA denylist drops crawler traffic at the door (no `bot` device type, no downstream filtering). Bot volume is already observable in Caddy/site logs.

## D10 — Single rollup owner with a persisted watermark

`rollup_view_events` becomes the sole consumer of `view_events`: rolls complete UTC days past a persisted `rolled_up_through` watermark into post-level and site-level (player) aggregates in one transaction, then deletes. `rollup_site_events` handles `site_events` only. Every reader = daily rows + raw events after the watermark. This eliminates the dual-cutoff band loss (player views recorded 01:00–02:00 ET were deleted un-rolled-up daily) and the double-count-on-failure mode.

## D11 — Denormalized counter is the single display source

`posts.view_count` (Views), maintained by ingestion increments + rollup reconciliation. All surfaces — SPO widget, permalink, PMD, profile sums — read it; the four divergent stitching implementations (appraisal D8) are deleted. Profiles become a SUM over the column, fixing the 7-day lag.

## D12 — Historical counts recomputed from stored breakdowns; silent cutover

Public counters are rebuilt as `Σ views_by_type["intentional"]` from `post_stats_daily` (the breakdown was stored all along) plus raw intentional events. Known approximations, accepted: historical dedup cannot be applied retroactively, and historical "intentional" includes GET-door noise (crawlers, mod refreshes). Counts will visibly drop; shipped silently (no announcement) — current audience size doesn't warrant one.

## D13 — Unique viewers: exact per day, labeled beyond

Within-day uniques stay exact (daily rollup sets). Any cross-day figure is a sum of daily uniques and is labeled "approximate" in owner-facing UI. Rejected: HyperLogLog sketches (complexity MPX's volume doesn't justify), dropping the metric.

## D14 — IP hashes get a static secret salt

`hash_ip` becomes SHA-256 over secret salt + IP (unsalted IPv4 hashes are brute-forceable, so "privacy-preserving" was not). Static (not rotating) salt: preserves cross-day linkage capability while defeating offline reversal. Salt is a managed secret (env), not in the repo.

## D15 — Observability: rejection counters + heartbeat

Redis counters for rejected/dropped registrations (422, 429, bot drops, dedup hits) and an O8-framework heartbeat check (alert on 422s > 0, watermark staleness > 48h). Context: the app's 422 went unnoticed from launch until the 2026-08 audit precisely for lack of this.

## D16 — Blog subsystem excluded: it is deprecated legacy

The entire Blog part of the site is deprecated and will eventually be deleted. The blog view pipeline (`BlogPostViewEvent`, its 01:30 rollup, blog stitchers) is untouched by this redesign except for code comments recording the deprecation, so nobody "fixes" it toward the new model in the meantime.

---

## Appendix — implementation decisions (2026-08-13, resolved during build)

- **I1 — 201/204 contract**: `POST /post/{id}/view` returns **201** when a View was counted, **204** when accepted but not counted (per-day dedup, bot, self-view, or an Impression). The SPO's optimistic +1 fires only on 201.
- **I2 — Permalink registers via POST**: `p/[sqid]` gained the SPO-style 2s-debounced body-less POST. Without it, permalink visits (the most intentional act) would have counted zero after the GET-door removal.
- **I3 — Views skip the 3s rate limiter**: per-day dedup is the guard. The limiter also silently dropped legitimate fast-swipe first Views; removing it for Views fixes that. Impressions keep the limiter, keyed on the real client IP (the D23b regression fix).
- **I4 — API always emits canonical `views_by_type` keys** (`{view, impression}`): DB history is never rewritten; the stats services normalize via `services/view_metrics.py` breakdown helpers.
- **I5 — Daily series carries impressions** and ships with an authenticated twin on the artist dashboard; `PostStatsListItem` gained per-artwork Impressions.
- **I6 — Author exclusion covers Impressions too** (status quo exclusion paths kept, including the Web Player self-skip).
- **I7 — Shared bot denylist**: `utils/bot_detection.py` extended with self-identifying headless/automation UAs (HeadlessChrome, Puppeteer, Playwright, Selenium, PhantomJS); consumers are view ingestion, site page-view tracking, and (pre-existing) download stats.
- **I8 — Migration transition hygiene**: the migration deletes >7-day-old *player* raw events (already aggregated by the old 01:00 rollup but retained for the old 02:00 site rollup) so the watermark seed cannot re-roll them. Un-rolled stragglers this discards match the band the old pipeline lost daily.
- **I9 — New-row invariant**: post-redesign daily rows have `total_views == unique_viewers == views_by_type["view"]` (per-day dedup makes daily Views ≡ daily distinct viewers); country/device breakdowns count Views only (first event per Visitor wins); `unique_viewers` is kept for schema/history compatibility.
- **I10 — Site-events watermark**: `rollup_site_events` records its own `site_events` watermark. `max(SiteStatsDaily.date)` stopped identifying the page-view boundary the moment the view rollup began writing player rows up to yesterday; without this the sitewide reader would have skipped a week of un-rolled site events.
- **I11 — Watermark never rewinds**: `seed_view_watermark` is INSERT-only (ON CONFLICT DO NOTHING); rewinding a live watermark would re-roll aggregated days. The `view_count` recompute is watermark-aware and dedupes its raw slice with the rollup's rule, so displayed counts never dip when a day rolls up.
- **I12 — `total_player_views` keeps meaning all player plays** (Views + Impressions), preserving the admin chart's semantics and history.
