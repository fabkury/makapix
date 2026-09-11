# 0001 — Server → App: identify yourself in the User-Agent (kickoff) + a views FYI

**From:** Club server team
**To:** Makapix app team (Makapix Club app)
**Date:** 2026-09-09
**Re:** docs/app-device-type/ (server repo); follow-up to artwork-views `0001` §4
**Status:** server side on `develop`, verified on dev; prod deploy pending
**Reply expected:** `0002-app-app-device-type-adopted.md` in this folder, with the build number that ships the change

Hello app team! One small ask (§2) and one FYI that needs nothing from you (§3).

## 1. What we found

Every request the app makes carries dart:io's default User-Agent,
`Dart/3.12 (dart:io)`. Our device detection had no pattern for it, so every
app View, every app-triggered page view, and the provenance User-Agent
cross-check were labeled **desktop**. The Moderator Dashboard's Metrics tab
therefore never showed an "app" device, even though 88 of the 147 web-sourced
Artwork Views on prod in the last 7 days came from the app.

**Healed server-side already:** the Dart default UA now maps to a new
`app` device bucket (platform unknown), for every installed build, no
release needed. Raw view events still inside the retention window were
relabeled by a migration.

## 2. The ask — send a real User-Agent (the contract)

To split Android from iOS (and to stop depending on a Dart default that could
change under us), please send this on **every** request to the Club API:

```
User-Agent: MakapixClub/<app version> (<platform>[; <os version>][; <model>])
```

- Product token exactly `MakapixClub/` + the marketing version
  (`1.9.0`; a `+36` build suffix is fine).
- `<platform>` is the word `Android` or `iOS` (`iPadOS` also counts as iOS).
  Anything after it inside the parentheses is free-form and optional.
- Examples: `MakapixClub/1.9.0 (Android 14; Pixel 8)`,
  `MakapixClub/1.9.0 (iOS 18.5; iPhone15,3)`.

Server mapping (live on dev, tests in `api/tests/test_device_detection.py`):
`MakapixClub/` + `Android` → `app_android`; + `iOS`/`iPadOS`/`iPhone`/`iPad`
→ `app_ios`; product token without a platform word → `app`.

Where it needs to go, as far as we can see from your tree: the two Dio
clients in `ClubApiClient._build` (`dio` and `dioRoot`) and the
interceptor-free Dio in `ClubSession` (auth calls). Setting
`BaseOptions(headers: {'User-Agent': ua})` is enough on dart:io; setting
`HttpClient.userAgent` inside your `createHttpClient` override works too.
`package_info_plus` (already a dependency) gives the version;
`Platform.isAndroid` / `Platform.isIOS` gives the platform word — an OS
version or model is welcome but not required. Vault image loads don't
matter (they are not tracked).

Your call on which release carries it; there is no compatibility cliff —
the Dart fallback stays permanent. Please reply with the build number so we
can watch the `app` bucket fade into `app_android` / `app_ios`.

## 3. FYI — how your view registration differs from the website (no action)

We diagnosed the app's view discipline against the website's, and the owner
decided to leave it as it is. For the record, the differences we observed:

| | Website | App |
|---|---|---|
| When it fires | 2 s after the artwork is displayed | The instant `GET /p/{sqid}` resolves (inside `postDetailProvider`) |
| Swiping the pager | Under 2 s on a page registers nothing | Every page fires (Sep 5: 48 Views from 2 users in one day) |
| Refresh | Once per post per session / page load | Re-fires on every `ref.invalidate(postDetailProvider)` (reaction, edit, mod hashtags, retry) |
| Intent | body-less = View; Web Player sends `intent:"impression"` | `channel:"artwork"` (inferred View) |

None of it inflates public counts: the per-Visitor-per-artwork-per-UTC-day
dedup caps every path at one View, and re-fires come back `204`. The app has
no playback surface, so no Impressions are expected from it. The standing
nicety from artwork-views `0001` §4 still applies whenever convenient:
send `intent: "view"` explicitly (keep `channel`).

## 4. Housekeeping — a new home for these messages

From this thread on, server → app messages live in **your** repo under
`messages/<NNNN>-<topic>/`, one sub-folder per thread, numbered files
inside (`0001-server-…`, `0002-app-…`, …). Please reply in the same
sub-folder. We keep our copy under `docs/<effort>/messages/` in the server
repo, as before. A short `messages/README.md` in your repo spells out the
convention.
