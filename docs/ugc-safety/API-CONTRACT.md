# UGC safety — API contract

**Status: FROZEN v1 (2026-07-06).** Changes require a numbered message to the
app team and a contract version bump. Additive server changes (new optional
fields, new enum values clients must tolerate) do not bump the version.

All endpoints live under `/api/v1` (public path; the FastAPI app sees `/v1`).
Errors use the standard envelope `{"error": {"code", "message", "details"?}}` —
**branch on `code`, never on `message`.** Decision references (Dn) point at
`DECISIONS.md`.

## 1. Feature discovery (build this first)

`GET /api/v1/config` gains a `moderation` block. **Presence of the key is the
feature gate**: key on development.makapix.club = dev go signal; key on
makapix.club = production launch signal (same mechanism as mkpx-upload and
mod-hashtags).

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

Render reason labels from the config (don't hardcode); the `code` list may
grow within v1 — tolerate unknown codes. URLs are absolute and per-environment
(dev serves development.makapix.club URLs).

## 2. Target identifiers (D9)

| `target_type` | `target_id` format | Example |
|---|---|---|
| `post` | decimal integer id, as string | `"1234"` |
| `comment` | comment UUID, as string | `"7d9f…"` |
| `user` | **`public_sqid`**, as string | `"t5"` |

The same `public_sqid` identifies users in the block endpoints below
(`/user/u/{public_sqid}/…`, matching the existing follow endpoints).

## 3. Reporting

### `POST /api/v1/report` — file a report

Auth **optional** (D2): send the Bearer token when the user is logged in;
logged-out reports are accepted subject to stricter IP rate limits.

```json
{
  "target_type": "post" | "comment" | "user",
  "target_id":  "<per §2>",
  "reason_code": "<code from config report_reasons>",
  "notes": "optional free text, ≤ 2000 chars"
}
```

**201** → the created Report object:

```json
{
  "id": "<uuid>",
  "target_type": "post",
  "target_id": "1234",
  "reason_code": "harassment",
  "notes": null,
  "status": "open",
  "action_taken": null,
  "created_at": "2026-07-06T12:00:00Z",
  "updated_at": null
}
```

| Status | `error.code` | When |
|---|---|---|
| 404 | `not_found` | target does not exist (or is hard-deleted) |
| 422 | `validation_error` | unknown `reason_code` / malformed `target_id` / notes too long |
| 429 | `rate_limited` | limits (D23): logged-in 10/h; anonymous 5/h + 20/day per IP. Operational values — may be tuned without a version bump. |

Reporting content that is already hidden or that the reporter has blocked is
allowed. Duplicate reports by the same reporter are accepted (moderator
alerting is deduplicated server-side, D18). Report objects also carry
`reporter_handle` and `mod_notes` fields — always `null` outside moderator
listings; ignore them. Note: the previous `abuse` reason is no longer accepted
on create — technically a breaking input change, recorded as safe because no
client has ever called this endpoint (D21).

UX expectation (both clients): a report affordance on posts, comments, and
user profiles; confirmation toast on 201; on 429 show "You're reporting too
fast — try again later, or email acme@makapix.club".

### Moderator endpoints (unchanged surface, fixed semantics)

`GET /api/v1/report` (roles `moderator`/`owner`) — cursor-paginated queue;
filters `status`, `target_type`, `reporter_id` (integer). Report objects in
moderator listings additionally carry `reporter_handle: string | null`
(`null` = anonymous report). `PATCH /api/v1/report/{id}` — unchanged
request shape; user-target actions now resolve `target_id` as `public_sqid`
(D9), and the moderator's `notes` are stored in a separate `mod_notes` field
so the reporter's original text is never overwritten (D25). Legacy rows may
carry `reason_code: "abuse"` (D21) — render it as "Harassment or bullying".

## 4. Blocking (D1)

All three endpoints require auth (`401 unauthorized` otherwise).

### `POST /api/v1/user/u/{public_sqid}/block` — block a user

**204** on success; **idempotent** (blocking an already-blocked user is 204).

| Status | `error.code` | When |
|---|---|---|
| 400 | `bad_request` | attempting to block yourself |
| 404 | `not_found` | no such user |
| 409 | `block_cap_reached` | more than 1000 blocks (D19) |

Side effects: follows between the two users are removed **both directions**
(D12); the blocked user's content disappears from the blocker's list surfaces
(D10); interactions between the two are refused both ways (D11).

### `DELETE /api/v1/user/u/{public_sqid}/block` — unblock

**204**; idempotent. 404 only if the *user* does not exist.

### `GET /api/v1/me/blocks` — the caller's blocked list

Cursor-paginated (`cursor`, `limit` ≤ 200):

```json
{
  "items": [
    {"public_sqid": "x9k2", "handle": "someuser", "avatar_url": null,
     "blocked_at": "2026-07-06T12:00:00Z"}
  ],
  "next_cursor": null
}
```

Both clients need a "Blocked users" management screen (unblock from the list)
— App Review looks for it.

### Profile field

Full user-profile responses gain **`is_blocked_by_viewer: boolean`** (always
present; `false` when logged out). When `true`, render the profile in a
blocked state (art hidden or collapsed, "Unblock" affordance) — the server
intentionally still returns the profile on direct navigation (D14).

## 5. What blocking changes on existing endpoints

For a logged-in viewer, these surfaces stop including blocked users' content
(server-side; no client filtering needed): post feeds/listings, search results
(posts + users), comment threads (a blocked author's comment disappears along
with its replies; an individual blocked reply disappears alone), who-reacted
lists, and the notifications list. Aggregate reaction counts are **not**
adjusted (D13). Direct URL fetches (`GET /v1/p/{sqid}`, profile by sqid) are
**not** filtered (D14). Playlists are not filtered (D15).

Interactions refused with **403 `blocked`** (D20) when a block exists in
either direction: creating a comment or reply on the other's post/comment,
adding a reaction, liking a comment, following. Clients should handle 403
`blocked` gracefully anywhere an interaction can be attempted.

Anonymous (logged-out) reactions/comments cannot be attributed to a blocked
account and are not preventable (D16).

## 6. Notifications (D22)

Two new `notification_type` values, delivered like every other type (list +
MQTT + FCM push, `data.type` mirrors the type; default-on per-type
preference; unknown types fall back to a generic push — old builds are safe):

| Type | Recipient | Trigger | Copy guidance |
|---|---|---|---|
| `new_report` | all moderators/owner | first report on a target within the 6 h throttle window (D18) | "New content report — open the moderation queue" |
| `report_resolved` | the (logged-in) reporter | moderator resolves the report | "Thanks — we've reviewed your report." No action details. |

## 7. Compliance mapping (for the store questionnaires)

| Store requirement | Where satisfied |
|---|---|
| Report UGC / users | §3 report endpoint + UI on posts, comments, profiles (logged-out capable) |
| Block users | §4 block endpoints + blocked-list management UI |
| Published moderation contact | `acme@makapix.club` in §1 config + About → Moderation tab |
| Published content rules | About → Rules tab (prohibited categories mirror §1 reason codes, plus an explicit zero-tolerance statement) |
| Agreed-to content rules (Apple 1.2) | App gates first run on acceptance of the rules at `guidelines_url` (§8.6); a formal standalone ToS page is a flagged follow-up (D26) |
| Timely action on reports | D4 immediate moderator alerting (email + push); 24 h response target published on the About page |

## 8. What we need from the app team

1. Ack of this contract (or objections) as message `0002-app-…`.
2. Report flow on posts, comments, profiles (§3), gated on the `moderation`
   config key.
3. Block/unblock on profiles + blocked-users screen (§4).
4. Handling of `403 blocked` (§5) and the two new notification types (§6).
5. ETA so we can line up the joint prod flip.
6. A first-run "agree to the community rules" gate (link `guidelines_url`,
   state zero tolerance for objectionable content) — App Review expects
   *agreed-to* rules for UGC apps, not just published ones (D26).
