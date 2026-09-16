# Progress — protect-artworks

| Date | Step | State |
|---|---|---|
| 2026-09-14 | Effort opened. Two clarification rounds with the owner → `DECISIONS.md` D1–D10. | done |
| 2026-09-14 | Exposure map verified against `develop` @ e67ff53 and prod (post/user/player counts, license mix, vault log UA/referer profile, Caddy 2.7.6 module list, every `Post`-returning endpoint, the download endpoints, frontend render sites, canvas readers). → `01-current-state.md` | done |
| 2026-09-14 | Options catalog (families A–G, 24 options + rejected list) with PROS/CONS/COSTS/RISKS each. → `02-options.md` | done |
| 2026-09-14 | Scoring matrix, phased recommended bundle, residuals-by-decision, open questions OQ1–OQ6. → `03-matrix-and-recommendation.md` | done |
| 2026-09-14 | Docs committed to `develop` (f959ee8). | done |
| 2026-09-14 | Round 3: OQ1–OQ6 + ToS timing + next step answered → D11–D18; measured prod usage of the frozen player lookup endpoints (1 request in 14 days) to size the daily cap. | done |
| 2026-09-14 | `PLAN.md` written: Phase 0 (no contract change, 7 steps), Phase 1 (gated path, viewer token, serialization split with dual window, detector v2, window close), Phase 2 triggers, risks. | done |
| 2026-09-16 | Outside this effort but load-bearing for Phase 0 step 0.5 (`harvest_signals_daily`): the main site now has a Caddy access log (`/var/log/caddy/main-access.log`, prod; `main-dev-access.log`, dev — JSON, 90 d) via `caddy.log.*` labels on the web service, so `/api/*` requests carry client IP + User-Agent; and `p3a/` was added to `PLAYER_PATTERN` with the firmware team asked to send `p3a/<fw>` (`docs/p3a/messages/0001`). Detector rules can key on `p3a/` once adopted instead of the ESP-IDF default. | done |
| — | **Owner reviews PLAN.md** (D18). | **next** |
| — | Phase 0 implementation on dev, then PR to main. | pending |
| — | App thread `messages/0001-protect-artworks/` before Phase 1. | pending |

Nothing has been implemented. No code, config, contract, or ToS text has
changed as part of this effort.
