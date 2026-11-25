# Pulse — progress

## 2026-11-25
- App proposal `0001` read. Owner chose: accept and build now, API + website,
  through to prod; `joined` left out of v1; `player` cards show the model
  only; signed-in only; 30 days of history; a bump re-surfaces a post; website
  page in the nav and as the signed-in landing page (decisions P1–P7 in the
  README).
- Reply `0002-server-pulse-contract-accepted.md` pushed **before** building,
  at the owner's request, so the app team could work in parallel.
- Built on `develop`:
  - `GET /v1/pulse` (`api/app/services/pulse.py`, `routers/pulse.py`,
    `PulseCard` schemas). No migration. The moderator endpoint's preview
    helper moved into the service and is shared.
  - Website: `/pulse`; `/` now redirects members to it and visitors to
    `/welcome`; the Recent feed moved from `/` to `/recent`; a fifth nav icon,
    with the phone header tightened so it still fits at 360 px and 320 px.
  - Tests: `api/tests/test_pulse.py` (25).
- Dev live check:
  - The endpoint answered 401 without a token and 200 with one, in about
    60 ms, over the public HTTPS URL.
  - With demo activity it returned all eight kinds, grouped as specified.
  - In a headless browser at desktop and phone widths: `/` landed on
    `/pulse`, 12 cards rendered, `/recent` showed the feed, and a signed-out
    visitor was sent to `/welcome` from both `/` and `/pulse`.

## Demo data left on dev (for the app team's testing)

The dev database had no activity newer than August, so Pulse was empty. Four
users `pulse_demo_1` … `pulse_demo_4` were created with likes, comments, two
badges, reputation changes and one registered player. Their cards age out of
the 30-day window on 2026-12-25. To remove them sooner, delete those users'
rows from `reactions`, `comments`, `badge_grants`, `reputation_history` and
`players`, then the users.

`posts`, `remixes` and `promoted` cards need real uploads or a promotion on
dev; three posts were re-timed for the check and put back afterwards.

## Open
- App team builds the page; a `0003-server-…` goes out when prod is live.
- `joined` cards, if the owner wants them later (see README, P2).
