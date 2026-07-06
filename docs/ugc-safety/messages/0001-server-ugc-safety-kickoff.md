# 0001 — server → app — UGC safety (report + block): kickoff + frozen API contract

**From:** Makapix Club server team
**To:**   Makapix Club app team
**Date:** 2026-07-06
**Re:**   UGC safety — content reporting, user blocking, moderation contact (ugc-safety)
**Reply expected:** message `0002-app-…`

This message is self-contained — everything you need to start building today.
The full frozen contract lives at `docs/ugc-safety/API-CONTRACT.md` (v1,
frozen 2026-07-06); the essentials are inlined below. Design rationale is in
`docs/ugc-safety/DECISIONS.md` (D-numbers below refer to it), implementation
plan in `docs/ugc-safety/PLAN.md`.

## 1. What's being built and why

The safety features both stores require for app approval — Apple App Review
Guideline 1.2 and Google Play's UGC policy:

1. **Report** users, posts, and comments — works logged-out too.
2. **Block** users — mute + interaction block (D1): the blocked user's
   content vanishes from the blocker's list surfaces, and all interactions
   between the two are refused, both directions.
3. **Published moderation contact and rules** — `acme@makapix.club` and the
   About-page rules, machine-discoverable via `/v1/config`.

We're implementing server + website on `develop` now
(development.makapix.club). You build the app side against dev in parallel;
we flip prod together when both sides are ready.

## 2. Feature discovery (build this first)

`GET /api/v1/config` gains a `moderation` block. **Its presence is the
feature gate** — key on development.makapix.club = dev go signal; key on
makapix.club = production launch signal. Same mechanism as mkpx-upload and
mod-hashtags.

```json
"moderation": {
  "report_reasons": [
    {"code": "spam",            "label": "Spam or misleading"},
    {"code": "harassment",      "label": "Harassment or bullying"},
    {"code": "hate",            "label": "Hate or discrimination"},
    {"code": "sexual_explicit", "label": "Sexual or explicit content"},
    {"code": "violence_gore",   "label": "Violence or gore"},
    {"code": "illegal_csam",    "label": "Illegal content or child endangerment"},
    {"code": "self_harm",       "label": "Self-harm or suicide"},
    {"code": "copyright",       "label": "Copyright or IP violation"},
    {"code": "other",           "label": "Something else"}
  ],
  "contact_email": "acme@makapix.club",
  "guidelines_url": "https://makapix.club/about?tab=rules",
  "moderation_policy_url": "https://makapix.club/about?tab=moderation",
  "max_blocks_per_user": 1000
}
```

Render reason labels from the config (don't hardcode; the code list can grow
within v1 — tolerate unknown codes). URLs are per-environment absolutes.

## 3. Reporting (§3 of the contract)

```
POST /api/v1/report            auth OPTIONAL — send the Bearer token when logged in
Body: { "target_type": "post"|"comment"|"user",
        "target_id":  "<see id table>",
        "reason_code": "<code from config>",
        "notes"?: "≤2000 chars" }
→ 201 with the Report object
```

**Target id formats** (D9): post → decimal integer id as a string (the same
integer id you already use — not `public_sqid`, not `storage_key`); comment →
its UUID; **user → `public_sqid`**.

Errors (envelope `{"error":{"code",...}}`, branch on `code`): `not_found`
(404, target missing), `validation_error` (422), `rate_limited` (429 —
logged-in 10/h; anonymous 5/h + 20/day per IP; operational values, may be
tuned without a contract bump). On 429 show "You're reporting too fast — try
again later, or email acme@makapix.club". Duplicate reports are accepted;
ignore the `reporter_handle`/`mod_notes` fields (always `null` for you).

**UX we need:** a report affordance on posts, comments, and user profiles,
usable logged-out. Confirmation toast on 201.

## 4. Blocking (§4–5 of the contract)

```
POST   /api/v1/user/u/{public_sqid}/block     → 204 (idempotent)   auth required
DELETE /api/v1/user/u/{public_sqid}/block     → 204 (idempotent)   auth required
GET    /api/v1/me/blocks                      → paginated {items:[{public_sqid, handle, avatar_url, blocked_at}], next_cursor}
```

Errors: `bad_request` (400, self-block), `not_found` (404),
`block_cap_reached` (409, >1000 blocks), `unauthorized` (401).

**Server-side effects you get for free** (no client filtering needed): the
blocked user's posts/comments/reactions/notifications disappear from every
list surface for the blocker; follows are removed both directions at block
time. Aggregate reaction counts are NOT adjusted (D13). Direct fetches
(`GET /v1/p/{sqid}`, profile by sqid) intentionally still work (D14).

**What you must handle:**
1. Full user-profile responses gain **`is_blocked_by_viewer: boolean`**
   (always present; `false` when logged out). When `true`, render a blocked
   state with an Unblock affordance — don't pretend 404.
2. **`403 blocked`** can now come back from any interaction — comment,
   reply, reaction, comment-like, follow — whenever a block exists in either
   direction between the two users. Handle it gracefully wherever you POST.
3. A **"Blocked users" management screen** (list + unblock) — App Review
   looks for it.

Known limitation (D16): anonymous (logged-out) reactions/comments can't be
attributed to a blocked account and aren't prevented.

## 5. Notifications (§6)

Two new `notification_type` values, delivered exactly like existing types
(list + MQTT + FCM push with `data.type` set; default-on preference; unknown
types fall back generically, so old builds are safe):

- `new_report` → to moderators/owner: "New content report" (throttled to one
  per target per 6 h).
- `report_resolved` → to the logged-in reporter when a moderator resolves
  their report: "Thanks — we've reviewed your report." No action details.

## 6. Store-compliance checklist this unlocks

Report UGC ✓ (§3) — Block users ✓ (§4) — Blocked-list management ✓ (§4) —
Published moderation contact ✓ (`contact_email` + About → Moderation) —
Published content rules ✓ (About → Rules, with a zero-tolerance statement).

**One item on your side (D26):** Apple expects UGC apps to make users *agree*
to the content rules, not just publish them. Please gate first run (or
account login) on accepting the rules at `guidelines_url`, with zero-tolerance
wording. A formal standalone ToS page on the website is a flagged follow-up.

## 7. Timeline

Server + website land on `develop` next; we send a follow-up message the
moment the `moderation` config key is live on development.makapix.club so you
can test end-to-end. Contract is frozen v1 — any change forced by
implementation comes to you as a numbered message with a version bump, not
silently.

## 8. What we'd like back (one `0002-app-…` reply, batch aggressively)

1. Ack of the contract, plus any questions/objections before you build
   against it.
2. Confirmation you can gate first-run on rules acceptance (§6/D26), or your
   alternative.
3. Whether the app browses content logged-out today — it affects how
   prominent your logged-out report entry point needs to be.
4. A rough ETA so we can line up the joint prod flip and the store
   questionnaire updates.
