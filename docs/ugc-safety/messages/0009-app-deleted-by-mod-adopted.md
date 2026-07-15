# 0009 — app → server — `deleted_by_mod` adopted (§3 applied to us)

**From:** Makapix Club app team
**To:**   Makapix Club server team
**Date:** 2026-07-13
**Re:**   0008 — additive `deleted_by_mod` on comment payloads

## 1. §3 applied to us — fixed same day

We do derive the tombstone from the flags rather than rendering `body`
as-is, so without a change a moderator-deleted comment would have parsed as
*not* deleted on our side: live styling instead of the tombstone treatment,
included in the visible comment count, and still offering a Report action.

Adopted in app commit `78bd191` (makapix-app, main):

- A comment is deleted when `deleted_by_owner || deleted_by_mod`
  (the legacy `deleted` key is still honoured defensively).
- Mod take-downs render **"[deleted by moderator]"**; owner self-deletes keep
  **"[deleted]"** — matching the website.
- Counts and the Report affordance treat both kinds as deleted.

Unit tests cover the three flag combinations (live / by-owner / by-mod).

## 2. Ships on the next Play build

Code-complete on `main`; rides the next Closed Testing release (current live
build is 1.0.10+15). Until then, shipped builds keep working per your
additive-change policy — they just show the mod tombstone as a live comment
with the literal `"[deleted by moderator]"` body, which is cosmetically fine.

## 3. §4 noted

Understood that pre-deletion text retention is server-internal only; nothing
for us to do there.
