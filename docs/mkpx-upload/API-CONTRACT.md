# mkpx-upload — API Contract (v2, FROZEN)

**Status:** FROZEN 2026-07-02 — acked unchanged by the app team in message 0002.
Open questions §11 all answered (0002): MIME + filename as proposed; slim shapes stay
slim; cap stays 50 MB (owner decision, relayed in 0003); app uploads compact profile
(plain accepted for attach-from-disk); attach-later on web-created artwork posts is
in-contract. Any future change requires a new message-numbered amendment.
Source of truth for both teams. Server = development.makapix.club (then makapix.club at flip).
All paths below are under the canonical prefix the app already uses: `https://{host}/api/v1`.
Note the **singular `/post`** prefix throughout — it matches the server's router; there is no `/posts`.

## 1. Capability discovery

`GET /v1/config` (public, ETag/300 s cache — unchanged) gains one key inside `upload`:

```json
{
  "upload": {
    "formats": ["png", "gif", "webp", "bmp"],
    "max_file_bytes": 5242880,
    "...": "existing fields unchanged",
    "mkpx": {
      "enabled": true,
      "max_file_bytes": 52428800
    }
  }
}
```

- `mkpx` **absent or `enabled: false`** → feature off; app must hide the share checkbox,
  golden Edit button styling, and any mkpx menu items. The key is absent on dev **today**,
  so gating can be implemented and verified immediately.
- `max_file_bytes`: server-enforced cap for the uploaded .mkpx (default 50 MB).
- This block appearing on makapix.club **is** the production launch signal (deploy = flip).

## 2. File acceptance rules (server-enforced)

- First 8 bytes must be one of:
  - plain profile: `89 4D 4B 50 58 0D 0A 1A` ("‰MKPX\r\n\x1a")
  - compact profile: `89 4D 4B 50 5A 0D 0A 1A` ("‰MKPZ\r\n\x1a")
- Size ≤ `upload.mkpx.max_file_bytes`.
- Nothing else is inspected — the server treats the file as an opaque blob and returns it
  **byte-identical** on download. Deep validation (chunk structure, CRC-32C, version) stays
  the app's job. Compact profile recommended for uploads (smaller), both accepted.

## 3. Error contract (frozen)

`/v1/*` errors use the standard envelope `{"error": {"code": "...", "message": "...", "details": ...}}`.
Codes are stable — branch on `code`, never on `message`. The mkpx endpoints use exactly:

| HTTP | `code` | When |
|---|---|---|
| 401 | `unauthorized` | Missing/invalid/expired Bearer token (download, attach, detach) |
| 403 | `forbidden` | Authenticated but not the post's author (attach, detach) |
| 404 | `not_found` | Post doesn't exist; post is a playlist; post is soft-deleted; detach/download when no mkpx attached; post not visible to requester |
| 413 | `mkpx_too_large` | File exceeds `upload.mkpx.max_file_bytes` |
| 413 | `quota_exceeded` | File would exceed the user's storage quota |
| 422 | `mkpx_invalid` | First 8 bytes match neither profile signature |
| 429 | `rate_limited` | Upload rate-limit bucket exhausted (upload, attach/replace) |

Example: `{"error": {"code": "mkpx_too_large", "message": "Layers file exceeds 52428800 bytes."}}`

## 4. Quota & rate limits (context you can't see server-side)

- **Storage quota tiers** (by reputation): 100 MB (<100), 200 MB (100–499), 500 MB
  (500–999), 1000 MB (1000+). Artwork bytes + mkpx bytes count together. A fresh account
  fits only **two** 50 MB layers files — surface quota state in your UX rather than
  discovering 413s.
- **Upload rate limit** (by reputation): 4 / 16 / 64 per hour. One upload = one token,
  with or without mkpx. Attach/replace consumes one token. **Detach consumes none.**
  A rejected attach (bad magic/oversize) still consumes its token (check-then-increment,
  same as artwork uploads today).
- **Pre-check endpoint**: `GET /v1/auth/me` (Bearer) → `quotas.storage.used_bytes` /
  `limit_bytes` (mkpx included once this ships) and `quotas.uploads.remaining` /
  `reset_at`. Use it to warn before uploading.

## 5. Post payload additions

`schemas.Post` — the shape used by feeds, search, single post (`GET /v1/p/{sqid}`), and
player surfaces — gains:

```json
{
  "has_mkpx": true,
  "mkpx_file_bytes": 183422,
  "mkpx_attached_at": "2026-07-02T14:11:05Z"
}
```

