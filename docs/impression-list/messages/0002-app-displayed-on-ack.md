# 0002 — App → Server: "Displayed on" list and the privacy switch adopted (ack)

**From:** Makapix app team (Makapix Club app)
**To:** Club server team
**Date:** 2026-11-26
**Re:** `0001-server-displayed-on-list.md` (this folder)
**Status:** implemented on `main` — commit `8cc8ceb6` (makapix-app); not released yet
**Ships in:** the next app release (version and build numbers get filled in here on release day)
**Reply expected:** none.

Hello server team! Thanks for the contract. The app adopts all of it, with no questions.

## 1. The list

- The 📺 number on the artwork page is now a button. It opens a full page titled
  **"Displayed on"**, built like the page ⚡ opens: the artwork header, then one row per member.
- A row reads as on the website: the handle, then `p3a, Pixel Jukebox · shown 14 times`, with
  the day at the end of the row. Tapping a row opens the member's profile.
- `device_models` are shown as sent. `web_player` and `app` add a "Web Player" and an "App"
  tag. A row with no model and both flags false reads "Player".
- The app calls `GET /v1/post/{id}/impression-users` with the default `limit` of 50 and follows
  `next_cursor` as the member scrolls, treating it as opaque.
- Your footer line is shown under the list as a fixed note. The app does no arithmetic against
  `impression_count`.
- Signed-out visitors get a sign-in prompt, and the app makes no request for them.
- All text is translated into the app's eight languages.

## 2. Day granularity

`last_shown_on` is read as a UTC calendar day and compared with today's UTC day. The app shows
"today", "yesterday" or "N days ago" and derives nothing finer. Should a time ever appear in the
field, the app reads only the date part.

## 3. The privacy switch

Settings → Account has a switch, **"Show me in Displayed on lists"**, with your explanatory
line under it. It reads `show_in_impression_lists` from `GET /v1/auth/me` (absent reads as
listed) and writes it with `PATCH /v1/user/{user_key}` on the tap. If the save fails, the switch
goes back and the member is told.

## 4. The "App" tag

The app still registers Views only (`{channel: "artwork", intent: "view"}`), so no `app: true`
row comes from this app today. It renders the tag all the same, for the day something sends one.

## 5. Housekeeping

This thread lives here as `messages/0009-impression-list/`, with your 0001 copied verbatim.
Your `docs/artwork-views/messages/0003` (📺 now counts explicit showings) is filed here as
`messages/0007-artwork-views/0004-server-impression-includes-explicit-fyi.md`, because our
ack already holds number 0003 in that folder. It needs no change in the app: the number is
shown as sent. Consider this the ack for it too.
