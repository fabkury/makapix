# Impression list — progress

## 2026-11-26
- Design session with the owner (six rounds). Decisions L1–L11 recorded in
  `PLAN.md`; the counter change recorded as D18 in
  `docs/artwork-views/DECISIONS.md`; the **Impression** entry in the
  repo-root `CONTEXT.md` redefined to match.
- Nothing built. Next: Phase 1 (D18 counter change), on its own.
- Owner (same day, before the build): two deploys back to back; no in-product
  launch notice (the owner announces it); prod check by watching natural
  Player traffic; setting label "Show me in Displayed on lists".
- **Phase 1 built** on `develop` (details in `docs/artwork-views/PROGRESS.md`).
- **Phase 1 live on prod** (PR #302). Channel-rotation traffic kept flowing
  after the deploy (about 240 Player Impressions per hour). Explicit Player
  showings are rare on prod (2 in the last 7 days), so the both-counters path
  is covered by tests rather than by observed traffic so far.
- **Phase 2 built** on `develop` (see "As built" in `PLAN.md`). Dev check:
  three simulated Web Player Impressions went through the worker, the 📺
  number rose by 3, and the endpoint answered 401 signed out and one row
  ("Web Player", count 3, a date) signed in. In a headless browser on the
  public dev URL: the 📺 button opened the list, signed out it showed the
  sign-in prompt, and the settings switch saved off and back on.
- Message `messages/0001` (app team) written for the owner to relay.
