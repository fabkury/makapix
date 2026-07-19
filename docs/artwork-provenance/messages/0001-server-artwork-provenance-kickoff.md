# 0001 — Server → App: Artwork provenance fields on upload (kickoff)

**From:** Club server team
**To:** Makapix app team (Makapix Editor)
**Date:** 2026-07-19
**Status:** Awaiting app reply (0002)

## Summary

The Club server is adding internal provenance tracking to every uploaded artwork, so we can distinguish (at minimum): hand-drawn editor works, editor works that used the **import** tool, and files created elsewhere and uploaded directly. The server accepts what clients declare; nothing is enforced. We're asking the app to start sending a few **optional, additive multipart form fields** on the two publish endpoints. No app release gates our rollout — absent fields simply record as "unknown".

Provenance is **internal-only** (moderators/admins). It does not appear in the public `Post` schema and there are no public badges for now.

## New optional form fields

On `POST /v1/post/upload` **and** `POST /v1/post/{id}/replace-artwork`:

| Field | Type | What to send |
|-------|------|--------------|
| `client` | str ≤ 64 | `app/<version>`, e.g. `app/1.0.14`. (The website sends `web`.) |
| `creation_method` | str | `editor_hand_drawn` \| `editor_import` \| `external_file` — see semantics below. Unknown values are rejected with 422 `invalid_creation_method`, so please send exactly these strings. |
| `source_details` | str (JSON object, ≤ 2048 bytes) | Optional extras; whitelisted keys: `editor_version` (str), `editor_platform` (`ios`\|`android`), `imported_format` (str, e.g. `png` — when method is `editor_import`). Unknown keys are silently dropped. Keys starting with `_` are reserved for the server. |
| `remixed_from` | str | `public_sqid` of the Club post the work was seeded from, when publishing an edit/remix of an existing post (your C3 flow). Best-effort on our side: if the post no longer exists we still record the sqid and the upload succeeds. |

Errors added: `invalid_creation_method` (422), `invalid_source_details` (422). Everything else about the endpoints — including the frozen mkpx contract (blob stays opaque, magic-bytes-only validation) — is unchanged.

## Proposed semantics (please confirm or counter-propose)

1. **Sticky import bit.** `editor_import` means the import tool was used *at any point in the work's history*, even if the pixels were later fully repainted. `editor_hand_drawn` is the strong claim: from-scratch, never imported. You own tracking this bit across saves/loads — persisting it in the project file (e.g. a META key) seems natural, but the mechanics are your call. When you genuinely can't tell (e.g. legacy project files predating the bit), omit `creation_method` entirely rather than guessing — absent means "unknown" on our side, which is honest.
2. **Remix seeding counts as import.** Loading an existing Club post into the editor for edit/remix ⇒ the published result is `editor_import` (+ `remixed_from`), not `editor_hand_drawn`.
3. **Gallery-pick direct uploads** (if/when the app lets users upload an existing file without going through the editor) ⇒ `external_file`, still with `client=app/<version>`.
4. **Replace-artwork:** provenance describes the *current* bytes, so please send the fields on replace too; if you send nothing, the method resets to unknown (it does not carry over from the original upload).

## What the server records alongside your declaration

For transparency: we also store observed signals (your raw `client` string, User-Agent, whether an `.mkpx` accompanied the upload) in a server-reserved area, visible to moderators. Declarations are trusted as-is; mismatches are just context for mods.

## Timeline

- Server implementation + dev deploy: next few days; we'll send a "live on dev" message (0002 or 0003) with test instructions.
- No deadline pressure on the app — fields are optional forever; old versions in the wild keep working.

## Questions for you

1. OK with the sticky-import-bit semantics (§1) and remix-counts-as-import (§2)?
2. Can the editor already tell, for an existing project, whether import was ever used — or is this a new bit that only future works will carry?
3. For C3 remixes, is `public_sqid` the id you naturally hold at publish time?

Reply as `0002-app-…` when convenient.
