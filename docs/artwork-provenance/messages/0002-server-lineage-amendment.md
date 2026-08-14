# 0002 — Server → App: Lineage amendment to the provenance kickoff

**From:** Club server team
**To:** Makapix app team (Makapix Editor)
**Date:** 2026-08-14
**Status:** Supersedes parts of 0001 (you hadn't replied yet, so nothing you've built is affected). Awaiting app reply (0003).

## What changed since 0001

The provenance feature grew into a full **remix lineage** system, designed and approved today. Three things in 0001 are amended; everything else there (field names, `client`, `creation_method`, `source_details` whitelist, sticky-import-bit semantics, replace-artwork behavior, opacity of `.mkpx`) still stands.

### 1. `remixed_from` is now a comma-separated LIST

A remix can have **multiple Parents** (e.g. the user opens post A2, then imports post A3 → the published work has Parents A2 *and* A3). Send every Club post that seeded or was imported into the work:

```
remixed_from=aB3xY,qW9zK
```

- Declaration order matters: **base first**, imports after, in the order they entered the work. We preserve it for display.
- Up to 8 Parents after de-duplication.
- Club posts only — an imported external PNG is still just `editor_import` + `imported_format`, not a Parent.

### 2. Lineage is now PUBLIC, and enforcement is real (this is the big one)

- Every post gains a public boolean **`remixable`** in the `Post` schema (default true; owners can turn it off at upload or any time later).
- **Gate your "open in editor / edit / remix" UX on it**: when `remixable` is false and the viewer isn't the post's owner, don't offer the remix path.
- Server-side enforcement you will observe:
  - `GET /d/{sqid}.mkpx` returns **403 `not_remixable`** for non-owners when the post isn't Remixable.
  - Publishing with a `remixed_from` entry whose post is missing → **422 `parent_not_found`**; whose post isn't Remixable → **422 `remix_not_allowed`** (the offending sqid is named in the error). The whole upload is rejected — please surface "the artist has since disabled remixes" and let the user decide (they can publish without the remix claim only by their own explicit choice; we'd rather you not automate stripping the declaration).
  - Links, once created, are permanent (moderators can sever) — a later `remixable` flip never invalidates existing remixes. Replace-artwork can *add* parents but never removes them.
- Public UI (web, and yours if you like): a discreet Remix badge + parent/child counts on every post; logged-in users can browse parents/children; parent owners get a `remix` notification when a remix of their work is published.

### 3. New REQUIREMENT: persist declarations in the project file

We read your snapshot: `_clubSource` is in-memory only and is cleared on save-to-local and reopen. That loses the lineage for the completely normal workflow "load A1 → save locally → finish next week → publish". Per our shared-matter split, this is the server-side contract requirement:

> The sticky import bit **and** the accumulated Parent-sqid list must survive save/load, so that publish-time declarations reflect the work's whole history.

Persisting them in the project file (e.g. META keys) seems natural, but the mechanics are entirely your call.

### 4. Small addition: `device_type`

Please add to `source_details`: `"device_type": "mobile" | "tablet"` (your form factor; the website sends `desktop`/`mobile`/`tablet`). It means the *upload* device.

## Unchanged asks from 0001 (still open, please answer in 0003)

1. OK with sticky-import-bit + remix-seeding-counts-as-import semantics?
2. Can existing project files tell whether import was ever used, or is the bit future-only?
3. (Answered by our code reading: you do hold `public_sqid` at publish — thanks.) New question: any obstacle to persisting the Parent list + sticky bit in the project file?

## Timeline

Server Phase 1 (schema, endpoints, enforcement, notifications) is being implemented now and will hit dev shortly; we'll send test instructions when it's live on dev. Fields remain optional forever — old app versions keep working; they just produce "unknown" provenance and no lineage.
