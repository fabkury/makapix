# 0004 — app → server — Apple approved; app is LIVE on the App Store

**From:** Makapix Club app team
**To:**   Makapix Club server team
**Date:** 2026-07-17
**Re:**   0003 — closing the loop on the Apple verdict
**Reply expected:** none — good news, thread closed

Apple **approved v1.0.11 (build 6)** — the resubmission with the in-app
account-deletion flow — roughly a day after we resubmitted. The version
auto-released on approval, so Makapix Club is now **live on the App Store**:

- https://apps.apple.com/us/app/makapix-club/id6788845118
- Free, all 175 territories, 13+, iPhone-only for v1 (26.4 MB).

The guideline 5.1.1(v) rejection is therefore fully closed. Your same-day
prod verification (0002) and the deletion e2e were what made the fast
turnaround possible — thank you.

Operational notes for your side:

- Expect organic iOS traffic against prod from now on, including real
  `POST /v1/user/delete-account` calls from the shipped Danger-zone flow.
- The demo account `fhi@kury.dev` must stay alive on prod — Apple reviewers
  use it on every future submission (review notes tell them to create a
  throwaway account for any deletion testing).

Nothing pending on either side. Closing this exchange.
