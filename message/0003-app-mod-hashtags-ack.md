# 0003 — app → server — Moderator hashtags: ack + implemented against dev

**From:** Makapix Club app team
**To:**   Makapix Club server team
**Date:** 2026-07-05
**Re:**   messages 0001 (kickoff + contract v1) and 0002 (live on dev)

## 1. Contract ack (0001 §6.1)

**Contract v1 acked as frozen** — no objections; we built against it as
written. One clarification for your notes, no action needed: your 0001 §3
item 1 ("owner edit form: exclude mod tags from the editable field") is
**N/A in the app** — the app has no post-metadata edit form at all (hashtags
are set once at publish; artwork "Replace" is bytes-only). The artist-facing
protection is covered by a read-only shield-marked display on the post page
plus a persistent "Tagged by a moderator" caption. If the app ever grows a
metadata editor, it will implement the exclusion.

## 2. Moderator surface (0001 §6.2)

The app had **no moderator UI surface**; we added one for this feature and are
shipping the **full feature in one release** (display + notification +
editor):

- **Display:** mod tags get a shield marker + tooltip, visible only to
  moderators and the post's artist (your D2), plus the always-visible caption
  above. Public users see plain tags.
- **Editor:** "Edit mod hashtags…" in the artwork detail page's overflow
  menu → a bottom sheet with one-tap chips for the five monitored tags (your
  D22), shield-highlighted monitored chips in the working set, free-text add
  (client-side mirror of your normalization for preview; response body stays
  the source of truth), an optional audit **note** (`reason_code` not exposed
  in v1), and a confirmation dialog when a save would *remove* a monitored
  tag (re-exposure guard). All of it gated on `roles` ∋ moderator|owner
  **and** the presence of `max_mod_hashtags_per_post` in `GET /v1/config`
  (your D19).
- **Notification:** list rendering added for `mod_hashtags_updated` (diff
  read from `comment_preview`). FYI the app has no push handling today (a
  `google-services.json` exists but no FCM client is wired; notifications are
  a polled list), so 0001 §3.4's push copy doesn't apply to us — nothing
  needed from you. One optional suggestion, not blocking: `#`-prefixing the
  tags in `comment_preview` (`+#nsfw −#politics`) would read more naturally
  to artists on both clients.

## 3. Status + ETA (0001 §6.3)

- **Code-complete today (2026-07-05)**: implementation + unit tests (contract
  parsing, config-key gating, normalization mirror, cap/toggle rules,
  notification) — full Dart suite green, analyzer clean.
- **Manual E2E against development.makapix.club is next** (moderator +
  artist + non-opted accounts, per our verification matrix). We'll flag
  anything we hit as a follow-up message; silence = clean.
- **Prod flip:** ready on our side as soon as E2E passes — expect a go from
  us within a day or two. Order stays irrelevant thanks to the config-key
  gate: our released builds show zero mod UI until the key appears on
  makapix.club.

Nothing hit while building against dev so far. Plan + decisions live in the
app repo under `docs/mod-hashtags/`.
