# 0001 — Server → App: "Use as profile photo" endpoint (kickoff)

**From:** Club server team
**To:** Makapix app team (Makapix Editor)
**Date:** 2026-07-19
**Status:** Awaiting app reply (0002)

## Summary

The Club now supports setting **any viewable artwork as your profile photo** with one call. The website ships this as a "Use as profile photo" action in the post's ⋮ menu: a confirmation dialog previews the artwork rendered as the user's avatar next to their handle, and on confirm the server copies the artwork into the avatar vault. We'd like the app to add the same action.

Key semantics (all server-side — the app just calls the endpoint):

- **Snapshot:** the artwork bytes are *copied* into the avatar vault, so the avatar survives later deletion or replacement of the source post. The response's `avatar_url` points at a brand-new file with a fresh UUID — the URL changes on every avatar change, so **no cache-busting is needed**; just start using the new URL.
- **Animation preserved:** animated GIF/WebP artworks become animated avatars (bytes copied as-is).
- **BMP handled:** BMP-native artworks are transcoded to PNG server-side.
- **Any viewable post qualifies**, not just the user's own. Attribution (which post the avatar came from) is recorded server-side, internal-only — it never appears in API payloads and there is nothing for the app to display.

## Contract

`POST /user/{user_key}/avatar/from-post` — sits beside the avatar endpoints you already call in `club_api_client.dart` (`POST`/`DELETE /user/{user_key}/avatar`), same base path, same auth (Bearer), same rate-limit bucket (20 avatar writes/hour).

Request body (JSON):

| Field | Type | What to send |
|-------|------|--------------|
| `post_sqid` | str | The post's `public_sqid` (the id you already hold on `Post`). |

Responses (legacy root-path `{detail}` error style, like the existing avatar endpoints):

| Status | Meaning |
|--------|---------|
| 201 | Success — full `UserFull` payload, incl. the new `avatar_url`. |
| 400 | Post has no artwork image (e.g. a playlist), or the image can't be used (too large). |
| 401 / 403 | Not signed in / not allowed to edit that user's avatar. |
| 404 | Unknown sqid, or the post isn't viewable by the caller (incl. deleted posts). |
| 429 | Avatar rate limit (20/hour, shared with avatar upload). |
| 507 | Storage temporarily full — ask the user to retry later. |

## Suggested UX (mirror of the website — your call on details)

1. New item **"Use as profile photo"** in the artwork detail page's `PopupMenuButton` (`ui/artwork_detail_page.dart`), visible to any signed-in user (not gated on ownership).
2. Confirmation dialog showing a preview row: the artwork rendered avatar-size (your `HandleAvatar` widget in `ui/widgets/common.dart` is the natural fit — pass the post's `art_url`) next to the current user's handle, i.e. exactly how it will look once set.
3. On 201: update the locally cached user `avatar_url` from the response and refresh any UI that shows it. Since the URL is new, `CachedNetworkImageProvider` will fetch it naturally.

## Status on our side

- Endpoint + website UI are implemented on `develop` and will be on development.makapix.club now; prod deploy expected within days. We'll send a "live on prod" message when it ships.
- No release gating in either direction — this is a purely additive endpoint.

## Questions for you

1. Does the suggested placement (artwork detail ⋮ menu) fit your UX, or would you rather surface it elsewhere (e.g. long-press on feed tiles too)?
2. Anywhere in the app that caches the avatar URL *outside* `avatarImageCache` (e.g. persisted session state) that would need an explicit refresh after the change?
3. Any objection to the shared 20/hour avatar rate limit from an app-UX perspective?

Reply as `0002-app-…` when convenient.
