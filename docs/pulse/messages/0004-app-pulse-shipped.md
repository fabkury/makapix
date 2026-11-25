# 0004 — App → Server: Pulse shipped in 1.15.0

**From:** Makapix app team (Makapix Club app)
**To:** Club server team
**Date:** 2026-11-25
**Re:** `0003-server-pulse-live.md` (this folder)
**Status:** shipped. This closes the thread from our side.
**Reply expected:** none.

Hello server team! You asked for the version: Pulse is in **1.15.0**.

- **Android:** 1.15.0 (versionCode 44), rolled out to Play production on 2026-11-25.
- **iOS:** 1.15.0 (build 37), submitted to App Review on 2026-11-25; it releases automatically
  on approval.

What the app does with the contract, in case it helps you read your logs:

- It calls `GET /api/v1/pulse` once when the Club home shows, whichever page the home opened
  on, and again on pull-to-refresh, on a filter change, and when the member comes back to the
  page after a minute or more. Page size is the default 20.
- The filter chips send `kinds`: `posts,remixes` · `likes` · `comments` · `promoted` · `player` ·
  `badge` · `reputation`. "All" sends no `kinds`.
- The home opens on Pulse from the second launch after the app has seen the endpoint answer.
  Builds before 1.15.0 never call it.
- A null `badges[].icon_url_64` (your 0003 §1) shows a placeholder glyph. An unknown `kind` is
  skipped, as agreed, so `joined` can arrive whenever you want it to.

The endpoint behaved exactly as 0002 describes when we tested on prod. Thanks for the quick
turnaround!
