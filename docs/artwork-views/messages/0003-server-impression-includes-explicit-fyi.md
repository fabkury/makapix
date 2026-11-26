# 0003 — server → app, p3a — FYI: 📺 now counts explicit player showings too

**From:** Makapix Club server team
**To:** Makapix Club app team; p3a firmware team
**Date:** 2026-11-26
**Re:** docs/artwork-views/ D18 — Impression redefined
**Reply expected:** none required; a short ack is welcome.

Hello both! A meaning change behind an existing number. No payload, field
name or firmware change.

## What changed

An **Impression (📺)** is now *an artwork shown in playback, on a player or in
the Web Player, whether it came up in rotation or was explicitly requested*.

- A player view event with `intent: "artwork"` used to count only as an
  Artwork View (👁). It now counts as an Impression **as well**, every time.
  It still counts as a View at most once per owner per artwork per UTC day.
- `intent: "channel"` and the Web Player are unchanged.
- Showings of the player owner's own artworks are still never counted.

So 👁 and 📺 now overlap by design. They remain two separate figures and are
never added together.

## What you will notice

- `impression_count` (Post payloads), `impressions_count` (widget payload) and
  `total_impressions` (profile stats) grow a little faster for artworks that
  people pick explicitly on players.
- Forward only: existing counts were not adjusted.
- p3a: a repeat explicit showing on the same day is now acknowledged as
  recorded rather than as a duplicate (HTTPS: `deduplicated` is no longer set
  for it). Retransmissions of the same event are still deduplicated.

## Coming next

A list of the members whose screens showed an artwork, opened from the 📺
number. It will come with its own message and contract
(`docs/impression-list/`).
