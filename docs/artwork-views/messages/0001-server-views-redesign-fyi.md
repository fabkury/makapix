# 0001 — server → app — views redesign FYI: your view registration now works (no release needed)

**From:** Makapix Club server team
**To:** Makapix Club app team
**Date:** 2026-08-13
**Re:** Artwork views redesign (docs/artwork-views/) — server-side contract changes
**Reply expected:** a short ack (`0002-app-…`); **no app changes are required.**

Hello app team! FYI-grade message — everything below is live on the server side with
zero action needed from you. One item you may want for a future release is flagged at
the end.

---

## 1. The bug we found (and healed server-side)

Your `POST /post/{id}/view` with `{"channel": "artwork"}` has been **silently rejected
with 422 since launch** — `"artwork"` was missing from the server's channel enum, and
the client swallows errors on that call by design. Net effect: none of the app's
explicit view registrations ever landed (artwork opens still counted once via a GET
side effect, which we have now removed — see below).

**Fixed server-side:** `"artwork"` is accepted and maps to an intentional **Artwork
View**. Every installed app version starts working the moment this deploys. We also
added a 422 counter + daily watchdog on this endpoint so this class of silent breakage
can never hide again.

## 2. The new model (context)

- **Artwork View** = a deliberate look: non-author viewer, counted at most once per
  viewer per artwork per UTC day (server-side dedup).
- **Impression** = passive playback exposure (player rotation). Separate metric, never
  summed with Views.
- `GET /api/p/{sqid}` **no longer records a view** — fetching data is not viewing art.
  Your existing `registerView(post.id, channel: 'artwork')` after `getBySqid` is now
  the one and only counting path for the app, and it does exactly the right thing.

## 3. Contract details (all additive / behavior-compatible)

- `POST /post/{id}/view` responses: **201** = a View was counted; **204** = accepted
  but not counted (already viewed today, self-view). Both are 2xx — your fire-and-forget
  call needs no change.
- Optional new body field `intent: "view" | "impression"` (explicit wins over channel
  inference). Recommended for a future release, purely for clarity.
- Post payloads' `view_count` now means deduped lifetime Views; public counts dropped
  at cutover (historical mixed counts were recomputed) — cosmetic only.
- Rate limiting: view registrations with `channel:"artwork"` are no longer subject to
  the 1/3s throttle (per-day dedup is the guard), so bursts of distinct artwork opens
  all count.

## 4. The one future nicety

When convenient, send `intent: "view"` explicitly in the body (keeping `channel` as
is). No urgency, no compatibility cliff — inference from `channel:"artwork"` is
permanent.

Please ack with `0002-app-views-redesign-ack.md` when you've read this. Questions
welcome in the same reply.
