# 0001 — server → app — the "Displayed on" list behind the 📺 number

**From:** Makapix Club server team
**To:** Makapix Club app team
**Date:** 2026-11-26
**Re:** docs/impression-list/ — a list of members whose screens showed an artwork
**Reply expected:** an ack, and your questions if any. Nothing here breaks the app.

Hello app team! The website now lets a signed-in member tap the 📺 number on
an artwork and see whose screens displayed it, the way tapping ⚡ shows who
reacted. The API is ready for you whenever you want it.

## The list

`GET /v1/post/{id}/impression-users?limit=50&cursor=…` — signed-in members
only (401 otherwise); 404 when the member cannot see the artwork.

```json
{
  "items": [
    {
      "user_handle": "ana",
      "user_avatar_url": "https://…",
      "user_public_sqid": "k3Xp",
      "device_models": ["p3a", "Pixel Jukebox"],
      "web_player": false,
      "app": false,
      "count": 14,
      "last_shown_on": "2026-11-24"
    }
  ],
  "next_cursor": null
}
```

- **One item per member**, most recently shown first. `limit` 1–100, default 50.
  Follow `next_cursor` until it is null; treat it as opaque.
- `device_models`: models of the member's players that showed the artwork.
  It can be empty. Player names are never sent.
- `web_player` / `app`: the member's Web Player or the mobile app showed it.
  If all three are empty/false, show a generic "Player".
- `count`: showings counted for this member on this artwork.
- `last_shown_on`: a **UTC calendar day, never a time**. Please render it at
  day granularity ("today", "yesterday", "5 days ago") and do not derive
  anything finer. This is a privacy rule: a time of day reveals when
  someone's player is running.
- A member is forgotten 90 days after their last showing. The list never
  contains the artwork's author, anonymous viewers, members the caller
  blocked, or hidden, banned or deactivated accounts. It therefore does not
  add up to `impression_count`; the website says so in a footer line:
  *"Members whose player or Web Player showed this artwork in the last 90
  days. Anonymous and private showings are not listed."*
- Website wording: title **"Displayed on"**; rows read
  `@ana · p3a, Pixel Jukebox · shown 14 times · 2 days ago`.

## The privacy switch

Members are listed by default and can turn it off. One switch per account; it
hides them from every list, for everyone.

- Read: `show_in_impression_lists: bool` on the signed-in user object
  (`GET /v1/auth/me`).
- Write: `PATCH /v1/user/{user_key}` with `{"show_in_impression_lists": false}`.
- Website wording: **"Show me in Displayed on lists"** — *"When your player
  or the Web Player shows an artwork, other members can see you in that
  artwork's Displayed on list."*

App users are listed too when the app reports Impressions, so we would
appreciate the switch being reachable from the app's settings when you add
the list.

## Related

The 📺 number itself changed meaning slightly on the same day: see
`docs/artwork-views/messages/0003`.
