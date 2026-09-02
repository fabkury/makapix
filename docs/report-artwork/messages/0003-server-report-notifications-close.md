# 0003 — server → app: acknowledged, thread closing

**From:** server team (makapix) · **Date:** 2026-09-02
**Re:** `0002-app-report-notifications-adopted`

## Summary

Thanks — `0002` is a complete adoption, nothing further is needed from you.
Both answers match our preference (plain post title in `content_title`;
comment reports keep the parent post), and your fallback chain for reason
labels (live `GET /config` → baked table → raw code) is exactly what we
hoped for: `moderation.report_reasons` on prod carries all nine labels today.

Two small notes, no action required:

- We are aligning the website's `new_report` glyph to your shield (🛡️) so the
  two clients read the same; it ships with the next website deploy.
- Legacy `new_report` rows (pre-2026-09-02) will age out under normal
  notification retention; we are not backfilling them.

## Closing

The effort is closed on our side (`docs/report-artwork/README.md`). Please
stamp the shipping build number in `0002` when the release is out and note
the on-device dev pass there; no separate reply is expected. Reopen by
sending a `0004-app-…` if the release pass turns up anything.
