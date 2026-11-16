# p3a firmware ↔ server: standing thread

Home for server ↔ p3a-firmware-team messages that are not tied to a single
feature effort (feature-specific threads keep living in their own folder, e.g.
`docs/cert-renewal/messages/`).

## How we exchange messages

Numbered markdown files in `docs/p3a/messages/`, committed to this repo:
`NNNN-<team>-<slug>.md`, `p3a` = player firmware team, `server` = Makapix Club
server team. Relayed manually — batch aggressively; make each message
self-contained and say what reply (if any) you expect.

## Threads

| # | Date | Topic | Status |
|---|------|-------|--------|
| 0001 | 2026-09-16 | Server → p3a: send a `p3a/<firmware>` User-Agent | server side LIVE on prod 2026-09-16 (PR #274); awaiting `0002-p3a-…` with the firmware version that ships it |
| 0002 | 2026-11-16 | Server → p3a: `submit_reaction` now notifies the post owner; new `blocked` error, hidden posts → `not_found` | server side LIVE on prod 2026-11-16; FYI, no firmware change required, no reply expected |
