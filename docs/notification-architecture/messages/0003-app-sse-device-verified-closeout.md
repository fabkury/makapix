# 0003 — App → Server: SSE device-verified end-to-end on prod — close-out

**From:** Makapix app team (Makapix Club app)
**To:** Club server team
**Date:** 2026-08-11
**Re:** 0002 (its "we'll flag when verified" promise)

Faster than expected, because prod turned out to be live already (nice — 0001
said "prod to follow," but PR #253 had landed by the time we replied):

- **End-to-end verified on prod, real devices:** new build installed on a
  physical Android phone; a reaction sent from the permanent test account
  (`fhi@kury.dev`, laptop) lit the phone's notification bell **immediately**
  — the SSE path, not the 60 s poll. No surprises.
- The app-side release train is rolling: the SSE client ships to Google Play
  as 1.0.22 (production track), iOS to follow on the normal Codemagic cycle.

Nothing further needed from your side. From ours, the exchange is closed:
SSE adopted and shipped, FCM answered (drop — per 0002, delete away), MQTT
topic removal confirmed harmless. Thanks for a clean contract and a working
reference client — the whole adoption fit in a day.
