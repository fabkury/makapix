# App device type — the app becomes its own device bucket

> **Status: LIVE ON PROD (2026-09-11, PR #272).** Migration `c3d4e5f6a7b8`
> ran at deploy and relabeled 78 raw app Views (desktop → app). App reply
> `0002`: contract UA + `intent:"view"` implemented on makapix-app `main`
> (`58e6586c`), unreleased; the app team stamps the store build number into
> `0002` on release day. Residual: next-day check of the Metrics "Devices"
> card; the `app` bucket fades into `app_android` / `app_ios` as that
> release rolls out.

One effort, two items ("two birds, one stone"):

1. **View discipline** — diagnose whether the Makapix Club app publishes
   Artwork Views the way the website does. Verdict below; owner decision: no
   change required from the app.
2. **Metrics** — the Moderator Dashboard's Metrics tab (and the Artist
   Dashboard) had no "app" device: app traffic was labeled `desktop`.

Source of truth for the views model: `docs/artwork-views/` (D2–D16). This
effort only changes *who* a view is attributed to, never *what counts*.

## Diagnosis (2026-09-09, prod)

**The app does publish Views, and they land.** Over the 7 days before
2026-09-09, 88 of the 147 web-sourced Views on prod came from the app
(matched by `view_events.user_agent_hash` = SHA-256 of the app's User-Agent).
The discipline differs from the website in four ways:

| | Website (SPO / permalink) | App (`ArtworkDetailPage`) |
|---|---|---|
| When it fires | 2 s after the artwork is displayed (debounced) | The instant `GET /p/{sqid}` resolves, inside `postDetailProvider` |
| Swiping | A swipe-through under 2 s registers nothing | Every page of the swipe pager fires (Sep 5: 48 Views from 2 users) |
| Refresh | Once per post per SPO session / page load | Re-fires on every `ref.invalidate(postDetailProvider)` (reaction, edit, mod hashtags, retry) |
| Intent | `intent` omitted (body-less = View) / `impression` in Web Player | `channel:"artwork"` (inferred View); no `intent` |

None of this inflates public counts: the server's per-Visitor-per-artwork
per-UTC-day dedup (artwork-views D2) caps every path at one View, and the
re-fires come back `204`. The app has no playback surface, so it emits no
Impressions — correct.

**The device bug.** The app sends dart:io's default User-Agent,
`Dart/3.12 (dart:io)`, which matched no pattern in
`view_tracking.detect_device_type`, so every app View, every app-triggered
site page view (`GET /p/{sqid}` and the list endpoints record `page_view`),
and the provenance `_server.device_type` cross-check were labeled `desktop`.
That is why "app" never appeared on the Metrics tab.

The Caddy site access log is not enabled for `makapix.club` (only the
global default log and the vault logs exist), so the database, not Caddy,
was the evidence source.

## Decisions (owner, 2026-09-09)

- **D1 — Taxonomy: three app buckets.** `DeviceType` gains `app_android`,
  `app_ios`, and `app` (platform unknown). `mobile` / `tablet` now mean
  *browsers only*; the Metrics tab labels them "Mobile (web)" / "Tablet (web)".
  Rejected: a single `app` value (owner wants the platform split); a separate
  client dimension (more schema/UI than the signal is worth).
- **D2 — Detection: server heals now, app identifies itself going forward.**
  `detect_device_type` maps the Dart default UA to `app` immediately (every
  installed build, no release), and maps the new contract UA
  (`MakapixClub/…`) to `app_android` / `app_ios`. `app` fades out as users
  update. Rejected: waiting for the app release (weeks of mislabeled data);
  a custom header (a second signal path next to UA-based detection, which
  provenance also records).
- **D3 — Backfill raw rows only.** Migration `c3d4e5f6a7b8` relabels
  `view_events` rows still inside the retention window (they carry the UA
  hash) from `desktop` to `app`. Rolled `post_stats_daily` /
  `site_stats_daily` rows and `site_events` (no UA hash) stay as they are.
- **D4 — View discipline: leave the app as is.** The per-day dedup is the
  guard; instant-on-swipe Views are accepted. The app gets the diagnosis as
  an FYI (no action), with `intent:"view"` re-offered as the standing nicety
  from artwork-views message 0001.
- **D5 — Message convention (new).** Messages to the app team live in *their*
  repo under `messages/<NNNN>-<topic>/<NNNN>-<from>-<slug>.md`, one
  sub-folder per thread; the server keeps its copy under
  `docs/<effort>/messages/`. This thread is `messages/0001-app-device-type/`.
- **D6 — Provenance untouched.** `UPLOAD_DEVICE_TYPES` stays
  `desktop`/`mobile`/`tablet` (a form-factor vocabulary, artwork-provenance
  L7). The server UA cross-check now records nothing for app uploads instead
  of the previous wrong `desktop`; the app declares `device_type` and
  `editor_platform` itself.

## Contract (server authority) — the app's User-Agent

Every request the app makes to the Club API carries:

```
User-Agent: MakapixClub/<app version> (<platform>[; <os version>][; <model>])
```

- Product token is exactly `MakapixClub/` followed by the app's marketing
  version (e.g. `1.9.0`; a `+build` suffix is fine).
- `<platform>` is the word `Android` or `iOS` (`iPadOS` also maps to iOS).
  Everything after it inside the parentheses is free-form and optional.
- Examples: `MakapixClub/1.9.0 (Android 14; Pixel 8)`,
  `MakapixClub/1.9.0 (iOS 18.5; iPhone15,3)`.
- Server mapping: `MakapixClub/` + `Android` → `app_android`; + `iOS`/`iPadOS`/
  `iPhone`/`iPad` → `app_ios`; neither → `app`. `Dart/<x.y> (dart:io)` → `app`.
- Consumers of the label: `view_events` (Artist Dashboard + post stats),
  `site_events` (Metrics tab "Devices"), provenance `_server.user_agent`.

## What changed (server, PR pending)

- `api/app/utils/view_tracking.py` — `DeviceType.APP/APP_ANDROID/APP_IOS`;
  app patterns checked after player and before tablet/mobile (the contract
  UA contains "Android").
- `api/alembic/versions/c3d4e5f6a7b8_app_device_type_backfill.py` — D3
  relabel; runs at API startup on deploy like every migration.
- `web/src/components/metrics/DeviceGrid.tsx` — labels for the three app
  buckets; "(web)" on Mobile/Tablet.
- `api/tests/test_device_detection.py` — detection matrix + enum stability.
- `CLAUDE.md` (Device Type Enum), `CONTEXT.md` (App glossary entry),
  provenance comment.

## Progress

- **2026-09-09** — Diagnosis on prod (numbers above). Owner grilled: D1–D6.
  Server implemented on `develop`; migration applied on dev (0 rows — dev
  has no app traffic); detection live-verified on dev with both UAs.
  Message `0001` written here and pushed to the app repo under the new
  `messages/` convention (makapix-app `main` `2e772841`).

- **2026-09-11** — App reply `0002`: UA adopted byte-for-byte on every Dio
  client (incl. the SSE stream, auth grant, pre-auth, vault download), with
  sanitized free-form parts and a `MakapixClub/unknown (<platform>)`
  fallback; `intent:"view"` now sent (closes artwork-views `0001` §4).
  Developer desktop builds send `Windows` / `macOS` / `Linux` → `app` bucket
  (accepted). Their exact strings added to `test_device_detection.py`.

- **2026-09-11** — `make check-full` green; PR #272 merged; `make deploy` on
  prod. Post-deploy: alembic at `c3d4e5f6a7b8`; last-7-day web Views now read
  app 78 / desktop 43 / mobile 13 / tablet 3 (was desktop 121); site + API
  healthy.

## Reopen / next

- App release carrying `58e6586c` → the app team stamps the build number
  into `0002`; once that build is the majority, the `app` bucket should
  trend to zero on the Metrics tab.
- Next-day check of the Metrics tab "Devices" card for `App` rows (site
  page views only carry the new label from deploy time onward).
