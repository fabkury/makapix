# Progress — Notification Architecture

## 2026-08-10 — Assessment delivered (no implementation decided)

- First-principles assessment of social-notification handling written to `README.md`,
  commissioned by the owner ("would we have built it differently from zero?").
- Scope locked by owner: social notifications only; judged on security & isolation,
  simplicity, reliability & catch-up; hard constraint single VPS / no new paid services.
- Method: three parallel code explorations (web consumption, native-app snapshot
  consumption, backend inventory) over develop @ 145bdf2; findings N1–N10 verified with
  file:line evidence during exploration.
- Headline: inbox/REST core is sound; delivery layer is sediment of three eras — browser
  MQTT (shared credential, live cross-user exposure = appraisal S1 residue), consumer-less
  SSE + FCM server halves, and REST polling doing the real work.
- Recommendation: plane separation (HTTPS = humans, MQTT = devices); Phase 1 core fixes →
  Phase 2 adopt hardened SSE + delete browser MQTT and the `webclient` broker account →
  Phase 3 app-team alignment on SSE/FCM.
- **Next step (owner decision):** whether to green-light Phase 1 and/or Phase 2.
  Nothing implemented yet.
