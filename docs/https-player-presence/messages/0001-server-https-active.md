# 0001 — server → app: `https_active` on players, and fresher `last_seen_at`

**From:** server team (makapix) · **Date:** 2026-11-25
**Status:** live on makapix.club (PRs #300, #301). Nothing breaks; one label
changes on its own, and one optional field is available.

## Background

Players that talk to us only over HTTPS (no MQTT session) used to look dead:
`connection_status` was always `offline` and `last_seen_at` was never written,
even while the device was fetching artwork and reporting views every few
seconds. Several such devices are active on prod today.

`connection_status` cannot be used to fix that. Both the website and the app
read `online` as "this player can receive commands", and commands are
MQTT-only. So we left it alone and added a separate signal.

## What changed in `GET /api/u/{sqid}/player` (list and single player)

### 1. `last_seen_at` is now written for HTTPS players

Every authenticated HTTPS player request refreshes the player's
`last_seen_at`, at most once a minute.

**This changes what the app shows today, with no release.** In
`my_players_page.dart`, `_offlineLabel` renders "offline" when `lastSeenAt` is
null and `playersOfflineSeen(timeAgo(...))` otherwise. An active HTTPS-only
player used to show the bare "Offline"; it now shows "Offline · last seen: now"
(or "1m", "2m", …), with the grey dot. That is accurate, but it may read oddly
next to a device that is visibly playing.

While a player is MQTT-online, `last_seen_at` is still driven only by its MQTT
status messages, as before.

### 2. New field: `https_active` (boolean, always present)

`true` when both hold:

- the player has no MQTT session (`connection_status != "online"`), and
- it made an authenticated HTTPS player API request in the last 5 minutes.

Otherwise `false`. It is never `true` together with
`connection_status == "online"`.

Sample from prod:

```json
{
  "name": "orbit-station",
  "connection_status": "offline",
  "https_active": true,
  "last_seen_at": "2026-11-25T22:00:59.825136Z"
}
```

## What did not change

- `connection_status` values and meaning: `online` = live MQTT session.
- Commands: still MQTT-only. A player with `https_active: true` cannot receive
  `swap_next`, `show_artwork`, brightness, and so on.
- The player SSE stream: no new event. `https_active` is computed when the
  player list is fetched and does not push.

## What we suggest (optional)

1. **Keep every command surface keyed on `isOnline` only.** The player bar,
   active-player selection and send-to-player must ignore `https_active`,
   otherwise commands go to a device that will never see them.
2. **Show a third state on My Players.** When `https_active` is true, show an
   "active" indicator instead of "Offline · last seen: …". On the website we use a
   cyan dot with the label "active (HTTPS)" and a note that remote control
   needs an MQTT connection; command buttons stay disabled.
3. **Count them separately**, if you keep the "N online" summary: the website
   shows Online / Active (HTTPS) / Offline.
4. **Refresh on your normal cadence.** The flag only updates when the list is
   re-fetched, and it lapses 5 minutes after the device's last request.

Parsing note: treat a missing `https_active` as `false`, so the app keeps
working against development.makapix.club builds that predate the field.

## Questions for you

- Is the changed offline label (point 1 above) acceptable until you ship a
  proper third state, or would you like us to hold anything back?
- Would a push over the player SSE stream when `https_active` flips be useful
  to you? We did not build it; it is not free on our side, so we would only
  add it on request.

Please reply with the app version that picks this up, if you decide to use it.
