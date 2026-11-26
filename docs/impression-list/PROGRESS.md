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
- **Phase 2 live on prod** (PR #303, migration `a1c4e9d27b63` applied by the
  API entrypoint). Two minutes after the worker came up, natural Player
  traffic had written 8 rows (3 members, 8 artworks; models
  pixel-jukebox-64x64, orbit-station-5x240, p64, p3a) and the row total
  matched the Impression events with a member since the deploy, 8 = 8. The
  list read back through the service with one row for a live artwork; the
  endpoint answers 401 signed out.

## Pending
- [ ] Owner relays `docs/artwork-views/messages/0003` (app + p3a) and
      `messages/0001` (app); owner announces the feature.
- [ ] See an explicit Player showing (`intent="artwork"`) on prod bump both
      👁 and 📺. Rare in natural traffic; covered by tests only so far.
- [ ] First 04:50 ET run of `cleanup_expired_impression_users` (should delete 0).
