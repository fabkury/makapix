# Visits History Report — May 2026 snapshot

PDF report covering human web traffic to makapix.club from 2025-12-02 through 2026-05-01.

## Files

- `report.pdf` — the deliverable.
- `report.md` — Markdown source consumed by Pandoc.
- `charts/` — six PNGs referenced by the Markdown.
- `generate_report.py` — single-script pipeline that reproduces everything.
- `requirements.txt` — pinned Python deps.
- `tests/` — pytest tests for data-shaping and Markdown assembly.

## How to re-run

System packages (one-time):

```
sudo apt-get install -y pandoc texlive-xetex texlive-fonts-recommended python3-venv
```

Python venv (one-time):

```
cd docs/visits-report-2026-05
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

Generate the report:

```
.venv/bin/python generate_report.py
```

The script reads DB credentials from `/opt/makapix/.env` and connects to `127.0.0.1:5432` (the prod DB container's published port). It writes `report.md`, `report.pdf`, and `charts/*.png` in place.

## Tests

```
.venv/bin/pytest tests/ -v
```

Expect 9 tests passing (3 reshape + 2 stats + 4 markdown).

## Producing a future snapshot

```
cp -r docs/visits-report-2026-05 docs/visits-report-2026-08
# Edit START_DATE / END_DATE in generate_report.py
# Update the snapshot date in the markdown template's `date:` frontmatter
.venv/bin/python docs/visits-report-2026-08/generate_report.py
```

## Notes

- Country/geographic distribution is omitted because GeoIP attribution isn't currently captured at request time, so the dimension is empty in the data.
- The May 2 → May 8 trailing window isn't included because rollups for those days haven't been written into `site_stats_daily` yet.
- The script connects directly to the production database; only run from a host that has `/opt/makapix/.env`.
