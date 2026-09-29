# 0012 - p3a -> server - cert-renewal: erratum to 0011, p3a does not install updates on its own

**From:** p3a player firmware team
**To:** Makapix Club server team
**Date:** 2026-09-29
**Re:** Our 0011, sections 2 and 3
**Reply expected:** optional; the one ask is in section 2

## 1. The correction

0011 said devices "poll GitHub Releases on a fixed interval and install
automatically", and that a 1.0.0 unit "updates itself" before self-healing.
Both statements are wrong, and we should have checked before writing them.

What p3a actually does, in every version shipped: it checks GitHub Releases
every 12 hours (first check 12 hours after boot) and, if a newer release
exists, shows a badge in the web UI. Installing waits for the owner to open
the web UI, go to the Update page, click Install and confirm. Nothing installs
unattended, firmware or web UI. That is also why your registry shows 1.0.0
through 1.2.3 side by side: those owners have not clicked, not failed.

## 2. What changes for Oct 25

- **1.0.0 units cannot recover on their own.** No renewal code, and no
  self-update either. From Oct 25 (or from the moment a dormant one wakes)
  such a unit fails every broker handshake until its owner installs a newer
  firmware by hand, after which the self-heal path runs. Nothing on the
  device screen tells the owner why Makapix stopped working. **Our one ask:**
  if any of the 15 pre-re-issue players run 1.0.0, please nudge those owners
  now. The recipe is one line: open `http://p3a.local/`, tap the Update tab,
  click Install. Owners on 1.1.0 or later need no action.
- **1.1.0 through 1.2.3: unchanged from 0011.** The three-failure self-heal
  runs whether or not the owner ever installs 1.2.4. About two minutes of
  failed reconnects per device, then online.
- **The 1.2.4 proactive path reaches only players whose owners install it.**
  Replace "a device that updates by about Oct 18" in 0011 with "a device
  whose owner installs 1.2.4 renews within a week of the install". Expect
  fewer than 15 proactive renewals before Oct 25; the rest take the
  three-failure path.
- **The latch gap in 0011 section 1 stays open on any player that does not
  take 1.2.4.** The fix rides 1.2.4 for those who install it. A player that
  goes dark and stays dark after Oct 25 is either a 1.0.0 unit or that gap,
  and a power-cycle clears the gap.

The release commitment stands: 1.2.4 by 2026-10-10.

## 3. On our side

We are correcting the same wording in the firmware repository. Nothing else
in 0011 changes.
