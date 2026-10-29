# 0002 — server → app — FYI: `impression_count` added to Post payloads (📺)

**From:** Makapix Club server team
**To:** Makapix Club app team
**Date:** 2026-10-29
**Re:** docs/artwork-views/ D17 — public lifetime Impression counter
**Reply expected:** none required; a short ack is welcome.

Hello app team! Additive change, no action needed.

## What changed

Every Post payload (`GET /post/{id}`, feeds, `/v1` equivalents) now carries
`impression_count: int` next to `view_count`. The widget payload
(`GET /post/{id}/widget-data`) carries `impressions_count`, and profile stats
carry `total_impressions`.

- **View (👁)** = deliberate look, deduped once per visitor per artwork per UTC day.
- **Impression (📺)** = passive playback exposure (player / web player rotation),
  undeduplicated.
- The two are **never summed**. The web renders them side by side as `👁 N  📺 M`.

Lifetime Impressions count from the 2026-08-13 views redesign onward (the old
mixed-semantics history is deliberately excluded), so numbers start small.

## If you want to show it

Render `impression_count` with 📺 beside the existing 👁 `view_count`, same
formatting. Nothing else in the contract moved.
