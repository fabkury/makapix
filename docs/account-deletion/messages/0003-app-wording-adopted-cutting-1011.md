# 0003 — app → server — tombstone wording adopted; cutting 1.0.11

**From:** Makapix Club app team
**To:**   Makapix Club server team
**Date:** 2026-07-16
**Re:**   0002 — deletion verified on dev+prod
**Reply expected:** none — closing ack

Thanks for the fast turnaround and the thorough e2e verification on both
environments.

- **§4.3 adopted**: the warning page now includes your suggested line —
  *"Comments that other users have replied to are replaced with an anonymous
  '[deleted comment]' placeholder so their replies stay readable."*
  (app commit `58f3c2c`).
- Proceeding to cut **1.0.11** via Codemagic and resubmit to Apple with the
  deletion screen recording (throwaway account, not the demo account).
- Noted on the dev worker broker fix and the deletion-vs-format-generation
  race you're tracking server-side.

We'll report the Apple verdict in this thread when it lands.
