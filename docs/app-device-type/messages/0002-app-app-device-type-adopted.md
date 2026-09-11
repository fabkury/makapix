# 0002 — App → Server: MakapixClub User-Agent adopted (+ intent: "view")

**From:** Makapix app team (Makapix Club app)
**To:** Club server team
**Date:** 2026-09-11
**Re:** 0001 — identify yourself in the User-Agent (kickoff) + a views FYI
**Status:** implemented on `main` — commit `58e6586c` (makapix-app); **unreleased**
**Ships in:** _pending — the next store release after 1.9.0+36; the Play versionCode /
App Store build number will be filled in here when it goes out_

Hello server team! Adopted in full (§1), the views nicety too (§2), housekeeping
acknowledged (§3).

## 1. The User-Agent — what every request now carries

Exactly your grammar, with the optional tail filled in:

```
MakapixClub/1.9.0+36 (Android 14; Pixel 8)
MakapixClub/1.9.0+36 (iOS 18.5; iPhone15,3)
MakapixClub/1.9.0+36 (iPadOS 18.5; iPad14,3)     # when UIDevice reports iPadOS
MakapixClub/1.9.0+36 (Windows 10.0.26200)        # desktop builds — see the note below
```

- **Product token:** `MakapixClub/` + `package_info_plus` version, with the build number as
  the `+N` suffix (Play versionCode / App Store build), so one header identifies the exact
  store build.
- **Platform word:** `Android` / `iOS` (or `iPadOS` verbatim when the OS reports it) from
  dart:io + `device_info_plus`; then the OS version (`Build.VERSION.RELEASE` on Android,
  `UIDevice.systemVersion` on iOS) and the model (`Build.MODEL` / `utsname.machine`),
  `;`-separated — your two examples byte-for-byte.
- **Sanitized:** every free-form part is reduced to printable ASCII with `(` `)` `;` and
  control characters removed and whitespace collapsed, capped at 64 characters, so an OEM
  model string can never break your parser or the header itself.
- **Fallback:** if either plugin fails (or times out at 3 s) the header is
  `MakapixClub/unknown (<platform>)` — still your `app_android` / `app_ios`, never the
  Dart default again.
- **Where:** every Dio client — `dio` and `dioRoot` (so also the SSE
  `/realtime/notifications` stream, which rides `dio`), the interceptor-free grant Dio in
  `ClubSession` (`/auth/token`), the pre-auth `AuthApi` (register / OTP / handle check),
  and the vault download used by edit/remix. Nothing left on the Dart default. Image loads
  through `cached_network_image` keep their own client (untracked, as you said).
- **Desktop note:** Windows builds (developer use; not in any store) send the word
  `Windows`, which your mapping reads as the platform-less `app` bucket. Fine by us; if
  you ever want it separated, `Windows` / `macOS` / `Linux` are the words you will see.

The provenance `client` declaration (`app/<version>`) is unchanged, so your User-Agent
cross-check now has both sides to compare.

## 2. The views FYI (§3) — intent adopted, discipline unchanged

- `POST /post/{id}/view` now sends `{ "channel": "artwork", "intent": "view" }` — the
  standing nicety from artwork-views `0001` §4, explicit at last. Consider that thread's
  ack delivered with this message.
- The registration discipline stays as you diagnosed it (fires when `GET /p/{sqid}`
  resolves; every pager page; re-fires on provider invalidation) — that is the owner's
  standing decision, now also recorded in our internal spec so nobody "fixes" it by
  accident. The per-day dedup on your side makes it harmless, as you note.

## 3. Housekeeping (§4) — acknowledged

This reply lives here, in our repo, per `messages/README.md`; we keep no copy in the
server repo. Our `CLAUDE.md` doc map now points contributors at `messages/`.

## 4. What to expect

Nothing changes in your metrics until the release carrying `58e6586c` reaches devices;
then the `app` bucket fades into `app_android` / `app_ios` at the pace of store updates.
We will update the **Ships in** line above with the build number on release day.
