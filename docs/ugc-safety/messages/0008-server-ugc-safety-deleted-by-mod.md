# 0008 — server → app — additive `deleted_by_mod` on comment payloads

**From:** Makapix Club server team
**To:**   Makapix Club app team
**Date:** 2026-07-13
**Re:**   Moderation follow-up — comment deletion attribution (ugc-safety)
**Reply expected:** none required — informational; reply only if §3 applies to you

## 1. What shipped

Live on prod today (PR #234). Moderator comment deletions used to be recorded
with the same flag as author self-deletes (`deleted_by_owner`), so clients
could not tell them apart. Comment objects now carry an explicit flag:

```json
{
  "body": "[deleted by moderator]",
  "hidden_by_mod": false,
  "deleted_by_owner": false,
  "deleted_by_mod": true
}
```

Semantics:

- **Author self-delete** → `deleted_by_owner: true`, body `"[deleted]"`.
- **Moderator delete** (direct or via report take-down) → `deleted_by_mod: true`,
  body `"[deleted by moderator]"`.
- Exactly as before, deleted comments appear in listings **only as tombstones
  for threads** — i.e. only when they still have visible replies; deleted
  leaves are omitted. Counts exclude both kinds.

## 2. Contract change (additive, no version bump)

`deleted_by_mod` (boolean) is added to comment objects everywhere they are
served (post comments in flat/tree views, create/edit responses, and blog-post
comments). Everything else is unchanged. Per the versioning policy this is
additive — older builds that ignore it keep working.

## 3. One nuance worth checking on your side

The `body` of a deleted comment always contains the correct tombstone text, so
**if you render `body` as-is you are done — no action needed.** But if you
mimic our website and derive the placeholder from the flag (render
`"[deleted]"` when `deleted_by_owner` is true), note that moderator-deleted
tombstones no longer set `deleted_by_owner` — treat a comment as deleted when
`deleted_by_owner || deleted_by_mod`, and ideally show
"[deleted by moderator]" for the latter (that's what the website does).

Existing data was migrated: the handful of historical moderator take-downs now
read `deleted_by_mod: true` / `deleted_by_owner: false`.

## 4. Not exposed to clients

Internally the server now also preserves the pre-deletion text for moderator
review (with a mod-only purge for PII). None of that is visible through any
client-facing endpoint — mentioning it only so the moderation story is
complete.
