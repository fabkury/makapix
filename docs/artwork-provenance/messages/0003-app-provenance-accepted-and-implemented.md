# 0003 — App → Server: Provenance + lineage accepted, implemented app-side

**From:** Makapix app team (Makapix Editor)
**To:** Club server team
**Date:** 2026-08-14
**Re:** 0001 (kickoff) + 0002 (lineage amendment)
**Status:** All asks accepted. App-side implementation is DONE on our `main` (unreleased); we'll e2e against dev when you send test instructions, and it ships with the next release.

## Answers to your open questions

1. **Sticky import bit + remix-seeding-counts-as-import — accepted as proposed.** The bit is set by any use of the import tool and by Club-post seeding, and never clears. `editor_hand_drawn` is only ever declared for documents tracked from birth by a provenance-aware app version.
2. **Legacy files: the bit is future-only.** Existing project files (and any foreign `.mkpx`) carry no provenance record and cannot be reconstructed honestly, so they publish with `creation_method` omitted → "unknown", per 0001. One deliberate wrinkle: if a user imports into a legacy document *after* updating, we do declare `editor_import` — "import was used" is then true regardless of the unknowable earlier history.
3. **No obstacle to project-file persistence — done.** We persist in the `.mkpx` container's ancillary `META` chunk (typed key/value, already in our v10 format spec; the engine core ignores it, so goldens/determinism are untouched). Keys: `club.everImported`, `club.importedFormats`, `club.parents` (comma list, declaration order). Every save path carries it — the library autosave, explicit save/export, and the layers file we attach at publish — so lineage survives "load A1 → save locally → finish next week → publish", and even survives the file being exported, shared, and reopened on another device. Consequence you should know: the parent list inside a shared `.mkpx` is readable by anyone holding the file. Since lineage is public now anyway, we judged that fine — flag it if you disagree.

## What the app now sends (both `POST /post/upload` and `replace-artwork`)

- `client=app/<version>`, `creation_method` (or omitted = unknown), `remixed_from` (comma list, base first), and `source_details` with `editor_version`, `editor_platform` (`ios`/`android` only — our Windows dev build omits it), `imported_format`, and `device_type`.
- `remixable` on upload only, from a new "Allow remixes" toggle (default on; an ND license disables the toggle and omits the field so your effective default applies — we never send the contradiction).
- On replace we exclude the replaced post's own sqid from `remixed_from` (self-loop) and send no `remixable`.

Two details worth confirming in your Phase-1 tests:

- **`imported_format` may be a comma list** (`png,gif`) when several formats were imported over the work's history, first-use order. It's a whitelisted str on your side, so we assumed free-form is fine — say so if you want single-value.
- **Multi-parent is real in the container but not yet in the UI**: the app currently seeds a document from ONE Club post and has no "import another Club post into the open document" flow, so we'll send at most one parent for now. The list format, ordering, dedup, and 8-cap are all implemented and tested (model + persistence), so we grow into multi-parent the day such a flow ships — no contract change needed.

## Lineage UX implemented per 0002

- **Gating:** the "Edit in Makapix" affordance is disabled (with a tooltip) when `remixable=false` and the viewer isn't the owner; a racing 403 `not_remixable` on the `.mkpx` download is surfaced and refreshes the post.
- **422 handling:** `remix_not_allowed` / `parent_not_found` at publish opens a dialog ("the artist has since disabled remixes" / "the original no longer exists") whose only path forward is the user's explicit "Publish without remix claim" — we never strip the declaration silently. The retry drops only `remixed_from`; the rest of the declaration still goes.
- **Owner controls:** "Allow remixes" at publish and in the post's Edit details (PATCH), both ND-aware.
- **Public UI:** a discreet Remix line on the post detail page — badge when `parent_count > 0`, visible-remixes count from `child_count`. Browsable parents/children lists and the `remix` notification rendering are NOT in this round; the notification arrives through the existing SSE pipe and displays as a generic notification meanwhile.

## Asks / notes for you

1. Send the dev test instructions when Phase 1 lands there — we'll run the e2e matrix (declare/omit, remix chain, Remixable flip mid-flight, replace-append, ND coupling) from a dev build.
2. We read `remixable`-absent as `true` client-side so pre-lineage servers don't lock every post; harmless, but worth knowing.
3. `GET /v1/post/{id}/parents`/`children` and `/v1/me/remixes` are noted for a later round.

Reply as `0004-server-…` when there's something to test.
