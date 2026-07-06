# UGC safety — decisions

Product decisions recorded 2026-07-06 (owner interview). Engineering decisions
follow. Reference these by number from PLAN/API-CONTRACT/messages.

## Product decisions (owner)

**D1 — Block semantics: mute + interaction block.** Blocking user B as user A
means: B's content disappears from A's list surfaces (feeds, search, comment
threads, notifications, user listings), and B can no longer comment on A's
posts, react to them, like A's comments, reply to A, or follow A. Follows
between A and B are removed in both directions at block time. B can still
*view* A's public content while logged in — full mutual invisibility was
rejected because content is public and a logout defeats it; a pure view-only
mute was rejected because it lets a harasser keep engaging with the victim's
work.

**D2 — Anonymous (logged-out) reporting is allowed**, with strict per-IP rate
limits. Content is browsable without an account on both web and app, and App
Review checks for a report path from any state. Alternative (auth-only +
"email us" fallback) rejected as a review risk.

**D3 — Store-aligned reason set.** `spam, harassment, hate, sexual_explicit,
violence_gore, illegal_csam, self_harm, copyright, other`. Replaces the
4-code set (`spam, abuse, copyright, other`); legacy `abuse` rows remain
readable. Gives reviewers the explicit illegal-content category and gives
moderators real triage signal.

**D4 — Moderator alerting: immediate email + in-app notification.** New
reports trigger an email to `acme@makapix.club` (existing Resend service) and
a system notification to all moderators/owner, both throttled per target so a
pile-on doesn't flood. Daily digest rejected (>24 h latency risk vs Apple's
timeliness expectation); dashboard-only status quo rejected (nobody is
watching it).

**D5 — Reporter gets a resolution notification.** When a moderator resolves a
report filed by a logged-in user, the reporter receives a `report_resolved`
notification ("Thanks — we've reviewed your report"). No action details are
disclosed. Anonymous reports get no callback.

**D6 — Reportable targets v1: posts, comments, users.** Playlists and blog
comments deferred; they can be added later as additive enum values.

**D7 — Community guidelines live in the existing About tabs**, not a new
standalone page. The About page already has Rules and Moderation tabs; we add
prohibited-content categories (aligned with D3 reason codes), "how to report",
"how to block", the moderation contact `acme@makapix.club`, and a response-time
commitment. The app links to these pages via URLs published in `/v1/config`.

**D8 — Per-post "hide this content" deferred.** Blocking users + reporting
content satisfies both stores ("block users **or** user-generated content").

## Engineering decisions

**D9 — Canonical `target_id` types (fixes a latent bug).** `reports.target_id`
is a string whose format depends on `target_type`: post → decimal integer id,
comment → UUID, **user → `public_sqid`**. The current moderator PATCH handler
parses user targets as UUID and compares against the integer `users.id` —
i.e. acting on user reports has never worked. Fixed as part of Phase 1. The
`reporter_id` list filter is likewise typed `UUID` today and becomes `int`.

**D10 — Visibility filtering is one-way and SQL-level.** List queries add a
`NOT EXISTS (SELECT 1 FROM user_blocks WHERE blocker_id = :viewer AND
blocked_id = <author col>)` predicate via a shared helper
(`api/app/utils/blocks.py`) — in-repo precedent for query-level predicates is
the JSONB role filter in `search.py:86`; `utils/visibility.py` stays the
per-object gate pattern. With the
`(blocker_id, blocked_id)` unique index this is an index probe per row —
negligible at Makapix scale, no denormalization, no cache invalidation. An
in-Python "load blocked-id set per request" variant is the fallback if query
plans ever disappoint.

**D11 — Interaction prevention is symmetric.** If a block exists between A
and B *in either direction*, comment/reply/reaction/comment-like/follow
between them is refused with `403 blocked`. One-sided prevention would let the
blocker keep engaging with the blocked user's content, which invites
retaliation loops and is harder to explain.

**D12 — Blocking removes follows in both directions** (delete `Follow` rows
A↔B in the same transaction). Blocked-state and follow-state never coexist.

**D13 — Aggregate reaction counts are not adjusted** for blocks; only
user-attributed lists (who-reacted, comment threads, feeds) are filtered.
Recomputing per-viewer counts is disproportionate for a single-VPS stack.

**D14 — Direct navigation is not filtered.** Visiting a blocked user's
profile URL or a direct post URL still works; the profile response carries
`is_blocked_by_viewer: true` so clients render a blocked state with an
Unblock affordance instead of pretending 404. Consistent with D1's mute
philosophy and keeps `can_access_post` untouched.

