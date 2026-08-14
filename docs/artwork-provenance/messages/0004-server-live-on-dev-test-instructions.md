# 0004 — Server → App: Everything is live on dev — test instructions

**From:** Club server team
**To:** Makapix app team (Makapix Editor)
**Date:** 2026-08-14
**Re:** 0003 (your acceptance + implementation)
**Status:** Server Phases 1+2 (API + web) are DEPLOYED ON DEV. Run your e2e matrix whenever you like and reply as `0005-app-…` with results.

## Verdicts on your two confirmables

1. **`imported_format` comma list — accepted.** Free-form comma list in first-use order is the documented convention now. The whitelist validator caps the *total* string at **64 chars**; beyond that the upload fails 422 `invalid_source_details` (same as any invalid whitelisted value). Live on dev as of today.
2. **Parent sqids readable in shared `.mkpx` META — accepted as-is.** A sqid inside a file someone already holds is a weak leak (a hidden/deleted parent's post still 404s for them), and the META persistence is exactly what makes lineage survive the download → edit → republish loop. No redaction requested. For the record: our web UI still anonymizes not-visible parents as "unavailable" slots in the lists — the two behaviors coexist fine.

Also noted and matching: you read absent `remixable` as `true` client-side — that equals our server default, no divergence possible.

## What's live on dev (development.makapix.club, same base + credentials as your previous e2e rounds)

- All upload/replace provenance + lineage fields per 0001+0002, all error codes (`invalid_creation_method`, `invalid_source_details`, `parent_not_found`, `remix_not_allowed`, `too_many_parents`, `lineage_cycle`, `remixable_conflicts_with_license`, `not_remixable`).
- `remixable` in the public `Post` schema, plus `parent_count` (all links incl. tombstones — the badge fact) and `child_count` (publicly-visible children).
- **Contrary to your "later round" note, the list endpoints are ALREADY live** — feel free to adopt them whenever: `GET /v1/post/{id}/parents` (ordered slots `{position, state: available|unavailable|deleted, post?}`), `GET /v1/post/{id}/children` (viewer-visible, cursor-paginated), `GET /v1/me/remixes` (aggregate, names which of the caller's works each Remix declares) — all login-required.
- The `remix` notification: `notification_type="remix"` over the existing SSE pipe, actor = remixer, content fields point at the **child** (the new Remix). Your generic rendering will work unchanged.
- Web side is live too (badge, lists, Remixable toggles, ToS clause), so you can cross-check behaviors against the website on the same posts.

## Seeded fixture for immediate checks

Dev carries one synthetic lineage pair: post `gZC` is declared a child of `P2J`. `GET /v1/p/gZC` → `parent_count: 1`; `GET /v1/p/P2J` → `child_count: 1`. Also note dev's catalog was relicensed per our launch decision: nearly everything is Remixable; one deliberately ND-locked post remains (`GET /v1/p/` it and you'll see `remixable: false`) — ask if you want its sqid, or create your own ND post for that leg.

## Your e2e matrix — expected outcomes

| Case | Expectation |
|------|-------------|
| Declare / omit provenance | 201 either way; omitted = unknown server-side. Channel/method/details are internal-only — send us the sqids of your test uploads and we'll verify the stored values on the mod surface (or use a dev mod account if you have one). |
| Remix chain (A → B → C) | Links visible via `parent_count`/`child_count` + the list endpoints; each publish fires a `remix` notification to the parent's owner (none for self-remix). |
| Remixable flip mid-flight | Publish after the parent flipped off → **422 `remix_not_allowed`**, `details.parent` names the sqid; your "publish without remix claim" retry then succeeds. Links created before the flip stay (grandfathered). |
| Replace-append | `remixed_from` on replace adds new parents (permission-checked), never removes; re-declaring an existing parent is a silent no-op; declaring the post's own sqid or a descendant → 422 `lineage_cycle` (you already exclude self client-side — good, both sides guard). |
| ND coupling | ND license + explicit `remixable=true` → 422 `remixable_conflicts_with_license`; ND + omitted → effective false (you never send the contradiction — correct). |
| mkpx gate | Non-owner `GET /d/{sqid}.mkpx` on a non-Remixable post → **403 `not_remixable`**; owner and mods pass. |
| Deleted parent | Delete a test parent → child's links survive; parents list shows a `deleted` tombstone slot. |

## One request

When you run the matrix, publish at least one upload with `imported_format` as a multi-entry list and one with `device_type` set, and include those sqids in 0005 — we'll confirm the stored `source_details` match byte-for-byte.
