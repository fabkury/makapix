# Visits History Report — Design Spec

**Date:** 2026-05-08
**Status:** Approved (design phase)
**Output folder:** `docs/visits-report-2026-05/`

## Goal

Produce a one-shot, archival PDF report covering the entire history of human web traffic to makapix.club, from the site's first recorded day (2025-12-02) through the most recent fully-aggregated day (2026-05-01). The PDF stands on its own — anyone opening it months later understands what they're looking at without needing to ask.

## Scope

**In scope:**

- Web traffic only (page views and unique visitors recorded via `site_events` and aggregated into `site_stats_daily`).
- Daily granularity over a continuous date range from 2025-12-02 to 2026-05-01.
- Six charts (listed below) plus light per-chart commentary.

**Out of scope** (explicitly stated in the report's intro):

- Physical-player view events (`view_events` / `total_player_views`).
- The trailing window 2026-05-02 → 2026-05-08, which exists only in raw `site_events` and has not yet been rolled up.
- Posts, errors, API calls, top pages, top referrers — all available in the data but reserved for a separate report.

## Data source

- **Database:** the production Postgres (`makapix-prod-db` container), table `site_stats_daily`. Rationale: prod is the source of truth for site history; the dev DB does not contain comparable historical data.
- **Connection:** `psycopg2` from a host-side Python venv, using credentials read from `/opt/makapix/.env` (`DB_API_WORKER_USER` / `DB_API_WORKER_PASSWORD` / `DB_DATABASE`). The prod DB container publishes Postgres on `127.0.0.1:5432`, so a direct connection from the host works — no `docker exec` indirection needed.
- **Query shape:** single `SELECT` over `site_stats_daily` ordered by `date`, returning all columns needed for the six charts (date, total_page_views, unique_visitors, authenticated_unique_visitors, new_signups, views_by_device, views_by_country).

## Deliverables

All artifacts live in `docs/visits-report-2026-05/`:

| File | Purpose |
|------|---------|
| `report.pdf` | The deliverable. |
| `report.md` | Markdown source consumed by Pandoc. |
| `charts/chart-01-unique-visitors.png` … `chart-06-top-countries.png` | Six PNGs at 2× DPI (~1600 px wide). |
| `generate_report.py` | Single Python script that re-renders everything end-to-end. |
| `README.md` | One paragraph: how to re-run, dependencies. |

## Charts

Order and content are fixed:

1. **Daily unique visitors** — line chart with two series on one axis: faint daily line + bold 7-day rolling average. Rolling line starts at day 7 (avoids misleading early-window values).
2. **Daily page views** — line chart, separate from chart 1 because the scale (~10× higher) would dwarf the unique-visitor series.
3. **Authenticated vs. anonymous unique visitors per day** — two-line overlay. `anonymous = unique_visitors − authenticated_unique_visitors`.
4. **New signups per day** — bar chart (sparse data: 22 events total over 5 months).
5. **All-time visitor share by device** — horizontal bar (desktop / mobile / tablet). Aggregated by summing the `views_by_device` JSON column across all days. Caption explicitly labels this as "share of page views, not unique visitors" — the underlying schema does not store unique-by-device counts.
6. **Top 10 countries by page views, all-time** — horizontal bar. Same labeling caveat as device chart.

## Visual style

- One shared matplotlib style applied to all figures: muted color palette, thin gridlines, no chartjunk, dates on the x-axis formatted as `"Dec 02"`, `"Jan 15"`.
- Same figure size and DPI throughout for visual consistency in the PDF.
- Captions are 1–3 sentences, factual, data-derived (e.g., "Visitor counts climbed from low single digits in early December to a peak of 90 on April 29"). No editorial language.

## Architecture

`generate_report.py` runs straight through, four stages:

1. **Extract.** Read `/opt/makapix/.env`, connect to prod DB, run the single query, load into a pandas DataFrame. Reindex to a continuous daily date range from 2025-12-02 to 2026-05-01, filling missing days with zeros (otherwise charts mislead by skipping x-ticks).
2. **Render charts.** Six small functions, one per chart, each writing a PNG to `charts/`. All share a `setup_style()` helper that applies the matplotlib rcParams.
3. **Build Markdown.** A single Python template assembles `report.md`. Dynamic numbers (totals, peaks, date range) are computed from the DataFrame and substituted in, so the prose stays accurate if the script is re-run.
4. **Render PDF.** `subprocess.run(["pandoc", "report.md", "-o", "report.pdf", "--pdf-engine=xelatex", "-V", "geometry:margin=1in"], check=True)`. If `xelatex` is missing, fall back to `pdflatex`. If neither is available, the script exits with a clear error.

**Re-runnability.** Rerunning the script overwrites all artifacts. No hidden state. To produce a future snapshot (e.g., `visits-report-2026-08/`), copy the folder and rerun.

## Report structure (markdown layout)

1. **Title page** — title, date range covered, generation date.
2. **Intro** (~80 words) — what the report is, what it isn't (out-of-scope items), data source.
3. **Six charts**, in the order above, each followed by a 1–3 sentence caption.
4. **Closing observations** (~60 words) — flags the most visible patterns (cold start, gradual ramp, auth-vs-anon ratio) without speculating about causes.

## Edge cases

- **Sparse early data:** rolling-average line starts at day 7, not day 1.
- **Date gaps in `site_stats_daily`:** reindex to a continuous date range, fill with zeros.
- **JSON aggregation for device/country:** sum across all days in Python; result is page-view share, not unique-visitor share — labeled accordingly in the caption.
- **Empty top-10:** if fewer than 10 countries have data, the bar chart shows whatever is present without padding.
- **Pandoc / LaTeX missing:** detected at runtime, surfaced as a clear error with installation hint, no silent fallback to a degraded output.

## Verification (before declaring done)

- Open `report.pdf` in a viewer; confirm all six charts render, captions are present, no broken image links, page breaks land sensibly.
- Spot-check three computed numbers (total unique visitors, peak day, total signups) against direct SQL queries.
- Re-run `generate_report.py` from a fresh shell to confirm reproducibility — output should be byte-identical-ish (charts may have minor antialiasing diffs but content is identical).

## Non-goals

- This is not a reusable analytics dashboard. It is a one-shot snapshot script.
- This is not a recurring report; future snapshots are produced by manually copying the folder and rerunning.
- This does not modify the database (no rollup writes, no schema changes).
- This is not deployed; the script runs locally and the artifacts are committed.