**D15 — Playlists are not block-filtered.** A playlist is viewer-curated; if
the blocker previously added the blocked user's art, they can remove it
manually. Hardware players are similarly unaffected (they are unauthenticated
broadcast surfaces).

**D16 — Anonymous-interaction loophole accepted.** Comments/reactions can be
anonymous (IP-attributed). A blocked user who logs out can still react
anonymously; there is no stable identity to block. Reporting still covers the
content itself. Documented, not solved.

**D17 — Feature discovery via a `moderation` block in `/v1/config`.**
Presence of the key = feature available (dev key = dev go signal, prod key =
production launch signal) — same mechanism as mkpx-upload and mod-hashtags.
Carries `report_reasons` (code + English label), `contact_email`,
`guidelines_url`, `moderation_policy_url`.

**D18 — Alert throttling: one email + one mod notification per target per
6 h** (Redis key `ratelimit:report_alert:{target_type}:{target_id}`, prefix
per D23a), regardless of how
many reports pile on. The report rows themselves are always written. The
alert email address is `MODERATION_ALERT_EMAIL` (env), default
`acme@makapix.club`. The `new_report` in-app notification is emitted with the
**system actor** (`utils/audit.py:SYSTEM_USER_KEY`) — anonymous reports have
no reporter to attribute, and mods shouldn't see reporter identity in the
notification anyway (it's in the queue/email). Moderator fan-out queries the
`roles` JSON column via a JSONB cast (`roles.cast(JSONB).contains(...)`,
precedent `search.py:86`) — plain JSON has no containment operator.

**D19 — Block cap: 1,000 blocks per user**, refused with a new
`block_cap_reached` error code (mirrors `reaction_cap_reached`). Bounds the
worst-case filter cost and is far above plausible legitimate use.

**D20 — New stable error code `blocked`** (HTTP 403) for interactions refused
under D11. Clients branch on the code, never the message.

**D21 — Legacy `abuse` reason stays readable.** The read schema keeps `abuse`
valid so pre-existing rows validate; the create schema only accepts the D3
set. No data migration. Removing `abuse` from create inputs is technically a
breaking change under `docs/api-versioning-policy.md`; recorded as safe
because zero clients have ever called `POST /report` (the web has no report
UI and the app hasn't been built) — stated explicitly in the contract.

**D22 — Notifications reuse the existing pipeline.** New types `new_report`
(system notification to moderators) and `report_resolved` (to the reporter)
via `SocialNotificationService.create_system_notification` — list + MQTT +
FCM push with default-on per-type preference, same as `mod_hashtags_updated`.
Old app builds tolerate unknown types by contract.

**D23 — Report rate limits** (Redis, `services/rate_limit.py`): logged-in
10/h per user; anonymous 5/h and 20/day per IP. Values are operational
tuning, not contract — documented in API-CONTRACT as changeable without a
version bump. Two hardening notes from independent review: (a) keys are
prefixed `ratelimit:report:…` so the autouse test fixture
(`conftest.py:195`, flushes `ratelimit:*`) resets them; (b) the existing
`get_client_ip` helper trusts the **leftmost** X-Forwarded-For value, which
is client-spoofable — since IP limits are the only abuse control for
anonymous reports, reporting uses a new trusted-IP helper that takes the
**rightmost** XFF hop (the one Caddy appends), falling back to the socket
peer. Migrating other `get_client_ip` callers (login throttle) to it is a
recommended follow-up, out of scope here.

## Decisions added after independent plan review (2026-07-06)

**D24 — `reporter_ip` is collected only for anonymous reports** (logged-in
reports are already attributed via `reporter_id`), and a nightly sweep nulls
`reporter_ip` on reports older than 30 days — indefinite IP retention on
every report would contradict the plain-English privacy posture. The privacy
page gains one line about it (bump the effective date per policy).

**D25 — Moderator notes get their own column (`mod_notes`).** The current
PATCH handler overwrites the reporter's `notes` with the moderator's note
(`reports.py:202-203`), destroying the original report text. Pre-existing
wart, fixed here because report text is compliance-relevant evidence.

**D26 — Terms acceptance (Apple 1.2 "agreed-to rules") is handled
app-side for now.** The Rules tab gains an explicit zero-tolerance statement,
and the app team is asked (contract §8.6) to gate first run on accepting the
rules at `guidelines_url`. A formal standalone ToS page + signup-time
acceptance checkbox on the website is recommended but deferred — flagged to
the owner as a follow-up decision, not silently dropped.
