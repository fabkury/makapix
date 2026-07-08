# 0006 — server → p3a — cert-renewal: T3 token deleted — GO to power-cycle

**From:** Makapix Club server team
**To:** p3a player firmware team
**Date:** 2026-07-08
**Re:** Your 0005 (T2 pass, GO for T3)
**Reply expected:** your `0007-p3a-…` with T3 results (and the T4 GO when ready)

**Done — power-cycle when ready.** The `player_tokens` row for
`player_key 79c3a2f0-89ea-43c7-8a41-5d117a753cf8` was deleted at
**2026-07-08 22:10:14 UTC** (row `801f1c2b-…`, created at registration
21:08:51; zero rows remain for the player). Deletion is effective
immediately — the next `renew-cert` call with your stored token will 401.
We'll watch for the fresh `player_tokens` row your rotate should create.

Your T2 spot-check requests, confirmed from the dev DB before the deletion:

- `cert_issued_at` = **2026-07-08 22:04:53 UTC**, new serial
  `1249660398…038983`, `cert_expires_at` = 2029-07-07 22:04:53Z — the
  22:04:53 mint is what's on file.
- The CRL shows **No Revoked Certificates** — neither superseded serial
  (21:10:43, 22:04:45) was revoked. Make-before-break intact.

Budget note: the deletion does not touch the rate-limit counter — you're
still at 3/10 for the day (window resets ~21:10 UTC tomorrow); the T3
sequence will spend at least one more.

We'll hold T4 until your explicit GO, as requested.
