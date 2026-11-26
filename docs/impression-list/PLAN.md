# Impression list — "Displayed on"

> **Status: BUILT (2026-11-26); see PROGRESS.md for what is live.** Decisions below come from
> the 2026-11-26 owner-grilled design session. Vocabulary is in the repo-root
> `CONTEXT.md`; the counter change is `docs/artwork-views/DECISIONS.md` D18.

Tapping the 📺 number on an artwork opens a list of the members whose screens
showed it, the way tapping ⚡ opens the list of members who reacted.

## Sequencing

1. **Phase 1 — counter change (D18).** Ships on its own, first.
2. **Phase 2 — the list.** Built on the settled number.

## Owner decisions

| # | Decision |
|---|---|
| L1 | **A row is a member**, not a device. Player owners show their device model(s); signed-in Web Player users show a "Web Player" tag. Anonymous sessions are never rows. |
| L2 | **Device model only.** Owner-typed Player names, ids and keys never leave the owner's account (same rule as Pulse P3). |
| L3 | **Each row shows a display count and when it was last shown, at day granularity** ("today", "5 days ago"). The API returns a date, never a time, so no client can show more. |
| L4 | **Running total, 90-day expiry.** One record per member per artwork with a running count and last-shown date; the record is forgotten 90 days after the last showing. |
| L5 | **Listed by default, one opt-out switch per account.** It covers all of the member's Players and their Web Player sessions. Opting out hides them from every list at once; they still count in 📺 and recording continues, so opting back in restores them. |
| L6 | **Signed-in only**; signed-out visitors see the number and a sign-in prompt. The list hides members the viewer blocked and hidden, banned or deactivated accounts. Opted-out members are hidden from everyone, including the artwork's author and moderators. |
| L7 | **The author's own screens are excluded** from the number and the list (unchanged pipeline behaviour). |
| L8 | **Footer is a fixed explanatory note** (members from the last 90 days; anonymous and private showings are not listed). No arithmetic against the 📺 number. |
| L9 | **Title "Displayed on"**; the 📺 number becomes a button. |
| L10 | **Clean start, no lead time.** The setting and the list ship together; lists start empty; no seeding from existing `view_events`; no advance announcement. |
| L11 | **Web at launch, app contract ready.** Endpoint and setting are a stable `/v1` contract; the app team gets a message. |

Defaults taken without a question (owner confirmed the summary):

- A member who showed an artwork on both a Player and the Web Player gets
  one row with both tags and a combined count.
- Sorted most recently shown first, paginated.
- Records go with the member's account or the artwork (cascade). A hidden
  artwork's list follows the artwork's own access rules
  (`get_accessible_post_or_404`).
- Impressions sent by the mobile app, if any, are a row tagged "App".
- p3a team: informational note only.

Launch notice: none in the product; the owner announces the feature
(decided 2026-11-26). Setting label: "Show me in Displayed on lists".

## Phase 1 — counter change (D18)

Facts: `record_view_event` (`api/app/services/player_views.py`) maps
`intent="artwork"` to a View and returns `DUPLICATE` on the daily dedup before
anything is written; `posts.impression_count` is incremented in
`write_view_event` and recomputed nightly from `view_type='impression'` rows
(`services/view_metrics.py`).

Proposed shape (to confirm while building):

- On `intent="artwork"`, always write an `impression` row; additionally write
  the `view` row when the daily dedup allows it. Two rows for the first
  showing of the day, one for repeats. This keeps the recompute SQL, the
  rollup and the breakdowns untouched, and makes "forward only" automatic.
- Check the rollup's `active_players` / `total_player_views` /
  `views_by_player` site-wide slice does not double-count the two-row case.
- Tests: explicit showing increments both counters; a same-day repeat
  increments 📺 only; self-display increments neither; nightly recompute
  agrees with the live increments.
- Docs: `docs/player/reporting.md` (what `artwork` intent feeds), messages to
  the app team and p3a team.

## Phase 2 — the list

**Storage.** New table, one row per (artwork, member): running count,
first/last shown, and which sources were seen (set of device models,
web-player flag, app flag). Upserted in `write_view_event` for every accepted
Impression with a known member (`viewer_user_id`; for Players that is the
owner). Device model is snapshotted from `players.device_model` at write
time via `player_id`. Unique on (post, user); index for
(post, last shown desc). Both FKs cascade.

**Expiry.** Daily beat task deletes rows whose last showing is older than
90 days. Slot it in the existing 01:00–05:00 ET window; it has no ordering
dependency on the view rollups.

**Setting.** New boolean on `users` (default listed), exposed through the
existing profile-update path and the settings page. Read at list time, not
write time (L5: recording continues).

**Endpoint.** `GET /post/{id}/impression-users`, auth required, paginated.
Item: handle, avatar, `public_sqid`, `device_models[]`, `web_player`, `app`,
`count`, `last_shown_on` (date). Filters per L6. Model it on
`GET /post/{id}/reaction-users` (`api/app/routers/reactions.py`) but note
that one is public and filters less.

**Web.** 📺 becomes a button on `web/src/pages/p/[sqid].tsx` and
`web/src/components/SelectedPostOverlay.tsx`, opening an overlay modelled on
`SPOReactionUsersOverlay`. Settings toggle. Sign-in prompt when signed out.

**Contract and messages.** `make openapi`; open `messages/` here with a
server message to the app team (endpoint, setting, the day-granularity rule).

**Tests.** Upsert and count; combined Player + Web Player row; opt-out hides
and opt-in restores; blocked/hidden/banned filtered; author never listed;
401 signed out; hidden artwork follows access rules; expiry task; no Player
name or id anywhere in the payload.

## As built (2026-11-26)

- Table `post_impression_users` (`models.PostImpressionUser`), migration
  `a1c4e9d27b63`. **Days, not timestamps, are stored** (`first_shown_on`,
  `last_shown_on`): the pagination cursor carries the sort value, so a stored
  time would have leaked through it.
- `api/app/services/impression_list.py`: `record_showing` (single-statement
  upsert, called from `write_view_event` for every Impression with a member
  behind it), `list_impression_users`, `delete_expired`.
- `GET /post/{id}/impression-users` in `routers/reactions.py`, returning
  `Page[ImpressionUserItem]`.
- `users.show_in_impression_lists`, on `UserFull` and `UserUpdate`.
- Beat task `cleanup_expired_impression_users`, 04:50 ET. The list also
  filters by the 90-day window on read.
- Web: `SPOImpressionUsersOverlay.tsx`, opened from 📺 on `p/[sqid]` and the
  single-post overlay; the switch is on `u/[sqid]/settings`.
- A row with no device model, not Web Player and not app renders as "Player"
  (a Player without a reported model).
- Tests: `api/tests/test_impression_list.py`.