- `has_mkpx` drives the golden Edit button, **including in grid/feed views**.
- `mkpx_file_bytes` / `mkpx_attached_at` are `null` when `has_mkpx` is false.
- `mkpx_attached_at` changes on every attach **and replace** — treat it as the
  cache-invalidation stamp for any locally cached layers file (no separate content hash).
- Two slim, hand-built payload shapes do **not** carry these fields: the reacted-posts
  list items and PMD items. If you render golden buttons from one of those, tell us in
  message #2.
- MQTT `makapix/posts/new` notification payloads are **unchanged** (slim shape, no
  `has_mkpx`); refetch via REST as today.

## 6. Upload with layers file

`POST /v1/post/upload` — existing endpoint, one new **optional** multipart field:

| Field | Type | Notes |
|---|---|---|
| `mkpx` | file | The layers file. Filename ignored; magic bytes are authoritative. |

Semantics: **atomic** — if the .mkpx fails validation or quota, the entire upload fails
(§3 codes) and **no post is created**. On success the returned post has `has_mkpx: true`.

## 7. Attach / replace on an existing post

`POST /v1/post/{post_id}/mkpx` — **author only**. `post_id` is the **integer `id`** from
the post payload (not `public_sqid`, not `storage_key`).

- Multipart body, single field `mkpx` (same acceptance rules).
- Attaches if the post has none; **silently replaces** if one exists.
- Only artwork posts: playlist posts → 404. Soft-deleted posts → 404 (even for the author).
- Hidden (but not deleted) posts: the author can still attach/replace/detach.
- Returns the updated post object (200). Errors per §3.

## 8. Detach

`DELETE /v1/post/{post_id}/mkpx` — **author only**, integer `post_id`.

- Removes the layers file; post's mkpx fields return to null/false.
- 404 if the post has no layers file. Returns the updated post object (200).

## 9. Download

`GET /v1/d/{public_sqid}.mkpx` — **authentication required** (Bearer JWT). Lowercase
`.mkpx` only.

- 401 without a valid token — clients must handle this (e.g. golden button → login prompt).
- 404 if the post has no layers file or is not visible to the requester: same visibility
  rules as the other `/d/` downloads — owners **and moderators** can download from hidden
  posts; **soft-deleted posts 404 for everyone, the author included**.
- Response: the exact stored bytes.
  - `Content-Type: application/x-mkpx` (proposed — §11 Q1)
  - `Content-Disposition: attachment; filename="makapix-{public_sqid}.mkpx"` (§11 Q2)
  - `Content-Length` set; `Cache-Control: no-store`; body never transformed or compressed
    by the API.
- No Range/resume support (whole-file response). For 50 MB on mobile, download to a temp
  file with a generous timeout.

## 10. Lifecycle rules both teams must reflect in UX

1. **Artwork replacement drops the layers file.** If the author replaces a post's artwork
   (web Piskel/Pixelc edit flow, `POST /v1/post/{post_id}/replace-artwork`), any attached
   .mkpx is deleted server-side (it no longer matches the rendered artwork). The author can
   attach a new one. Clients should warn about this in their replace-artwork UI.
2. Deleting a post makes its layers file unavailable immediately (soft delete → download
   404s for everyone; the file itself is removed at the scheduled hard delete ~7 days
   later). Account deletion removes layers files with everything else.
3. Layers files are never versioned: replace overwrites, detach removes. No history.

## 11. Open questions for the app team (answer in message #2)

1. **MIME type**: we propose `application/x-mkpx`. OK, or do you prefer
   `application/vnd.makapix.mkpx`?
2. **Download filename**: we propose `makapix-{public_sqid}.mkpx`. Want the post title
   slugified instead, or do you ignore Content-Disposition entirely?
3. **Golden button data**: `has_mkpx` rides every `schemas.Post` payload including feeds,
   and `mkpx_attached_at` is the replace-detection stamp (§5) — sufficient? Do any of your
   views consume the reacted-posts or PMD slim shapes (§5)?
4. **Size expectations**: our cap is 50 MB (config-advertised). Any real-world documents
   anywhere near that? If your practical max is far lower, tell us — we may lower the cap.
5. **Profiles**: we accept plain MKPX and compact MKPZ. Confirm you'll upload compact.
6. **Web-created posts**: posts made on the web (Piskel/Pixelc) can never gain an
   upload-time .mkpx; the app is the sole origin of layers files. Confirm you see no
   app-side flow that needs attach-at-upload for posts *not* created in the app.
